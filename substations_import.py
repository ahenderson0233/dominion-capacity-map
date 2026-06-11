#!/usr/bin/env python3
"""
substations_import.py  (Dominion VA+NC playbook, Part 14)

Builds dominion_substations.json (the substation layer the dashboard renders
and uses for "count substations within N miles" + interconnection scoring)
from EITHER:

  A) the provided national OSM-derived CSV
     (Substations-YYYY-MM-DD....csv, ~89k rows, columns:
      "Substation Name","Min Voltage (kV)","Max Voltage (kV)","County",
      "Latitude","Longitude","Owner Source","Source ID","State",
      "Substation ID","Substation Status","Type")
     -> set SOURCE = "csv" and CSV_PATH

  B) the public HIFLD Electric Substations FeatureServer (no file needed)
     -> set SOURCE = "hifld"   (requires network)

Both routes filter to VA+NC, classify by Max kV, and emit the same schema:
  {name, lat, lon, maxkv, minkv, class, county, state, status, stype,
   source, source_id}

Stdlib only.   Run:  python substations_import.py
"""

import csv
import json
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------- #
SOURCE = "csv"                         # "csv" or "hifld"
CSV_PATH = "Substations-2026-06-06.csv"  # <-- point at the provided file
OUTFILE = "dominion_substations.json"
STATES = {"VA", "NC"}
KEEP_TYPES = None                      # e.g. {"Substation"} to drop Taps/Risers
IN_SERVICE_ONLY = False                # True -> keep only "In Service"
HIFLD_URL = ("https://services5.arcgis.com/HDRa0B57OVrv2E1q/arcgis/rest/services/"
             "Electric_Substations/FeatureServer/0")
# --------------------------------------------------------------------------- #


def classify(maxkv):
    if maxkv is None:
        return "Undetermined"
    if maxkv >= 230:
        return "Transmission-EHV"
    if maxkv >= 115:
        return "Transmission"
    if maxkv >= 69:
        return "Sub-transmission"
    if maxkv > 0:
        return "Distribution"
    return "Undetermined"


def to_float(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def from_csv(path):
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # tolerate header variations
        def col(row, *names):
            for n in names:
                for k in row:
                    if k.strip().lower() == n.lower():
                        return row[k]
            return None
        for row in reader:
            state = (col(row, "State") or "").strip().upper()
            if state not in STATES:
                continue
            stype = (col(row, "Type") or "").strip()
            if KEEP_TYPES and stype not in KEEP_TYPES:
                continue
            status = (col(row, "Substation Status") or "").strip()
            if IN_SERVICE_ONLY and status.lower() != "in service":
                continue
            lat = to_float(col(row, "Latitude (Degrees)", "Latitude", "LATITUDE", "Lat"))
            lon = to_float(col(row, "Longitude (Degrees)", "Longitude", "LONGITUDE", "Lon"))
            if lat is None or lon is None:
                continue
            maxkv = to_float(col(row, "Max Voltage (kV)", "Max Voltage", "MAX_VOLT"))
            minkv = to_float(col(row, "Min Voltage (kV)", "Min Voltage", "MIN_VOLT"))
            out.append({
                "name": (col(row, "Substation Name", "NAME") or "").strip(),
                "lat": round(lat, 6), "lon": round(lon, 6),
                "maxkv": maxkv, "minkv": minkv, "class": classify(maxkv),
                "county": (col(row, "County") or "").strip(),
                "state": state, "status": status, "stype": stype,
                "source": "OSM/CSV",
                "source_id": (col(row, "Substation ID", "Source ID") or "").strip(),
            })
    return out


def from_hifld():
    out, offset = [], 0
    while True:
        params = {
            "where": "STATE IN ('VA','NC')",
            "outFields": "NAME,STATE,COUNTY,LATITUDE,LONGITUDE,MAX_VOLT,MIN_VOLT,STATUS,TYPE",
            "returnGeometry": "false", "outSR": 4326, "f": "json",
            "resultOffset": offset, "resultRecordCount": 2000,
            "orderByFields": "OBJECTID",
        }
        url = HIFLD_URL + "/query?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "dominion-playbook/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        feats = data.get("features", [])
        if not feats:
            break
        for f in feats:
            a = f["attributes"]
            maxkv = to_float(a.get("MAX_VOLT"))
            if maxkv is not None and maxkv < 0:
                maxkv = None
            lat, lon = to_float(a.get("LATITUDE")), to_float(a.get("LONGITUDE"))
            if lat is None or lon is None:
                continue
            stype = a.get("TYPE") or ""
            if KEEP_TYPES and stype not in KEEP_TYPES:
                continue
            status = a.get("STATUS") or ""
            if IN_SERVICE_ONLY and status.lower() != "in service":
                continue
            out.append({
                "name": a.get("NAME") or "", "lat": round(lat, 6), "lon": round(lon, 6),
                "maxkv": maxkv, "minkv": to_float(a.get("MIN_VOLT")),
                "class": classify(maxkv), "county": a.get("COUNTY") or "",
                "state": a.get("STATE") or "", "status": status, "stype": stype,
                "source": "HIFLD", "source_id": "",
            })
        offset += len(feats)
        if len(feats) < 2000:
            break
    return out


def main():
    subs = from_csv(CSV_PATH) if SOURCE == "csv" else from_hifld()
    with open(OUTFILE, "w", encoding="utf-8") as fh:
        json.dump(subs, fh)
    counts = {}
    for s in subs:
        counts[s["class"]] = counts.get(s["class"], 0) + 1
    print(f"Wrote {OUTFILE} with {len(subs)} substations (source={SOURCE}).")
    for k in ["Transmission-EHV", "Transmission", "Sub-transmission", "Distribution", "Undetermined"]:
        if k in counts:
            print(f"  {k}: {counts[k]}")


if __name__ == "__main__":
    main()
