import socket
import json

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9999


def get_suggestions(command, model=None, timeout=0.5):
    """Send a small JSON request to the suggestion server and return the list of suggestions.

    Returns list of suggestion dicts (source, suggestion, confidence, reason) or [] on error.
    """
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(timeout)
        client.connect((DEFAULT_HOST, DEFAULT_PORT))
        payload = {"cmd": command}
        if model:
            payload["model"] = model
        client.sendall((json.dumps(payload) + "\n").encode())

        data = b""
        while True:
            try:
                chunk = client.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        client.close()
        if not data:
            return []
        try:
            obj = json.loads(data.decode().strip())
            # server may return {"model":..., "suggestions":[...]}
            if isinstance(obj, dict) and "suggestions" in obj:
                return obj.get("suggestions", [])
            # or it might return a list directly
            if isinstance(obj, list):
                return obj
            return []
        except Exception:
            return []
    except Exception:
        return []
