import socket
import json

def get_suggestions(command):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("localhost", 8888))
        client.sendall((json.dumps({"cmd": command}) + "\n").encode())
        
        response = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break
        
        client.close()
        return json.loads(response.decode().strip())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Test some commands
    test_commands = ["git staus", "docker ps", "python manage.py", "npm install"]
    
    for cmd in test_commands:
        print(f"Command: {cmd}")
        suggestions = get_suggestions(cmd)
        print("Suggestions:", json.dumps(suggestions, indent=2))
        print("-" * 50)