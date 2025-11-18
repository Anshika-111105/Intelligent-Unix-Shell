import socket, json
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion

# Connect to suggestion server
def get_suggestions(prefix):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", 8888))
        s.sendall((json.dumps({"cmd": prefix}) + "\n").encode())

        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        s.close()
        suggestions = json.loads(data.decode().strip())
        return suggestions

    except Exception as e:
        return []

# Completer that shows suggestions live
class SuggestionCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text
        if not text.strip():
            return

        suggestions = get_suggestions(text)

        for item in suggestions:
            if isinstance(item, dict):
                suggestion = item.get("suggestion", "")
            else:
                suggestion = str(item)

            if suggestion:
                yield Completion(suggestion, start_position=-len(text))


# Interactive Shell
def main():
    print("🚀 Interactive OS Shell with Live Suggestions")
    print("Type commands like your OS shell. Suggestions pop up below.\n")
    
    session = PromptSession(completer=SuggestionCompleter())

    while True:
        try:
            user_cmd = session.prompt("myOS> ")

            if user_cmd.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            print(f"Running command: {user_cmd}")

        except KeyboardInterrupt:
            continue
        except EOFError:
            break

if __name__ == "__main__":
    main()
