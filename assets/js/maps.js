/* =============================================================================
   maps.js — world map (with trip pins + expandable routes) and trip mini-maps
   =============================================================================
   Uses Leaflet (loaded from CDN by the page) and OpenStreetMap tiles.
   No API key required.

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
  // Shared style constants — tuned to the coastal palette.
  // ---------------------------------------------------------------------------
  var COLORS = {
    navy:     "#1F4858",
    navyMid:  "#2C5876",
    seaglass: "#7FB3A2",
    sand:     "#E8DCC4"
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

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function tileLayer() {
    // OpenStreetMap standard tiles. Free, no key. Attribution required.
    return L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18
    });
  }

  function tripPopupHtml(trip) {
    var img = trip.cover
      ? '<img src="' + trip.cover + '" alt="" style="width:100%; height:90px; object-fit:cover; border-radius:6px; margin-bottom:0.5em;">'
      : "";
    return (
      '<div style="min-width:180px;">' +
        img +
        '<strong>' + escapeHtml(trip.name) + '</strong><br>' +
        '<span style="color:#888; font-size:0.85em;">' +
          (trip.posts ? trip.posts.length : 0) + ' post(s)' +
        '</span><br>' +
        '<a href="' + trip.url + '" style="display:inline-block; margin-top:0.5em;">Read trip &rarr;</a>' +
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

    // The trip pins themselves.
    var tripPins = L.layerGroup();
    var bounds = [];
    trips.forEach(function (trip) {
      if (typeof trip.lat !== "number" || typeof trip.lng !== "number") return;
      bounds.push([trip.lat, trip.lng]);
      var marker = L.marker([trip.lat, trip.lng], { icon: TRIP_ICON })
        .bindPopup(tripPopupHtml(trip))
        .on("click", function () {
          showTripDetail(trip);
        });
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
              'display:inline-block; font-size:0.85em; color:#1F4858;">' +
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
