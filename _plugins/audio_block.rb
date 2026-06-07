# =============================================================================
# audio_block.rb — Liquid tag for inline audio players
# =============================================================================
# Paired with the "🎵 Audio Clip" editor component in admin/index.html.
# When she clicks the audio button in the markdown editor and uploads a
# sound file + optional title, Decap writes this into the post body:
#
#   {% audio_block ENCODED_JSON %}
#
# At build time this tag decodes the JSON, pulls the audio URL and title,
# and emits an HTML5 <audio controls> player styled to match the site.
# Audio doesn't autoplay — browsers block that anyway.
# =============================================================================

require "json"
require "uri"
require "cgi"

module Jekyll
  class AudioBlockTag < Liquid::Tag
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
        rescue StandardError => e
          return "<!-- audio_block: failed to parse data: #{CGI.escapeHTML(e.message)} -->"
        end

      url = (data["audio"] || data["url"]).to_s.strip
      title = data["title"].to_s.strip

      return "" if url.empty?

      safe_url = CGI.escapeHTML(url)
      title_html = title.empty? ? "" : %(<p class="inline-audio-title">#{CGI.escapeHTML(title)}</p>)

      <<~HTML
        <figure class="inline-audio">
          #{title_html}
          <audio controls preload="none" src="#{safe_url}">
            Your browser doesn't support the audio element. <a href="#{safe_url}">Download the file</a>.
          </audio>
        </figure>
      HTML
    end
  end
end

Liquid::Template.register_tag("audio_block", Jekyll::AudioBlockTag)
