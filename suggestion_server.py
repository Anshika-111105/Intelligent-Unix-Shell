#!/usr/bin/env python3
import socket, os, json, threading, joblib
from rapidfuzz import process, fuzz
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import traceback

# Use TCP instead of Unix sockets for Windows compatibility
HOST = "localhost"
PORT = 9999

MODELS_DIR = "models"

# Default model for suggestions; can be overridden with env var SUGGEST_DEFAULT_MODEL
DEFAULT_MODEL = os.environ.get("SUGGEST_DEFAULT_MODEL", "Claude Haiku 4.5")

def load_models():
    """Load models with error handling"""
    try:
        vectorizer = joblib.load(f"{MODELS_DIR}/tfidf_vectorizer.pkl")
        commands_list = joblib.load(f"{MODELS_DIR}/commands_list.pkl")
        markov = joblib.load(f"{MODELS_DIR}/markov_model.pkl")
        with open(f"{MODELS_DIR}/known_cmds.json", "r", encoding="utf8") as f:
            known_cmds = json.load(f)

        print(f"Loaded {len(commands_list)} commands, {len(known_cmds)} known commands")
        print(f"Sample commands: {commands_list[:5]}")  
        return vectorizer, commands_list, markov, known_cmds

    except Exception as e:
        print(f"Error loading models: {e}")
        print(traceback.format_exc())
        from sklearn.feature_extraction.text import TfidfVectorizer
        vectorizer = TfidfVectorizer()
        vectorizer.fit([""])
        return vectorizer, [], {}, []

vectorizer, commands_list, markov, known_cmds = load_models()

# -------------------------------------------
# ADDING EXTRA COMMANDS HERE
# -------------------------------------------

extra_commands = [
    # ------------------------------
    # GIT
    "git status", "git add", "git commit", "git push", "git pull",
    "git clone", "git branch", "git checkout", "git merge",
    "git log", "git reset", "git fetch", "git rebase",

    # ------------------------------
    # DOCKER
    "docker ps", "docker run", "docker build", "docker images", "docker logs",
    "docker exec", "docker stats", "docker stop", "docker start", "docker pull",

    # ------------------------------
    # PYTHON
    "python manage.py runserver", "python --version", "python -m pip install",
    "python -m venv env", "python script.py", "python setup.py install",

    # ------------------------------
    # NPM
    "npm install", "npm start", "npm run build", "npm test", "npm update",
    "npm uninstall"
]

# Add to lists if not already present
for cmd in extra_commands:
    if cmd not in commands_list:
        commands_list.append(cmd)
    if cmd not in known_cmds:
        known_cmds.append(cmd)

print(f"Added {len(extra_commands)} extra commands.")
print(f"Total commands: {len(commands_list)} | Total known commands: {len(known_cmds)}")
# -------------------------------------------

def typo_fix(query):
    """Fix typos in PowerShell commands with better matching"""
    if not known_cmds or not query.strip():
        return None, 0.0

    print(f"  TypoFix: searching for '{query}' in {len(known_cmds)} known commands")

    match, score, _ = process.extractOne(query, known_cmds, scorer=fuzz.ratio)
    normalized_score = float(score) / 100.0

    print(f"  TypoFix: best match '{match}' with score {normalized_score}")

    if normalized_score > 0.60:
        return match, normalized_score

    return None, 0.0

def predict_next(query):
    """Predict next PowerShell command in sequence"""
    if not query.strip():
        return []

    print(f"  NextCmd: checking Markov for '{query}'")

    if query in markov:
        nxts = markov[query]
        top_next = sorted(nxts.items(), key=lambda x: x[1], reverse=True)[:3]
        results = []
        total = sum(nxts.values())

        for nxt, count in top_next:
            confidence = float(count) / total
            if confidence > 0.05:
                results.append((nxt, confidence))

        print(f"  NextCmd: found {len(results)} next commands")
        return results
    print(f"  NextCmd: no Markov transitions for '{query}'")
    return []

