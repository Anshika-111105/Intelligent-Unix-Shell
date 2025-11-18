from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.patch_stdout import patch_stdout
import threading
import time
import queue

from suggestion_client import get_suggestions

# Debounce interval (seconds) before sending prefix to server
DEBOUNCE = 0.15
# Suggestion fetch timeout (seconds)
FETCH_TIMEOUT = 0.5
# Default model name to request from server
DEFAULT_MODEL = "Claude Haiku 4.5"

class SharedSuggestions:
    def __init__(self):
        self.lock = threading.Lock()
        self.suggestions = []  # list of dicts
        self.last_query = ""

    def update(self, query, suggestions):
        with self.lock:
            self.last_query = query
            self.suggestions = suggestions

    def snapshot(self):
        with self.lock:
            return self.last_query, list(self.suggestions)


class LiveCompleter(Completer):
    def __init__(self, shared: SharedSuggestions):
        self.shared = shared

    def get_completions(self, document: Document, complete_event):
        text = document.text
        q, suggs = self.shared.snapshot()
        if not suggs:
            return
        prefix = text
        for it in suggs:
            s = it.get("suggestion")
            reason = it.get("reason", "")
            if not s:
                continue
            if prefix == "" or prefix.lower() in s.lower():
                yield Completion(
                    s,
                    start_position=-len(document.get_word_before_cursor()),
                    display=s,
                    display_meta=reason
                )


def suggestion_worker(input_q: "queue.Queue[str]", shared: SharedSuggestions, stop_event: threading.Event):
    """Background worker that consumes latest text, waits for debounce, queries server and updates shared suggestions."""
    last = None
    while not stop_event.is_set():
        try:
            # Wait for new text (block short time so we can check stop_event)
            val = input_q.get(timeout=0.05)
            last = val
            # consume any additional queued updates so we only process the latest
            while True:
                try:
                    last = input_q.get_nowait()
                except queue.Empty:
                    break
            # debounce: wait a short interval to allow user to keep typing
            t0 = time.time()
            while time.time() - t0 < DEBOUNCE:
                try:
                    # if new input arrives, reset debounce and use latest
                    last = input_q.get(timeout=DEBOUNCE - (time.time() - t0))
                    t0 = time.time()
                except queue.Empty:
                    break
            # If last is empty or whitespace, clear suggestions
            if not last or last.strip() == "":
                shared.update(last, [])
                continue
            # Query suggestion server (may block up to FETCH_TIMEOUT)
            suggs = get_suggestions(last, model=DEFAULT_MODEL, timeout=FETCH_TIMEOUT)
            # If returned object is dict with suggestions key, normalize (handled in client)
            shared.update(last, suggs if isinstance(suggs, list) else [])
        except queue.Empty:
            continue
        except Exception:
            # On any error, ensure shared updated to empty to avoid stale suggestions
            shared.update(last if last else "", [])


def main_loop():
    session = PromptSession()
    shared = SharedSuggestions()
    comp = LiveCompleter(shared)

    # Queue of prefix updates from prompt buffer
    input_q = queue.Queue()
    stop_event = threading.Event()
    worker = threading.Thread(target=suggestion_worker, args=(input_q, shared, stop_event), daemon=True)
    worker.start()

    try:
        while True:
            # Use a small wrapper to push buffer text to fetcher while typing
            def on_text_changed(buf):
                # push current text to queue (non-blocking)
                try:
                    input_q.put_nowait(buf.text)
                except queue.Full:
                    pass

            buf = session.default_buffer
            # attach handler
            handler = buf.on_text_changed
            # register callback
            cb = lambda _: on_text_changed(buf)
            buf.on_text_changed += cb

            with patch_stdout():
                text = session.prompt("myOS> ", completer=comp, complete_while_typing=True, enable_history_search=False)

            # detach handler
            try:
                buf.on_text_changed -= cb
            except Exception:
                pass

            if text.strip().lower() == "exit":
                print("Exiting myOS shell.")
                break

            # On submit, get final suggestions one more time synchronously
            final_suggestions = get_suggestions(text, model=DEFAULT_MODEL, timeout=FETCH_TIMEOUT)
            if final_suggestions:
                print("\n--- Suggestions ---")
                for s in final_suggestions:
                    # s is expected to be a dict with keys suggestion and reason
                    if isinstance(s, dict):
                        print(f"• {s.get('suggestion')}  ({s.get('reason')})")
                    else:
                        print(f"• {s}")
                print("-------------------\n")

            print(f"Executing: {text}\n")

    except (KeyboardInterrupt, EOFError):
        print("\nExiting myOS shell.")
    finally:
        stop_event.set()
        worker.join(timeout=0.5)


if __name__ == "__main__":
    main_loop()
