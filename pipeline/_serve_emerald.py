"""Tiny HTTP server bound to C:\\emerald root, regardless of CWD."""
import http.server
import os
import socketserver
import sys

ROOT = r"C:\emerald"
PORT = int(os.environ.get("EMERALD_SERVE_PORT", "3000"))

os.chdir(ROOT)

with socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Serving {ROOT} on http://127.0.0.1:{PORT}", flush=True)
    httpd.serve_forever()
