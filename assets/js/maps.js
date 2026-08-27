/* =============================================================================
   maps.js — world map (with trip pins + expandable routes) and trip mini-maps
   =============================================================================
   Uses Leaflet, loaded by _includes/map-libs.html, which also passes in the
   basemap settings from _config.yml (`map:` block). See PROVIDERS below for
   which tile services are available and which of them need a key.

   PUBLIC API (called from page templates):
     TravelMap.initWorld("element-id", data)
       - `data` is an array of trip objects: [{ slug, name, lat, lng, cover,
         url, posts: [{ title, lat, lng, url, name }] }]
       - Renders pins; clicking a trip pin zooms in and shows the day route.

     TravelMap.initTrip("element-id", trip)
       - `trip` is a single object same shape as above.
       - Renders a small map zoomed to that trip with day pins + polyline.

   The page template builds the data from Liquid and injects it as JSON in a
   <script> tag, then calls one of the init functions.
============================================================================= */

window.TravelMap = (function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Shared style constants — read from the site's palette.
  // ---------------------------------------------------------------------------
  // These are the CSS custom properties main.scss publishes from
  // _data/palette.yml. They used to be a second copy of the hex values here,
  // which is how a colour changes everywhere except the map.
  //
  // The fallbacks are the same colours again, and exist only for the case
  // where the stylesheet hasn't loaded — a pin drawn in roughly the right
  // navy beats a pin drawn in browser-default black.
  function paletteColor(prop, fallback) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(prop);
      v = (v || "").trim();
      return v || fallback;
    } catch (e) {
      return fallback;
    }
  }

  var COLORS = {
    navy:     paletteColor("--navy-deep", "#1F4858"),
    navyMid:  paletteColor("--navy-mid",  "#2C5876"),
    seaglass: paletteColor("--seaglass",  "#7FB3A2"),
    sand:     paletteColor("--sand-warm", "#E8DCC4"),
    repeat:   paletteColor("--map-repeat", "#C1783C")  // visited on more than one trip
  };

  // Custom pin icons. We use Leaflet's divIcon with inline SVG so we don't
  // depend on any image files.
  function makeIcon(color) {
    var html =
      '<svg width="28" height="40" viewBox="0 0 28 40" xmlns="http://www.w3.org/2000/svg">' +
        '<path d="M14 0 C6 0 0 6 0 14 C0 24 14 40 14 40 C14 40 28 24 28 14 C28 6 22 0 14 0 Z"' +
              ' fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
        '<circle cx="14" cy="14" r="5" fill="#fff"/>' +
      '</svg>';
    return L.divIcon({
      html: html,
      className: "",          // no extra wrapper class
      iconSize: [28, 40],
      iconAnchor: [14, 40],   // tip of the pin = the actual location
      popupAnchor: [0, -34]
    });
  }
  var TRIP_ICON = makeIcon(COLORS.navy);
  var DAY_ICON  = makeIcon(COLORS.seaglass);

  // Pin for a place we've been to on more than one trip. Amber so it reads
  // as distinct from the navy single-visit pins at a glance, and carries the
  // visit count in the middle instead of the plain dot.
  function makeMultiIcon(count) {
    var label = count > 9 ? "9+" : String(count);
    var html =
      '<svg width="32" height="46" viewBox="0 0 32 46" xmlns="http://www.w3.org/2000/svg">' +
        '<path d="M16 0 C7 0 0 7 0 16 C0 27 16 46 16 46 C16 46 32 27 32 16 C32 7 25 0 16 0 Z"' +
              ' fill="' + COLORS.repeat + '" stroke="#fff" stroke-width="2"/>' +
        '<circle cx="16" cy="16" r="8.5" fill="#fff"/>' +
        '<text x="16" y="16" text-anchor="middle" dominant-baseline="central"' +
             ' font-family="system-ui, sans-serif" font-size="11" font-weight="700"' +
             ' fill="' + COLORS.repeat + '">' + label + '</text>' +
      '</svg>';
    return L.divIcon({
      html: html,
      className: "",
      iconSize: [32, 46],
      iconAnchor: [16, 46],
      popupAnchor: [0, -40]
    });
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  // Basemap providers.
  //
  // The tiles under our pins come from somebody else's server, and that is
  // the piece that changes without asking: CARTO served these key-free for
  // years, then in 2026 began stamping "API KEY REQUIRED" across every tile
  // of an unkeyed request. So the choice is a setting in _config.yml (`map:`)
  // rather than a URL buried here, and switching is one line there.
  //
  // Whichever one is picked has to label places in English. OSM's own style
  // renders every label in the local script — Georgia as თბილისი, Japan as
  // 東京 — which is unreadable unless you read the script, and is the reason
  // the plain OSM tiles are the last resort rather than the default.
  var PROVIDERS = {
    // Esri World Street Map. No key, no signup, English labels worldwide,
    // and close enough to CARTO Voyager in feel that the maps look the same
    // as they always have.
    esri: {
      url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      options: {
        maxZoom: 19,
        attribution:
          'Tiles &copy; <a href="https://www.esri.com/">Esri</a> — Esri, HERE, Garmin, ' +
          'USGS, Intermap, INCREMENT P, NRCan, Esri Japan, METI, Esri China (Hong Kong), ' +
          '&copy; OpenStreetMap contributors, and the GIS User Community'
      }
    },

    // CARTO Voyager. Needs a free key (carto.com/basemaps/apikey) — without
    // one the tiles arrive watermarked rather than blocked, which is easy to
    // miss on a small mini-map and impossible to miss on /map/.
    carto: {
      needsKey: true,
      url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      options: {
        subdomains: "abcd",
        maxZoom: 20,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
          '&copy; <a href="https://carto.com/attributions">CARTO</a>'
      }
    },

    // Plain OpenStreetMap. Free and dependable, but local-script labels.
    osm: {
      url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      options: {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }
    }
  };

  var DEFAULT_PROVIDER = "esri";

  function tileLayer() {
    // _includes/map-libs.html puts this on the page from _config.yml. If it
    // is missing — the include left out of a new page, say — fall back to the
    // default rather than drawing a blank grey rectangle.
    var cfg  = window.TRAVEL_MAP_CONFIG || {};
    var name = cfg.provider || DEFAULT_PROVIDER;
    var key  = cfg.cartoKey || "";

    if (!PROVIDERS[name]) {
      console.warn("TravelMap: unknown map provider '" + name +
                   "' in _config.yml — using " + DEFAULT_PROVIDER + ".");
      name = DEFAULT_PROVIDER;
    }

    // Asked for a keyed provider with no key. Watermarked tiles would still
    // draw, so nothing would look broken from here — better to quietly use a
    // provider that works and say why in the console.
    if (PROVIDERS[name].needsKey && !key) {
      console.warn("TravelMap: map.provider is '" + name + "' but map.carto_key " +
                   "is blank in _config.yml, which serves watermarked tiles — " +
                   "using " + DEFAULT_PROVIDER + " instead.");
      name = DEFAULT_PROVIDER;
      key  = "";
    }

    var provider = PROVIDERS[name];
    var url      = provider.url;
    if (provider.needsKey && key) {
      url += "?key=" + encodeURIComponent(key);
    }
    return L.tileLayer(url, provider.options);
  }

  function tripPopupHtml(trip) {
    var img = trip.cover
      ? '<img src="' + trip.cover + '" alt="" style="width:100%; height:90px; object-fit:cover; border-radius:6px; margin-bottom:0.5em;">'
      : "";
    // Prefer trip.postCount (total posts regardless of location coords).
    // Fall back to trip.posts.length only for legacy data without the field.
    var count = (typeof trip.postCount === "number")
      ? trip.postCount
      : (trip.posts ? trip.posts.length : 0);
    return (
      '<div style="min-width:180px;">' +
        img +
        '<strong>' + escapeHtml(trip.name) + '</strong><br>' +
        '<span style="color:#888; font-size:0.85em;">' +
          count + ' post' + (count === 1 ? '' : 's') +
        '</span><br>' +
        '<a href="' + trip.url + '" style="display:inline-block; margin-top:0.5em;">Read trip &rarr;</a>' +
      '</div>'
    );
  }

  // Popup for a location we've reached on several different trips. Lists
  // every trip so none of them get buried, with its own post count.
  function multiTripPopupHtml(tripsHere) {
    var rows = tripsHere.map(function (t) {
      var count = (typeof t.postCount === "number")
        ? t.postCount
        : (t.posts ? t.posts.length : 0);
      return '<li style="margin:0 0 0.45em 0;">' +
        '<a href="#" data-trip-slug="' + escapeHtml(t.slug) + '"' +
           ' style="font-weight:600; text-decoration:none;">' +
          escapeHtml(t.name) +
        '</a>' +
        '<br><span style="color:#888; font-size:0.85em;">' +
          count + ' post' + (count === 1 ? '' : 's') +
        '</span></li>';
    }).join("");

    return (
      '<div style="min-width:190px;">' +
        '<div style="font-weight:700; margin-bottom:0.15em;">' +
          'Visited ' + tripsHere.length + ' times' +
        '</div>' +
        '<div style="color:#888; font-size:0.8em; margin-bottom:0.6em;">' +
          'Pick a trip to see its route' +
        '</div>' +
        '<ul style="list-style:none; margin:0; padding:0;">' + rows + '</ul>' +
      '</div>'
    );
  }

  function dayPopupHtml(post) {
    return (
      '<div style="min-width:140px;">' +
        '<strong>' + escapeHtml(post.title) + '</strong>' +
        (post.name ? '<br><span style="color:#888; font-size:0.85em;">' + escapeHtml(post.name) + '</span>' : '') +
        '<br><a href="' + post.url + '" style="display:inline-block; margin-top:0.4em;">Read post &rarr;</a>' +
      '</div>'
    );
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ---------------------------------------------------------------------------
  // WORLD MAP — pins for every trip. Click a pin to zoom in and show the
  // route of day pins for that trip. A "Reset" button returns to the world.
  // ---------------------------------------------------------------------------
  function initWorld(elementId, trips) {
    var map = L.map(elementId, {
      worldCopyJump: true,
      minZoom: 2
    }).setView([20, 0], 2);
    tileLayer().addTo(map);

    // Layer group that holds the currently-loaded trip-detail (day pins +
    // route line). We clear and rebuild it whenever the user clicks a trip.
    var detailLayer = L.layerGroup().addTo(map);

    // The trip pins themselves. A multi-country trip can have additional
    // pins via trip.countries[] — each renders as its own marker on the
    // world map but all point at the same trip page.
    var tripPins = L.layerGroup();
    var bounds = [];

    // ---- Pass 1: collect every pin we intend to draw --------------------
    // Nothing is rendered yet. We need the full set first so we can tell
    // which coordinates host more than one trip.
    var candidates = [];
    function addCandidate(trip, lat, lng) {
      if (typeof lat !== "number" || typeof lng !== "number") return;
      candidates.push({ trip: trip, lat: lat, lng: lng });
    }

    trips.forEach(function (trip) {
      // Always show the primary pin at the trip's own lat/lng. Previously
      // we skipped this when countries[] was set, but that meant the
      // PRIMARY country got no pin — e.g. African Safari with South
      // Africa as location + Botswana/Zimbabwe in countries[] rendered
      // only Botswana/Zimbabwe pins, no SA. Now: primary pin always
      // shows; countries[] pins are ADDITIONAL.
      addCandidate(trip, trip.lat, trip.lng);
      if (Array.isArray(trip.countries)) {
        trip.countries.forEach(function (c) { addCandidate(trip, c.lat, c.lng); });
      }
    });

    // ---- Pass 2: group by rounded coordinate ---------------------------
    // 1 decimal place is roughly 11km, so separate trips that each start in
    // e.g. New York collapse into one group even when their coordinates
    // aren't byte-identical, while genuinely different cities stay apart.
    var groups = {};
    var order = [];
    candidates.forEach(function (c) {
      var key = c.lat.toFixed(1) + "," + c.lng.toFixed(1);
      if (!groups[key]) {
        groups[key] = { lat: c.lat, lng: c.lng, trips: [] };
        order.push(key);
      }
      // De-dupe by slug: a trip listing its own primary country again in
      // countries[] shouldn't make the place look twice-visited.
      var seen = groups[key].trips.some(function (t) { return t.slug === c.trip.slug; });
      if (!seen) groups[key].trips.push(c.trip);
    });

    // ---- Pass 3: render one marker per group ---------------------------
    order.forEach(function (key) {
      var g = groups[key];
      bounds.push([g.lat, g.lng]);
      var repeat = g.trips.length > 1;
      var marker = L.marker([g.lat, g.lng], {
        icon: repeat ? makeMultiIcon(g.trips.length) : TRIP_ICON
      });

      if (repeat) {
        // Several trips here: list them all and let her pick. Don't jump
        // straight into a trip, since we can't know which one she means.
        marker.bindPopup(multiTripPopupHtml(g.trips));
        marker.on("popupopen", function (e) {
          var root = e.popup.getElement();
          if (!root) return;
          root.querySelectorAll("[data-trip-slug]").forEach(function (el) {
            el.addEventListener("click", function (ev) {
              ev.preventDefault();
              var slug = el.getAttribute("data-trip-slug");
              var picked = g.trips.filter(function (t) { return t.slug === slug; })[0];
              if (picked) { map.closePopup(); showTripDetail(picked); }
            });
          });
        });
      } else {
        marker.bindPopup(tripPopupHtml(g.trips[0]))
              .on("click", function () { showTripDetail(g.trips[0]); });
      }

      tripPins.addLayer(marker);
    });
    tripPins.addTo(map);

    // Fit world view to whatever trips exist (only if we have multiple).
    if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 4 });
    }

    function showTripDetail(trip) {
      detailLayer.clearLayers();
      var posts = (trip.posts || []).filter(function (p) {
        return typeof p.lat === "number" && typeof p.lng === "number";
      });
      if (posts.length === 0) {
        // No day-level coords — just zoom to the trip pin and keep going.
        map.flyTo([trip.lat, trip.lng], 6);
        return;
      }

      // Day pins.
      var coords = [];
      posts.forEach(function (post) {
        coords.push([post.lat, post.lng]);
        L.marker([post.lat, post.lng], { icon: DAY_ICON })
          .bindPopup(dayPopupHtml(post))
          .addTo(detailLayer);
      });

      // Route line connecting the day pins in order.
      L.polyline(coords, {
        color: COLORS.navyMid,
        weight: 3,
        opacity: 0.8,
        dashArray: "6 6"
      }).addTo(detailLayer);

      // Zoom to fit just this trip's pins, with a little padding.
      map.flyToBounds(coords, { padding: [50, 50], maxZoom: 9, duration: 0.8 });
      showResetButton();
    }

    // -------- Reset-to-world button (added to the map's top-right) --------
    var resetCtl;
    function showResetButton() {
      if (resetCtl) return;
      resetCtl = L.control({ position: "topright" });
      resetCtl.onAdd = function () {
        var div = L.DomUtil.create("div", "leaflet-bar");
        div.innerHTML =
          '<a href="#" role="button" title="Back to world view" ' +
              'style="padding:0 0.6em; background:#fff; line-height:30px; ' +
              'display:inline-block; font-size:0.85em; color:' + COLORS.navy + ';">' +
              '&#x21ba; World view</a>';
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.on(div, "click", function (e) {
          e.preventDefault();
          detailLayer.clearLayers();
          if (bounds.length > 1) {
            map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 4 });
          } else {
            map.flyTo([20, 0], 2);
          }
          map.removeControl(resetCtl);
          resetCtl = null;
        });
        return div;
      };
      resetCtl.addTo(map);
    }
  }

  // ---------------------------------------------------------------------------
  // TRIP MINI-MAP — embedded on a single trip page. Shows day pins + route.
  // ---------------------------------------------------------------------------
  function initTrip(elementId, trip) {
    var map = L.map(elementId, { scrollWheelZoom: false });
    tileLayer().addTo(map);

    var posts = (trip.posts || []).filter(function (p) {
      return typeof p.lat === "number" && typeof p.lng === "number";
    });

    if (posts.length === 0) {
      // No day coords — just center on trip lat/lng.
      map.setView([trip.lat, trip.lng], 6);
      L.marker([trip.lat, trip.lng], { icon: TRIP_ICON })
        .bindPopup(tripPopupHtml(trip))
        .addTo(map);
      return;
    }

    var coords = [];
    posts.forEach(function (post) {
      coords.push([post.lat, post.lng]);
      L.marker([post.lat, post.lng], { icon: DAY_ICON })
        .bindPopup(dayPopupHtml(post))
        .addTo(map);
    });

    if (coords.length === 1) {
      map.setView(coords[0], 9);
    } else {
      L.polyline(coords, {
        color: COLORS.navyMid,
        weight: 3,
        opacity: 0.8,
        dashArray: "6 6"
      }).addTo(map);
      map.fitBounds(coords, { padding: [30, 30], maxZoom: 10 });
    }
  }

  return { initWorld: initWorld, initTrip: initTrip };
})();
