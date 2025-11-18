# Integration Steps: C Shell + ML Suggestion Server

## **Phase 1: Prerequisites & Environment Setup**

### **Step 1.1: Verify Python Dependencies**
```powershell
# Install all required ML and networking packages
python -m pip install prompt-toolkit joblib rapidfuzz scikit-learn numpy
```

**Verification:**
```powershell
python -c "import joblib, rapidfuzz, sklearn, numpy, prompt_toolkit; print('All packages OK')"
```

---

### **Step 1.2: Verify SQLite3 for C Compilation**
```powershell
# Windows: Check if sqlite3 development files are available
# You can download pre-built binaries from: https://www.sqlite.org/download.html

# Alternative: Use MinGW with sqlite3 installed
# MinGW users: pacman -S mingw-w64-x86_64-sqlite3
```

**Verification:**
```powershell
gcc --version  # Ensure GCC is in PATH (MinGW)
```

---

## **Phase 2: Start the ML Suggestion Server**

### **Step 2.1: Start the Server Process**
```powershell
cd C:\Users\hp\OneDrive\Desktop\OS_PBL

# Option A: Full ML Server (requires all deps)
python .\suggestion_server.py

# Option B: Lightweight Test Server (no ML deps)
python .\simple_server.py
```

**Expected Output:**
```
Suggestion server listening on localhost:8888 (default model: Claude Haiku 4.5)
```

**Verification - Server is running:**
```powershell
# In another PowerShell window
Test-NetConnection -ComputerName 127.0.0.1 -Port 8888
# Expected: TcpTestSucceeded : True
```

---

### **Step 2.2: Test Server with Python Client**
```powershell
# In a new PowerShell window (server still running in first window)
python .\test_client.py
```

**Expected Output:**
```json
Command: git staus
Server response: {
  "model": "Claude Haiku 4.5",
  "suggestions": [
    {
      "source": "TypoFixer",
      "suggestion": "git status",
      "confidence": 0.85,
      ...
    },
    ...
  ]
}
```

If this works → **Server is healthy and responding correctly**

---

## **Phase 3: Verify Python UI Integration**

### **Step 3.1: Test Interactive Python Shell**
```powershell
# In a new PowerShell window (server still running)
python .\my_shell_prompt.py
```

**Expected Behavior:**
```
myOS> git st
[suggestion list appears below]
• git status  (Similar to 'git st')
• git stash   (Similar to 'git st')
• git store   (Similar to 'git st')
---

--- Suggestions ---
• git status  (TypoFixer: Possible typo correction)
-------------------

Executing: git st
```

**Test Cases:**
- Type `git ` → should show git-related suggestions
- Type `docker` → should show docker commands
- Type `python` → should show python-related commands
- Type nonsense like `xyz` → should show fallback suggestions

If all work → **Python UI is correctly integrated with server**

---

## **Phase 4: Prepare C Shell for Compilation**

### **Step 4.1: Review core.c**
```bash
# Verify core.c has the TCP client code:
# - Look for get_suggestion_tcp() function
# - Look for SUGGEST_HOST, SUGGEST_PORT, DEFAULT_SUGGEST_MODEL
# - Look for JSON payload construction
```

**Key Functions to Check:**
```c
// Line ~100: get_suggestion_tcp() — TCP socket connection
// Line ~150: get_suggestion() — UDS fallback + TCP fallback
// Line ~300: json_escape() — JSON string escaping
```

---

### **Step 4.2: Windows-Only: Prepare Winsock Initialization (Optional)**
If using MSVC instead of MinGW, add WSAStartup in main():

```c
#if defined(_WIN32) || defined(_WIN64)
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2,2), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed\n");
        return 1;
    }
#endif

// ... rest of main() ...

#if defined(_WIN32) || defined(_WIN64)
    WSACleanup();
#endif
```

