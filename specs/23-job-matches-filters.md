# 23 — Job matches filters: one connected bar, freshness and live filtering

**Status:** DONE

## 1. Problem

1. *Freshness (days)* lives only in Settings (`search.max_age_days`, `search.max_age_days_ats`): it decides what the **search** keeps. In *Job matches* there is no way to say "show me only what was posted this week" without changing the configuration and re-filtering.
2. The filter bar needs a **Filter** button: pick a source, press the button, wait for a page reload. It should react as you choose.

## 2. Design

### 2.1 Freshness filter in Job matches
- New control **Posted** next to the other filters: *Any date*, *last 1 / 3 / 7 / 14 / 30 / 60 / 90 days*. The value the person configured as their rule (`search.max_age_days`, default 30) is added to the list if missing and marked **(your rule)**, so the relation with Settings is visible.
- Query parameter `fresh=<days>` (positive integer up to 3650; anything else is ignored). It is a **view filter**: it never changes the stored data or the configuration, and it combines with every other filter and tab.
- A posting matches when its `posted_at` is within the window **or it has no date** (many company-board postings have none and a still-listed posting is open; hiding them would hide good postings). The control's help text says so.
- Settings keeps *Freshness (days)* as the ingestion rule and gets a hint pointing to the new filter ("you can also narrow what you see in Job matches").
- The Top matches board is shown only when no filter is active; `fresh` counts as a filter (like search or source).

### 2.2 Live filtering
- Choosing a source, work mode, favorites, sort or freshness applies **immediately**; typing in search or minimum score applies after a short pause (300 ms). The **Filter** button is removed (kept only inside `<noscript>` so the page still works without JavaScript).
- No full page reload: the script requests the same `/jobs?...` URL, replaces the results area (board, count, list, pager) and updates the address with `history.replaceState`, so the URL stays shareable and the Back button is not flooded. A newer request cancels an older one; typing never loses focus; if the request fails the script falls back to a normal navigation.
- Tabs, filters and the page header never move.
- Nothing new is stored and nothing is written: it only reads.

### 2.3 One connected filter bar (redesign after the first version)
The first version left seven loose controls (a search box, three dropdowns that only said "Any ...", a number box and a button) that looked unrelated, and a changed script could be served from the browser cache so the new behaviour looked dead. The bar was redesigned:
- **One rounded bar** holds everything. Every dropdown carries its **name inside the control** (`SOURCE`, `POSTED`, `SCORE`, `MODE`, `SORT`), so "Any" is never ambiguous; a control that narrows the list turns orange. The search box has an icon and is the widest item; *Favorites* is a toggle chip; *Sort* sits at the right.
- **Score is a choice**, not a number box: *Any, 50+, 60+, 70+, 75+ (your threshold), 80+, 90+*. It is hidden on *Filtered out*, which has no scores. *Mode* stays but is secondary (most people only want remote).
- **Showing only:** under the bar, every active filter appears as a removable chip (`✕`) with **Clear all**, followed by the count. Removing a chip clears its control and refreshes at once.
- **Static files are versioned** (`/static/app.js?v=<mtime>`), so a changed script or stylesheet is never taken from the cache.

## 3. Principles and safety
Read-only GET requests under the existing Host/Origin rules; the filter value is parsed as an integer and passed as a SQL parameter; no new dependency (vanilla JS, no build).

## 4. Tests
- `fresh` keeps recent and undated postings and drops older ones; invalid values are ignored; it combines with status, source and search; it turns the Top board off.
- The configured rule appears in the options marked *(your rule)*, with no duplicate when it equals a standard option.
- The page has no **Filter** button (only inside `noscript`), has the results container the script updates, and the script wires `change` and debounced `input`.
- Settings shows the hint.

## 5. Tasks
- [x] Spec.
- [x] `fresh` filter in `/jobs`, the **Posted** control and the *(your rule)* option.
- [x] Live filtering script and removal of the Filter button; results container.
- [x] Settings hint; tests (`tests/test_web.py`); README (Job matches) and this spec marked done.

## 6. Acceptance criteria
- [x] "Last 7 days" shows (`test_fresh_filter_keeps_recent_and_undated_postings_and_drops_older_ones`) only postings posted in the last 7 days (plus undated ones) on any tab.
- [x] Changing any filter updates the list without pressing a button or reloading the page, and the URL reflects it.
- [x] Typing in search keeps focus and does not fire a request per keystroke.

## 7. Verification

First version, checked in a real browser on the demo workspace: choosing a source, then *last 1 day*, then typing "back" updated the list without reloading the page (a marker set on `window` survived), the address changed to `?status=all&q=back&source=ashby&fresh=1&sort=score`, the burst of four keystrokes produced **one** request, the search field kept focus, and there was no submit button.

Redesigned bar, checked in a real browser against a copy of the author's real database (28,000 postings): choosing *Source: Greenhouse* gave 17 cards, adding *Score 75+* gave 5, adding *Posted: last 30 days* gave 1; removing the source chip and *Clear all* restored 41, each time without a page reload. This run also caught a real bug (the script still looked for the old form class, so nothing updated); `test_filters_form_one_connected_bar_that_applies_live` now asserts the script targets `form.filterbar`.
