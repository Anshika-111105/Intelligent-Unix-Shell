# Intelligent Shell with ML Suggestions - Architecture & Integration Guide

## **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│  Python Shell UI (my_shell_prompt.py)                           │
│  - Uses prompt_toolkit for interactive input                    │
│  - Shows live completions as user types                         │
│  - Debounced suggestion fetcher (background thread)             │
└──────────────────────┬──────────────────────────────────────────┘
                       │ JSON Request/Response over TCP
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│               IPC (Inter-Process Communication)                 │
├─────────────────────────────────────────────────────────────────┤
│  Transport Layer:                                               │
│  - TCP Socket (127.0.0.1:8888) for cross-platform support      │
│  - Unix Domain Socket (/tmp/shell_suggest.sock) on Unix         │
│  - Payload: JSON with "cmd" and "model" fields                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│          SUGGESTION SERVER (Python ML Backend)                  │
├─────────────────────────────────────────────────────────────────┤
│  suggestion_server.py (Listens on localhost:8888)               │
│  - Accepts multiple concurrent connections (threaded)           │
│  - Parses JSON request: {"cmd":"...", "model":"..."}           │
│  - Routes to three parallel ML suggestion engines:              │
│    1. Typo Fixer (rapidfuzz fuzzy matching)                    │
│    2. Next-Command Predictor (Markov chain)                    │
│    3. Template Recommender (TF-IDF + cosine similarity)        │
│  - Returns JSON: {"model":"...", "suggestions":[...]}          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│            MACHINE LEARNING MODELS (joblib pickles)             │
├─────────────────────────────────────────────────────────────────┤
│  models/ directory contains:                                    │
│  - tfidf_vectorizer.pkl: Fitted TF-IDF vectorizer              │
│  - commands_list.pkl: List of known PowerShell commands        │
│  - markov_model.pkl: Markov transition dict (cmd → next_cmd)   │
│  - known_cmds.json: Reference list of valid commands           │
│  (Built from PowerShell commands CSV via train_from_csv.py)    │
└─────────────────────────────────────────────────────────────────┘

Optional: C Shell Core (future/parallel)
┌─────────────────────────────────────────────────────────────────┐
│            C SHELL CORE (core.c - Native Binary)                │
├─────────────────────────────────────────────────────────────────┤
│  - Read/Parse/Execute loop (low-level process management)       │
│  - Built-in commands: cd, exit, history                         │
│  - Background job support (&)                                   │
│  - SQLite command history logging                               │
│  - TCP Client connecting to suggestion server (same as above)   │
│  - Compiles to: intelligent_shell.exe (Windows) or              │
│    intelligent_shell (Linux/macOS)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## **IPC Protocol Details**

### **Request Format (Client → Server)**
```json
{
  "cmd": "git staus",
  "model": "Claude Haiku 4.5"
}
```
- Sent as a single line terminated with `\n`
- Both fields are optional (server has defaults)

### **Response Format (Server → Client)**
```json
{
  "model": "Claude Haiku 4.5",
  "suggestions": [
    {
      "source": "TypoFixer",
      "suggestion": "git status",
      "confidence": 0.85,
      "reason": "Possible typo correction for 'git staus'"
    },
    {
      "source": "NextCmd",
      "suggestion": "git add .",
      "confidence": 0.72,
      "reason": "Commonly follows 'git status'"
    },
    {
      "source": "Template",
      "suggestion": "git stash",
      "confidence": 0.65,
      "reason": "Similar to 'git staus'"
    }
  ]
}
```
- Response is **always JSON** terminated with `\n`
- Suggestions are sorted by confidence (highest first)
- Returns top 5 suggestions per request

---

## **Integration Points**

### **1. Python Frontend → Server (my_shell_prompt.py)**

**Real-time Suggestion Flow:**
1. User types in `myOS> ` prompt
2. `prompt_toolkit` triggers buffer change event
3. Current text pushed to a queue (non-blocking)
4. Background thread (`suggestion_worker`):
   - Consumes queue, keeps only latest text
   - Waits 150ms (debounce) for more typing
   - Calls `get_suggestions()` with timeout=0.5s
   - Updates shared `SharedSuggestions` object
5. `LiveCompleter` reads shared suggestions
6. Completions displayed in real-time as the user types
7. On Enter: server queried again, final suggestions printed

**Why Debounce?**
- Without it: 10 keystrokes = 10 server requests = network congestion
- With 150ms debounce: "git st" = 1 server request (user pauses briefly)

### **2. Socket Client Library (suggestion_client.py)**

**Single Entry Point:**
```python
def get_suggestions(command, model=None, timeout=0.5):
    # 1. Create TCP socket
    # 2. Connect to 127.0.0.1:8888
    # 3. Send JSON request
    # 4. Read JSON response (with timeout)
    # 5. Parse and return list of suggestion dicts
    # 6. On error: return empty list (graceful degradation)
```

**Why Graceful Degradation?**
- If server is down → shell still works (no suggestions)
- If network timeout → shell continues (non-blocking)
- Default timeout 0.5s prevents UI lag

### **3. ML Suggestion Server (suggestion_server.py)**

