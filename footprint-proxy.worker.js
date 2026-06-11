/*
 * footprint-proxy.worker.js  (Dominion VA+NC playbook, Part 7)
 *
 * Cloudflare Worker that re-creates the local server's /gis proxy so the Site
 * Footprint engine works on a STATIC host (GitHub Pages). Parcels use VGIN (VA)
 * + NC OneMap (NC) only; there is no ReportAll fallback.
 *
 * Deploy:
 *   1. wrangler init footprint-proxy  (or paste into the dashboard editor)
 *   2. wrangler deploy
 *   3. In the dashboard "Proxy base" field, enter: https://<worker>.workers.dev
 *
 * Set ALLOWED_ORIGIN to your Pages origin to lock CORS.
 */

const ALLOWED_HOSTS = [
  "vginmaps.vdem.virginia.gov",
  "services.nconemap.gov",
  "services2.arcgis.com",
  "services.arcgis.com",
  "services1.arcgis.com",
  "services5.arcgis.com",
];
const ALLOWED_ORIGIN = "*"; // e.g. "https://yourname.github.io"

function cors(resp) {
  const h = new Headers(resp.headers);
  h.set("Access-Control-Allow-Origin", ALLOWED_ORIGIN);
  h.set("Access-Control-Allow-Methods", "GET,OPTIONS");
  h.set("Access-Control-Allow-Headers", "*");
  return new Response(resp.body, { status: resp.status, headers: h });
}

function allowed(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return ALLOWED_HOSTS.some((h) => host === h || host.endsWith("." + h));
  } catch (e) {
    return false;
  }
}

function json(obj, status = 200) {
  return cors(new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json" },
  }));
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return cors(new Response(null, { status: 204 }));
    const u = new URL(request.url);

    if (u.pathname === "/gis") {
      const target = u.searchParams.get("url");
      if (!target || !allowed(target)) return json({ error: "host not allowed" }, 403);
      const r = await fetch(target, { headers: { "User-Agent": "dominion-proxy/1.0" } });
      return cors(r);
    }

    return json({ ok: true, proxies: ["/gis?url="] });
  },
};
