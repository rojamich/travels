# =============================================================================
# youtube_block.rb — Liquid tag for embedding a YouTube video by URL
# =============================================================================
# Paired with the "🎬 YouTube Video" editor component in admin/index.html.
# She pastes a YouTube URL in any common format:
#   - https://www.youtube.com/watch?v=ABCDEF12345
#   - https://youtu.be/ABCDEF12345
#   - https://www.youtube.com/embed/ABCDEF12345
#   - ABCDEF12345 (just the ID)
# We extract the 11-character video ID and emit a clean <iframe> embed.
# The site's existing video CSS (.fluid-width-video-wrapper) makes it
# render responsively with 16:9 aspect ratio.
# =============================================================================

require "json"
require "uri"
require "cgi"

module Jekyll
  class YoutubeBlockTag < Liquid::Tag
    YOUTUBE_ID_RE = %r{(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|v/|shorts/)|youtu\.be/)([\w-]{11})|^([\w-]{11})$}

    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(_context)
      decoded =
        begin
          URI.decode_www_form_component(@markup)
        rescue StandardError
          @markup
        end

      data =
        begin
          JSON.parse(decoded)
        rescue StandardError
          {}
        end

      url = data["url"].to_s.strip
      return "" if url.empty?

      match = url.match(YOUTUBE_ID_RE)
      video_id = match && (match[1] || match[2])
      return %(<!-- youtube_block: could not extract a video ID from URL: #{CGI.escapeHTML(url)} -->) unless video_id

      safe_id = CGI.escapeHTML(video_id)
      %(<iframe src="https://www.youtube.com/embed/#{safe_id}" frameborder="0" allowfullscreen></iframe>)
    end
  end
end

Liquid::Template.register_tag("youtube_block", Jekyll::YoutubeBlockTag)
