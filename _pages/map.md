---
# =============================================================================
# /map/ — interactive world map
# =============================================================================
# Top-level "where we've been" map. Shows one pin per trip. Click a pin to
# zoom in and reveal that trip's day-by-day route, then click any day pin
# to read that day's post.
# =============================================================================

title: "Map"
permalink: /map/
layout: single
author_profile: false
classes: wide
---

<p>Click any pin to see the trip's route. Click a day pin to read that post.</p>

<!-- Map container — Leaflet attaches the map to this div. -->
<div id="world-map" style="height: 600px; border-radius: 14px; overflow: hidden; border: 1px solid #ddd;"></div>

<!--
  Leaflet stylesheet + script, loaded from a CDN. No npm/build step needed.
  We use a pinned version so the page won't break if Leaflet changes their
  default behavior in a later release.
-->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
      crossorigin="" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
        crossorigin=""></script>

<!--
  Build the trip + post data from Liquid and inject as JSON. The map JS reads
  this and draws the pins. Putting the data in the page (rather than fetching
  it separately) means everything renders instantly with no extra request.
-->
<script>
  window.TRAVEL_DATA = [
  {%- if site.trips and site.trips.size > 0 -%}
  {%- assign sorted = site.trips | sort: "start_date" -%}
  {%- for trip in sorted -%}
    {%- assign trip_posts = site.categories[trip.slug] | sort: "order" -%}
    {
      "slug":  {{ trip.slug | jsonify }},
      "name":  {{ trip.title | jsonify }},
      "lat":   {{ trip.lat | default: 0 }},
      "lng":   {{ trip.lng | default: 0 }},
      "cover": {{ trip.cover | relative_url | jsonify }},
      "url":   {{ trip.url | relative_url | jsonify }},
      "posts": [
        {%- for post in trip_posts -%}
          {%- if post.location and post.location.lat -%}
            {
              "title": {{ post.title | jsonify }},
              "name":  {{ post.location.name | jsonify }},
              "lat":   {{ post.location.lat }},
              "lng":   {{ post.location.lng }},
              "url":   {{ post.url | relative_url | jsonify }}
            }{%- unless forloop.last -%},{%- endunless -%}
          {%- endif -%}
        {%- endfor -%}
      ]
    }{%- unless forloop.last -%},{%- endunless -%}
  {%- endfor -%}
  {%- endif -%}
  ];
</script>

<script src="{{ '/assets/js/maps.js' | relative_url }}"></script>
<script>
  // Fire after Leaflet, maps.js, and the data are all on the page.
  TravelMap.initWorld("world-map", window.TRAVEL_DATA);
</script>
