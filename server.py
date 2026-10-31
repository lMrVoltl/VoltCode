import http.server
import socketserver
import subprocess
import os
import json
import urllib.request

PORT = 3000
STATIC_DIR = os.path.expanduser("~/voltcode/static")

FAST_URL = "http://127.0.0.1:8080/v1/chat/completions"
VISION_URL = "http://127.0.0.1:8081/v1/chat/completions"

class OptiVoltHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_POST(self):
        # 1. Возврат в Termux
        if self.path == '/api/open-termux':
            subprocess.run(["am", "start", "-n", "com.termux/.app.TermuxActivity"], stderr=subprocess.DEVNULL)
            subprocess.run([
                "termux-notification",
                "--id", "voltcode",
                "--title", "🐱 VoltCode Studio",
                "--content", "Нажми для возврата в Termux",
                "--action", "am start -n com.termux/.app.TermuxActivity"
            ], stderr=subprocess.DEVNULL)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        # 2. Умный прокси для ИИ
        if self.path == '/api/chat':
            content_length = int(self.headers['Content-Length'])
            req_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            mode = req_data.get("mode", "optivolt")
            has_image = req_data.get("has_image", False)
            
            # Маршрутизация OptiVolt
            if mode == "fast":
                target_url = FAST_URL
            elif mode == "vision":
                target_url = VISION_URL
            else: # optivolt
                target_url = VISION_URL if has_image else FAST_URL

            # Подготовка запроса к llama-server
            payload = json.dumps(req_data["payload"]).encode('utf-8')
            forward_req = urllib.request.Request(
                target_url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            
            try:
                with urllib.request.urlopen(forward_req, timeout=120) as resp:
                    resp_body = resp.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(resp_body)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        self.send_error(404)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), OptiVoltHandler) as httpd:
    httpd.serve_forever()
