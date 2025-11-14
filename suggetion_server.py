#!/usr/bin/env python3
import socket, os, json, threading, joblib
from rapidfuzz import process, fuzz
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import traceback

# Use TCP instead of Unix sockets for Windows compatibility
HOST = "localhost"
PORT = 8888

MODELS_DIR = "models"

def load_models():
    """Load models with error handling"""
    try:
        vectorizer = joblib.load(f"{MODELS_DIR}/tfidf_vectorizer.pkl")
        commands_list = joblib.load(f"{MODELS_DIR}/commands_list.pkl")
        markov = joblib.load(f"{MODELS_DIR}/markov_model.pkl")
        with open(f"{MODELS_DIR}/known_cmds.json", "r", encoding="utf8") as f:
            known_cmds = json.load(f)
        print(f"Loaded {len(commands_list)} commands, {len(known_cmds)} known commands")
        print(f"Sample commands: {commands_list[:5]}")  # Debug: show sample commands
        return vectorizer, commands_list, markov, known_cmds
    except Exception as e:
        print(f"Error loading models: {e}")
        print(traceback.format_exc())
        # Return empty models as fallback
        from sklearn.feature_extraction.text import TfidfVectorizer
        vectorizer = TfidfVectorizer()
        vectorizer.fit([""])  # Fit with empty data
        return vectorizer, [], {}, []

vectorizer, commands_list, markov, known_cmds = load_models()

def typo_fix(query):
    """Fix typos in PowerShell commands with better matching"""
    if not known_cmds or not query.strip():
        return None, 0.0
    
    print(f"  TypoFix: searching for '{query}' in {len(known_cmds)} known commands")
    
    # Try different matching strategies
    match, score, _ = process.extractOne(query, known_cmds, scorer=fuzz.partial_ratio)
    normalized_score = float(score) / 100.0
    
    print(f"  TypoFix: best match '{match}' with score {normalized_score}")
    
    # Lower threshold for better matching
    if normalized_score > 0.6:  # Reduced from 0.7
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
            if sims[i] > 0.05:  # Lower threshold
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
    
    # Add typo fix if confident
    if typo_s and typo_conf > 0.6:  # Reduced threshold
        items.append({
            "source": "TypoFixer", 
            "suggestion": typo_s, 
            "confidence": round(typo_conf, 2),
            "reason": f"Possible typo correction for '{query}'"
        })
    
    # Add next command predictions
    if next_commands:
        for next_cmd, next_conf in next_commands:
            items.append({
                "source": "NextCmd", 
                "suggestion": next_cmd, 
                "confidence": round(next_conf, 2),
                "reason": f"Commonly follows '{query}'"
            })
    
    # Add template suggestions (filter out exact matches)
    for s, c in templ:
        if s.lower() != query.lower():  # Don't suggest the same command
            items.append({
                "source": "Template", 
                "suggestion": s, 
                "confidence": round(c, 2),
                "reason": f"Similar to '{query}'"
            })
    
    # If no good suggestions, provide partial matches
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
                if len(items) >= 3:  # Limit fallback results
                    break
    
    # Dedupe and sort by confidence
    seen = {}
    for it in items:
        s = it["suggestion"]
        if s not in seen or it["confidence"] > seen[s]["confidence"]:
            seen[s] = it
    
    merged = sorted(seen.values(), key=lambda x: x["confidence"], reverse=True)
    result = merged[:5]  # Return top 5
    
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
        
        try:
            obj = json.loads(raw)
            query = obj.get("cmd","")
        except:
            query = raw
            
        resp = rank_and_merge(query)
        response_data = (json.dumps(resp) + "\n").encode()
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
    print(f"Suggestion server listening on {HOST}:{PORT}")
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
    