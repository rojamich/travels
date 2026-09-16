/* =============================================================================
   sort-filter.js — sort & tag-filter for trip lists
   =============================================================================

   USAGE
   -----
   The page should contain:
     1. A container element with class `js-trip-list` whose direct children
        are the cards to sort/filter.
     2. Each card has these data attributes:
          data-name="Iceland 2024"           (string, for alphabetical sort)
          data-location="Iceland"            (string, for location sort)
          data-start-date="2024-06-01"       (ISO date, for date sort)
          data-tags="Europe|Road Trip|South Africa" (pipe-separated, for filter)
     3. A controls container with class `js-controls` where the script will
        inject the sort dropdown and tag chips.

   The script auto-initializes on DOMContentLoaded. No setup call needed.
============================================================================= */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Initialize every sort/filter setup on the page.
  // (We support multiple lists per page in case we ever want them.)
  // ---------------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".js-controls").forEach(function (controls) {
      var listSelector = controls.dataset.listSelector || ".js-trip-list";
      var list = document.querySelector(listSelector);
      if (!list) return;
      setupControls(controls, list);
    });
  });

  // ---------------------------------------------------------------------------
  // THE DAY INDEX — which post inside each trip carries which tags.
  //
  // Rendered by _includes/trip-post-index.html and keyed by the same trip slug
  // the cards are stamped with. Read once and kept: both lists on a page share
  // the parse. Absent on pages that don't include it (the day list inside a
  // trip), where the drill-down simply doesn't appear.
  // ---------------------------------------------------------------------------
  var dayIndexCache = null;
  function dayIndex() {
    if (dayIndexCache) { return dayIndexCache; }
    dayIndexCache = {};
    var el = document.getElementById("trip-posts");
    if (el) {
      try { dayIndexCache = JSON.parse(el.textContent) || {}; } catch (e) { /* leave empty */ }
    }
    return dayIndexCache;
  }

  // "2024-09-12" -> "12 Sep 2024". Split by hand rather than `new Date(iso)`:
  // a bare ISO date parses as UTC, which renders the day before anywhere west
  // of Greenwich — including every timezone this blog is read from.
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function formatDay(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) { return ""; }
    return parseInt(m[3], 10) + " " + MONTHS[parseInt(m[2], 10) - 1] + " " + m[1];
  }

  // ---------------------------------------------------------------------------
  // Build the sort dropdown + tag chips inside `controls`, and wire them up
  // to filter/sort children of `list`.
  // ---------------------------------------------------------------------------
  function setupControls(controls, list) {
    var cards = Array.from(list.children);
    if (cards.length === 0) return;

    // ----- SORT DROPDOWN -----
    // Options can be configured per-controls via data-sort-options attribute:
    //   <div class="js-controls" data-sort-options="order,oldest,recent,name">
    // The first value in the list becomes the default sort on load.
    var SORT_LABELS = {
      order:    "Day order",
      recent:   "Most recent",
      oldest:   "Oldest first",
      location: "By location (A–Z)",
      name:     "By title (A–Z)"
    };
    var sortOptions = (controls.dataset.sortOptions || "recent,oldest,location,name")
      .split(",")
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return SORT_LABELS[s]; });
    var optionsHtml = sortOptions.map(function (opt) {
      return '<option value="' + opt + '">' + SORT_LABELS[opt] + '</option>';
    }).join("");

    var sortWrap = document.createElement("div");
    // Same flex-row treatment as .tag-filter. Without it this div is a plain
    // block, so its label sat ABOVE the select while "Filter:" sat beside its
    // button, and the two controls read as different shapes.
    sortWrap.className = "sort-filter";
    sortWrap.innerHTML =
      '<label for="sort-select">Sort:</label>' +
      '<select id="sort-select">' + optionsHtml + "</select>";
    controls.appendChild(sortWrap);

    // ----- TAG FILTER -----
    // A dropdown rather than a row of chips. There are around 140 distinct
    // tags, so one chip each filled the whole control bar and buried the sort
    // dropdown. A dropdown keeps the bar one line high however many tags
    // exist.
    //
    //   [ Tags v ]  <- opens a scrolling checkbox list with a search box
    //   selections appear beside it as chips, each with its own x
    //
    // Ticking boxes does NOT filter as you go; the panel has a Filter button.
    // Choosing four tags one at a time would otherwise re-filter four times
    // and make the list jump under the cursor. Removing a chip DOES apply
    // immediately, because that is one deliberate action with an obvious result.
    //
    // data-tags is PIPE-separated, not space-separated. Plenty of tags are two
    // words — South Africa, North Island, New York — and so are the city names
    // the day lists filter by. Splitting on whitespace tore each of those into
    // halves that matched no card, and any half that happened to spell a real
    // tag ("Africa" out of "South Africa") had its count inflated by cards
    // that were never tagged with it.
    function tagsOf(card) {
      return (card.dataset.tags || "").split("|")
        .map(function (t) { return t.trim(); })
        .filter(function (t) { return t.length > 0; });
    }

    var allTags = new Set();
    var tagCounts = {};
    cards.forEach(function (card) {
      // Within one card a tag counts once, however many of its posts carry it.
      new Set(tagsOf(card)).forEach(function (t) {
        allTags.add(t);
        tagCounts[t] = (tagCounts[t] || 0) + 1;
      });
    });

    // Most-used first, alphabetical within a count. The tags worth filtering
    // by are the ones on many cards; most of the long tail is on exactly one.
    var sortedTags = Array.from(allTags).sort(function (a, b) {
      var d = tagCounts[b] - tagCounts[a];
      return d !== 0 ? d : a.localeCompare(b);
    });

    var activeTags = new Set();   // applied
    var draftTags = new Set();    // ticked in the panel, not yet applied

    var tagWrap = document.createElement("div");
    tagWrap.className = "tag-filter";

    var tagLabel = document.createElement("label");
    tagLabel.textContent = "Filter:";
    tagWrap.appendChild(tagLabel);

    var dd = document.createElement("div");
    dd.className = "tag-dd";

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "tag-dd-toggle";
    toggle.setAttribute("aria-expanded", "false");
    dd.appendChild(toggle);

    var panel = document.createElement("div");
    panel.className = "tag-dd-panel";
    panel.hidden = true;
    panel.innerHTML =
      '<div class="tag-dd-search">' +
      '<input type="search" placeholder="Search tags..." aria-label="Search tags">' +
      "</div>" +
      '<div class="tag-dd-list" role="group" aria-label="Tags"></div>' +
      '<div class="tag-dd-actions">' +
      '<button type="button" class="tag-dd-clear">Clear</button>' +
      '<button type="button" class="tag-dd-apply">Filter</button>' +
      "</div>";
    dd.appendChild(panel);
    tagWrap.appendChild(dd);

    var listEl = panel.querySelector(".tag-dd-list");
    var searchEl = panel.querySelector(".tag-dd-search input");
    var applyBtn = panel.querySelector(".tag-dd-apply");
    var panelClear = panel.querySelector(".tag-dd-clear");

    var rows = {};
    sortedTags.forEach(function (tag) {
      var row = document.createElement("label");
      row.className = "tag-dd-row";

      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = tag;
      cb.addEventListener("change", function () {
        if (cb.checked) { draftTags.add(tag); } else { draftTags.delete(tag); }
        syncApplyLabel();
      });

      var name = document.createElement("span");
      name.className = "tag-dd-name";
      name.textContent = tag;

      var count = document.createElement("span");
      count.className = "tag-dd-count";
      count.textContent = tagCounts[tag];

      row.appendChild(cb);
      row.appendChild(name);
      row.appendChild(count);
      listEl.appendChild(row);
      rows[tag] = { row: row, cb: cb };
    });

    var noMatch = document.createElement("p");
    noMatch.className = "tag-dd-none";
    noMatch.textContent = "No tags match.";
    noMatch.hidden = true;
    listEl.appendChild(noMatch);

    searchEl.addEventListener("input", function () {
      var q = searchEl.value.trim().toLowerCase();
      var shown = 0;
      sortedTags.forEach(function (tag) {
        var hit = !q || tag.toLowerCase().indexOf(q) !== -1;
        rows[tag].row.hidden = !hit;
        if (hit) { shown++; }
      });
      noMatch.hidden = shown > 0;
    });

    function syncApplyLabel() {
      applyBtn.textContent =
        draftTags.size > 0 ? "Filter (" + draftTags.size + ")" : "Filter";
    }

    // ----- applied filters, shown as removable chips -----
    var chipsWrap = document.createElement("div");
    chipsWrap.className = "tag-selected";
    tagWrap.appendChild(chipsWrap);

    function renderChips() {
      chipsWrap.innerHTML = "";
      if (activeTags.size === 0) { return; }

      Array.from(activeTags).sort().forEach(function (tag) {
        var chip = document.createElement("span");
        chip.className = "tag-chip is-active";

        var text = document.createElement("span");
        text.textContent = tag;
        chip.appendChild(text);

        var x = document.createElement("button");
        x.type = "button";
        x.className = "tag-chip-x";
        x.setAttribute("aria-label", "Remove " + tag + " filter");
        x.innerHTML = "&times;";
        x.addEventListener("click", function () {
          activeTags.delete(tag);
          draftTags.delete(tag);
          if (rows[tag]) { rows[tag].cb.checked = false; }
          syncApplyLabel();
          syncToggle();
          renderChips();
          applyFilter();
        });
        chip.appendChild(x);
        chipsWrap.appendChild(chip);
      });

      if (activeTags.size > 1) {
        var all = document.createElement("button");
        all.type = "button";
        all.className = "tag-clear";
        all.textContent = "Clear all";
        all.addEventListener("click", function () {
          activeTags.clear();
          draftTags.clear();
          Object.keys(rows).forEach(function (t) { rows[t].cb.checked = false; });
          syncApplyLabel();
          syncToggle();
          renderChips();
          applyFilter();
        });
        chipsWrap.appendChild(all);
      }
    }

    function syncToggle() {
      toggle.textContent =
        activeTags.size > 0 ? "Tags (" + activeTags.size + ")" : "Tags";
      toggle.classList.toggle("has-active", activeTags.size > 0);
    }

    // The panel always opens showing what is currently applied, so it reflects
    // reality rather than whatever was last ticked and then abandoned.
    function openPanel() {
      draftTags = new Set(activeTags);
      Object.keys(rows).forEach(function (t) {
        rows[t].cb.checked = draftTags.has(t);
      });
      syncApplyLabel();
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      searchEl.focus();
    }

    function closePanel() {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    }

    toggle.addEventListener("click", function () {
      if (panel.hidden) { openPanel(); } else { closePanel(); }
    });

    applyBtn.addEventListener("click", function () {
      activeTags = new Set(draftTags);
      syncToggle();
      renderChips();
      applyFilter();
      closePanel();
      toggle.focus();
    });

    panelClear.addEventListener("click", function () {
      draftTags.clear();
      Object.keys(rows).forEach(function (t) { rows[t].cb.checked = false; });
      searchEl.value = "";
      searchEl.dispatchEvent(new Event("input"));
      syncApplyLabel();
    });

    // Clicking away closes without applying — which is what a half-finished
    // selection deserves. Escape does the same and hands focus back.
    document.addEventListener("click", function (ev) {
      if (!panel.hidden && !dd.contains(ev.target)) { closePanel(); }
    });
    dd.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !panel.hidden) {
        closePanel();
        toggle.focus();
      }
    });

    syncToggle();
    controls.appendChild(tagWrap);

    // ---------------------------------------------------------------------------
    // FILTER LOGIC — show/hide cards based on activeTags.
    //
    // AND semantics: a card must carry EVERY active tag, not just one of them.
    // Picking Food and Hiking asks for trips that were both, which is the
    // question worth asking; OR just returned the union and adding a second
    // tag made the list longer, which is the opposite of filtering.
    //
    // No active tags = show all. An empty state appears when nothing matches,
    // which matters more with AND — narrow combinations legitimately return
    // nothing, and silence would look like a broken page.
    // ---------------------------------------------------------------------------
    var emptyMsg = document.createElement("p");
    emptyMsg.className = "empty-state";
    emptyMsg.textContent = "Nothing matches all of those tags together \u2014 " +
      "try removing one.";
    emptyMsg.style.display = "none";
    list.parentNode.insertBefore(emptyMsg, list.nextSibling);

    // ----- WHICH DAYS MATCHED -----
    // A trip card can match on a tag that appears nowhere on the card, because
    // the tag was written on one day post out of ninety-five. Saying "this trip
    // has a bird post in it somewhere" and stopping there just moves the search
    // rather than ending it, so each matching card names the days and links
    // straight to them.
    //
    // Only while a filter is on: with nothing ticked there is no question to
    // answer, and every card would carry a list of its entire contents.
    //
    // A card stops after this many days and offers the rest behind a click.
    // Filtering by Food matches fifteen days of the European Exploration, and
    // a card taller than the screen is worse than no list at all.
    var MATCH_CAP = 6;

    function renderMatches(card, active) {
      var existing = card.querySelector(".trip-card-matches");
      if (existing) { existing.parentNode.removeChild(existing); }
      if (active.length === 0) { return; }

      // A trip with no posts written yet has no days to point at and nothing
      // to explain — the card is the whole answer, so leave it alone.
      var posts = dayIndex()[card.dataset.slug] || [];
      if (posts.length === 0) { return; }

      // Same AND rule the cards themselves are filtered by, so the list can
      // never claim a day that would not have matched on its own.
      var hits = posts.filter(function (p) {
        return active.every(function (t) { return p.g.indexOf(t) !== -1; });
      });

      var box = document.createElement("div");
      box.className = "trip-card-matches";

      // The card is here on the strength of its own front-matter tags, or on
      // two tags that no single day carries between them. Say which, rather
      // than leave an empty panel that reads like a bug.
      if (hits.length === 0) {
        var note = document.createElement("p");
        note.className = "trip-card-matches-note";
        note.textContent = active.length === 1
          ? "Tagged on the trip itself, not on any one day."
          : "No single day has all of these — the trip does.";
        box.appendChild(note);
        card.appendChild(box);
        return;
      }

      var head = document.createElement("p");
      head.className = "trip-card-matches-head";
      head.textContent = hits.length + (hits.length === 1 ? " day" : " days") +
        " tagged " + active.join(" + ");
      box.appendChild(head);

      var ul = document.createElement("ul");
      hits.forEach(function (p, i) {
        var li = document.createElement("li");
        if (i >= MATCH_CAP) {
          li.className = "is-overflow";
          li.hidden = true;
        }

        var link = document.createElement("a");
        link.href = p.u;
        link.textContent = p.t;
        li.appendChild(link);

        var when = document.createElement("span");
        when.className = "trip-card-matches-date";
        when.textContent = formatDay(p.d);
        li.appendChild(when);

        ul.appendChild(li);
      });
      box.appendChild(ul);

      if (hits.length > MATCH_CAP) {
        var more = document.createElement("button");
        more.type = "button";
        more.className = "trip-card-matches-more";
        more.textContent = "Show " + (hits.length - MATCH_CAP) + " more";
        more.addEventListener("click", function () {
          ul.querySelectorAll("li.is-overflow").forEach(function (li) {
            li.hidden = false;
          });
          more.parentNode.removeChild(more);
        });
        box.appendChild(more);
      }

      card.appendChild(box);
    }

    function applyFilter() {
      var active = Array.from(activeTags);
      var visibleCount = 0;
      cards.forEach(function (card) {
        var cardTags = tagsOf(card);
        var match = active.length === 0 ||
          active.every(function (t) {
            return cardTags.indexOf(t) !== -1;
          });
        card.style.display = match ? "" : "none";
        if (match) { visibleCount++; }
        // Hidden cards get their list cleared, so a card coming back under a
        // different filter never shows the previous filter's days.
        renderMatches(card, match ? active : []);
      });
      emptyMsg.style.display = visibleCount === 0 ? "" : "none";
    }

    // ---------------------------------------------------------------------------
    // SORT LOGIC — re-order cards by setting CSS `order:` on each.
    // Works with both flex and grid layouts that respect `order`.
    // For plain block lists, we re-append in order instead.
    // ---------------------------------------------------------------------------
    var sortSelect = sortWrap.querySelector("select");
    sortSelect.addEventListener("change", function () {
      applySort(sortSelect.value);
    });

    function applySort(mode) {
      var sorted = cards.slice();   // copy so we don't mutate the original
      sorted.sort(function (a, b) {
        switch (mode) {
          case "order":
            // parseFloat, not parseInt: posts from the same day are numbered
            // 15.1 / 15.2, and parseInt would flatten both to 15 and leave
            // their order to chance.
            return (parseFloat(a.dataset.order || 999) -
                    parseFloat(b.dataset.order || 999));
          case "oldest":
            return cmpDate(a, b);
          case "location":
            return cmpStr(a.dataset.location, b.dataset.location);
          case "name":
            return cmpStr(a.dataset.name, b.dataset.name);
          case "recent":
          default:
            return cmpDate(b, a);     // reversed for desc
        }
      });
      // Re-append in the new order. The browser keeps existing event
      // listeners and styles intact when you move a node like this.
      sorted.forEach(function (card) {
        list.appendChild(card);
      });
    }

    function cmpDate(a, b) {
      return new Date(a.dataset.startDate) - new Date(b.dataset.startDate);
    }
    function cmpStr(a, b) {
      return (a || "").localeCompare(b || "", undefined, { sensitivity: "base" });
    }

    // Apply default sort on load — the first option from the configured list,
    // so order is deterministic regardless of how Liquid produced the markup.
    applySort(sortOptions[0] || "recent");
  }
})();
