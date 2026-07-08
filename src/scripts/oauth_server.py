"""
AmoCRM OAuth redirect server.
VPS da ishga tushiring: python oauth_server.py
Brauzerda oching: http://109.199.100.137:9999/auth
"""
import http.server
import json
import os
import urllib.parse
import sys

CODE = None

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global CODE
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            CODE = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"""
            <html><body style="font-family:monospace;padding:40px">
            <h1>Token olingan!</h1>
            <pre>{CODE}</pre>
            <p>Server to'xtatilmoqda...</p>
            </body></html>
            """.encode())
            print(f"\nCODE: {CODE}")
            print("Token olinmoqda...")
            sys.exit(0)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Waiting for OAuth callback...</h1>")

    def log_message(self, format, *args):
        pass


def run_server():
    """Bir martalik OAuth callback serverini ishga tushiradi (bitta
    so'rovni kutib, keyin to'xtaydi). Modul import qilinganda emas, faqat
    shu funksiya chaqirilganda ishga tushadi — shu bilan modulni import
    qilish (masalan testlarda) hech qachon osilib qolmaydi."""
    host = os.getenv("OISHA_OAUTH_BIND_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("OISHA_OAUTH_PORT", "9999"))
    except ValueError:
        port = 9999
    print(f"Server {host}:{port} da ishga tushdi")
    print(f"Brauzerda oching: http://{host}:{port}/auth")
    with http.server.HTTPServer((host, port), Handler) as server:
        server.handle_request()


if __name__ == "__main__":
    run_server()
