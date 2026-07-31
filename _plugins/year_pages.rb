# =============================================================================
# year_pages.rb — auto-generate a wrap-up page for every year we have posts
# =============================================================================
# Enumerates every distinct year across site.posts and creates a virtual
# page at /year/YYYY/ using the "year" layout. No manual per-year files
# needed — publish a post from a new year and its wrap-up page appears
# automatically on the next build.
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
        "layout"        => "year",
        "title"         => "#{year} in Review",
        "permalink"     => "/year/#{year}/",
        "year"          => year.to_s,
        "author_profile"=> false,
        "classes"       => "wide",
        # Give the layout a pre-sorted list of just this year's posts so
        # Liquid doesn't have to re-filter site.posts on every render.
        "posts_count"   => posts_in_year.size
      }
      self.content = ""
    end
  end

  class YearPageGenerator < Generator
    safe true
    priority :low

    def generate(site)
      # Group posts by year (YYYY string), keeping only years that have at least one post.
      by_year = site.posts.docs.group_by { |p| p.date.strftime("%Y") }
      by_year.each do |year, posts|
        site.pages << YearPage.new(site, site.source, year, posts)
      end
    end
  end
end
