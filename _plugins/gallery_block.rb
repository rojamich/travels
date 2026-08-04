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
    # Focal-point coordinates are 0-100. Anything missing, non-numeric or out
    # of range falls back to 50 (centre) rather than producing broken CSS.
    def clamp_pct(value)
      n = Float(value)
      return 50 if n.nan?
      n = 0 if n < 0
      n = 100 if n > 100
      n.round
    rescue StandardError
      50
    end

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

      # Each photo item is either a bare URL string (older galleries) or an
      # object from the Decap list widget:
      #
      #   { "image": "https://…", "x": 50, "y": 30 }
      #
      # x/y are the focal point, 0–100. Tiles are a fixed shape, so a photo
      # whose aspect ratio differs from the tile gets cropped — a landscape
      # shot in a portrait-ish tile loses its top and bottom. The focal point
      # decides WHICH part survives that crop, so the subject can be kept in
      # frame without changing the tile size.
      #
      # Both fields are optional and default to dead centre, which is exactly
      # what every existing gallery already renders — so this is backwards
      # compatible and nothing needs re-saving.
      items = photos.map do |p|
        if p.is_a?(Hash)
          url = p["image"].to_s
          next nil if url.empty?
          { url: url, x: clamp_pct(p["x"]), y: clamp_pct(p["y"]) }
        else
          url = p.to_s
          next nil if url.empty?
          { url: url, x: 50, y: 50 }
        end
      end.compact

      return "" if items.empty?

      # Unique gallery ID per block so GLightbox treats each block as its own
      # gallery (prev/next arrows cycle within this block only, not across
      # all galleries on the page).
      gallery_id = "gb" + Digest::SHA1.hexdigest(@markup)[0, 8]

      tiles = items.map do |item|
        safe_url = CGI.escapeHTML(item[:url])
        # Wrap each image in an <a> so GLightbox finds them. The full-size
        # image is the same URL — Cloudinary serves the original, plus our
        # default_transformations downsize the delivered version.
        #
        # object-position decides which part of an off-ratio photo survives
        # the tile crop. Emitted only when it differs from centre, to keep
        # the markup clean for the common case.
        pos =
          if item[:x] == 50 && item[:y] == 50
            ""
          else
            %( style="object-position: #{item[:x]}% #{item[:y]}%;")
          end
        %(<a href="#{safe_url}" class="inline-gallery-link" data-glightbox="type: image" data-gallery="#{gallery_id}"><img src="#{safe_url}" alt="" loading="lazy"#{pos}></a>)
      end.join

      # Use <figure>/<figcaption> so the caption is semantically tied to the
      # gallery AND so Kramdown reliably treats the whole thing as one block.
      # The previous structure (<div> followed by sibling <p>) sometimes had
      # Kramdown wrap the <p> incorrectly when the gallery had only one
      # photo, causing the caption to disappear.
      html = %(<figure class="inline-gallery-figure"><div class="inline-gallery">#{tiles}</div>)
      unless caption.empty?
        html += %(<figcaption class="inline-gallery-caption">#{CGI.escapeHTML(caption)}</figcaption>)
      end
      html += "</figure>"
      html
    end
  end
end

Liquid::Template.register_tag("gallery_block", Jekyll::GalleryBlockTag)