def recommend_templates(query, topk=5):
    """Recommend similar PowerShell command templates"""
    if not commands_list or not query.strip():
        return []

    try:
        print(f"  Template: finding similar to '{query}'")
        qv = vectorizer.transform([query])
        sims = cosine_similarity(qv, vectorizer.transform(commands_list)).flatten()
        idx = sims.argsort()[-topk:][::-1]
        results = []
        for i in idx:
            if sims[i] > 0.05:
                results.append((commands_list[i], float(sims[i])))

        print(f"  Template: found {len(results)} similar commands")
        return results
    except Exception as e:
        print(f"Template recommendation error: {e}")
        return []

def rank_and_merge(query):
    """Merge suggestions with PowerShell-specific logic"""
    if not query or not query.strip():
        return [{"source": "Info", "suggestion": "Type a command to get suggestions", "confidence": 0.0, "reason": "Empty input"}]

    query = query.strip()
    print(f"Processing query: '{query}'")

    typo_s, typo_conf = typo_fix(query)
    next_commands = predict_next(query)
    templ = recommend_templates(query, topk=5)

    items = []

    if typo_s and typo_conf > 0.6:
        items.append({
            "source": "TypoFixer",
            "suggestion": typo_s,
            "confidence": round(typo_conf, 2),
            "reason": f"Possible typo correction for '{query}'"
        })

    if next_commands:
        for next_cmd, next_conf in next_commands:
            items.append({
                "source": "NextCmd",
                "suggestion": next_cmd,
                "confidence": round(next_conf, 2),
                "reason": f"Commonly follows '{query}'"
            })

    for s, c in templ:
        if s.lower() != query.lower():
            items.append({
                "source": "Template",
                "suggestion": s,
                "confidence": round(c, 2),
                "reason": f"Similar to '{query}'"
            })

    if not items and len(query) > 1:
        print(f"  Fallback: searching for partial matches to '{query}'")
        for cmd in known_cmds:
            if query.lower() in cmd.lower() and cmd.lower() != query.lower():
                items.append({
                    "source": "Partial",
                    "suggestion": cmd,
                    "confidence": 0.3,
                    "reason": f"Contains '{query}'"
                })
                if len(items) >= 3:
                    break

    seen = {}
    for it in items:
        s = it["suggestion"]
        if s not in seen or it["confidence"] > seen[s]["confidence"]:
            seen[s] = it

    merged = sorted(seen.values(), key=lambda x: x["confidence"], reverse=True)
    result = merged[:5]
    print(f"  Final: returning {len(result)} suggestions")
    return result

def handle_conn(conn):
    try:
        data = b""
        conn.settimeout(1.0)
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
        except socket.timeout:
            pass

        if not data:
            conn.close()
            return

        raw = data.decode().strip()
        print(f"Received: {raw}")

        query = raw
        model_req = None
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                query = obj.get("cmd", "")
                model_req = obj.get("model")
        except Exception:
            pass

        model_used = model_req if model_req else DEFAULT_MODEL
        resp = rank_and_merge(query)

        response_payload = {"model": model_used, "suggestions": resp}
        response_data = (json.dumps(response_payload) + "\n").encode()
        conn.sendall(response_data)

    except Exception as e:
        print(f"Error handling connection: {e}")
        try:
            error_resp = json.dumps({"error": str(e)}) + "\n"
            conn.sendall(error_resp.encode())
        except:
            pass
    finally:
        try:
            conn.close()
        except:
            pass

def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"Suggestion server listening on {HOST}:{PORT} (default model: {DEFAULT_MODEL})")
    try:
        while True:
            conn, addr = server.accept()
            print(f"Connection from {addr}")
            t = threading.Thread(target=handle_conn, args=(conn,))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        server.close()

if __name__ == "__main__":
    run_server()
