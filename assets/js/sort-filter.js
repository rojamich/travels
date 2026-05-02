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
          data-tags="europe road-trip nature" (space-separated, for filter)
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
  // Build the sort dropdown + tag chips inside `controls`, and wire them up
  // to filter/sort children of `list`.
  // ---------------------------------------------------------------------------
  function setupControls(controls, list) {
    var cards = Array.from(list.children);
    if (cards.length === 0) return;

    // ----- SORT DROPDOWN -----
    var sortWrap = document.createElement("div");
    sortWrap.innerHTML =
      '<label for="sort-select">Sort:</label>' +
      '<select id="sort-select">' +
        '<option value="recent">Most recent</option>' +
        '<option value="oldest">Oldest first</option>' +
        '<option value="location">By location (A–Z)</option>' +
        '<option value="name">By name (A–Z)</option>' +
      "</select>";
    controls.appendChild(sortWrap);

    // ----- TAG CHIPS -----
    // Collect every unique tag across all cards.
    var allTags = new Set();
    cards.forEach(function (card) {
      (card.dataset.tags || "").split(/\s+/).forEach(function (t) {
        if (t) allTags.add(t);
      });
    });

    var tagWrap = document.createElement("div");
    tagWrap.className = "tag-filter";
    var tagLabel = document.createElement("label");
    tagLabel.textContent = "Filter:";
    tagWrap.appendChild(tagLabel);

    var activeTags = new Set();   // currently selected tag filters

    Array.from(allTags).sort().forEach(function (tag) {
      var chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.textContent = tag;
      chip.dataset.tag = tag;
      chip.addEventListener("click", function () {
        if (activeTags.has(tag)) {
          activeTags.delete(tag);
          chip.classList.remove("is-active");
        } else {
          activeTags.add(tag);
          chip.classList.add("is-active");
        }
        applyFilter();
      });
      tagWrap.appendChild(chip);
    });

    // "Clear" button — only shows when something is active.
    var clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "tag-clear";
    clearBtn.textContent = "Clear";
    clearBtn.style.display = "none";
    clearBtn.addEventListener("click", function () {
      activeTags.clear();
      tagWrap.querySelectorAll(".tag-chip.is-active").forEach(function (c) {
        c.classList.remove("is-active");
      });
      applyFilter();
    });
    tagWrap.appendChild(clearBtn);

    controls.appendChild(tagWrap);

    // ---------------------------------------------------------------------------
    // FILTER LOGIC — show/hide cards based on activeTags.
    // OR semantics: a card matches if it has ANY of the active tags.
    // No active tags = show all.
    // Also reveals an empty-state message when nothing matches.
    // ---------------------------------------------------------------------------
    var emptyMsg = document.createElement("p");
    emptyMsg.className = "empty-state";
    emptyMsg.textContent = "No trips match the selected filter.";
    emptyMsg.style.display = "none";
    list.parentNode.insertBefore(emptyMsg, list.nextSibling);

    function applyFilter() {
      var visibleCount = 0;
      cards.forEach(function (card) {
        var cardTags = (card.dataset.tags || "").split(/\s+/);
        var match = activeTags.size === 0 ||
          cardTags.some(function (t) { return activeTags.has(t); });
        card.style.display = match ? "" : "none";
        if (match) visibleCount++;
      });
      emptyMsg.style.display = visibleCount === 0 ? "" : "none";
      clearBtn.style.display = activeTags.size > 0 ? "" : "none";
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

    // Apply default sort (most recent) on load so order is deterministic
    // regardless of how Liquid produced the markup.
    applySort("recent");
  }
})();
