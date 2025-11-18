#!/usr/bin/env python3
"""
A tiny TCP suggestion server for local testing — no ML dependencies.
Listens on 127.0.0.1:8888 and returns a JSON object:
  {"model":"Claude Haiku 4.5","suggestions":[{...}, ...]}
This lets you test the UI and IPC without installing heavy Python packages.
"""
import socket
import threading
import json

HOST = '127.0.0.1'
PORT = 9999

SAMPLE_TEMPLATES = [
    'git status',
    'git commit -m "message"',
    'git push',
    'docker ps',
    'docker run --rm -it IMAGE',
    'python -m venv .venv',
    'pip install -r requirements.txt',
    'npm install',
]


def make_suggestions(q):
    ql = q.strip().lower()
    items = []
    if ql == '':
        return items
    # partial matches from templates
    for t in SAMPLE_TEMPLATES:
        if ql in t.lower():
            items.append({
                'source': 'Template',
                'suggestion': t,
                'confidence': 0.6,
                'reason': f"Contains '{q}'",
            })
    # fallback: echo suggestion by appending '-suggested'
    if not items:
        items.append({
            'source': 'Echo',
            'suggestion': q + ' --suggested',
            'confidence': 0.3,
            'reason': 'Echo fallback',
        })
    return items


def handle_conn(conn, addr):
    try:
        conn.settimeout(1.0)
        data = b''
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
        except socket.timeout:
            pass

        if not data:
            print(f"[{addr}] no data received")
            return

        raw = data.decode().strip()
        print(f"[{addr}] received: {raw}")
        query = raw
        model = 'Claude Haiku 4.5'
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                query = obj.get('cmd', raw)
                model = obj.get('model', model)
        except Exception:
            # not JSON, keep raw
            pass

        suggestions = make_suggestions(query)
        payload = {'model': model, 'suggestions': suggestions}
        resp = (json.dumps(payload) + '\n').encode()
        conn.sendall(resp)
        print(f"[{addr}] sent {len(suggestions)} suggestions (model={model})")
    except Exception as e:
        print(f"[{addr}] error: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


def run():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"simple_server listening on {HOST}:{PORT}")
    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_conn, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print('shutting down')
    finally:
        server.close()

if __name__ == '__main__':
    run()
