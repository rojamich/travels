---
# =============================================================================
# /trips/ — full list of all trips
# =============================================================================
# Same idea as the homepage but accessible from the nav at any time.
# Reads the full trip list from _data/trips.yml.
# =============================================================================

title: "All Trips"
permalink: /trips/
layout: single
author_profile: false
classes: wide
---

{% assign sorted_trips = site.data.trips | sort: "start_date" | reverse %}

{% for trip in sorted_trips %}
  <article class="trip-list-item">
    <h2>
      <a href="{{ '/' | append: trip.slug | append: '/' | relative_url }}">{{ trip.name }}</a>
    </h2>
    <p style="color:#888;">
      {{ trip.location }} &middot;
      {{ trip.start_date | date: "%B %-d, %Y" }} &mdash;
      {{ trip.end_date | date: "%B %-d, %Y" }}
    </p>
    <p>{{ trip.description }}</p>
    <hr>
  </article>
{% endfor %}
