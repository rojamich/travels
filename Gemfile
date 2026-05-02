# =============================================================================
# Gemfile — Ruby dependency list
# =============================================================================
# You don't need to install Ruby or run anything with this file locally.
# GitHub Pages reads it on their servers when it builds the site.
#
# This file just tells GitHub: "use the github-pages gem and these plugins."
# =============================================================================

source "https://rubygems.org"

# The `github-pages` gem bundles the exact versions of Jekyll and plugins that
# GitHub Pages supports. Pinning to it guarantees what builds locally will
# also build on GitHub.
gem "github-pages", group: :jekyll_plugins

# Plugins. These must also be listed in _config.yml under `plugins:`.
group :jekyll_plugins do
  gem "jekyll-include-cache"
  gem "jekyll-paginate"
  gem "jekyll-sitemap"
  gem "jekyll-feed"
  gem "jekyll-seo-tag"
  gem "jemoji"
end

# Windows / JRuby do not include zoneinfo, so bundle the tzinfo-data gem.
# (Harmless on Linux/macOS — only loads when needed.)
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end
