#!/usr/bin/env python3
"""
server.py  (Dominion VA+NC playbook, Part 7)

Local dev server for the dashboard. Serves the static folder AND a proxy
so the Site Footprint engine can reach CORS-restricted parcel/building sources:

  /gis?url=<encoded ArcGIS REST url>   -> server-side fetch (VGIN, NC OneMap,
                                          USA Structures) bypassing browser CORS

Parcels use VGIN (VA) + NC OneMap (NC) only. There is no ReportAll fallback:
if neither statewide layer returns a parcel, the site is flagged in the UI.

The dashboard's "Proxy base" field should be left EMPTY when using this server
(calls go to /gis on the same origin).

Capacity layers + HIFLD/CSV substations + NCES schools are public & CORS-enabled,
so they need NO proxy — the page queries them directly in the browser.

Usage:
    python server.py        # then open http://localhost:8000
"""

import json
import os
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8000"))

# Only proxy to known GIS hosts (avoid an open relay).
ALLOWED_HOSTS = (
    "vginmaps.vdem.virginia.gov",
    "services.nconemap.gov",
    "services2.arcgis.com",          # USA Structures
    "services.arcgis.com",
    "services1.arcgis.com",
    "services5.arcgis.com",
)


def _allowed(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)
    except Exception:
        return False


class Handler(SimpleHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.wfile.write(body)

    def _proxy(self, target):
        if not _allowed(target):
            return self._send(403, json.dumps({"error": "host not allowed"}))
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "dominion-proxy/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "application/json")
            self._send(200, data, ctype)
        except Exception as e:
            self._send(502, json.dumps({"error": str(e)}))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/gis":
            return self._proxy(qs.get("url", [""])[0])
        return super().do_GET()

    def end_headers(self):
        if self.path.endswith((".html", ".json", ".js")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    print(f"Serving on http://localhost:{PORT}  (proxy: /gis)")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
