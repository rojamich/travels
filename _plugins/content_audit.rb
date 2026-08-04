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
