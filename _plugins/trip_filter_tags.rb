# =============================================================================
# trip_filter_tags.rb — what a trip can be filtered BY, and which days matched
# =============================================================================
# A trip card carries `tags:` in its own front matter, and those are the six
# or so words that describe the trip as a whole — the chips printed on the
# card. The tag filter on the homepage and /trips/ used to build its list from
# nothing else, which made it far smaller than the tag vocabulary actually in
# use: 60 tags rather than the ~140 the posts use between them.
#
# So the tags that only ever get written on a day post — Birds, PaddleBoarding,
# Snorkeling, Sunrise — could not be filtered by anywhere, even though they are
# on the master list in _data/tags.yml and offered by the editor's dropdown.
# Tagging a post Birds looked like it did nothing.
#
# This sets two things on every trip:
#
#   filter_tags   its own tags PLUS every tag on every post belonging to it,
#                 de-duplicated. Filter by Birds and you get the trips that
#                 have a bird post in them. The card still prints only the
#                 trip's own tags — a card listing all 41 tags of a three-week
#                 trip would be unreadable.
#
#   filter_posts  one entry per tagged post, in the order they are read on the
#                 trip page. Once a filter narrows the grid to six trips, this
#                 is what lets each card name the exact days that matched and
#                 link straight to them, rather than leaving her to open a
#                 trip and hunt through ninety-five posts for the bird one.
#                 Keys are short because this ships on every card:
#                 t=title, u=url, d=date, g=tags.
#
# The count beside each tag in the filter therefore counts TRIPS, not posts:
# it is how many cards you will be left with, which is the only number that
# means anything next to a checkbox in that list.
#
# Every POST gets a `filter_tags` of its own, for the day list inside a trip
# page. That control used to offer nothing but the city each day was in, which
# on the New Zealand trip meant 22 cities and not one of the 40 tags actually
# written across its posts — so you could ask "which day were we in Wanaka"
# but not "which days did we hike". The city stays in the list, because asking
# where is still worth doing; it is just no longer the only question allowed.
#
# A trip's identity is its `slug:` if it has one, else its filename — the same
# rule content_audit.rb uses, and the thing a post's `categories:` entry has to
# match. It is published as `trip_slug` so the templates key the day index by
# exactly what this computed, rather than re-deriving it in Liquid and drifting.
#
# Runs at :low so tag_merge (:highest) has already folded each document's
# `new_tags` into `tags`; a brand-new tag typed onto a post is therefore
# filterable on the same build.
# =============================================================================
module TravelBlog
  class TripFilterTags < Jekyll::Generator
    safe true
    priority :low

    def generate(site)
      by_trip = Hash.new { |h, k| h[k] = [] }

      site.posts.docs.each do |post|
        tags = clean(post.data["tags"])

        # Set on every post, including untagged ones: those still have a city,
        # and dropping them here would take away filtering the day list by
        # where you were, which is what it could already do.
        post.data["filter_tags"] =
          (tags + [city_of(post)]).reject(&:empty?).uniq { |t| t.downcase }

        # A post with no tags can never match a tag filter, so it is not worth
        # shipping in the trip grid's day index.
        next if tags.empty?
        Array(post.data["categories"]).each do |slug|
          by_trip[slug.to_s] << post
        end
      end

      # Matches what the `relative_url` filter would produce, so the links are
      # right if the site ever moves off the domain root.
      base = site.config["baseurl"].to_s.chomp("/")

      (site.collections["trips"]&.docs || []).each do |trip|
        slug  = trip.data["slug"] || File.basename(trip.basename_without_ext)
        posts = by_trip[slug].sort_by { |p| [order_of(p), p.date] }

        trip.data["trip_slug"] = slug

        # The trip's own spelling wins a case clash, since that is the one
        # printed on the card.
        trip.data["filter_tags"] =
          (clean(trip.data["tags"]) + posts.flat_map { |p| clean(p.data["tags"]) })
          .uniq { |t| t.downcase }
          .sort_by(&:downcase)

        trip.data["filter_posts"] = posts.map do |post|
          {
            "t" => post.data["title"].to_s,
            "u" => base + post.url,
            "d" => post.date.strftime("%Y-%m-%d"),
            "g" => clean(post.data["tags"]),
          }
        end
      end
    end

    private

    # The city, not the whole "Queenstown, New Zealand". Every day of a trip
    # tends to share a country, and a filter entry that matches every card
    # filters nothing.
    def city_of(post)
      loc = post.data["location"]
      return "" unless loc.is_a?(Hash)
      loc["name"].to_s.split(",").first.to_s.strip
    end

    # Same rule as the day list's sort: parseFloat, not integer — posts written
    # on the same day are numbered 15.1 / 15.2 and must not collapse together.
    # An unnumbered post sorts last, then by date.
    def order_of(post)
      post.data["order"] ? post.data["order"].to_f : Float::INFINITY
    end

    def clean(value)
      Array(value).map { |t| t.to_s.strip }.reject(&:empty?)
    end
  end
end