**Per-Request Processing Pipeline:**

```
Incoming JSON Request
    ↓
Parse: Extract "cmd" and "model"
    ↓
Run 3 engines in parallel:
    ├→ typo_fix(cmd)           [rapidfuzz fuzzy matching]
    │   Returns: best match + confidence score
    │
    ├→ predict_next(cmd)       [Markov chain lookup]
    │   Returns: top 3 likely next commands with probabilities
    │
    └→ recommend_templates(cmd) [TF-IDF similarity]
        Returns: top 5 similar commands with cosine distances
    ↓
Merge Results:
    - Deduplicate (keep highest confidence)
    - Sort by confidence score
    - Filter low-confidence items
    - Return top 5
    ↓
Wrap in JSON Response
    {
      "model": requested_model,
      "suggestions": [...]
    }
    ↓
Send back to client
```

### **4. ML Training Pipeline (train_from_csv.py)**

**One-time Setup (offline):**
1. Read PowerShell commands from CSV
2. Build vocabulary & train TF-IDF vectorizer
3. Extract command sequences, build Markov chain
4. Serialize all three models to `models/` directory
5. Save command list and known commands reference

**Why This Separation?**
- Training is expensive (happens once)
- Inference is fast (happens on every keypress)
- Models are reloaded only on server startup

---

## **C Shell Core Integration (core.c)**

### **How C Shell Connects to Suggestion Server**

**TCP Connection Method (Cross-platform):**
```c
// 1. Create TCP socket
int sock = socket(AF_INET, SOCK_STREAM, 0);

// 2. Connect to suggestion server
struct sockaddr_in serv;
serv.sin_family = AF_INET;
serv.sin_port = htons(8888);              // Port 8888
inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr);
connect(sock, (struct sockaddr*)&serv, sizeof(serv));

// 3. Send JSON request (same format as Python clients)
char payload[MAXLINE];
snprintf(payload, sizeof(payload), 
         "{\"cmd\":\"%s\",\"model\":\"Claude Haiku 4.5\"}\n", 
         command);
send(sock, payload, strlen(payload), 0);

// 4. Receive JSON response (with timeout)
fd_set rfds;
struct timeval tv = {0, 250000};  // 250ms timeout
select(sock+1, &rfds, NULL, NULL, &tv);
recv(sock, buf, sizeof(buf)-1, 0);

// 5. Parse and display
printf("[suggestion-json] %s\n", buf);
```

**Why TCP Instead of Unix Sockets on Windows?**
- Unix domain sockets don't exist on Windows
- TCP works everywhere (Windows/Linux/macOS)
- 127.0.0.1 loopback is local, no network overhead

### **C Shell Features**

| Feature | Implementation |
|---------|-----------------|
| **Command Execution** | `fork()` + `execvp()` (process spawning) |
| **Built-in Commands** | `cd`, `exit`, `history` (in-process) |
| **Background Jobs** | `&` suffix, tracked with PID |
| **History** | SQLite database (`commands.db`) |
| **Suggestions** | TCP client to suggestion server |
| **Signal Handling** | `SIGINT` (Ctrl+C) traps |

---

## **Key Design Decisions**

### **1. Why Python ML + C Shell?**

| Aspect | Python | C |
|--------|--------|---|
| **Speed** | Slower startup, fast inference (ML) | Fast startup, fast execution |
| **Data Handling** | Excellent (numpy, pandas, scikit-learn) | Manual memory management |
| **ML Libraries** | Rich ecosystem (sklearn, rapidfuzz) | None built-in |
| **Cross-platform** | Native support | Requires conditional compilation |

