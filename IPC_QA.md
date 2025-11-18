# IPC (Inter-Process Communication) - Important Questions & Answers

## **Q1: What is IPC and why do we need it in this project?**

**Answer:**
IPC (Inter-Process Communication) is a mechanism that allows two or more separate processes to communicate with each other and share data.

**In this project:**
- **Process 1:** Shell (my_shell_prompt.py or core.c)
- **Process 2:** ML Suggestion Server (suggestion_server.py)
- **Why we need it:** 
  - Separation of concerns (shell ≠ ML)
  - If server crashes, shell still works
  - Server can be updated independently
  - Could run on different machines
  - Simpler than embedding Python in C

---

## **Q2: What IPC method are we using and why?**

**Answer:**
We're using **TCP (Transmission Control Protocol) sockets** over localhost.

**Why TCP instead of alternatives?**
| Method | Pros | Cons | Used? |
|--------|------|------|-------|
| **TCP Socket** | Cross-platform, reliable, ordered | Slightly more overhead | ✅ YES |
| **Unix Domain Socket** | Very fast, local only | Doesn't work on Windows | No (fallback) |
| **Named Pipes** | Windows-native | Unix incompatible | No |
| **Message Queues** | Decoupled, robust | Overkill, complex | No |
| **HTTP REST** | Standard, easy | More overhead than raw TCP | No |
| **Shared Memory** | Very fast | Complex sync, OS-specific | No |
| **Files** | Simple | Slow, not real-time | No |

**Our choice:** TCP is the best balance of simplicity, performance, and cross-platform support.

---

## **Q3: What is the protocol/format used for communication?**

**Answer:**
We use **JSON** over TCP with newline termination.

**Request format (Shell → Server):**
```json
{
  "cmd": "git st",
  "model": "Claude Haiku 4.5"
}
\n
```

**Response format (Server → Shell):**
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
    }
  ]
}
\n
```

**Why JSON?**
- Human-readable (easy debugging)
- Language-agnostic (any language can parse it)
- Self-documenting (field names clear)
- Standard format (no custom parsing)

---

## **Q4: What port number are we using and why?**

**Answer:**
We use **port 9999** (changed from 8888 to avoid conflicts).

**Port details:**
```
Host: 127.0.0.1 (localhost)
Port: 9999
Address: tcp://127.0.0.1:9999
```

**Why 9999?**
- Above 1024 (no root/admin required)
- Not a standard service port (less likely to conflict)
- Easy to remember
- Can be changed in code if needed

**Why localhost (127.0.0.1)?**
- Local machine only (no network exposure)
- No security concerns
- Fast (no actual network latency)
- Works offline

---

## **Q5: How does the shell connect to the server?**

**Answer:**
The shell creates a TCP socket and connects to the server.

**Python code:**
```python
import socket
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 9999))
```

**C code:**
```c
int sock = socket(AF_INET, SOCK_STREAM, 0);
struct sockaddr_in serv;
serv.sin_family = AF_INET;
serv.sin_port = htons(9999);
inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr);
connect(sock, (struct sockaddr*)&serv, sizeof(serv));
```

**Connection lifecycle:**
1. Shell creates socket
2. Shell connects to server (tries to reach 127.0.0.1:9999)
3. Server accepts connection
4. Shell sends request
5. Server sends response
6. Connection closes

---

## **Q6: What happens if the server is down/not running?**

**Answer:**
The shell **gracefully degrades** — it continues to work without suggestions.

**Code handling:**
```python
try:
    client.connect(("127.0.0.1", 9999))
    # ... rest of code
except ConnectionRefusedError:
    return []  # Return empty suggestions
    # Shell continues, just no suggestions shown
```

**User experience:**
- Server down → suggestions don't appear
- Shell still works normally
- Commands still execute
- Once server restarts, suggestions reappear

**Advantage:** The shell is **resilient** — doesn't depend on server.

---

## **Q7: What is the timeout mechanism and why is it needed?**

**Answer:**
Timeout prevents the shell from hanging if the server is slow or unresponsive.

**Python implementation:**
```python
client.settimeout(0.5)  # 500ms timeout
try:
    data = client.recv(4096)
