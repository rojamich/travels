# =============================================================================
# seo_image.rb — auto-populate page.image for social-share previews
# =============================================================================
# When someone pastes a post URL into iMessage, WhatsApp, Facebook, Twitter,
# Slack, etc, those services fetch the page and look for an og:image meta
# tag to render a nice preview card. The jekyll-seo-tag plugin generates
# this tag, but only if `page.image` is set.
#
# Our posts use `header.overlay_image` (banner) and `header.teaser`
# (thumbnail) — they don't set `page.image` directly. This plugin maps
# those fields to `page.image` automatically before render, so social
# previews work out of the box without the wife having to set anything
# extra in the CMS.
#
# Trip pages use `cover` instead — also handled here.
#
# Priority order:
#   1. existing page.image (don't overwrite)
#   2. page.header.overlay_image (post banner)
#   3. page.header.teaser (post thumbnail)
#   4. page.cover (trip cover photo)
# =============================================================================

Jekyll::Hooks.register [:posts, :documents, :pages], :pre_render do |doc|
  next if doc.data["image"]

  candidate =
    (doc.data["header"] && doc.data["header"]["overlay_image"]) ||
    (doc.data["header"] && doc.data["header"]["teaser"]) ||
    doc.data["cover"]

  doc.data["image"] = candidate if candidate
end
