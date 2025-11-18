import socket
import json
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion

class SuggestionCompleter(Completer):
    def get_completions(self, document, complete_event):
        command = document.text.strip()
        if not command:
            return

        # send to suggestion server
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
            suggestions = json.loads(response.decode().strip())
        except Exception:
            suggestions = []

        # show suggestion completions below the input
        for suggestion in suggestions:
            if isinstance(suggestion, dict) and "suggestion" in suggestion:
                yield Completion(suggestion["suggestion"], start_position=-len(command))
            elif isinstance(suggestion, str):
                yield Completion(suggestion, start_position=-len(command))

if __name__ == "__main__":
    print("Interactive Command Suggestion Terminal")
    print("Type commands — live suggestions will appear below. Type 'exit' to quit.\n")

    completer = SuggestionCompleter()

    while True:
        try:
            user_input = prompt(">> ", completer=completer)
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting...")
                break
        except KeyboardInterrupt:
            break
        except EOFError:
            break
