# IPC Connection: ML Server ↔ Shell (Detailed Explanation)

## **What is IPC?**
**IPC (Inter-Process Communication)** = Two separate programs talking to each other over a network connection.

In your project:
- **Process 1:** Your shell (Python `my_shell_prompt.py` or C `core.c`)
- **Process 2:** ML suggestion server (`suggestion_server.py`)
- **Connection:** TCP socket on localhost:9999

They communicate by passing JSON messages back and forth.

---

## **Step-by-Step: What Happens When You Type "git st"**

### **Step 1: User Types in Shell**
```
User at keyboard:  g → i → t → [space] → s → t
Shell receives:    "git st"
```

### **Step 2: Shell Creates a TCP Socket Connection**
```
Shell code (Python):
────────────────────
import socket
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create socket
client.connect(("127.0.0.1", 9999))                         # Connect to server

Shell code (C):
────────────────────
int sock = socket(AF_INET, SOCK_STREAM, 0);               // Create socket
struct sockaddr_in serv;
serv.sin_family = AF_INET;
serv.sin_port = htons(9999);                              // Port 9999
inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr);
connect(sock, (struct sockaddr*)&serv, sizeof(serv));     // Connect
```

**What's happening:**
- `socket()` = create a communication channel
- `connect()` = establish connection to the server at 127.0.0.1:9999
- `127.0.0.1` = localhost (local machine only)
- `9999` = the port the server is listening on

---

### **Step 3: Shell Sends JSON Request to Server**
```json
{
  "cmd": "git st",
  "model": "Claude Haiku 4.5"
}
```

**Python code:**
```python
import json
payload = json.dumps({"cmd": "git st", "model": "Claude Haiku 4.5"}) + "\n"
client.sendall(payload.encode())  # Send as bytes, newline-terminated
```

**C code:**
```c
char payload[MAXLINE];
snprintf(payload, sizeof(payload), "{\"cmd\":\"git st\",\"model\":\"Claude Haiku 4.5\"}\n");
send(sock, payload, strlen(payload), 0);
```

**What's happening:**
- `json.dumps()` = convert Python dict to JSON string
- `.encode()` = convert string to bytes (network format)
- `+ "\n"` = add newline terminator (so server knows message is complete)
- `send()` = transmit bytes over the socket

**Over the network (actually TCP packets):**
```
[IP Header][TCP Header][{"cmd":"git st","model":"Claude Haiku 4.5"}\n]
```

---

### **Step 4: Server Receives the JSON Request**
Server is listening on port 9999. When data arrives:

```python
# Server code
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("localhost", 9999))   # Listen on this address
server.listen(5)                   # Accept up to 5 connections
conn, addr = server.accept()       # Wait for connection from client

# When client connects and sends data:
data = conn.recv(4096)             # Read up to 4096 bytes
raw = data.decode().strip()        # Convert bytes to string
print(f"Received: {raw}")           # Output: Received: {"cmd":"git st","model":"Claude Haiku 4.5"}
```

**Server output (in terminal):**
```
Connection from 127.0.0.1:54321
Received: {"cmd":"git st","model":"Claude Haiku 4.5"}
```

---

### **Step 5: Server Parses the JSON Request**
```python
obj = json.loads(raw)              # Parse JSON string to Python dict
query = obj.get("cmd", "")         # Extract command: "git st"
model = obj.get("model")           # Extract model: "Claude Haiku 4.5"
print(f"Processing: '{query}' with model '{model}'")
```

**Result:**
```python
query = "git st"
model = "Claude Haiku 4.5"
```

---

### **Step 6: Server Runs ML Suggestion Engines**
The server runs **3 parallel engines** on "git st":

**Engine 1: Typo Fixer (rapidfuzz)**
```python
def typo_fix(query):
    # Fuzzy match against known commands
    match, score, _ = process.extractOne(query, known_cmds, scorer=fuzz.partial_ratio)
    # Finds: "git status" (score 0.85)
    return "git status", 0.85
```

**Engine 2: Next-Command Predictor (Markov chain)**
```python
def predict_next(query):
    # Look up what commands usually follow "git st"
    if query in markov:
        nxts = markov[query]
        # Finds: "git add" (confidence 0.72)
    return [("git add", 0.72), ...]
```

**Engine 3: Template Recommender (TF-IDF)**
```python
def recommend_templates(query):
    # Find similar commands using TF-IDF vectorization
    qv = vectorizer.transform([query])
    sims = cosine_similarity(qv, vectorizer.transform(commands_list))
    # Finds: "git stash" (similarity 0.65)
    return [("git stash", 0.65), ...]
```

**Result: List of suggestions**
```python
suggestions = [
    {
        "source": "TypoFixer",
        "suggestion": "git status",
        "confidence": 0.85,
        "reason": "Possible typo correction for 'git st'"
    },
    {
        "source": "Template",
        "suggestion": "git stash",
        "confidence": 0.65,
        "reason": "Similar to 'git st'"
    },
    {
        "source": "NextCmd",
        "suggestion": "git add",
        "confidence": 0.72,
        "reason": "Commonly follows 'git st'"
    }
]
```

