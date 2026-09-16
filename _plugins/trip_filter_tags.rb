# =============================================================================
# trip_filter_tags.rb — what a trip can be filtered BY
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
# This sets `filter_tags` on every trip: its own tags PLUS every tag on every
# post belonging to it, de-duplicated. Filter by Birds and you get the trips
# that have a bird post in them. The card still prints only the trip's own
# tags — a card listing all 40 tags of a three-week trip would be unreadable.
#
# The count beside each tag in the filter therefore counts TRIPS, not posts:
# it is how many cards you will be left with, which is the only number that
# means anything next to a checkbox in that list.
#
# A trip's identity is its `slug:` if it has one, else its filename — the same
# rule content_audit.rb uses, and the thing a post's `categories:` entry has to
# match.
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
        next if tags.empty?
        Array(post.data["categories"]).each do |slug|
          by_trip[slug.to_s].concat(tags)
        end
      end

      (site.collections["trips"]&.docs || []).each do |trip|
        slug = trip.data["slug"] || File.basename(trip.basename_without_ext)
        # The trip's own spelling wins a case clash, since that is the one
        # printed on the card.
        trip.data["filter_tags"] =
          (clean(trip.data["tags"]) + by_trip[slug])
          .uniq { |t| t.downcase }
          .sort_by(&:downcase)
      end
    end

    private

    def clean(value)
      Array(value).map { |t| t.to_s.strip }.reject(&:empty?)
    end
  end
end
