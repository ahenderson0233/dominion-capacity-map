# Dominion Hosting Capacity & Siting Dashboard

An interactive map for screening large‑load + battery‑storage (BESS) and PV sites across
**Dominion Energy's Virginia and North Carolina service territories**, built on the ArcGIS
Maps SDK for JavaScript. It overlays Dominion's published PV/BESS (generation) and EV (load)
hosting‑capacity feeders, substations, and transmission lines, and scores candidate parcels
(e.g. public schools) against user‑defined capacity, substation, and transmission criteria.

This is the Dominion counterpart to the ComEd/Ameren Illinois dashboard.

---

## Required files (must sit in the same folder)

The dashboard loads its data from files next to `index.html`. All four must be present:

| File | Purpose |
|------|---------|
| `index.html` | The dashboard application |
| `dominion_territory.js` | VA + NC service‑territory boundary (used to clip substations & schools) |
| `dominion_transmission.js` | All in‑service transmission lines in VA + NC, by kV class |
| `dominion_substations.js` | Substation point layer (CSV + OSM, deduped) — loads via `<script src>` so it works offline / in preview |
| `dominion_substations.json` | Same substation data as JSON (fetch fallback; safe to keep for reference) |
| `xlsx.full.min.js` | SheetJS offline fallback for Excel/CSV export |

The ArcGIS SDK 4.29 and the live capacity layers load from the internet, so an internet
connection is required. SheetJS loads from jsdelivr (the same source the Illinois tool uses),
with the local `xlsx.full.min.js` as an offline/firewall fallback.

---

## Running it

**Locally:** open `index.html` in a browser. The map, capacity layers, substations, transmission,
schools, Find/Sites analysis, and Excel/CSV exports all work directly.

**Footprint (parcel) lookups need a proxy.** The Footprint tab pulls parcels from VGIN (VA) and
NC OneMap (NC). Browsers block many of those cross‑origin requests when the page is opened as a
file or hosted statically. Two options:

1. **Local Python server** — run `python server.py` and open the dashboard through it. The
   included `/gis` proxy forwards parcel/building requests. Leave the Footprint → *Advanced*
   "proxy base" box empty.
2. **Static hosting (GitHub Pages):** deploy the included `footprint-proxy.worker.js` as a
   Cloudflare Worker and paste its URL into the Footprint → *Advanced* "proxy base" box.
   Without this, footprint falls back to building‑only and flags the row.

Everything **except** the footprint parcel lookups works on GitHub Pages with no proxy.

---

## Features

- **Layers** — PV/BESS, EV load, or combined (averaged) capacity; substations with class +
  min‑kV filter and Excel export; transmission lines filterable by kV class; service‑territory
  outline; NCES schools; satellite basemap toggle. Capacity line width scales with zoom so dense
  feeders stay legible.
- **Find** — minimum gen/load MW, voltage floor, optional search radius, dual‑use eligibility
  distance, and optional **substation** / **transmission** eligibility (with a kV‑class dropdown).
  **Run Find** highlights matching feeders *and* scores every loaded site in one step.
- **Sites** — add by coordinates, map click, address search, or current location; upload Excel/CSV
  (each sheet becomes its own colored layer; address‑only rows are geocoded); per‑site breakdown
  (feeders + sum gen/load at 0.1/0.3/0.5 mi, qualifying feeders, nearest substation & transmission);
  sort by generation/load/name; coordinate‑capture log with CSV export; Excel + `.json` export.
- **Footprint** — lot area (geometry‑computed **and** assessor‑recorded), building area
  (USA Structures), and outdoor area for every site, with a results table, review flags, and a
  dedicated Excel export. Click a site name to zoom and open its popup.
- **Save standalone (.html)** — exports a single self‑contained copy of the dashboard with the
  territory, transmission, substation, and site data embedded, so it opens from any folder without
  the sibling files (still needs internet for the SDK, basemap, and live capacity layers).

---

## Data sources & disclaimer

Capacity feeders and operating voltages come from Dominion's public Experience Builder hosting‑
capacity services; substations and transmission lines from HIFLD/utility datasets; parcels from
VGIN and NC OneMap; building footprints from Esri's USA Structures; schools from the NCES public
school locations service.

All capacity, footprint, and proximity figures are **modeled estimates for screening only** and
must be independently verified before any siting, interconnection, or investment decision.
Site scoring is intentionally **not** included — ranking is left to the user's own validation
methodology.
