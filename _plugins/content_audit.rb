# =============================================================================
# content_audit.rb — check every cross-reference in the site at build time
# =============================================================================
# Most of this site is one piece of content pointing at another by NAME:
# a post names its trip in `categories:`, a favourite names a trip in
# `trip_slug:`, a flag image names a country, Daydreaming names a country.
# Nothing enforces those names. A typo doesn't crash anything — it just
# quietly drops the thing from a list, and the number on the page is wrong
# by one with no indication anything happened.
#
# That is how Costa Rica ended up counting toward the Countries tile while
# being invisible on the world map, and it is why the two figures on /stats/
# disagreed for months before anyone noticed.
#
# So this doesn't try to FIX anything — guessing what she meant is how you
# corrupt someone's content. It reports, every build, in two places:
#
#   - the build log, so a broken reference is visible in the Netlify deploy
#   - site.data.content_problems, rendered on /admin-stats/, because she
#     doesn't read build logs and a warning nobody sees is not a check
#
# Nothing here fails the build. A dangling reference should be fixed, but it
# is never a reason to take the site down.
#
# Runs at priority :low so country_data.rb has already built the alias table.
# =============================================================================
module TravelBlog
  class ContentAudit < Jekyll::Generator
    safe true
    priority :low

    def generate(site)
      @problems = []

      trips = collect_trips(site)
      known = known_country_names(site)

      check_post_trips(site, trips)
      check_post_order(site, trips)
      check_trip_slugs(site, trips)
      check_country_names(site, known)
      check_shadowed_keys(site)
      check_post_dates(site, trips)
      check_tags(site)

      site.data["content_problems"] = @problems

      if @problems.empty?
        Jekyll.logger.info "Content audit:", "all cross-references resolve"
      else
        Jekyll.logger.warn "Content audit:", "#{@problems.size} problem(s):"
        @problems.each { |p| Jekyll.logger.warn "  -", p }
      end
    end

    private

    def flag(where, message)
      @problems << "#{where}||#{message}"
    end

    # A trip's identity is its `slug:` if it has one, else its filename. That
    # is the same rule the rest of the site follows, so this matches what a
    # post's `categories:` entry actually has to say.
    def collect_trips(site)
      (site.collections["trips"]&.docs || []).each_with_object({}) do |doc, h|
        slug = doc.data["slug"] || File.basename(doc.basename_without_ext)
        h[slug] = doc
      end
    end

    def known_country_names(site)
      names = {}
      Array(site.data["countries"]).each do |rec|
        next unless rec.is_a?(Hash)
        n = rec["name"].to_s.strip
        names[n] = true unless n.empty?
        Array(rec["aliases"]).each do |a|
          a = a.to_s.strip
          names[a] = true unless a.empty?
        end
      end
      names
    end

    # ---- posts point at a trip that exists -----------------------------------
    def check_post_trips(site, trips)
      site.posts.docs.each do |post|
        cats = Array(post.data["categories"])
        if cats.empty?
          flag(post.data["title"] || post.basename,
               "has no trip in categories: — it won't appear on any trip page")
          next
        end
        cats.each do |c|
          next if trips.key?(c)
          flag(post.data["title"] || post.basename,
               "is filed under trip #{c.inspect}, which doesn't exist. " \
               "Check the spelling against the trip's slug.")
        end
      end
    end

    # ---- `order:` is unique within a trip ------------------------------------
    # order is the post's position in the trip: it drives the sort AND the
    # "Day N" label. It can't be derived from the date, because several posts
    # often share one day. But two posts holding the SAME number is never
    # intentional — they both render "Day 16" and their relative order is
    # then whatever the sort happens to do.
    def check_post_order(site, trips)
      by_trip = Hash.new { |h, k| h[k] = [] }
      site.posts.docs.each do |post|
        Array(post.data["categories"]).each do |c|
          next unless trips.key?(c)
          by_trip[c] << post
        end
      end

      by_trip.each do |slug, posts|
        seen = Hash.new { |h, k| h[k] = [] }
        posts.each do |post|
          o = post.data["order"]
          if o.nil?
            flag(trips[slug].data["title"] || slug,
                 "#{(post.data['title'] || post.basename).inspect} has no order: — " \
                 "it sorts last and shows no day number")
          else
            seen[o] << (post.data["title"] || post.basename)
          end
        end
        seen.each do |o, titles|
          next if titles.size < 2
          flag(trips[slug].data["title"] || slug,
               "order: #{o} is used by #{titles.size} posts — #{titles.map(&:inspect).join(', ')}. " \
               "They'll both show the same day number and their order is arbitrary.")
        end
      end
    end

    # ---- data files point at trips that exist --------------------------------
    def check_trip_slugs(site, trips)
      walk_trip_slugs(site.data["favorites"], "favorites.yml", trips)
      walk_trip_slugs(site.data["records"],   "records.yml",   trips)
    end

    def walk_trip_slugs(node, where, trips)
      case node
      when Hash
        s = node["trip_slug"]
        if s.is_a?(String) && !s.empty? && !trips.key?(s)
          flag(where, "points at trip #{s.inspect}, which doesn't exist — " \
                      "that entry won't link anywhere")
        end
        node.each_value { |v| walk_trip_slugs(v, where, trips) }
      when Array
        node.each { |v| walk_trip_slugs(v, where, trips) }
      end
    end

    # ---- every country named anywhere has a record ---------------------------
    # A country with no record still displays, so this never breaks a page.
    # It just won't shade on the map or count toward continents — the silent
    # failure this whole file exists to make loud.
    def check_country_names(site, known)
      each_named_country(site) do |raw, where, label|
        name = raw.to_s.split(",").last.to_s.strip
        next if name.empty? || known.key?(name)
        flag(where, "#{label} names #{name.inspect}, which has no record in " \
                    "_data/countries.yml — it won't shade on the map or count " \
                    "toward continents. Add a record, or add it as an alias " \
                    "of an existing country if it's another spelling.")
      end
    end

    # ---- a post's date should be when it HAPPENED -----------------------------
    # A post's date is the single source for where it lands on the "On this
    # day" widget, its year page, and the archive. Everything treats it as the
    # day being written about.
    #
    # Several were entered as the day the post was PUBLISHED instead, which is
    # sometimes months later: "South Korea: a Whole New World!" carries an
    # August 2025 date for a trip that ended in January. Nothing looks broken
    # — the post renders, the trip page lists it in the right order because
    # `order:` decides that — but the post surfaces on the wrong day of the
    # year and lands in the wrong year's review.
    #
    # Only a date outside the trip's OWN range is reported. Being a day either
    # side is normal for a flight home written up the next morning, so a small
    # grace period keeps this signal worth reading.
    GRACE_DAYS = 2

    def check_post_dates(site, trips)
      # Grouped by trip on purpose. Reporting each post separately produced 55
      # rows, which buries every other finding on the page. One row per trip,
      # naming the worst offenders, is the same information at a size someone
      # will actually read.
      drift_by_trip = Hash.new { |h, k| h[k] = [] }

      site.posts.docs.each do |post|
        next unless post.date

        Array(post.data["categories"]).each do |slug|
          trip = trips[slug]
          next unless trip

          start_on = as_date(trip.data["start_date"])
          end_on   = as_date(trip.data["end_date"])
          next if start_on.nil? || end_on.nil?

          on = post.date.to_date
          drift =
            if on < start_on then (start_on - on).to_i
            elsif on > end_on then (on - end_on).to_i
            else 0
            end
          next if drift <= GRACE_DAYS

          drift_by_trip[slug] << [drift, post.data["title"] || post.basename, on]
        end
      end

      drift_by_trip.each do |slug, entries|
        trip  = trips[slug]
        worst = entries.sort_by { |d, _, _| -d }
        names = worst.first(3).map { |d, title, on| "#{title.inspect} (#{on}, #{d}d)" }
        more  = entries.size > 3 ? ", and #{entries.size - 3} more" : ""

        flag(trip.data["title"] || slug,
             "#{entries.size} post#{"s" unless entries.size == 1} dated outside " \
             "the trip's own range (#{as_date(trip.data['start_date'])} to " \
             "#{as_date(trip.data['end_date'])}): #{names.join(', ')}#{more}. " \
             "If those are publish dates rather than the day each thing " \
             "happened, the posts show up on the wrong day in 'On this day' " \
             "and can land in the wrong year's review.")
      end
    end

    def as_date(value)
      return nil if value.nil?
      return value.to_date if value.respond_to?(:to_date)
      Date.parse(value.to_s)
    rescue StandardError
      nil
    end

    # ---- every tag used is on the canonical list ------------------------------
    # The editor offers tags as a pick-list from _data/tags.yml, so new typos
    # shouldn't appear. This catches the two ways one still can: a post edited
    # outside the CMS, and a tag renamed in tags.yml without updating the posts
    # that already used the old name.
    #
    # A stray tag is invisible rather than broken — it shows up as its own
    # entry in the filter dropdown, matching one post, next to the real tag it
    # was meant to be. That is exactly how "Food"/"food" and "Museum"/"Museums"
    # went unnoticed long enough to need a bulk merge.
    def check_tags(site)
      known = {}
      Array(site.data.dig("tags", "tags")).each do |rec|
        name = rec.is_a?(Hash) ? rec["name"].to_s.strip : rec.to_s.strip
        known[name] = true unless name.empty?
      end
      return if known.empty?   # no list yet: nothing to check against

      stray = Hash.new { |h, k| h[k] = [] }
      docs = (site.collections["trips"]&.docs || []) + site.posts.docs
      docs.each do |doc|
        Array(doc.data["tags"]).each do |tag|
          t = tag.to_s.strip
          next if t.empty? || known.key?(t)
          stray[t] << (doc.data["title"] || doc.basename)
        end
      end

      stray.each do |tag, users|
        shown = users.first(3).map(&:inspect).join(", ")
        more = users.size > 3 ? ", and #{users.size - 3} more" : ""
        flag("tags.yml",
             "#{tag.inspect} is used by #{users.size} " \
             "#{users.size == 1 ? 'entry' : 'entries'} (#{shown}#{more}) but is " \
             "not on the master list. It already works everywhere — filters, " \
             "counts, the tag sheet — so this is only a reminder to add it " \
             "under Tags, which is what puts it in the dropdown next time. " \
             "Usually it came from the \"New tag(s)\" box on a post. " \
             "If it was meant to be an existing tag, fix the post instead — left " \
             "alone it stays a separate filter.")
      end
    end

    # ---- front matter that Jekyll quietly ignores -----------------------------
    # Jekyll renders a document through a Drop, and the Drop answers for any
    # key it defines a method for BEFORE it looks at front matter. So a page
    # asking for `trip.collection` gets the collection's label, "trips", and
    # never the `collection: true` someone wrote in the file.
    #
    # This is nastier than a typo. The field looks right, the CMS saves it,
    # git shows it, and every template reading it silently gets something
    # else. It cost a whole deploy: the flag meant to keep a 15-year
    # collection entry out of the duration stats did nothing at all, and the
    # days-on-the-road figure stayed wrong with no sign anything had failed.
    #
    # `excerpt` is deliberately absent from this list — Jekyll honours a
    # front matter excerpt, so setting it is correct and common.
    SHADOWED = %w[
      collection content id next output path previous relative_path url
    ].freeze

    def check_shadowed_keys(site)
      docs = (site.collections["trips"]&.docs || []) + site.posts.docs
      docs.each do |doc|
        (doc.data.keys & SHADOWED).each do |key|
          flag(doc.data["title"] || doc.basename,
               "sets #{key}: in its front matter, but Jekyll's document drop " \
               "defines its own #{key} — templates reading it get Jekyll's " \
               "value, never this one. Rename the field (e.g. #{key}_trip).")
        end
      end
    end

    def each_named_country(site)
      Array(site.data.dig("favorites", "categories")).each do |cat|
        Array(cat["entries"]).each do |e|
          yield e["country"], "favorites.yml", (e["name"] || "an entry").to_s
        end
      end

      %w[upcoming queue].each do |section|
        Array(site.data.dig("daydream", section)).each do |e|
          yield e["country"], "daydream.yml", "the #{section} list"
        end
      end

      Array(site.data.dig("country_images", "entries")).each do |e|
        yield e["name"], "country_images.yml", "a flag image"
      end

      (site.collections["trips"]&.docs || []).each do |doc|
        where = doc.data["title"] || doc.basename
        Array(doc.data["countries"]).each do |c|
          yield(c.is_a?(Hash) ? c["name"] : c, where, "countries:")
        end
      end
    end
  end
end