---

### **Step 7: Server Wraps Suggestions in JSON Response**
```python
response = {
    "model": "Claude Haiku 4.5",
    "suggestions": suggestions
}
response_json = json.dumps(response) + "\n"
conn.sendall(response_json.encode())
```

**Full response sent back:**
```json
{
  "model": "Claude Haiku 4.5",
  "suggestions": [
    {
      "source": "TypoFixer",
      "suggestion": "git status",
      "confidence": 0.85,
      "reason": "Possible typo correction for 'git st'"
    },
    {
      "source": "Template",
      "suggestion": "git stash",
      "confidence": 0.65,
      "reason": "Similar to 'git st'"
    },
    {
      "source": "NextCmd",
      "suggestion": "git add",
      "confidence": 0.72,
      "reason": "Commonly follows 'git st'"
    }
  ]
}
```

**Over the network (TCP packets):**
```
[IP Header][TCP Header][{"model":"Claude Haiku 4.5","suggestions":[...]\n]
```

---

### **Step 8: Shell Receives JSON Response**
Shell is waiting for the server to respond (with timeout):

**Python code:**
```python
response = b""
while True:
    chunk = client.recv(4096)  # Read up to 4096 bytes
    if not chunk:
        break
    response += chunk
    if b"\n" in response:      # Stop when we see newline
        break
client.close()                 # Close connection
```

**C code:**
```c
char buf[MAXLINE];
fd_set rfds;
FD_ZERO(&rfds);
FD_SET(sock, &rfds);
struct timeval tv;
tv.tv_sec = 0;
tv.tv_usec = 500000;           // 500ms timeout
select(sock+1, &rfds, NULL, NULL, &tv);  // Wait for data
ssize_t r = recv(sock, buf, sizeof(buf)-1, 0);  // Read bytes
buf[r] = '\0';
```

**Result: Response is now in memory**
```
response = b'{"model":"Claude Haiku 4.5","suggestions":[...]}\n'
```

---

### **Step 9: Shell Parses and Displays Suggestions**
**Python code:**
```python
obj = json.loads(response.decode().strip())  # Parse JSON
suggestions = obj.get("suggestions", [])

# Update shared suggestions for completions menu
shared.update("git st", suggestions)
```

**What happens next:**
1. `LiveCompleter.get_completions()` is called
2. It reads from `shared.suggestions`
3. For each suggestion, it yields a `Completion` object:
   ```python
   yield Completion(
       "git status",                                    # The suggestion text
       start_position=-len("st"),
       display="git status",
       display_meta="Possible typo correction for 'git st'"  # The explanation
   )
   ```

**User sees in the shell:**
```
myOS> git st
┌────────────────────────────────────────────┐
│ git status    ◄ Possible typo correction   │
│ git stash     ◄ Similar to 'git st'        │
│ git add       ◄ Commonly follows 'git st'  │
└────────────────────────────────────────────┘
```

---

### **Step 10: User Selects a Suggestion**
- User presses **Arrow Down** to move to "git status"
- User presses **Tab** or **Enter** to accept
- Shell replaces "git st" with "git status"

```
myOS> git status_
```

---

### **Step 11: User Executes the Command**
- User presses **Enter** to execute
- Shell prints final suggestions:
  ```
  --- Suggestions ---
  • git status  (TypoFixer: Possible typo correction for 'git st')
  -------------------
  
  Executing: git status
  ```
- Actual command runs (not implemented in demo, but in real shell would fork/exec)

---

## **Complete Message Flow Diagram**

```
┌──────────────────────────────────────────────────────────────────┐
│                        SHELL PROCESS                             │
│  User types: "git st"                                            │
│  ↓                                                               │
│  suggestion_client.get_suggestions("git st")                     │
│  ├─ Create TCP socket                                            │
│  ├─ Connect to 127.0.0.1:9999                                    │
│  ├─ Send JSON: {"cmd":"git st","model":"Claude Haiku 4.5"}\n     │
│  │                                                               │
│  │  ════════════════════ TCP NETWORK ════════════════════        │
│  │                                                               │
│  └─ Receive JSON: {"model":"...","suggestions":[...]}\n          │
│  ├─ Parse JSON                                                   │
│  ├─ Update suggestions list                                      │
│  └─ Display completions menu                                     │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    ML SERVER PROCESS                             │
│  Listening on localhost:9999                                     │
│  ↓                                                               │
│  Accept connection from shell                                    │
│  ├─ Receive JSON: {"cmd":"git st","model":"Claude Haiku 4.5"}\n  │
│  │                                                               │
│  ├─ Parse: query="git st", model="Claude Haiku 4.5"              │
│  │                                                               │
│  ├─ Run ML engines:                                              │
│  │  ├─ typo_fix("git st") → "git status" (0.85)                 │
│  │  ├─ predict_next("git st") → "git add" (0.72)                │
│  │  └─ recommend_templates("git st") → "git stash" (0.65)       │
│  │                                                               │
│  ├─ Merge & sort suggestions                                    │
│  │                                                               │
│  └─ Send JSON: {"model":"...","suggestions":[...]}\n             │
│     ════════════════════ TCP NETWORK ════════════════════        │
└──────────────────────────────────────────────────────────────────┘
```

