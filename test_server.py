#!/usr/bin/env python3
"""Quick test to verify suggestion server is working"""
import socket
import json

try:
    s = socket.socket()
    s.settimeout(2)
    s.connect(('127.0.0.1', 9999))
    
    payload = json.dumps({"cmd": "git st", "model": "Claude Haiku 4.5"}) + "\n"
    s.sendall(payload.encode())
    
    data = s.recv(4096)
    print("✓ Server is responding!")
    print("Response:", data.decode().strip()[:200])  # First 200 chars
    s.close()
except ConnectionRefusedError:
    print("✗ Server not running on 127.0.0.1:9999")
    print("  Start it with: python .\suggetion_server.py")
except socket.timeout:
    print("✗ Server timeout (not responding)")
except Exception as e:
    print(f"✗ Error: {e}")
