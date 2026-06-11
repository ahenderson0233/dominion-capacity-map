#!/usr/bin/env python3
"""
osm_substations_merge.py
========================
Pull OpenStreetMap `power=substation` features across VA + NC, classify them by
voltage/type, then merge them into the dashboard's existing substation file
(`dominion_substations.json`) using a nearest-neighbor de-duplication:

  * Existing (Excel/CSV) substations are ALWAYS kept.
  * An OSM substation within DEDUPE_M meters of an existing one is treated as a
    duplicate and DROPPED.
  * Surviving OSM substations (the distribution-scale assets we don't otherwise
    have) are appended, tagged source="OSM".

Run it in the SAME folder as dominion_substations.json (e.g. your Dashboard
folder). In Jupyter:  %run osm_substations_merge.py     — or just paste & run.

Only needs `requests` (standard in Anaconda/Jupyter). No GIS libraries required.
"""

import json, math, time, os, urllib.request, urllib.error, urllib.parse

# ----------------------------- config -----------------------------
# Absolute paths so this runs from any Jupyter working directory.
DASHBOARD_DIR = r"C:\Users\ahend\Downloads\Decennial Summer Work\Project Reverse Uno\Dominion\Dashboard + Map"
EXTRA_DIR     = r"C:\Users\ahend\Downloads\Decennial Summer Work\Project Reverse Uno\Nation-Wide Substation Dataset"

EXISTING_JSON = os.path.join(DASHBOARD_DIR, "dominion_substations.json")     # base set (always kept)
BACKUP_JSON   = os.path.join(DASHBOARD_DIR, "dominion_substations_csv_backup.json")
# Merged file is written to BOTH the dashboard folder (so the map picks it up)
# AND the Nation-Wide Substation Dataset folder (your archive copy).
OUTPUT_JSONS  = [os.path.join(DASHBOARD_DIR, "dominion_substations.json"),
                 os.path.join(EXTRA_DIR,    "dominion_substations_merged.json")]
BBOX          = (33.7, -84.4, 39.5, -75.0)           # (south, west, north, east) — all of VA + NC + margin
DEDUPE_M      = 200                                  # drop OSM subs within this many meters of an existing one
# OSM substations with no voltage and no helpful tag default to this class
# (OSM `power=substation` without a voltage is overwhelmingly distribution-scale,
#  which is exactly what we want to add here). Change to "Undetermined" if preferred.
DEFAULT_OSM_CLASS = "Distribution"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# ----------------------- classification helpers -----------------------
def sub_class_of(kv):
    """Mirror the dashboard's subClassOf(): tier a substation by its max kV."""
    if kv is None or kv < 0:
        return "Undetermined"
    if kv >= 230: return "Transmission-EHV"
    if kv >= 115: return "Transmission"
    if kv >= 69:  return "Sub-transmission"
    return "Distribution"

def parse_kv(voltage_tag):
    """OSM `voltage` is in volts, sometimes multi-valued ('115000;34500').
    Return the max in kV, or None."""
    if not voltage_tag:
        return None
    vals = []
    for part in str(voltage_tag).replace(",", ";").split(";"):
        part = part.strip().lower().replace("kv", "").strip()
        try:
            v = float(part)
        except ValueError:
            continue
        if v > 1000:          # volts -> kV
            v = v / 1000.0
        vals.append(v)
    return max(vals) if vals else None

def classify(tags):
    """Return (class, maxkv) for an OSM substation element."""
    kv = parse_kv(tags.get("voltage"))
    if kv is not None:
        return sub_class_of(kv), round(kv, 2)
    st = (tags.get("substation") or "").lower()
    if st in ("distribution", "minor_distribution"):
        return "Distribution", None
    if st in ("transmission",):
        return "Transmission", None
    if st in ("traction",):
        return "Distribution", None
    return DEFAULT_OSM_CLASS, None

