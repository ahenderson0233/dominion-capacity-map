#!/usr/bin/env python3
"""
fetch_territory.py  (Dominion VA+NC playbook)

Pulls Dominion's electric retail service-territory boundary from HIFLD and writes,
for EACH service territory (split by STATE):

    dominion_territory_<ST>.shp / .shx / .dbf / .prj      (shapefile per territory)

plus the web-ready boundary the dashboard actually loads:

    dominion_territory.geojson                            (all territories, WGS84)

The dashboard clips substations + candidate sites to this boundary; if the GeoJSON
is absent it falls back to a boundary derived by buffering the capacity network.

Run this where HIFLD is reachable (a normal internet connection):

    pip install pyshp            # only dependency; fetch uses the stdlib
    python fetch_territory.py

If your environment can't reach the first endpoint, the script tries the others in
ENDPOINTS; add/replace URLs there as HIFLD mirrors change.
"""

import json
import ssl
import urllib.parse
import urllib.request

try:
    import shapefile  # pyshp
except ImportError:
    raise SystemExit("pyshp is required:  pip install pyshp")

# --- HIFLD "Electric Retail Service Territories" candidate endpoints ----------
# The script uses the first one that returns Dominion features.
ENDPOINTS = [
    "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Retail_Service_Territories/FeatureServer/0",
    "https://maps.nccs.nasa.gov/mapping/rest/services/hifld_open/energy/FeatureServer/26",
    # add EIA / geoplatform mirrors here if needed
]
# Dominion operates as "Virginia Electric & Power Co" (VA) and Dominion Energy NC.
WHERE = "NAME LIKE '%VIRGINIA ELECTRIC%' OR NAME LIKE '%DOMINION%'"
WGS84_WKT = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
             'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
_CTX = ssl.create_default_context()


def fetch_features():
    params = {"where": WHERE, "outFields": "NAME,STATE", "returnGeometry": "true",
              "outSR": "4326", "f": "geojson"}
    qs = urllib.parse.urlencode(params)
    for base in ENDPOINTS:
        url = base + "/query?" + qs
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dominion-playbook/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
                data = json.load(r)
            feats = data.get("features", [])
            if feats:
                print(f"  {len(feats)} feature(s) from {base}")
                return feats
            print(f"  (no Dominion features at {base})")
        except Exception as e:
            print(f"  endpoint failed: {base}\n    {e}")
    return []


def polygons_of(geom):
    """Return a list of polygons, each a list of rings ([[x,y],...])."""
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def state_of(props):
    st = (props.get("STATE") or props.get("State") or "").strip().upper()
    return st if st in ("VA", "NC") else (st or "XX")


def write_shapefile(path_base, features):
    w = shapefile.Writer(path_base, shapeType=shapefile.POLYGON)
    w.field("NAME", "C", 120)
    w.field("STATE", "C", 2)
    for f in features:
        name = (f.get("properties", {}).get("NAME") or "")[:120]
        st = state_of(f.get("properties", {}))
        for poly in polygons_of(f.get("geometry")):
            w.poly(poly)             # rings as parts
            w.record(name, st)
    w.close()
    with open(path_base + ".prj", "w", encoding="utf-8") as fh:
        fh.write(WGS84_WKT)


def main():
    print("Querying HIFLD Electric Retail Service Territories for Dominion…")
    feats = fetch_features()
    if not feats:
        raise SystemExit("No Dominion features found at any endpoint. "
                         "Update ENDPOINTS with a current HIFLD mirror and retry.")

    # group by state -> one shapefile per service territory
    by_state = {}
    for f in feats:
        by_state.setdefault(state_of(f.get("properties", {})), []).append(f)

    for st, group in sorted(by_state.items()):
        base = f"dominion_territory_{st}"
        write_shapefile(base, group)
        print(f"  wrote {base}.shp/.shx/.dbf/.prj  ({len(group)} feature(s))")

    # combined GeoJSON the dashboard loads
    out = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"NAME": f.get("properties", {}).get("NAME", ""),
                        "STATE": state_of(f.get("properties", {}))},
         "geometry": f.get("geometry")}
        for f in feats]}
    with open("dominion_territory.geojson", "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"  wrote dominion_territory.geojson ({len(feats)} feature(s)) "
          "— place beside index.html so the dashboard clips to it.")


if __name__ == "__main__":
    main()
