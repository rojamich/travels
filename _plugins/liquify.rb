# =============================================================================
# liquify.rb — run Liquid over a string that came from a data file
# =============================================================================
# WHY THIS EXISTS
#
# Jekyll renders Liquid inside page and post CONTENT, but never inside values
# loaded from _data/*.yml — those are handed to templates as plain strings.
#
# That's fine for ordinary prose, but the Lessons page pulls its text out of
# _data/lessons.yml, and those fields are edited with the full markdown editor
# in /admin/. When she uses the "Photo Gallery" button there, Decap writes
#
#     {% gallery_block <encoded json> %}
#
# into the field. With only `| markdownify`, that tag is never executed — the
# markdown converter treats it as ordinary text and wraps it in a <p>, so the
# reader sees the raw tag and its URL-encoded payload instead of photos.
#
# `liquify` parses and renders the string as a Liquid template first, so any
# tags inside it (gallery_block, audio_block, youtube_block, emoji) behave
# exactly as they do in a post body. Use it BEFORE markdownify:
#
#     {{ entry.current | liquify | markdownify }}
#
# Order matters. Liquify first means the tag emits its HTML at block level and
# kramdown passes that through untouched. The other way round, markdownify
# would have already buried the tag inside a paragraph.
#
# Passing @context through preserves Jekyll's registers (site, page), so tags
# that need them keep working.
# =============================================================================

module Jekyll
  module LiquifyFilter
    def liquify(input)
      return input if input.nil? || input.to_s.empty?
      Liquid::Template.parse(input.to_s).render(@context)
    rescue StandardError => e
      # Never fail a build over one malformed field — emit the original text
      # and warn, so a bad tag shows up in the build log rather than taking
      # the whole site down.
      Jekyll.logger.warn "liquify:", "could not render a data field: #{e.message}"
      input
    end
  end
end

Liquid::Template.register_filter(Jekyll::LiquifyFilter)
