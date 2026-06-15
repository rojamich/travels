# =============================================================================
# caption_images.rb — wrap <img title="..."> in <figure>/<figcaption>
# =============================================================================
# When she writes a standalone image in markdown with a "title":
#
#     ![](photo.jpg "this is the caption")
#
# Kramdown renders that as <img title="this is the caption">. By itself the
# title attribute only shows on hover, which isn't useful as a real caption.
#
# This plugin runs after the page is rendered and rewrites every <img> that
# has a non-empty title attribute into a <figure>/<figcaption> structure.
# If the <img> is already wrapped in an <a> (Markdown link or click-to-zoom
# anchor), we wrap the whole anchor instead of the bare image.
#
# Gallery images from _plugins/gallery_block.rb don't get a title attribute,
# so they're not affected by this plugin.
# =============================================================================

require "cgi"

module Jekyll
  module CaptionImages
    # Match optional <a>...</a> wrapper around an <img> that has a title="...".
    # Captures: 1=anchor open (or nil), 2=img tag, 3=title text, 4=anchor close (or nil)
    PATTERN = %r{
      (<a\b[^>]*>)?           # optional <a> opener
      (<img\b[^>]*?\s
        title\s*=\s*"([^"]+)" # title="..."
        [^>]*>)               # rest of img tag
      (</a>)?                 # optional </a>
    }mix

    def self.process(html)
      html.gsub(PATTERN) do
        a_open  = Regexp.last_match(1) || ""
        img_tag = Regexp.last_match(2)
        title   = Regexp.last_match(3)
        a_close = Regexp.last_match(4) || ""

        # Defensive: skip empty titles (shouldn't happen given regex, but safe).
        next "#{a_open}#{img_tag}#{a_close}" if title.to_s.strip.empty?

        # Strip the title attribute from the <img> tag itself. Two reasons:
        #   1. The caption is now visible in the figcaption — the hover-only
        #      title tooltip is redundant and clutters the UI on touch devices.
        #   2. Idempotency. Jekyll's :post_render hook fires for posts AND
        #      documents (which includes posts in newer Jekyll), so this
        #      method runs twice. Without the strip, the second pass would
        #      re-wrap an already-wrapped image, producing nested figures.
        img_stripped = img_tag.sub(/\stitle\s*=\s*"[^"]+"/, "")

        %(<figure class="captioned-image">#{a_open}#{img_stripped}#{a_close}<figcaption class="inline-gallery-caption">#{CGI.escapeHTML(title)}</figcaption></figure>)
      end
    end
  end
end

Jekyll::Hooks.register [:posts, :pages, :documents], :post_render do |doc|
  next if doc.output.nil?
  next unless doc.output.include?("title=")
  doc.output = Jekyll::CaptionImages.process(doc.output)
end
