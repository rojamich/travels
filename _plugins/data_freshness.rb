# =============================================================================
# data_freshness.rb — how long ago each hand-kept data file was last changed
# =============================================================================
# Most of this site cannot go stale. The countries, the nights, the leaderboard
# positions, the maps — all of it is computed from posts and trips every build,
# so it is either right or it is visibly broken.
#
# A handful of files are different. Nothing computes them, nothing checks them,
# and nothing complains when they age:
#
#     _data/status.yml          the "we are in Yerevan" bar on every page
#     _data/records.yml         personal bests on /stats/
#     _data/country_images.yml  the flags beside country names
#     _data/us_state_images.yml the same for US states
#     _data/favorites.yml       the favourites page
#     _data/lessons.yml         the lessons page
#
# A stale one doesn't look stale. The status bar says Yerevan in the same
# confident type whether they landed yesterday or left in March.
#
# So this records when each was last actually edited, and /admin-stats/ turns
# that into a reminder. The date comes from git rather than the file's
# timestamp on disk: a build server clones the repo fresh, which makes every
# file look like it was written seconds ago.
#
# Exposes site.data.freshness — { "status" => { "date" => "2026-08-15",
#                                               "days" => 12 }, ... }
# A file git can't answer for is simply left out, and the page skips it. That
# happens with a shallow clone whose history doesn't reach back to the last
# edit, which is a reason to say nothing, not to guess.
#
# safe: false, because this shells out to git. Jekyll's safe mode (which this
# site never builds in — that's a GitHub Pages restriction, and we build on
# Netlify) would skip the plugin, and /admin-stats/ would quietly drop the
# reminders rather than break.
# =============================================================================
require "open3"

module TravelBlog
  class DataFreshness < Jekyll::Generator
    safe false
    priority :low

    WATCHED = {
      "status"          => "_data/status.yml",
      "records"         => "_data/records.yml",
      "country_images"  => "_data/country_images.yml",
      "us_state_images" => "_data/us_state_images.yml",
      "favorites"       => "_data/favorites.yml",
      "lessons"         => "_data/lessons.yml"
    }.freeze

    def generate(site)
      out = {}

      WATCHED.each do |key, path|
        stamp = last_commit_time(site.source, path)
        next unless stamp
        out[key] = {
          "date" => stamp.strftime("%-d %B %Y"),
          "days" => ((Time.now - stamp) / 86_400).floor,
          "path" => path
        }
      end

      site.data["freshness"] = out
      Jekyll.logger.info "Freshness:", "dated #{out.size} of #{WATCHED.size} hand-kept files"
    end

    private

    # Seconds-since-epoch of the last commit that touched this path. Returns
    # nil for anything unexpected — no git, no history, no such file — because
    # the page treats "unknown" as "say nothing", and a wrong date here would
    # be worse than a missing one.
    def last_commit_time(source, path)
      out, status = Open3.capture2(
        "git", "-C", source.to_s, "log", "-1", "--format=%ct", "--", path
      )
      return nil unless status.success?

      seconds = out.strip
      return nil if seconds.empty?

      Time.at(Integer(seconds))
    rescue StandardError => e
      Jekyll.logger.debug "Freshness:", "no date for #{path} (#{e.class})"
      nil
    end
  end
end
