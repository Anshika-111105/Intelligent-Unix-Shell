# train_from_csv.py
import pandas as pd
from rapidfuzz import process, fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import joblib
import json
from collections import defaultdict, Counter
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--input", default="powershell_commands.csv", help="CSV or XLSX file with commands")
parser.add_argument("--col", default=None, help="column name that contains commands (optional)")
parser.add_argument("--outdir", default="models", help="folder to save models")
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

# 1) Load dataset (CSV or XLSX)
if args.input.endswith(".xlsx") or args.input.endswith(".xls"):
    df = pd.read_excel(args.input)
else:
    df = pd.read_csv(args.input)

# try to detect command column
if args.col:
    cmd_col = args.col
else:
    candidates = [c for c in df.columns if "command" in c.lower() or "cmd" in c.lower() or "command" in c.lower()]
    cmd_col = candidates[0] if candidates else df.columns[0]

commands = df[cmd_col].astype(str).dropna().tolist()
# Optionally dedupe while preserving order
seen = set()
commands = [c for c in commands if not (c in seen or seen.add(c))]

print(f"Loaded {len(commands)} commands from '{cmd_col}'")

# 2) Typo Fix: we will keep the full known command list (for rapidfuzz)
known_cmds = commands.copy()

# save known commands (used by server for fuzzy)
with open(f"{args.outdir}/known_cmds.json", "w", encoding="utf8") as f:
    json.dump(known_cmds, f, indent=2, ensure_ascii=False)

# 3) Next command predictor (Markov / 1-gram transitions)
transitions = defaultdict(Counter)
for i in range(len(commands) - 1):
    transitions[commands[i]][commands[i+1]] += 1

# Convert to regular dict for saving
transitions_dict = {k: dict(v) for k, v in transitions.items()}
joblib.dump(transitions_dict, f"{args.outdir}/markov_model.pkl")
print("Saved markov_model.pkl")

# 4) TF-IDF for flag/template recommender
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(commands)
joblib.dump(vectorizer, f"{args.outdir}/tfidf_vectorizer.pkl")
joblib.dump(commands, f"{args.outdir}/commands_list.pkl")  # save the corpus
print("Saved tfidf_vectorizer.pkl and commands_list.pkl")

# 5) Quick test function printout
print("\nQuick tests (examples):")
sample = commands[0] if commands else "ls -la"
print(" Sample command:", sample)

# Done
print("\nTraining complete. Models are in:", args.outdir)