---

## **Why This Design?**

### **Advantages:**
1. **Decoupled:** Shell and server are independent processes
2. **Resilient:** If server crashes, shell still works (no suggestions)
3. **Scalable:** Could run server on different machine
4. **Cross-platform:** TCP works on Windows, Linux, macOS
5. **Simple protocol:** JSON is human-readable and language-agnostic
6. **Non-blocking:** Shell uses timeout (doesn't hang if server is slow)

### **Alternatives Considered:**
- **Embedding Python in C:** Complex, heavy, maintenance burden
- **Files (disk IPC):** Slow, not real-time
- **Message queues (RabbitMQ):** Overkill for local use
- **HTTP REST API:** More overhead than raw TCP

---

## **Key Technical Details**

### **TCP Connection Lifecycle:**
```
1. Server starts: socket() → bind(9999) → listen()
2. Server waits: accept() [blocks until client connects]
3. Client starts: socket() → connect(127.0.0.1:9999)
4. Connection established (TCP handshake)
5. Client sends: sendall(JSON + "\n")
6. Server receives: recv(4096)
7. Server sends: sendall(JSON + "\n")
8. Client receives: recv(4096)
9. Client closes: close()
10. Server closes: close()
```

### **Timeout Mechanism:**
```python
# Python: socket.settimeout(0.5)
socket.settimeout(0.5)  # 500ms max wait
data = socket.recv(4096)  # Raises socket.timeout if no response

# C: select() with timeval
struct timeval tv;
tv.tv_sec = 0;
tv.tv_usec = 500000;  // 500ms
select(sock+1, &rfds, NULL, NULL, &tv);
```

**Why timeout?**
- Prevents shell from hanging if server is slow or crashed
- Graceful degradation: if no response, just return empty list

### **JSON Newline Terminator:**
```python
# Server knows message is complete when it sees "\n"
while True:
    chunk = recv(4096)
    data += chunk
    if b"\n" in data:
        break
```

**Why newline?**
- TCP is a stream; there's no "message boundary" by default
- Newline tells the receiver "this message is done, parse it"

---

## **Real-World Example Timing**

Assuming:
- Shell to server network latency: ~5ms (localhost)
- ML inference time: ~50-100ms
- JSON parsing: ~1ms

```
Timeline:
0ms    User pauses typing (debounce timer starts)
150ms  Debounce timeout → send request to server
155ms  Server receives request (5ms latency)
156ms  Server starts ML inference
206ms  Server finishes ML (50ms inference)
207ms  Server sends response
212ms  Shell receives response (5ms latency)
213ms  Shell parses JSON, updates suggestions
215ms  Suggestions appear on screen

Total: ~215ms from debounce timeout to user sees suggestions
       (Feels instant to user)
```

---

## **Error Handling & Edge Cases**

### **What if server is down?**
```python
try:
    client.connect(("127.0.0.1", 9999))
except ConnectionRefusedError:
    return []  # Return empty suggestions list
    # Shell continues without suggestions
```

### **What if network is slow?**
```python
socket.settimeout(0.5)  # 500ms max wait
try:
    data = socket.recv(4096)
except socket.timeout:
    return []  # Timeout, return empty
    # Shell continues without hanging
```

### **What if JSON is malformed?**
```python
try:
    obj = json.loads(response)
except json.JSONDecodeError:
    return []  # Invalid JSON, return empty
```

### **What if server returns no suggestions?**
```python
suggestions = obj.get("suggestions", [])
if not suggestions:
    # Show empty completions menu (or none)
    # Shell continues normally
```

---

## **Summary for Presentation**

When you present this to your mentor, highlight:

1. **Two separate processes** communicate via TCP socket
2. **JSON protocol** is simple, human-readable, language-agnostic
3. **Localhost:9999** is used (local machine only, no security concerns)
4. **Non-blocking with timeout** (shell never hangs)
5. **Graceful degradation** (works without server)
6. **Real-time:** debounce prevents network storms, async fetch doesn't block UI
7. **Extensible:** could easily swap server with different implementation

---

**Key Takeaway:**
> IPC is a bridge between two independent programs. The shell sends a request (what command did the user type?), the server processes it (run ML models), and sends back a response (here are the suggestions). All using a simple JSON protocol over a TCP socket.