except socket.timeout:
    return []  # No response in 500ms, give up and return empty
```

**C implementation:**
```c
fd_set rfds;
FD_ZERO(&rfds);
FD_SET(sock, &rfds);
struct timeval tv;
tv.tv_sec = 0;
tv.tv_usec = 500000;  // 500ms timeout
select(sock+1, &rfds, NULL, NULL, &tv);
```

**Why timeout?**
- Shell never blocks indefinitely
- User experience stays responsive
- If server is slow, shell doesn't freeze
- Prevents "hanging" shell

**Real scenario:**
```
User types "git st"
Shell sends request → server
[waiting for response...]
500ms passes → timeout → return empty suggestions
User sees shell prompt immediately (no suggestions, but works)
```

---

## **Q8: What does the debounce mechanism do?**

**Answer:**
Debounce waits for the user to stop typing before sending a request to the server.

**How it works:**
```
User types: g-i-t-[space]-s-t
            └─────────────── Shell waits for 150ms of no input
                         Then sends ONE request to server
```

**Without debounce (bad):**
```
Keystroke 1: g    → Send request (server query)
Keystroke 2: i    → Send request (server query)
Keystroke 3: t    → Send request (server query)
Keystroke 4: sp   → Send request (server query)
Keystroke 5: s    → Send request (server query)
Keystroke 6: t    → Send request (server query)
Total: 6 requests for "git st" (wasteful!)
```

**With debounce (good):**
```
Keystrokes: g-i-t-sp-s-t
Then: [150ms no input]
Result: Send ONE request for "git st" (efficient!)
```

**Code (Python):**
```python
# In suggestion_worker():
DEBOUNCE = 0.15  # 150ms
t0 = time.time()
while time.time() - t0 < DEBOUNCE:
    try:
        last = input_q.get(timeout=DEBOUNCE - (time.time() - t0))
        t0 = time.time()  # Reset timer if new input
    except queue.Empty:
        break
# After debounce timeout, send request
```

**Benefits:**
- Reduces network traffic
- Reduces server load
- Faster response (fewer requests processed)
- User doesn't notice delay (150ms is imperceptible)

---

## **Q9: How does the server handle multiple clients?**

**Answer:**
The server uses **threading** to handle multiple concurrent connections.

**Server code:**
```python
server.listen(5)  # Allow up to 5 queued connections
while True:
    conn, addr = server.accept()  # Wait for connection
    t = threading.Thread(target=handle_conn, args=(conn,), daemon=True)
    t.start()  # Handle client in separate thread
    # Server loops back to accept next client
