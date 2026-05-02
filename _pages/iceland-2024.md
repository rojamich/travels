---
# =============================================================================
# TRIP PAGE — Iceland 2024
# =============================================================================
# This is the "table of contents" for one trip. It lists every post in this
# trip in the order you choose (via the `order:` field in each post).
#
# To create a new trip page:
#   1. Copy this file and rename it to match your trip slug
#      e.g. _pages/japan-2025.md
#   2. Change `permalink` and `trip_slug` to match the new slug
#   3. Update the title and the intro paragraph
#   4. Make sure trips.yml has a matching entry
# =============================================================================

title: "Iceland 2024"
permalink: /iceland-2024/
layout: single
author_profile: false
classes: wide

# `trip_slug` is what links this page to its posts. It must match:
#   - the `slug` in _data/trips.yml
#   - the category used in each post's front matter
trip_slug: iceland-2024
---

<!--
  Pull the full trip record from _data/trips.yml using the slug above.
  This gives us access to dates, location, description, etc.
-->
{% assign trip = site.data.trips | where: "slug", page.trip_slug | first %}

<p style="color:#888; font-size:0.95em;">
  {{ trip.location }} &middot;
  {{ trip.start_date | date: "%B %-d, %Y" }} &mdash;
  {{ trip.end_date | date: "%B %-d, %Y" }}
</p>

<p style="font-size:1.1em;">{{ trip.description }}</p>

<hr>

<!--
  Get all posts in this trip's category and sort by the manual `order:` field
  in each post's front matter. That gives the wife full control over sequence
  regardless of when each was actually written.
-->
{% assign trip_posts = site.categories[page.trip_slug] | sort: "order" %}

{% if trip_posts.size == 0 %}
  <p><em>No posts yet for this trip. Check back soon!</em></p>
{% else %}
  <div class="day-list">
    {% for post in trip_posts %}
      <a href="{{ post.url | relative_url }}" class="day-card">
        <div class="day-card-image">
          {% if post.header.teaser %}
            <img src="{{ post.header.teaser | relative_url }}"
                 alt="{{ post.title }}"
                 onerror="this.style.display='none'">
          {% endif %}
        </div>
        <div class="day-card-body">
          <h3>{{ post.title }}</h3>
          <p style="color:#888; margin:0 0 0.5em 0;">
            {{ post.date | date: "%A, %B %-d, %Y" }}
          </p>
          {% if post.excerpt %}
            <p>{{ post.excerpt | strip_html | truncate: 200 }}</p>
          {% endif %}
        </div>
      </a>
    {% endfor %}
  </div>
{% endif %}

<style>
  .day-list {
    display: flex;
    flex-direction: column;
    gap: 1em;
    margin: 1.5em 0;
  }
  .day-card {
    display: flex;
    text-decoration: none !important;
    color: inherit !important;
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .day-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.10);
  }
  .day-card-image {
    flex: 0 0 200px;
    height: 140px;
    background: #f0f0f0;
  }
  .day-card-image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .day-card-body {
    padding: 1em;
    flex: 1;
  }
  .day-card-body h3 {
    margin: 0 0 0.3em 0;
  }
  @media (max-width: 600px) {
    .day-card { flex-direction: column; }
    .day-card-image { flex: none; width: 100%; height: 200px; }
  }
</style>
