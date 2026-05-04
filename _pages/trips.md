---
# =============================================================================
# /trips/ — full list of all trips, with sort + tag filter
# =============================================================================
# Same sort/filter widget as the homepage, but with a slightly different
# presentation (vertical list instead of grid).
# =============================================================================

title: "All Trips"
permalink: /trips/
layout: single
author_profile: false
classes: wide
---

<div class="js-controls controls" data-list-selector=".js-trip-list"></div>

{% if site.trips and site.trips.size > 0 %}
  {% assign sorted_trips = site.trips | sort: "start_date" | reverse %}
{% else %}
  {% assign sorted_trips = "" | split: "" %}
{% endif %}

<div class="js-trip-list">
  {% for trip in sorted_trips %}
    <article class="trip-card trip-list-row"
             data-name="{{ trip.title }}"
             data-location="{{ trip.location }}"
             data-start-date="{{ trip.start_date | date: '%Y-%m-%d' }}"
             data-tags="{% if trip.tags %}{{ trip.tags | join: ' ' }}{% endif %}">
      <h2 style="margin-bottom:0.2em;">
        <a href="{{ trip.url | relative_url }}">{{ trip.title }}</a>
      </h2>
      <p class="trip-card-meta">
        {{ trip.location }} &middot;
        {{ trip.start_date | date: "%B %-d, %Y" }} &mdash;
        {{ trip.end_date | date: "%B %-d, %Y" }}
      </p>
      <p>{{ trip.description }}</p>
      {% if trip.tags %}
        <p style="margin:0.4em 0 0;">
          {% for tag in trip.tags %}
            <span class="tag-chip" style="cursor:default;">{{ tag }}</span>
          {% endfor %}
        </p>
      {% endif %}
    </article>
  {% endfor %}
</div>

<style>
  .trip-list-row {
    padding: 1.2em 1.4em;
    margin-bottom: 1em;
  }
  .trip-list-row h2 a {
    text-decoration: none;
  }
</style>

<script src="{{ '/assets/js/sort-filter.js' | relative_url }}"></script>
