# =============================================================================
# gallery_block.rb — Liquid tag for inline photo galleries
# =============================================================================
# Wired up with the Decap CMS "Photo Gallery" editor component (admin/index.html).
# When she clicks the gallery button in the markdown editor and picks N photos,
# Decap writes this into the post body:
#
#   {% gallery_block ENCODED_JSON %}
#
# At build time, this Liquid tag decodes the JSON, pulls the photo URLs and
# optional caption, and emits the gallery HTML. GLightbox handles the click-
# to-zoom behavior via the .inline-gallery-link selector (set in head/custom).
# =============================================================================

require "json"
require "uri"
require "cgi"
require "digest"

module Jekyll
  class GalleryBlockTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(_context)
      decoded =
        begin
          # The JS in the editor component URI-encodes the JSON. Decode it back.
          URI.decode_www_form_component(@markup)
        rescue StandardError
          @markup
        end

      data =
        begin
          JSON.parse(decoded)
        rescue StandardError => e
          return "<!-- gallery_block: failed to parse data: #{CGI.escapeHTML(e.message)} -->"
        end

      photos = data["photos"] || []
      caption = data["caption"].to_s

      # Each photo item is an object like { "image": "https://..." } from the
      # Decap list widget. Filter out empty/blank URLs defensively.
      urls = photos.map { |p| p.is_a?(Hash) ? p["image"] : p }.compact.reject(&:empty?)

      return "" if urls.empty?

      # Unique gallery ID per block so GLightbox treats each block as its own
      # gallery (prev/next arrows cycle within this block only, not across
      # all galleries on the page).
      gallery_id = "gb" + Digest::SHA1.hexdigest(@markup)[0, 8]

      tiles = urls.map do |url|
        safe_url = CGI.escapeHTML(url)
        # Wrap each image in an <a> so GLightbox finds them. The full-size
        # image is the same URL — Cloudinary serves the original, plus our
        # default_transformations downsize the delivered version.
        %(<a href="#{safe_url}" class="inline-gallery-link" data-glightbox="type: image" data-gallery="#{gallery_id}"><img src="#{safe_url}" alt="" loading="lazy"></a>)
      end.join

      html = %(<div class="inline-gallery">#{tiles}</div>)

      unless caption.empty?
        html += %(<p class="inline-gallery-caption">#{CGI.escapeHTML(caption)}</p>)
      end

      html
    end
  end
end

Liquid::Template.register_tag("gallery_block", Jekyll::GalleryBlockTag)
