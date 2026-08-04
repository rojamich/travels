# =============================================================================
# country_data.rb — derive every country lookup from one source file
# =============================================================================
# Reads _data/countries.yml (one record per country) and builds the three
# lookup tables the templates use:
#
#     site.data.country_codes      name  -> ISO 3166-1 alpha-3
#     site.data.continents         name  -> continent
#     site.data.country_aliases    alias -> canonical name
#
# Those were three hand-maintained YAML files. Nothing kept them in step, and
# they drifted: Costa Rica had a continent but no ISO code, so it counted
# toward the Countries tile while being invisible on the world map, and the
# two figures on /stats/ disagreed. One record per country makes that
# impossible — a country cannot have a continent but no code, because both
# are on the same line.
#
# Templates were NOT changed to match. They still read site.data.country_codes
# and friends exactly as before; this generator just supplies those hashes
# instead of the files doing it. That keeps the blast radius small and means
# an unfamiliar template still reads the way its comments describe.
#
# Runs at priority :high so the data exists before any page renders.
# =============================================================================
module TravelBlog
  class CountryData < Jekyll::Generator
    safe true
    priority :high

    VALID_CONTINENTS = [
      "North America", "South America", "Europe",
      "Asia", "Africa", "Oceania", "Antarctica"
    ].freeze

    def generate(site)
      records = site.data["countries"]

      unless records.is_a?(Array) && !records.empty?
        # Refuse to carry on quietly. Every country count on the site depends
        # on this file, and silently producing empty lookups would show a
        # plausible-looking zero everywhere rather than an obvious failure.
        raise "_data/countries.yml is missing or empty — every country count " \
              "on the site derives from it. Restore it before building."
      end

      codes      = {}
      continents = {}
      aliases    = {}
      problems   = []
      seen_names = {}

      records.each_with_index do |rec, i|
        unless rec.is_a?(Hash)
          problems << "record ##{i + 1} is not a name/code/continent block"
          next
        end

        name = rec["name"].to_s.strip
        if name.empty?
          problems << "record ##{i + 1} has no name"
          next
        end

        if seen_names.key?(name)
          problems << "#{name} is listed twice"
          next
        end
        seen_names[name] = true

        code = rec["code"].to_s.strip
        cont = rec["continent"].to_s.strip

        # A missing code means the country counts but never shades on the map;
        # a missing continent means it silently drops out of the continent
        # tally. Both are the exact drift this file exists to prevent, so both
        # are reported rather than shrugged off.
        problems << "#{name} has no ISO code (it will not shade on the map)" if code.empty?
        if cont.empty?
          problems << "#{name} has no continent (it will not count toward continents)"
        elsif !VALID_CONTINENTS.include?(cont)
          problems << "#{name} has continent #{cont.inspect}, which is not one of: " \
                      "#{VALID_CONTINENTS.join(', ')}"
        end

        codes[name]      = code unless code.empty?
        continents[name] = cont unless cont.empty?

        # The canonical name maps to itself. Templates look a name up in the
        # alias table and keep it if there's no hit, so this is belt-and-braces
        # rather than required — but it makes the table self-describing.
        aliases[name] = name

        Array(rec["aliases"]).each do |raw|
          a = raw.to_s.strip
          next if a.empty?

          if aliases.key?(a) && aliases[a] != name
            problems << "#{a.inspect} is claimed by both #{aliases[a]} and #{name}"
            next
          end

          aliases[a] = name

          # An alias needs the same lookups as its canonical name: trip front
          # matter may well say "England" or "USA", and those must still find
          # a code and a continent.
          codes[a]      = code unless code.empty?
          continents[a] = cont unless cont.empty?
        end
      end

      site.data["country_codes"]   = codes
      site.data["continents"]      = continents
      site.data["country_aliases"] = aliases

      # Exposed so /admin-stats/ can show the same problems the build log
      # reports — she doesn't read build logs, and a warning nobody sees is
      # not a check.
      site.data["country_problems"] = problems

      if problems.empty?
        Jekyll.logger.info "Countries:",
                           "#{seen_names.size} countries, #{aliases.size} names resolved"
      else
        Jekyll.logger.warn "Countries:",
                           "#{problems.size} problem(s) in _data/countries.yml:"
        problems.each { |p| Jekyll.logger.warn "  -", p }
      end
    end
  end
end
