# =============================================================================
# lazy_images.rb — automatically add loading="lazy" to <img> tags
# =============================================================================
# Performance optimization: tells the browser not to load images until they're
# about to scroll into view. Hugely useful when a post has 20+ photos —
# instead of fetching all 20 immediately, the browser only fetches the first
# few (above the fold) plus the rest as the reader scrolls down.
#
# Native browser feature, no JS required. Supported in all modern browsers.
#
# This plugin runs after each page is rendered and rewrites the HTML to add
# loading="lazy" on every <img> tag that doesn't already have a loading
# attribute (so we don't override any explicit loading="eager" tags).
#
# Hero/cover images aren't <img> tags in Minimal Mistakes — they're rendered
# as CSS background-images on a div — so they're already loaded eagerly.
# =============================================================================

Jekyll::Hooks.register [:posts, :pages, :documents], :post_render do |doc|
  next if doc.output.nil?
  next unless doc.output.include?("<img")

  doc.output = doc.output.gsub(
    /<img(?![^>]*\bloading\s*=)([^>]*?)>/im
  ) do |_match|
    attrs = Regexp.last_match(1)
    "<img loading=\"lazy\" decoding=\"async\"#{attrs}>"
  end
end