**Solution:** Use Python for ML (where it excels), C for shell core (where it's efficient).

### **2. Why IPC Over Embedding?**

**Option A: Embed Python in C** ❌
- Complex: Python C API, memory management
- Heavy: Entire Python interpreter in memory
- Maintenance burden

**Option B: Separate Processes + IPC** ✅
- Decoupled: Each component independent
- Resilient: If server crashes, shell survives
- Scalable: Could run on different machines
- Simple: HTTP-like JSON protocol

### **3. Why JSON Protocol?**

- Human-readable (debugging)
- Language-agnostic (can use any client)
- Self-documenting (field names)
- Standard format (no custom parsing needed)

### **4. Why Debounce in Python UI?**

Naive approach: Send request on every keystroke
```
User types: g → i → t   (3 requests, <100ms)
Server overhead: high
Network latency: wasted
```

Smart approach: Debounce 150ms
```
User types slowly: g[wait]i[wait]t → [send after 150ms idle]
User types fast: git staus[send after 150ms]
```
Result: 1 request instead of 5, no perceptible UI lag

---

## **Deployment Architecture**

### **Single Machine (Development)**
```
┌──────────────┐         ┌──────────────┐
│ my_shell.py  │         │   core.c     │
│ (UI process) │ ←→ IPC  │ (Shell proc) │
└──────┬───────┘         └──────┬───────┘
       │                        │
       └────────────┬───────────┘
                    │ TCP :8888
                    ↓
            ┌──────────────────┐
            │ suggestion_server│
            │ (ML + inference) │
            └──────────────────┘
```

### **Future: Distributed Deployment**
```
Multiple Shells ──┐
                  ├─→ Shared ML Server (could be remote)
                  │   - Centralized model management
                  │   - Load balanced
                  │   - High availability
```

---

## **Error Handling & Resilience**

### **Suggestion Server Down**
```
my_shell_prompt.py tries to connect → timeout (0.5s) → returns [] → shell works without suggestions
```

### **Malformed JSON Response**
```python
try:
    obj = json.loads(response)
except json.JSONDecodeError:
    return []  # Return empty list, don't crash
```

### **Network Timeout**
```
socket.settimeout(0.5)  # 500ms max wait
# If no response by then, move on
```

### **Invalid Model Name**
```
Server uses DEFAULT_MODEL if client requests unknown model
Always returns valid response structure
```

---

## **Performance Characteristics**

| Operation | Time | Bottleneck |
|-----------|------|-----------|
| **Keystroke → Suggestion Display** | ~250ms | Network round-trip + ML inference |
| **ML Inference (single query)** | ~50-100ms | TF-IDF + similarity computation |
| **Network Round-trip (localhost)** | ~5-10ms | TCP loopback |
| **JSON Parsing** | <1ms | Python json module |
| **Suggestion Merging & Sorting** | ~5ms | Python dict operations |

**Total E2E latency:** ~250ms (debounce) + network + inference = **perceivable but acceptable**

---

## **Scalability & Extensibility**

### **Adding a New Suggestion Engine**
1. Add function to `suggestion_server.py`: `def new_engine(query):`
2. Call it in `rank_and_merge()` pipeline
3. Append results to `items` list
4. Automatic deduplication & sorting

### **Switching ML Models**
1. Retrain with different algorithm
2. Save to `models/` folder
3. Update `load_models()` to use new model
4. No client changes needed

### **Custom Client**
Create a `new_client.py`:
```python
import socket, json
def get_suggestions(cmd):
    s = socket.socket()
    s.connect(('127.0.0.1', 8888))
    s.sendall(json.dumps({"cmd": cmd}).encode() + b'\n')
    return json.loads(s.recv(4096).decode())
```
Any language works!

---

## **Testing the Integration**

### **1. Start Server**
```bash
python .\suggetion_server.py
# Listen on localhost:8888 (default model: Claude Haiku 4.5)
```

### **2. Test with Python Client**
```bash
python .\test_client.py
# Output: JSON responses from server
```

### **3. Test with Interactive Shell**
```bash
python .\my_shell_prompt.py
# Type: git st → see completions
```

### **4. Test with C Shell** (when compiled)
```bash
gcc -std=gnu11 -Wall core.c -o intelligent_shell -lsqlite3 -lws2_32
.\intelligent_shell
# Type: git st → see JSON suggestion printed
ish> git st
[suggestion-json] {"model":"Claude Haiku 4.5","suggestions":[...]}
```

---

## **Summary: What Happens When You Type "git st"**

```
1. my_shell_prompt.py: User types 'g'
   → Buffer change event fired
   → Text 'g' pushed to queue
   
2. suggestion_worker thread:
   → Sees 'g', waits 150ms for more typing
   → 150ms passes, user still typing, reset wait
   → ...waits for 'git st' + 150ms idle

3. (User finishes typing 'git st', pauses)
   → 150ms idle timeout → call server

4. suggestion_client.py:
   → Create socket, connect to 127.0.0.1:8888
   → Send: {"cmd":"git st","model":"Claude Haiku 4.5"}\n

5. suggestion_server.py:
   → Receives request, parses JSON
   → Runs: typo_fix('git st'), predict_next('git st'), recommend_templates('git st')
   → Engine 1: No typo match
   → Engine 2: Markov predicts "git add" follows "git st"
   → Engine 3: TF-IDF finds "git status", "git stash" similar
   → Merges: [git status (0.9), git stash (0.7), git add (0.6), ...]
   → Returns JSON response

6. my_shell_prompt.py:
   → Receives response, updates SharedSuggestions
   → LiveCompleter.get_completions() yields completions
   → prompt_toolkit displays them below input
   → User sees: "git status" as completion option
   → User presses Tab or Arrow → accepts "git status"

7. User presses Enter
   → Shell fetches final suggestions again
   → Prints: "--- Suggestions --- • git status ... ----"
   → Prints: "Executing: git status"
   → Actually runs: git status
```

---

## **Mentor Talking Points**

✅ **Cross-platform IPC Design** — TCP + conditional compilation for Windows/Unix
✅ **Separation of Concerns** — ML in Python (data science), shell in C (systems)
✅ **Graceful Degradation** — Shell works even if server is offline
✅ **Real-time Responsiveness** — Debouncing prevents network storms
✅ **Extensible Architecture** — Easy to add new engines, swap models
✅ **Production-Ready Patterns** — Timeouts, error handling, JSON protocol
✅ **Integrated with Training Pipeline** — Models built offline, served online
✅ **Low-Latency Inference** — Pre-trained models, <100ms per suggestion

---

**End of Architecture Document**
