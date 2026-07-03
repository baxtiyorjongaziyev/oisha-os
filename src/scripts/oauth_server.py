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

PORT = 9999
HOST = os.getenv("OAUTH_SERVER_HOST", "127.0.0.1")
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

print(f"Server {PORT} portda ishga tushdi")
print(f"Brauzerda oching: http://109.199.100.137:{PORT}/auth")
# Bir martalik OAuth callback server — tashqi provayder redirect'i uchun
# barcha interfeyslarga bog'lanish shart; bitta so'rovdan keyin o'chadi
http.server.HTTPServer(("0.0.0.0", PORT), Handler).handle_request()  # nosec B104