# ----------------------------- Overpass fetch -----------------------------
def fetch_osm(bbox):
    s, w, n, e = bbox
    query = (
        "[out:json][timeout:180];"
        '(nwr["power"="substation"](%f,%f,%f,%f););'
        "out center tags;" % (s, w, n, e)
    )
    last_err = None
    for url in OVERPASS_MIRRORS:
        try:
            print("Querying Overpass:", url, "…")
            data = ("data=" + urllib.parse.quote(query)).encode("utf-8")
            req = urllib.request.Request(url, data=data,
                                         headers={"User-Agent": "dominion-substation-merge/1.0"})
            with urllib.request.urlopen(req, timeout=200) as r:
                payload = json.loads(r.read().decode("utf-8"))
            els = payload.get("elements", [])
            print("  -> %d raw elements" % len(els))
            if els:
                return els
        except Exception as ex:        # try the next mirror
            last_err = ex
            print("  mirror failed:", ex)
            time.sleep(2)
    raise RuntimeError("All Overpass mirrors failed. Last error: %s" % last_err)

def osm_to_records(elements):
    out = []
    for el in elements:
        if "lat" in el and "lon" in el:           # node
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:                       # way / relation
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        tags = el.get("tags", {}) or {}
        cls, kv = classify(tags)
        out.append({
            "class": cls,
            "county": "",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "maxkv": kv,
            "minkv": None,
            "name": tags.get("name", "") or "",
            "source": "OSM",
            "source_id": "osm:%s/%s" % (el.get("type", "?"), el.get("id", "?")),
            "state": "",
            "status": "In Service",
            "stype": "Substation",
        })
    return out

# ----------------------------- de-duplication -----------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def build_grid(records, cell_deg):
    grid = {}
    for r in records:
        if r["lat"] is None or r["lon"] is None:
            continue
        key = (int(math.floor(r["lat"]/cell_deg)), int(math.floor(r["lon"]/cell_deg)))
        grid.setdefault(key, []).append(r)
    return grid

def has_neighbor(grid, cell_deg, lat, lon, max_m):
    gx = int(math.floor(lat/cell_deg)); gy = int(math.floor(lon/cell_deg))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for r in grid.get((gx+dx, gy+dy), []):
                if haversine_m(lat, lon, r["lat"], r["lon"]) <= max_m:
                    return True
    return False

# ----------------------------- main -----------------------------
def main():
    if not os.path.exists(EXISTING_JSON):
        raise SystemExit("Can't find %s — edit DASHBOARD_DIR at the top of this script." % EXISTING_JSON)

    existing = json.load(open(EXISTING_JSON, encoding="utf-8"))
    print("Existing substations (kept as-is):", len(existing))

    osm = osm_to_records(fetch_osm(BBOX))
    print("OSM substations parsed:", len(osm))

    # nearest-neighbor dedupe against the existing (kept) set
    cell = DEDUPE_M / 111000.0 * 1.5          # grid cell a bit larger than the search radius
    grid = build_grid(existing, cell)
    kept_osm, dropped = [], 0
    for r in osm:
        if has_neighbor(grid, cell, r["lat"], r["lon"], DEDUPE_M):
            dropped += 1
        else:
            kept_osm.append(r)

    print("OSM dropped as duplicates (<= %dm):" % DEDUPE_M, dropped)
    print("OSM added (new distribution-scale assets):", len(kept_osm))

    merged = existing + kept_osm

    # backup the original, then write merged to every output path
    if not os.path.exists(BACKUP_JSON):
        json.dump(existing, open(BACKUP_JSON, "w"), separators=(",", ":"))
        print("Backed up original ->", BACKUP_JSON)
    for out_path in OUTPUT_JSONS:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        json.dump(merged, open(out_path, "w"), separators=(",", ":"))
        print("Wrote merged file ->", out_path, "(", len(merged), "total )")

    # class breakdown of the final set
    counts = {}
    for r in merged:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    print("\nFinal class breakdown:")
    for k in ("Transmission-EHV", "Transmission", "Sub-transmission", "Distribution", "Undetermined"):
        if k in counts:
            print("  %-18s %d" % (k, counts[k]))

if __name__ == "__main__":
    main()
