from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, datetime, threading

IPTABLES = "/usr/sbin/iptables"
LOCK = threading.Lock()

def add_rule():
    with LOCK:
        subprocess.run([IPTABLES, "-I", "INPUT", "-p", "tcp", "--dport", "30001",
                         "-m", "limit", "--limit", "10/second", "-j", "ACCEPT"])
        subprocess.run([IPTABLES, "-A", "INPUT", "-p", "tcp", "--dport", "30001", "-j", "DROP"])
    print(f"[THROTTLE] rate-limit aplicado ao NodePort 30001", flush=True)

def delete_rule():
    with LOCK:
        subprocess.run([IPTABLES, "-D", "INPUT", "-p", "tcp", "--dport", "30001", "-j", "DROP"])
        subprocess.run([IPTABLES, "-D", "INPUT", "-p", "tcp", "--dport", "30001",
                         "-m", "limit", "--limit", "10/second", "-j", "ACCEPT"])
    print(f"[THROTTLE] rate-limit removido do NodePort 30001 (auto-expirado, 60s)", flush=True)

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[" + datetime.datetime.now().isoformat() + "] " + (fmt % args), flush=True)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode(errors="replace")
        action = "add" if "add" in self.path else "delete" if "delete" in self.path else "add"

        if action == "add":
            add_rule()
            # Auto-expira ao fim de 60s. Nao depende do Wazuh chamar /delete:
            # a regra 100200/100201 nao tem decoder a extrair alert keys, por
            # isso o wazuh-execd nunca agenda a expiracao nativa (confirmado em
            # execd.debug=2: "Active response won't be added to timeout list").
            threading.Timer(60.0, delete_rule).start()
        else:
            delete_rule()

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

HTTPServer(("0.0.0.0", 9100), H).serve_forever()
