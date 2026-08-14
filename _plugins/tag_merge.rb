# =============================================================================
# tag_merge.rb — fold `new_tags` into `tags`
# =============================================================================
# Tags are picked from a dropdown so they can't be mistyped, but a dropdown can
# only offer what already exists. Inventing a tag meant leaving the post, going
# to Tags, adding it, and coming back — enough friction that it wouldn't happen
# mid-write.
#
# So a post can also carry `new_tags`: plain text, typed straight onto the
# post. This merges the two before anything else looks at them, so a brand-new
# tag works immediately — filters, the tag sheet, the counts, all of it — with
# nothing else in the site needing to know the field exists.
#
# The new tag is NOT written back to _data/tags.yml. Doing that would mean a
# plugin editing a file the CMS also edits, and a build that changes its own
# inputs. content_audit.rb reports it instead, so it gets added to the master
# list deliberately rather than by a side effect.
#
# Case and whitespace are normalised against the master list: type "food" when
# "Food" already exists and it folds into the existing tag rather than starting
# a rival. That is the failure this whole arrangement is meant to prevent, and
# it is the one most likely to happen while typing quickly.
#
# Runs at :highest so every later generator sees one merged list.
# =============================================================================
module TravelBlog
  class TagMerge < Jekyll::Generator
    safe true
    priority :highest

    def generate(site)
      known = known_tags(site)
      merged = 0

      docs = (site.collections["trips"]&.docs || []) + site.posts.docs
      docs.each do |doc|
        extra = Array(doc.data["new_tags"]).map { |t| t.to_s.strip }.reject(&:empty?)
        next if extra.empty?

        tags = Array(doc.data["tags"]).map { |t| t.to_s.strip }.reject(&:empty?)

        extra.each do |raw|
          # Fold onto the existing spelling when one exists in any case.
          tag = known[raw.downcase] || raw
          next if tags.any? { |t| t.casecmp?(tag) }
          tags << tag
          merged += 1
        end

        doc.data["tags"] = tags
      end

      Jekyll.logger.info "Tags:", "#{merged} new tag(s) merged from new_tags" if merged.positive?
    end

    private

    def known_tags(site)
      out = {}
      Array(site.data.dig("tags", "tags")).each do |rec|
        name = rec.is_a?(Hash) ? rec["name"].to_s.strip : rec.to_s.strip
        out[name.downcase] = name unless name.empty?
      end
      out
    end
  end
end
