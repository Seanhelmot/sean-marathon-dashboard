#!/usr/bin/env python3
"""
Local dev server for Coach Hub.
  python serve.py          → http://localhost:8765/coach-hub/
  GET /api/refresh         → runs pull_coach_data.py, returns JSON status
  GET /api/coach.json      → serves data/coach.json directly
  Everything else          → static file from repo root
"""
import http.server, json, os, subprocess, sys, threading
from pathlib import Path

ROOT = Path(__file__).parent
PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def do_GET(self):
        if self.path == '/api/refresh':
            self._refresh()
        elif self.path == '/api/coach.json':
            self._serve_json()
        else:
            super().do_GET()

    def _refresh(self):
        script = ROOT / 'scripts' / 'pull_coach_data.py'
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=60
            )
            ok = result.returncode == 0
            body = json.dumps({
                'ok': ok,
                'stdout': result.stdout[-2000:],
                'stderr': result.stderr[-500:] if not ok else '',
            }).encode()
        except subprocess.TimeoutExpired:
            body = json.dumps({'ok': False, 'stdout': '', 'stderr': 'Timed out after 60s'}).encode()
        except Exception as e:
            body = json.dumps({'ok': False, 'stdout': '', 'stderr': str(e)}).encode()

        self._send(200, 'application/json', body)

    def _serve_json(self):
        p = ROOT / 'data' / 'coach.json'
        if not p.exists():
            self._send(404, 'application/json', b'{"error":"coach.json not found"}')
            return
        self._send(200, 'application/json', p.read_bytes())

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # suppress noisy request logs; only print refresh calls
        if '/api/' in (args[0] if args else ''):
            print(f'  {args[0]}  →  {args[1]}')


if __name__ == '__main__':
    os.chdir(ROOT)
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    import socket
    local_ip = socket.gethostbyname(socket.gethostname())
    print(f'Coach Hub  →  http://localhost:{PORT}/coach-hub/')
    print(f'Network    →  http://{local_ip}:{PORT}/coach-hub/')
    print('Ctrl-C to stop\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
