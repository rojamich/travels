# =============================================================================
# nights.rb — how many nights were spent in each country and continent
# =============================================================================
# A trip from start to end has (end - start) NIGHTS: a trip that leaves on the
# 1st and returns on the 8th is 8 days but 7 nights. Nights are the honest
# measure of "how long were we there", because the travel days at each end are
# shared with somewhere else.
#
# ATTRIBUTION
# Each night is credited to wherever that day's post says they were. Days with
# no post carry forward the last known country, and anything before the first
# post falls back to the trip's own `location:`. So a trip through three
# countries splits its nights between them instead of crediting all three with
# the whole trip — which is what a naive "trip visited X" count would do.
#
# Carrying forward is what makes this cheap to maintain: you only need a post
# on the day you ARRIVE somewhere. Stay four nights and write one post, and
# all four nights land in the right country.
#
# A post marked `transit: true` is ignored here — see below.
#
# TRANSIT
# `transit: true` on a post means "we were here, we did not sleep here": an
# airport layover, an overnight flight that crossed a date line. The post
# still appears on the map with its own pin; it simply doesn't claim the
# night, which carries forward from wherever they last actually stayed.
# Without it a nine-hour stop in Paris takes a night off the country they
# woke up in and gives it to France.
#
# ONE SOURCE
# Country names are resolved exactly as everywhere else on the site: take the
# text after the last comma, then fold it through the alias table. That table
# and the continent lookup are both derived from _data/countries.yml by
# country_data.rb, so these totals cannot disagree with the Countries tile,
# the world map or the continent count. Nothing is hand-maintained here.
#
# Collection trips are excluded, for the same reason they are excluded from
# every other duration figure: "Party in the USA" spans 2011-2026 and would
# contribute 5,000 nights it never actually accounted for.
#
# Exposes:
#   site.data.nights.countries    [{name, nights, continent}], most first
#   site.data.nights.continents   [{name, nights}], most first
#   site.data.nights.total        nights placed
#   site.data.nights.undeclared   nights credited to a country the trip does
#                                 not list — see below
#
# UNDECLARED COUNTRIES
# A post can name a country the trip itself never declares: a layover in
# Taipei on a Japan trip, say. Those nights are still counted — they happened
# — but the country will NOT appear in the Countries tile, because that counts
# from the trip's `location:` and `countries:`. Rather than let the two
# quietly disagree, the mismatch is reported on /admin-stats/ so the trip can
# be corrected either way.
#
# Runs at :low, after country_data.rb has built the lookup tables.
# =============================================================================
module TravelBlog
  class Nights < Jekyll::Generator
    safe true
    priority :low

    def generate(site)
      @aliases    = site.data["country_aliases"] || {}
      @continents = site.data["continents"] || {}
      return if @aliases.empty?

      by_country  = Hash.new(0)
      # Keyed by [trip title, country] so a fortnight in an undeclared country
      # is one finding rather than fourteen identical ones.
      @undeclared = Hash.new(0)

      posts_by_trip = group_posts(site)

      (site.collections["trips"]&.docs || []).each do |trip|
        next if trip.data["collection_trip"] == true
        add_trip(trip, posts_by_trip[trip_slug(trip)], by_country)
      end

      by_continent = Hash.new(0)
      by_country.each do |name, n|
        cont = @continents[name]
        by_continent[cont] += n if cont
      end

      site.data["nights"] = {
        "countries"  => sort_rows(by_country) { |name| { "continent" => @continents[name] } },
        "continents" => sort_rows(by_continent),
        "total"      => by_country.values.sum,
        "undeclared" => @undeclared.map { |(trip, country), n|
          { "trip" => trip, "country" => country, "nights" => n }
        }.sort_by { |r| -r["nights"] }
      }

      Jekyll.logger.info "Nights:",
                         "#{by_country.values.sum} night(s) across " \
                         "#{by_country.size} countries, #{by_continent.size} continents"
    end

    private

    def trip_slug(trip)
      trip.data["slug"] || File.basename(trip.basename_without_ext)
    end

    def group_posts(site)
      out = Hash.new { |h, k| h[k] = [] }
      site.posts.docs.each do |post|
        next unless post.date
        Array(post.data["categories"]).each { |c| out[c] << post }
      end
      out
    end

    # The site-wide rule, in Ruby: text after the last comma, then the alias
    # table. Returns nil when the result isn't a country we know — "Old Town,
    # Tbilisi" resolves to nothing, and the caller falls back.
    def canon(raw)
      return nil if raw.nil?
      name = raw.to_s.split(",").last.to_s.strip
      return nil if name.empty?
      @aliases[name]
    end

    def as_date(value)
      return nil if value.nil?
      return value.to_date if value.respond_to?(:to_date)
      Date.parse(value.to_s)
    rescue StandardError
      nil
    end

    def add_trip(trip, posts, by_country)
      start_on = as_date(trip.data["start_date"])
      end_on   = as_date(trip.data["end_date"])
      return if start_on.nil? || end_on.nil?

      nights = (end_on - start_on).to_i
      return if nights <= 0

      # First post of each day wins; later posts that day don't move them.
      #
      # Posts marked `transit: true` are skipped entirely. A nine-hour layover
      # in Paris or an overnight flight through Taipei is a place you were,
      # not a place you slept — without this the layover steals that night from
      # wherever you actually woke up, and hands a country a night it never
      # had. The pin still shows on the map; only the night is withheld.
      by_date = {}
      Array(posts).each do |post|
        next if post.data["transit"] == true
        c = canon(post.data.dig("location", "name"))
        next unless c
        d = post.date.to_date
        by_date[d] ||= c
      end

      fallback = canon(trip.data["location"])
      declared = declared_countries(trip)

      current = nil
      nights.times do |i|
        day = start_on + i
        current = by_date[day] if by_date.key?(day)
        country = current || fallback
        next unless country
        by_country[country] += 1

        next if declared.empty? || declared.include?(country)
        @undeclared[[trip.data["title"] || trip_slug(trip), country]] += 1
      end
    end

    # What the trip itself claims, using the same rule the Countries tile uses.
    def declared_countries(trip)
      out = []
      c = canon(trip.data["location"])
      out << c if c
      Array(trip.data["countries"]).each do |entry|
        name = entry.is_a?(Hash) ? entry["name"] : entry
        c2 = canon(name)
        out << c2 if c2
      end
      out.uniq
    end

    def sort_rows(counts)
      counts.sort_by { |name, n| [-n, name] }.map do |name, n|
        row = { "name" => name, "nights" => n }
        row.merge!(yield(name)) if block_given?
        row
      end
    end
  end
end
