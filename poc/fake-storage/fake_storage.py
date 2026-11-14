from http.server import BaseHTTPRequestHandler, HTTPServer
import datetime

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[' + datetime.datetime.now().isoformat() + '] ' + (fmt % args), flush=True)
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        print('[INTERCEPT] ' + self.path + ' <- ' + body.decode(errors='replace'), flush=True)
        self.send_response(200); self.end_headers()
        self.wfile.write(b'{"status":"intercepted"}')

HTTPServer(('0.0.0.0', 9999), H).serve_forever()
