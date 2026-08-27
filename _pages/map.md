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

{% include page-quote.html
   text="…no place to go, and all the time in the world to get there."
   author="Lee Child, Jack Reacher" %}

<p>Click on any pin to see the route from that country's trip!</p>

<!-- Map container — Leaflet attaches the map to this div. -->
<div id="world-map" style="height: 600px; border-radius: 14px; overflow: hidden; border: 1px solid #ddd;"></div>

<!--
  Leaflet itself, plus the basemap settings from _config.yml. Both live in
  _includes/map-libs.html so the version is pinned in exactly one place —
  see the comments in that file.
-->
{% include map-libs.html %}

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
    {%- assign trip_posts = "" | split: "" -%}
    {%- if site.categories[trip.slug] -%}
      {%- assign trip_posts = site.categories[trip.slug] | sort: "order" -%}
    {%- endif -%}
    {
      "slug":  {{ trip.slug | jsonify }},
      "name":  {{ trip.title | jsonify }},
      "lat":   {{ trip.lat | default: 0 }},
      "lng":   {{ trip.lng | default: 0 }},
      "cover": {{ trip.cover | relative_url | jsonify }},
      "url":   {{ trip.url | relative_url | jsonify }},
      "postCount": {{ trip_posts | size }},
      "countries": [
        {%- assign c_first = true -%}
        {%- if trip.countries -%}
        {%- for c in trip.countries -%}
          {%- assign clat = c.lat | default: "" -%}
          {%- assign clng = c.lng | default: "" -%}
          {%- if clat != "" and clng != "" -%}
            {%- if c_first %}{% else %},{% endif -%}
            {%- assign c_first = false -%}
            { "name": {{ c.name | jsonify }}, "lat": {{ clat }}, "lng": {{ clng }} }
          {%- endif -%}
        {%- endfor -%}
        {%- endif -%}
      ],
      "posts": [
        {%- assign p_first = true -%}
        {%- for post in trip_posts -%}
          {%- assign plat = post.location.lat | default: "" -%}
          {%- assign plng = post.location.lng | default: "" -%}
          {%- if post.location and plat != "" and plng != "" -%}
            {%- if p_first %}{% else %},{% endif -%}
            {%- assign p_first = false -%}
            { "title": {{ post.title | jsonify }}, "name": {{ post.location.name | jsonify }}, "lat": {{ plat }}, "lng": {{ plng }}, "url": {{ post.url | relative_url | jsonify }} }
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
