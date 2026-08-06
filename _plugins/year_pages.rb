# =============================================================================
# year_pages.rb — auto-generate a wrap-up page for every year we travelled
# =============================================================================
# Creates a virtual page at /year/YYYY/ using the "year" layout. No manual
# per-year files needed — the pages appear on the next build.
#
# A year qualifies if EITHER a post was published in it OR a trip's date
# range touches it. It used to be posts only, which meant a trip with no
# posts written yet had no year at all: The Singaporean Stopover is dated
# January 2026 and was missing from /year/2026/ entirely.
#
# Trips count for every year they span, so a trip over New Year appears on
# both years' pages — which is true, and is what the trip page itself says.
#
# Collection trips (collection_trip: true) are skipped when deciding which
# years exist. "Party in the USA" spans 2011-2026; counting it would conjure
# fifteen year pages for years with nothing else in them.
# =============================================================================

module Jekyll
  class YearPage < Page
    def initialize(site, base, year, posts_in_year)
      @site = site
      @base = base
      @dir  = File.join("year", year.to_s)
      @name = "index.html"

      self.process(@name)
      self.data = {
        "layout"         => "year",
        "title"          => "#{year} in Review",
        "permalink"      => "/year/#{year}/",
        "year"           => year.to_s,
        "author_profile" => false,
        "classes"        => "wide",
        "posts_count"    => posts_in_year.size
      }
      self.content = ""
    end
  end

  class YearPageGenerator < Generator
    safe true
    priority :low

    def generate(site)
      by_year = site.posts.docs.group_by { |p| p.date.strftime("%Y") }
      by_year.default = []

      # Plain array + uniq rather than a Set, so this doesn't depend on
      # whether something else in the build happened to require "set".
      years = by_year.keys.dup

      (site.collections["trips"]&.docs || []).each do |trip|
        next if trip.data["collection_trip"] == true
        first, last = trip_year_span(trip)
        next if first.nil?
        (first..last).each { |y| years << y.to_s }
      end

      years = years.uniq.sort

      years.each do |year|
        site.pages << YearPage.new(site, site.source, year, by_year[year])
      end

      Jekyll.logger.info "Year pages:", "#{years.size} generated (#{years.first}-#{years.last})"
    end

    private

    # Front matter dates arrive as Date/Time from YAML, or as a string if
    # someone typed one by hand. Both are handled; anything unparseable is
    # skipped rather than crashing the build over one trip.
    def trip_year_span(trip)
      first = year_of(trip.data["start_date"])
      last  = year_of(trip.data["end_date"]) || first
      return [nil, nil] if first.nil?
      last = first if last < first
      [first, last]
    end

    def year_of(value)
      return nil if value.nil?
      return value.year if value.respond_to?(:year)
      m = value.to_s.strip[/\A(\d{4})/, 1]
      m&.to_i
    end
  end
end
