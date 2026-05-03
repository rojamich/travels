# =============================================================================
# Gemfile — Ruby dependency list
# =============================================================================
# You don't need to install Ruby or run anything with this file locally.
# GitHub Pages reads it on their servers when it builds the site.
#
# This file just tells GitHub: "use the github-pages gem and these plugins."
# =============================================================================

source "https://rubygems.org"

# We use plain Jekyll on Netlify (not the `github-pages` meta-gem, which
# pins old versions). This gives us a faster, more current Jekyll.
gem "jekyll", "~> 4.3"

# Plugins. These must also be listed in _config.yml under `plugins:`.
group :jekyll_plugins do
  gem "jekyll-include-cache"
  gem "jekyll-paginate"
  gem "jekyll-sitemap"
  gem "jekyll-feed"
  gem "jekyll-seo-tag"
  gem "jemoji"
  gem "jekyll-remote-theme"   # required for `remote_theme:` in _config.yml
end

# webrick is no longer in stdlib for Ruby 3+ — needed for `jekyll serve`.
gem "webrick"

# Windows / JRuby do not include zoneinfo, so bundle the tzinfo-data gem.
# (Harmless on Linux/macOS — only loads when needed.)
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end
