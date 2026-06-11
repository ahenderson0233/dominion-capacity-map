# Dominion Hosting Capacity & Siting Dashboard

Interactive map for screening large-load + battery-storage (BESS) and PV sites across
**Dominion Energy's Virginia and North Carolina service territories**. It overlays Dominion's
published PV/BESS (generation) and EV (load) hosting-capacity feeders, substations
(utility CSV + OpenStreetMap, deduped), and transmission lines, and scores candidate parcels
(e.g. public schools) against user-defined capacity, substation, and transmission criteria.

The Dominion counterpart to the ComEd/Ameren Illinois dashboard
(https://ahenderson0233.github.io/comed-capacity-map/).

**Live site:** `https://<your-username>.github.io/dominion-capacity-map/` (after the deploy below)

---

## What's in this repo

| File | Required? | Purpose |
|------|-----------|---------|
| `index.html` | ✅ | The dashboard application |
| `dominion_territory.js` | ✅ | VA + NC service-territory boundary (clips substations & schools) |
| `dominion_transmission.js` | ✅ | All in-service transmission lines in VA + NC, by kV class |
| `dominion_substations.js` | ✅ | Substation point layer (utility CSV + OSM, deduped) — loads via `<script>` |
| `dominion_substations.json` | optional | Same substation data as JSON (fetch fallback) |
| `xlsx.full.min.js` | ✅ | SheetJS — needed to *read* uploaded spreadsheets (Excel **export** is dependency-free) |
| `footprint-proxy.worker.js` | optional | Cloudflare Worker source for the parcel/footprint proxy (see below) |
| `.gitignore`, `README.md` | — | Repo housekeeping |

The ArcGIS Maps SDK and the live Dominion capacity layers load from the internet, so the page
needs a connection. Everything else is in the repo.

---

## Deploy to GitHub Pages (same process as the Illinois tool)

1. **Create the repository.** On github.com → **New repository**. Name it
   `dominion-capacity-map`, set it **Public**, and click **Create repository**.
2. **Upload the files.** On the repo page click **Add file → Upload files**, then drag in
   **all** the files from this folder (`index.html`, the four data/library `.js` files,
   `dominion_substations.json`, `footprint-proxy.worker.js`, `README.md`, `.gitignore`).
   Wait for the large files (`dominion_transmission.js` ≈ 4 MB, `dominion_substations.js` ≈ 2 MB)
   to finish, then **Commit changes**.
3. **Turn on Pages.** Repo **Settings → Pages**. Under *Build and deployment*, Source =
   **Deploy from a branch**, Branch = **main**, folder = **/ (root)**, then **Save**.
4. **Wait ~1 minute**, refresh the Pages settings page, and open the published URL:
   `https://<your-username>.github.io/dominion-capacity-map/`.

To update later: **Add file → Upload files** (overwrite) or push commits; Pages redeploys
automatically in a minute or so.

Everything works on Pages out of the box **except** the Footprint parcel lookups — see next.

---

## Footprint / parcel lookups (Cloudflare Worker)

The Footprint tab pulls parcels from VGIN (VA) and NC OneMap (NC). Browsers block those
cross-origin requests on a static site, so a tiny proxy is required (this is the same
limitation the Illinois tool documents).

1. Sign in at **dash.cloudflare.com → Workers & Pages → Create → Worker**.
2. Replace the worker code with the contents of `footprint-proxy.worker.js`, **Deploy**.
3. Copy the worker URL (e.g. `https://dominion-proxy.<account>.workers.dev`).
4. In the dashboard, open **Footprint → Advanced: where parcel data comes from** and paste the
   worker URL into the proxy-base box.

Without this, the map, capacity layers, substations, transmission, Find, Site Analysis, and all
Excel/CSV exports still work — only the footprint parcel areas fall back to "no parcel found".

(For local use instead of a worker, run `server.py` from the project's working folder and open
`http://localhost:8000`; leave the proxy-base box empty.)

---

## Features

- **Layers** — PV/BESS, EV load, or combined (averaged) capacity; substations with class filter,
  min-kV filter, live per-class legend counts, and Excel export; transmission lines filterable by
  kV class; service-territory outline; NCES schools; satellite basemap toggle.
- **Find** — minimum gen/load MW, voltage floor, optional radius, dual-use eligibility distance,
  and optional substation / transmission eligibility (with a kV-class dropdown). **Run Find**
  highlights matching feeders and scores every loaded site in one step.
- **Sites** — add by coordinates, map click, address search, or current location; upload Excel/CSV
  (each sheet becomes a colored layer; address-only rows are geocoded); per-site breakdown; sort
  by generation/load/name; coordinate-capture log (CSV); Excel + `.json` export. The site-analysis
  Excel export contains exactly the sites matching the current Find parameters.
- **Footprint** — lot area (geometry + assessor), building area (USA Structures), outdoor area, with
  review flags and a dedicated Excel export; click a site name to zoom and open its popup.
- **Save standalone (.html)** — self-contained offline copy with all data embedded.

---

## Data sources & disclaimer

Capacity feeders/voltages: Dominion public Experience Builder hosting-capacity services.
Substations: utility dataset + OpenStreetMap (`power=substation`), deduped at 200 m.
Transmission: HIFLD/utility datasets. Parcels: VGIN + NC OneMap. Buildings: Esri USA Structures.
Schools: NCES public school locations.

All capacity, footprint, and proximity figures are **modeled estimates for screening only** and
must be independently verified before any siting, interconnection, or investment decision. Site
scoring is intentionally not included — ranking is left to the user's own validation methodology.