```

**What happens:**
```
Client 1 connects → Thread 1 starts → handles Client 1
Server loops back
Client 2 connects → Thread 2 starts → handles Client 2
...
Both threads run in parallel (concurrent processing)
```

**Benefits:**
- Multiple clients can connect simultaneously
- Server doesn't block on one slow client
- Threads are daemon (die if server dies)

**Real scenario:**
```
Shell 1 sends: "git st"
[Server thread 1 processes...]
Shell 2 sends: "docker ps" (at same time)
[Server thread 2 processes...]
Both requests processed in parallel
```

---

## **Q10: What happens if the network is slow?**

**Answer:**
The shell uses a **timeout** to prevent indefinite waiting.

**Scenario 1: Network is slow but responds in time**
```
Shell sends request
[Waiting...]
150ms → Server responds
Shell shows suggestions
(Works fine, feels slow but acceptable)
```

**Scenario 2: Network is very slow (>500ms)**
```
Shell sends request
[Waiting...]
500ms → Timeout triggers
Shell returns empty suggestions
User sees shell prompt immediately
(No suggestions, but shell doesn't freeze)
```

**Code:**
```python
socket.settimeout(0.5)  # 500ms max wait
try:
    data = socket.recv(4096)
except socket.timeout:
    return []  # Give up, return empty
```

---

## **Q11: Can the server and shell run on different machines?**

**Answer:**
**Technically yes, but not recommended in this setup.**

**Current setup (local only):**
```
127.0.0.1:9999  ← Only accessible on this machine
Shell connects to: 127.0.0.1 (localhost)
```

**To run on different machines, you would:**
1. Change server to listen on `0.0.0.0` instead of `127.0.0.1`
2. Change shell to connect to server's IP address
3. Add authentication/encryption (security)
4. Handle network latency (much higher)

**Example:**
```python
# Server on machine A (192.168.1.100)
server.bind(("0.0.0.0", 9999))  # Listen on all interfaces

# Shell on machine B
client.connect(("192.168.1.100", 9999))  # Connect to server's IP
```

**Why not recommended for this project:**
- Local is faster and simpler
- No security/authentication needed
- Works offline
- No firewall issues
- Lower latency

---

## **Q12: How is JSON parsing handled on both sides?**

**Answer:**
Both sides use language-native JSON libraries.

**Server (Python):**
```python
import json
raw = '{"cmd":"git st","model":"Claude Haiku 4.5"}'
obj = json.loads(raw)  # Parse JSON string to dict
query = obj.get("cmd")  # Extract field
```

**Shell (Python):**
```python
import json
response = '{"model":"Claude Haiku 4.5","suggestions":[...]}'
obj = json.loads(response.decode().strip())  # Parse
suggestions = obj.get("suggestions", [])
```

**C Shell:**
Would need a library like `cJSON`:
```c
#include "cJSON.h"
cJSON *json = cJSON_Parse(response);
cJSON *suggestions = cJSON_GetObjectItem(json, "suggestions");
cJSON *item = NULL;
cJSON_ArrayForEach(item, suggestions) {
    char *suggestion = cJSON_GetStringValue(cJSON_GetObjectItem(item, "suggestion"));
    printf("  • %s\n", suggestion);
}
cJSON_Delete(json);
```

**Why JSON?**
- No custom parsing needed
- Built-in library support
- Easy to debug
- Self-explanatory

---

## **Q13: What happens if JSON is malformed/invalid?**

**Answer:**
The shell catches the error and returns empty suggestions.

**Code:**
```python
try:
    obj = json.loads(response)
    suggestions = obj.get("suggestions", [])
except json.JSONDecodeError:
    print("Invalid JSON response")
    return []  # Return empty, don't crash
```

**Scenarios:**
1. **Server sends broken JSON:** Shell catches error → returns [] → no suggestions
2. **Network corruption:** Socket receives garbage → JSON parse fails → returns []
3. **Server crashes mid-send:** Incomplete JSON → parse fails → returns []

**Result:** Shell continues working, just no suggestions (graceful degradation).

---

## **Q14: What is the complete lifecycle of a single request/response?**

**Answer:**
Here's the complete flow:

```
┌─────────────────────────────────────────────────────────────┐
│ SHELL SIDE                                                   │
├─────────────────────────────────────────────────────────────┤
1. User types "git st"
   ↓
2. Buffer change event triggered
   ↓
3. Text pushed to queue: input_q.put_nowait("git st")
   ↓
4. Background worker sees queue not empty
   ↓
5. Extract latest text: "git st"
   ↓
6. Wait 150ms for more typing (debounce)
   ↓
7. 150ms passes, no more input
   ↓
8. Create socket: socket.socket(AF_INET, SOCK_STREAM)
   ↓
9. Connect: client.connect(("127.0.0.1", 9999))
   ↓
10. Create JSON: {"cmd":"git st","model":"Claude Haiku 4.5"}
    ↓
11. Send: client.sendall(json_bytes + "\n")
    ↓
12. Set timeout: client.settimeout(0.5)
    ↓
13. Wait for response: data = client.recv(4096)
    ↓
14. Response arrives (within 500ms)
    ↓
15. Parse JSON: obj = json.loads(response)
    ↓
16. Extract suggestions: suggestions = obj["suggestions"]
    ↓
17. Update shared storage: shared.update("git st", suggestions)
    ↓
18. Close socket: client.close()
    ↓
19. LiveCompleter reads shared.suggestions
    ↓
20. Yields Completion objects with suggestions + explanations
    ↓
21. prompt_toolkit displays suggestions menu
    ↓
22. User sees:
    ┌─────────────────────────┐
    │ git status  ◄ Typo fix  │
    │ git stash   ◄ Similar   │
    └─────────────────────────┘

└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SERVER SIDE                                                  │
├─────────────────────────────────────────────────────────────┤
1. Server listening on localhost:9999
   ↓
2. Accept connection: conn, addr = server.accept()
   ↓
3. Print: "Connection from 127.0.0.1:XXXXX"
   ↓
4. Receive data: data = conn.recv(4096)
   ↓
5. Request data: {"cmd":"git st","model":"Claude Haiku 4.5"}
   ↓
6. Parse JSON: obj = json.loads(data.decode().strip())
   ↓
7. Extract: query = obj.get("cmd") = "git st"
   ↓
8. Run ML engines in parallel:
   ├─ typo_fix("git st") → "git status" (0.85)
   ├─ predict_next("git st") → "git add" (0.72)
   └─ recommend_templates("git st") → "git stash" (0.65)
   ↓
9. Merge results: suggestions = [typo, template, next_cmd]
   ↓
10. Create response JSON:
    {"model":"Claude Haiku 4.5","suggestions":[...]}
    ↓
11. Encode and send: conn.sendall(json_bytes + "\n")
    ↓
12. Close connection: conn.close()
    ↓
13. Server loops back to accept next connection

└─────────────────────────────────────────────────────────────┘

TOTAL TIME: ~250-300ms
- Debounce: 150ms
- Network round-trip: ~10ms (localhost)
- ML inference: 50-100ms
- JSON parsing: ~1ms
- Display: ~1ms
```

---

## **Q15: What are the security implications of this IPC design?**

**Answer:**
**Current setup is safe because:**

1. **Localhost only (127.0.0.1):**
   - Only accessible from the local machine
   - Cannot be reached from other machines
   - No remote attack surface

2. **No authentication:**
   - Safe for local development
   - No need for passwords/tokens
   - Assumes trusted user

3. **No encryption:**
   - Safe for local/private network
   - No sensitive data in transmission
   - Commands are just user input

**If running on network, would need:**
```python
# Add firewall rules
# Add authentication (API key/token)
# Use TLS/SSL encryption
# Validate/sanitize input
# Rate limiting
# Access control lists
```

**For this project: Safe as-is (local only).**

---

## **Q16: How do you debug IPC issues?**

**Answer:**
Use these debugging techniques:

**1. Check if server is running:**
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 9999
# Expected: TcpTestSucceeded : True
```

**2. Test server directly (simple test):**
```python
python .\test_server.py
```

**3. Check server logs (look for connection messages):**
```
Connection from 127.0.0.1:54321
Received: {"cmd":"git st",...}
Sent: {"model":"...","suggestions":[...]}
```

**4. Check shell logs (add debug prints):**
```python
print(f"Connecting to 127.0.0.1:9999...")
print(f"Sending: {payload}")
print(f"Received: {response}")
print(f"Parsed suggestions: {suggestions}")
```

**5. Packet sniffer (advanced):**
```powershell
# Windows: netstat -an | findstr 9999
netstat -an | findstr :9999
```

**6. Common issues:**
| Issue | Check |
|-------|-------|
| "Connection refused" | Server not running |
| Timeout | Server slow or crashed |
| No suggestions | Server returns empty list |
| Invalid JSON error | Server response malformed |
| "Port already in use" | Kill old process or change port |

---

## **Q17: Can the protocol be extended/modified?**

**Answer:**
**Yes, easily.** The JSON protocol is flexible.

**Example 1: Add confidence threshold:**
```json
{
  "cmd": "git st",
  "model": "Claude Haiku 4.5",
  "min_confidence": 0.5
}
```

**Example 2: Request specific engine:**
```json
{
  "cmd": "git st",
  "engines": ["typo_fix", "template"]  // Skip "predict_next"
}
```

**Example 3: Get explanations:**
```json
{
  "cmd": "git st",
  "include_docs": true
}
```

**Server would respond with:**
```json
{
  "model": "Claude Haiku 4.5",
  "suggestions": [
    {
      "suggestion": "git status",
      "confidence": 0.85,
      "reason": "Typo fix",
      "docs": "Show current repository status"  // NEW
    }
  ]
}
```

**To implement:**
1. Add field to request JSON
2. Server parses and uses it
3. Shell doesn't break (ignores unknown fields)

**Advantage:** Backward compatible (old shells still work).

---

## **Q18: What's the difference between TCP and UDP for this use case?**

**Answer:**

| Aspect | TCP | UDP |
|--------|-----|-----|
| **Reliability** | Guaranteed delivery | Best-effort (may drop) |
| **Order** | In-order delivery | Out-of-order OK |
| **Connection** | Connection-oriented | Connectionless |
| **Speed** | Slightly slower | Faster |
| **Good for** | Requests that must arrive | Real-time audio/video |
| **Our use case** | ✅ Better (need all data) | ❌ Bad (suggestions might drop) |

**Why we chose TCP:**
- Suggestions MUST arrive completely
- One dropped packet = missing suggestions
- Data integrity is important
- Slight latency trade-off is acceptable

**If we used UDP:**
```
Shell: "git st"
Server: "git status" (packet 1/3)
Server: "git stash" (packet 2/3) [DROPPED]
Server: "git add" (packet 3/3)
Shell receives: incomplete suggestions
```
Bad! We'd lose "git stash".

---

## **Q19: How would you test the IPC connection?**

**Answer:**
Multiple testing approaches:

**1. Unit test (server responds):**
```python
def test_server_responds():
    response = get_suggestions("git st")
    assert isinstance(response, list)
    assert len(response) > 0
    assert response[0].get("suggestion") is not None
```

**2. Integration test (end-to-end):**
```python
# Start server
# Run shell
# Type command
# Assert suggestions appear
# Kill server
# Assert shell still works
```

**3. Stress test (many requests):**
```python
for i in range(1000):
    response = get_suggestions(f"test{i}")
    # Check no crashes
```

**4. Timeout test:**
```python
# Kill server while shell is waiting
# Shell should timeout after 500ms
# Should not hang
```

**5. Manual test:**
```powershell
# Terminal 1: python .\suggetion_server.py
# Terminal 2: python .\my_shell_prompt.py
# Type: git st
# Visually confirm suggestions appear
```

---

## **Q20: What would you change if requirements changed?**

**Answer:**

**If requirement: "Support 1000 concurrent users"**
- Current: Single server thread-per-client (limited)
- Solution: Use async (asyncio), multiprocessing, or distributed architecture

**If requirement: "Support remote connections"**
- Current: localhost only (127.0.0.1)
- Solution: Bind to 0.0.0.0, add authentication, use TLS/SSL, firewall rules

**If requirement: "Persistence (cache suggestions)"**
- Current: No caching
- Solution: Add Redis or database, cache by command prefix

**If requirement: "Faster suggestions"**
- Current: 50-100ms ML inference
- Solution: Pre-compute suggestions, use faster models, GPU acceleration

**If requirement: "Custom ML model"**
- Current: scikit-learn models
- Solution: Swap model loading, keep same protocol (backward compatible)

**If requirement: "Real-time updates"**
- Current: Request-response (pull)
- Solution: WebSocket (push) for live updates

**Key principle:** Keep the JSON protocol, swap implementations (servers, clients, models) independently.

---

## **Summary: 5 Most Important Points**

1. **IPC = Bridge**: Two processes communicate via TCP socket
2. **Protocol = JSON**: Simple, readable, language-agnostic
3. **Reliability = Timeout**: Shell never hangs (500ms max wait)
4. **Resilience = Degradation**: Server down = no suggestions, shell still works
5. **Performance = Debounce**: 150ms wait prevents network storms

---

## **Quick Reference**

```
Connection:     tcp://127.0.0.1:9999
Protocol:       JSON + newline
Request:        {"cmd": "...", "model": "..."}
Response:       {"model": "...", "suggestions": [...]}
Timeout:        500ms
Debounce:       150ms
Threads:        One per client on server
Error handling: Graceful degradation (return empty list)
```

---

**Ready to answer questions from your mentor!** 🎓
