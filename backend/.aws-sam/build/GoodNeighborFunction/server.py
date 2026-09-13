"""
Local dev server for the Good Neighbor backend — no AWS required.

Runs every tool handler behind one HTTP server using only the Python standard
library, so you can exercise the whole backend (and point the agent or curl at
it) on your machine.

Run:
    python backend/server.py            # serves on http://localhost:8080
    PORT=9000 python backend/server.py  # custom port

Routes (all GET; guidelines also accepts POST):
    GET  /                         -> surplus listings (community gateway root)
    GET  /catalog                  -> resource catalog (?category= &resource=)
    GET  /needs                    -> recipient needs   (?resource_id= &org_id=)
    GET  /pantry                   -> pantry levels      (?resource_id=)
    GET  /volunteers               -> volunteers         (filters, see schema)
    GET  /volunteers/{id}          -> one volunteer
    GET  /vehicles                 -> vehicles           (filters, see schema)
    GET  /vehicles/{id}            -> one vehicle
    GET|POST /guidelines           -> guideline details  (?guideline_type= or JSON body)
    GET  /health                   -> {"status":"ok"}

Note: surplus and catalog both map to "GET /" in their individual schemas
(each is its own API Gateway). Here they share one server, so the catalog is
exposed at /catalog to avoid a collision while keeping the surplus root at /.

MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handlers import community, pantry, logistics, guidelines  # noqa: E402


def _qs_to_params(query):
    """Flatten parse_qs {k:[v]} into {k:v}."""
    return {k: v[0] for k, v in parse_qs(query).items()}


def _route(method, path, params, body):
    """Map an incoming request to a handler and a Lambda-style event."""
    event = {"queryStringParameters": params, "body": body, "pathParameters": {}}

    if path == "/" or path == "/surplus":
        return community.surplus_listings_handler(event)
    if path == "/catalog":
        return community.resource_catalog_handler(event)
    if path == "/needs":
        return community.recipient_needs_handler(event)
    if path == "/pantry":
        return pantry.handler(event)

    if path == "/volunteers":
        return logistics.volunteers_handler(event)
    if path.startswith("/volunteers/"):
        event["pathParameters"] = {"volunteer_id": path.split("/", 2)[2]}
        return logistics.volunteers_handler(event)

    if path == "/vehicles":
        return logistics.vehicles_handler(event)
    if path.startswith("/vehicles/"):
        event["pathParameters"] = {"vehicle_id": path.split("/", 2)[2]}
        return logistics.vehicles_handler(event)

    if path == "/guidelines":
        return guidelines.handler(event)

    if path == "/health":
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "ok"})}

    return {"statusCode": 404, "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"No route for {method} {path}"})}


class Handler(BaseHTTPRequestHandler):
    def _send(self, result):
        status = result.get("statusCode", 200)
        headers = result.get("headers", {"Content-Type": "application/json"})
        body = result.get("body", "")
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        # Ensure CORS even on routes that didn't set it (health/404).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = _qs_to_params(parsed.query)
        self._send(_route("GET", parsed.path.rstrip("/") or "/", params, None))

    def do_POST(self):
        parsed = urlparse(self.path)
        params = _qs_to_params(parsed.query)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8") if length else None
        self._send(_route("POST", parsed.path.rstrip("/") or "/", params, body))

    def log_message(self, fmt, *args):
        sys.stderr.write("[server] " + (fmt % args) + "\n")


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Good Neighbor backend running on http://localhost:{port}")
    print("Try:  curl http://localhost:%d/pantry" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