(MinGW with -lws2_32 usually doesn't need explicit WSAStartup)

---

## **Phase 5: Compile C Shell**

### **Step 5.1: Windows with MinGW**
```powershell
cd C:\Users\hp\OneDrive\Desktop\OS_PBL

# Compile with SQLite3 and Winsock support
gcc -std=gnu11 -Wall -Wextra core.c -o intelligent_shell.exe -lsqlite3 -lws2_32

# Verify binary was created
ls .\intelligent_shell.exe
```

**If Compilation Fails:**

**Error: "sqlite3.h not found"**
```
Solution: Download sqlite3 dev package or use:
  - https://www.sqlite.org/download.html (get sqlite-amalgamation)
  - Extract and add to MinGW include path, or
  - Use pacman: pacman -S mingw-w64-x86_64-sqlite3
```

**Error: "undefined reference to `sqlite3_*`"**
```
Solution: Link against sqlite3 library:
  gcc core.c -o intelligent_shell.exe -lsqlite3 -lws2_32
  (already in command above)
```

**Error: "-lws2_32 not found"**
```
Solution: MinGW Winsock is built-in, try without explicit link:
  gcc core.c -o intelligent_shell.exe -lsqlite3
  (Winsock headers are in standard MinGW include)
```

---

### **Step 5.2: Linux/macOS Compilation**
```bash
cd ~/Desktop/OS_PBL

# Compile with SQLite3 (no Windows-specific flags)
gcc -std=gnu11 -Wall -Wextra core.c -o intelligent_shell -lsqlite3

# Verify binary
ls -la intelligent_shell
```

---

## **Phase 6: Test C Shell Integration with Server**

### **Step 6.1: Start Server (if not already running)**
```powershell
# Terminal 1: Start ML server
python .\suggetion_server.py
```

### **Step 6.2: Run C Shell**
```powershell
# Terminal 2: Run compiled C shell
.\intelligent_shell.exe
```

**Expected Prompt:**
```
ish>
```

### **Step 6.3: Test Suggestion Integration**
```
ish> git staus

[suggestion-json] {"model":"Claude Haiku 4.5","suggestions":[{"source":"TypoFixer","suggestion":"git status","confidence":0.85,"reason":"Possible typo correction for 'git staus'"},...]}

ish>
```

**Test Cases:**
```
ish> git st
ish> docker
ish> python --help
ish> npm install
ish> exit          # Exit the shell
```

Each command should print a `[suggestion-json]` line with the server response.

**If NO suggestions appear:**
- Verify server is running: `Test-NetConnection -ComputerName 127.0.0.1 -Port 8888`
- Check C shell output for any error messages
- Try the Python client in another window to confirm server responds

---

## **Phase 7: Enhance C Shell (Optional)**

### **Step 7.1: Add JSON Parsing in C (Pretty-Print Suggestions)**

**Current:** Prints raw JSON string
```c
[suggestion-json] {"model":"Claude Haiku 4.5",...}
```

**Desired:** Pretty-printed suggestions
```
[Suggestions from Claude Haiku 4.5]
  • git status (TypoFixer: Possible typo correction)
  • git stash  (Template: Similar to 'git staus')
  • git add    (NextCmd: Commonly follows 'git staus')
```

**To Implement:**
1. Add lightweight C JSON parser (e.g., `cJSON.h` — single file library)
2. Parse server response
3. Extract "suggestions" array
4. Loop and print formatted output

**Option A: Use cJSON**
```c
#include "cJSON.h"

char *response = get_suggestion(line, DEFAULT_SUGGEST_MODEL, 250);
if (response) {
    cJSON *json = cJSON_Parse(response);
    if (json) {
        cJSON *suggestions = cJSON_GetObjectItem(json, "suggestions");
        cJSON_ArrayForEach(item, suggestions) {
            char *suggestion = cJSON_GetStringValue(cJSON_GetObjectItem(item, "suggestion"));
            char *reason = cJSON_GetStringValue(cJSON_GetObjectItem(item, "reason"));
            printf("  • %s (%s)\n", suggestion, reason);
        }
        cJSON_Delete(json);
    }
    free(response);
}
```

**Option B: Simple Regex-Based Parsing (lightweight)**
```c
// Extract "suggestion":"..." values using simple string search
// Trade-off: Less robust but no external library
```

---

### **Step 7.2: Add Server Health Check on Startup**
```c
// In main(), before prompt loop:
char *test = get_suggestion("test", DEFAULT_SUGGEST_MODEL, 100);
if (test) {
    printf("[OK] Connected to suggestion server\n");
    free(test);
} else {
    printf("[WARNING] Suggestion server not responding (shell will work without suggestions)\n");
}
```

---

### **Step 7.3: Log Commands + Suggestions to SQLite**
```c
// Extend log_command() to also store suggestion metadata
void log_command_with_suggestion(const char *cmd, const char *suggestion_json) {
    // INSERT INTO history (cmd, suggestion, timestamp) VALUES (...)
}
```

---

## **Phase 8: End-to-End Testing Checklist**

### **Checklist Before Presenting to Mentor**

- [ ] **Server Startup**
  - [ ] `python .\suggetion_server.py` starts without errors
  - [ ] Prints "Suggestion server listening on localhost:8888"
  - [ ] Stays running (doesn't crash on idle)

- [ ] **Python Client Testing**
  - [ ] `python .\test_client.py` returns valid JSON responses
  - [ ] Suggestions have "source", "suggestion", "confidence", "reason"
  - [ ] Response includes "model": "Claude Haiku 4.5"

- [ ] **Python Interactive UI**
  - [ ] `python .\my_shell_prompt.py` starts
  - [ ] Typing shows live completions
  - [ ] Press Tab/Enter accepts suggestion
  - [ ] Suggestions update as you type (150ms debounce)

- [ ] **C Shell Compilation**
  - [ ] `gcc ... core.c -o intelligent_shell.exe` succeeds
  - [ ] Binary is created (`ls intelligent_shell.exe` works)
  - [ ] File size > 0 KB (not corrupted)

- [ ] **C Shell Execution**
  - [ ] `.\intelligent_shell.exe` starts with `ish>` prompt
  - [ ] Can type commands without crashing
  - [ ] `exit` command quits gracefully

- [ ] **C Shell + Server Integration**
  - [ ] With server running, type `git st` in C shell
  - [ ] `[suggestion-json]` line appears with server response
  - [ ] JSON contains valid suggestions (not error)
  - [ ] Without server, C shell still works (graceful degradation)

- [ ] **SQLite History** (C Shell)
  - [ ] Run C shell, type some commands, exit
  - [ ] File `commands.db` is created
  - [ ] Commands are logged (can verify with sqlite3 CLI)

---

## **Phase 9: Demo Script for Mentor**

### **Script: 5-Minute Live Demo**

**Setup (30 seconds):**
```powershell
# Terminal 1: Start server
python .\suggetion_server.py

# Terminal 2: Start Python UI
python .\my_shell_prompt.py
```

**Demo Part 1 - Python UI (1 minute):**
- Type slowly: `git st` → show live completions
- Type: `docker ps` → show docker suggestions
- Press Tab to accept suggestion
- Press Enter → show final suggestions block

**Demo Part 2 - C Shell (2 minutes):**
```powershell
# Terminal 3: Compile and run C shell
gcc -std=gnu11 -Wall core.c -o intelligent_shell.exe -lsqlite3 -lws2_32
.\intelligent_shell.exe
```

- Type: `git st` → show `[suggestion-json]` output
- Type: `docker` → show suggestion response
- Type: `history` → show SQLite history from previous runs
- Type: `exit` → quit shell gracefully

**Demo Part 3 - Network Resilience (1 minute):**
```powershell
# Kill server (Terminal 1: Ctrl+C)
# Try C shell again (Terminal 3)
ish> git st
# [No suggestion-json, but shell continues]
# Demonstrates graceful degradation
```

**Talking Points:**
- "Without suggestions, shell still works (resilient design)"
- "Suggestions come from ML models trained on PowerShell commands"
- "Communication is via simple JSON over TCP socket (cross-platform)"
- "Real-time debouncing prevents network storms"
- "C shell logs all commands to SQLite"

---

## **Phase 10: Troubleshooting Guide**

### **Problem: C Shell Shows No Suggestions**

**Step 1: Verify Server is Running**
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8888
```
Expected: `TcpTestSucceeded : True`

**Step 2: Test Server with Python Client**
```powershell
python .\test_client.py
```
Expected: JSON responses printed

**Step 3: Check C Shell Compilation**
```powershell
# Re-compile with verbose output
gcc -v -std=gnu11 -Wall -Wextra core.c -o intelligent_shell.exe -lsqlite3 -lws2_32
```

**Step 4: Debug C Shell Socket Connection**
Add temporary debug output to `core.c`:
```c
printf("DEBUG: Attempting to connect to %s:%d\n", SUGGEST_HOST, SUGGEST_PORT);
char *suggest = get_suggestion(line, DEFAULT_SUGGEST_MODEL, 250);
printf("DEBUG: get_suggestion returned: %s\n", suggest ? "OK" : "NULL");
if (suggest) {
    printf("\t[suggestion-json] %s\n", suggest);
    free(suggest);
} else {
    printf("\t[suggestion] failed (server down?)\n");
}
```

---

### **Problem: Server Won't Start**

**ModuleNotFoundError: No module named 'joblib'**
```powershell
python -m pip install joblib rapidfuzz scikit-learn numpy
```

**Address already in use (Port 8888 taken)**
```powershell
# Kill process using port 8888
netstat -ano | findstr :8888
taskkill /PID <PID> /F

# Or use different port (edit suggestion_server.py PORT = 9999)
```

---

### **Problem: C Shell Crashes on Startup**

**Likely Cause: SQLite3 not linked**
```powershell
# Ensure -lsqlite3 is in compile command
gcc core.c -o intelligent_shell.exe -lsqlite3 -lws2_32
```

**Alternative: Remove SQLite dependency for testing**
```c
// Comment out in core.c temporarily:
// if (init_db(DB_PATH) != SQLITE_OK) { ... }
```

---

## **Summary: Collaboration Workflow**

```
User Interaction Flow:

User types in my_shell_prompt.py (Python UI)
    ↓
Live completions from suggestion server
    ↓
User presses Enter
    ↓
Command executed, final suggestions shown
    
---

Alternative: C Shell Integration

User types in intelligent_shell.exe (C program)
    ↓
C program connects to suggestion server via TCP
    ↓
Server responds with JSON suggestions
    ↓
C program prints suggestions as JSON
    ↓
User sees suggestion hint

---

Architecture:

┌─────────────────────┐
│ my_shell_prompt.py  │  (Interactive UI)
│ intelligent_shell   │  (Native Shell)
└──────────┬──────────┘
           │
           │ JSON over TCP :8888
           ↓
    ┌──────────────────┐
    │ suggestion_server│  (ML Backend)
    └──────────────────┘
           ↑
           │
        Models
    (TF-IDF, Markov,
     rapidfuzz)
```

---

**You are now ready to demonstrate the full C Shell + ML Suggestion Server integration!**

Next Steps:
1. Follow Phase 1-6 to get everything running
2. Use Phase 8 checklist before mentor meeting
3. Use Phase 9 demo script during presentation
4. Reference Phase 10 if issues arise
