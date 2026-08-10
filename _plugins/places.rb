# =============================================================================
# places.rb — fill in coordinates a place has already been given once
# =============================================================================
# Every trip and most posts carry a lat/lng so they can be pinned on a map.
# Those were typed by hand, one at a time, including for places already
# pinned on an earlier trip — Oslo has been looked up more than once.
#
# This reads _data/places.yml (name -> lat/lng) and fills the gap whenever a
# trip or post names a place it recognises but has no coordinates of its own.
#
# THE CACHE NEVER OVERRIDES
# Coordinates written on the trip or post always win. This only fills blanks,
# so a remembered value can't silently move a pin that was set deliberately.
# The one thing it does with an existing pin is COMPARE: if a pin sits more
# than 25km from the remembered position for the same name, that's reported
# as a possible typo — a digit dropped from a longitude moves a pin oceans
# away and looks perfectly normal in the front matter.
#
# WHAT IT DOESN'T DO
# There is no geocoding here. Nothing calls out to a maps API at build time:
# that would make builds depend on a third-party service being up, need a key
# in the environment, and quietly change pins when the service changed its
# mind. A place still has to be pinned by hand ONCE. After that it's known.
#
# Runs at priority :low, after country_data.rb and alongside content_audit.rb.
# =============================================================================
module TravelBlog
  class Places < Jekyll::Generator
    safe true
    priority :low

    # How far a pin may sit from the remembered position before we call it a
    # mistake. Generous on purpose: a city-centre pin and an airport pin for
    # the same city are both legitimate and are usually well inside this.
    DRIFT_KM = 25.0

    def generate(site)
      @places   = normalise(site.data["places"])
      @filled   = []
      @unknown  = []
      @drifted  = []
      @invalid  = []

      return if @places.empty?

      (site.collections["trips"]&.docs || []).each { |doc| handle_trip(doc) }
      site.posts.docs.each { |doc| handle_post(doc) }

      site.data["place_problems"] = build_report
      log(site)
    end

    private

    def normalise(raw)
      out = {}
      return out unless raw.is_a?(Hash)
      raw.each do |name, v|
        next unless v.is_a?(Hash)
        lat = to_f(v["lat"])
        lng = to_f(v["lng"])
        next if lat.nil? || lng.nil?
        out[name.to_s.strip.downcase] = [lat, lng]
      end
      out
    end

    def to_f(v)
      return nil if v.nil? || v.to_s.strip.empty?
      Float(v)
    rescue StandardError
      nil
    end

    def lookup(name)
      @places[name.to_s.strip.downcase]
    end

    # A trip pins itself with top-level lat/lng and names the place in
    # `location:`.
    def handle_trip(doc)
      name = doc.data["location"].to_s.strip
      return if name.empty?

      lat = to_f(doc.data["lat"])
      lng = to_f(doc.data["lng"])
      known = lookup(name)

      if lat.nil? || lng.nil?
        if known
          doc.data["lat"], doc.data["lng"] = known
          @filled << [doc.data["title"] || doc.basename, name]
        else
          @unknown << [doc.data["title"] || doc.basename, name]
        end
      elsif !valid?(lat, lng)
        @invalid << [doc.data["title"] || doc.basename, name, lat, lng]
      elsif known && distance_km([lat, lng], known) > DRIFT_KM
        @drifted << [doc.data["title"] || doc.basename, name, [lat, lng], known]
      end
    end

    # A post nests it: location: { name:, lat:, lng: }.
    def handle_post(doc)
      loc = doc.data["location"]
      return unless loc.is_a?(Hash)
      name = loc["name"].to_s.strip
      return if name.empty?

      lat = to_f(loc["lat"])
      lng = to_f(loc["lng"])
      known = lookup(name)

      if lat.nil? || lng.nil?
        if known
          loc["lat"], loc["lng"] = known
          @filled << [doc.data["title"] || doc.basename, name]
        else
          @unknown << [doc.data["title"] || doc.basename, name]
        end
      elsif !valid?(lat, lng)
        @invalid << [doc.data["title"] || doc.basename, name, lat, lng]
      elsif known && distance_km([lat, lng], known) > DRIFT_KM
        @drifted << [doc.data["title"] || doc.basename, name, [lat, lng], known]
      end
    end

    # Latitude runs -90..90 and longitude -180..180. Anything outside that is
    # not a place, it is a typo — and Leaflet doesn't reject it, it just draws
    # the track off to infinity and back, which is what put a line straight
    # across the Africa map. That one was `lng: 182704`, a dropped decimal
    # point in 18.2704.
    def valid?(lat, lng)
      lat.between?(-90, 90) && lng.between?(-180, 180)
    end

    # Equirectangular approximation. Accurate to well under a kilometre at
    # these distances, and we're only deciding "is this pin plausible".
    def distance_km(a, b)
      mean_lat = (a[0] + b[0]) / 2 * Math::PI / 180
      dy = (a[0] - b[0]) * 111.0
      dx = (a[1] - b[1]) * 111.0 * Math.cos(mean_lat)
      Math.sqrt((dx * dx) + (dy * dy))
    end

    # Same "where||what" shape /admin-stats/ already renders for the other checks.
    def build_report
      rows = []
      @invalid.each do |where, name, lat, lng|
        rows << "#{where}||is pinned at #{lat}, #{lng}, which is not a real " \
                "coordinate (latitude is -90..90, longitude -180..180). The " \
                "map draws a line straight across the world to reach it. " \
                "Check for a missing decimal point or minus sign in " \
                "#{name.inspect}."
      end
      @unknown.each do |where, name|
        rows << "#{where}||names #{name.inspect} but has no coordinates, and " \
                "_data/places.yml doesn't know that place yet. It won't appear " \
                "on any map. Pin it once and every later use fills itself in."
      end
      @drifted.each do |where, name, got, known|
        rows << "#{where}||is pinned at #{fmt(got)} but #{name.inspect} is " \
                "remembered at #{fmt(known)}, #{distance_km(got, known).round}km away. " \
                "One of the two is wrong — check for a missing digit."
      end
      rows
    end

    def fmt(pair)
      format("%.4f, %.4f", pair[0], pair[1])
    end

    def log(site)
      Jekyll.logger.info "Places:", "#{@filled.size} coordinate(s) filled from cache, " \
                                    "#{@places.size} places remembered"
      problems = site.data["place_problems"]
      return if problems.empty?
      Jekyll.logger.warn "Places:", "#{problems.size} problem(s):"
      problems.each { |p| Jekyll.logger.warn "  -", p.sub("||", ": ") }
    end
  end
end
