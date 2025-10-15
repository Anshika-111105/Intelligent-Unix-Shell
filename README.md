# NeuroShell: Blending Unix Power with Machine Learning Intelligence

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey.svg)]()

**A self-learning Unix shell that combines low-level systems programming with machine learning to provide intelligent, context-aware command assistance.**

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [Testing](#testing)
- [Team](#team)
- [License](#license)

## 🎯 Overview

NeuroShell is an intelligent command-line shell that goes beyond traditional shells like bash or zsh. By integrating POSIX-compliant systems programming with machine learning, NeuroShell learns from your command history to provide smart suggestions, correct typos, and predict your next commands.

### Why NeuroShell?

Traditional shells are powerful but lack intelligent guidance. NeuroShell addresses common pain points:

- **Typo Correction**: Automatically suggests fixes for mistyped commands (e.g., `gti` → `git`)
- **Command Prediction**: Predicts your next command based on context and history
- **Smart Recommendations**: Suggests relevant flags and command templates
- **Explainable AI**: Shows why each suggestion was made
- **Privacy-First**: Operates entirely offline with no cloud dependency

## ✨ Features

### Shell Core (C, POSIX)
- Full command parsing with support for pipes (`|`), redirections (`<`, `>`, `>>`), and sequencing (`;`)
- Process management using `fork()` and `execvp()`
- Job control with foreground/background execution
- Signal handling (`SIGINT`, `SIGTSTP`, `SIGCHLD`)
- Built-in commands: `cd`, `exit`, `export`, `alias`, `history`, and more
- SQLite-based history with rich metadata (timestamps, working directory, exit status, tags)

### Suggestion Engine (Python, ML)
- **Typo Fixer**: Uses Damerau-Levenshtein distance for intelligent command correction
- **Next Command Predictor**: N-gram/Markov models trained on your command history
- **Flag/Template Recommender**: TF-IDF and cosine similarity for context-aware suggestions
- **Confidence Scoring**: Each suggestion comes with a confidence score and rationale
- **Self-Learning**: Continuously improves from local usage patterns

### Communication
- Unix domain sockets for efficient IPC between shell and suggestion engine
- JSON-based message protocol for structured data exchange

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                         User                             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Shell Core (C, POSIX)                       │
│  • REPL Loop                                             │
│  • Command Parser                                        │
│  • Process Manager (fork/exec)                           │
│  • Job Control & Signals                                 │
│  • Built-in Commands                                     │
└──────────┬──────────────────────┬───────────────────────┘
           │                      │
           │ Unix Socket          │
           │ (JSON)               │
           │                      ▼
           │          ┌────────────────────────────┐
           │          │  Suggestion Engine (Python) │
           │          │  • Typo Fixer              │
           │          │  • Command Predictor       │
           │          │  • Flag Recommender        │
           │          │  • Ranking & Scoring       │
           │          └──────────┬─────────────────┘
           │                     │
           ▼                     ▼
    ┌──────────────────────────────────┐
    │     SQLite Database               │
    │  • Command History                │
    │  • Timestamps & Metadata          │
    │  • Training Data                  │
    └──────────────────────────────────┘
```

## 🚀 Installation

### Prerequisites

- Linux (Ubuntu/Arch) or macOS
- GCC/Clang compiler
- Python 3.10+
- SQLite3
- Make

### Build Steps

```bash
# Clone the repository
git clone https://github.com/kernel-mind/neuroshell.git
cd neuroshell

# Build the shell core
make

# Install Python dependencies
pip install -r requirements.txt

# Run NeuroShell
./neuroshell
```

## 💻 Usage

### Basic Commands

```bash
# Start NeuroShell
./neuroshell

# Use it like any Unix shell
$ ls -la
$ cd projects
$ git status

# Typo correction in action
$ gti status
→ Did you mean: git status? [confidence: 95%]

# Next command prediction
$ git add .
→ Suggestions: git commit -m, git status, git push
```

### Built-in Commands

- `history` - View command history
- `alias name='command'` - Create command aliases
- `export VAR=value` - Set environment variables
- `cd [directory]` - Change directory
- `exit` - Exit the shell

### Configuration

NeuroShell stores its configuration and history in `~/.neuroshell/`:
- `history.db` - SQLite database with command history
- `config.json` - User preferences and settings

## 🛠 Development

### Project Structure

```
neuroshell/
├── src/
│   ├── shell/          # C shell core
│   │   ├── main.c
│   │   ├── parser.c
│   │   ├── executor.c
│   │   ├── builtins.c
│   │   └── history.c
│   └── ml/             # Python suggestion engine
│       ├── engine.py
│       ├── typo_fixer.py
│       ├── predictor.py
│       └── recommender.py
├── tests/
│   ├── shell/          # bats tests
│   └── ml/             # pytest tests
├── docs/
├── Makefile
└── requirements.txt
```

### Building from Source

```bash
# Debug build
make debug

# Release build
make release

# Clean build artifacts
make clean
```

### Technologies Used

- **Languages**: C (POSIX), Python 3.10+
- **Libraries**: SQLite3, rapidfuzz, numpy, scikit-learn (optional)
- **Tools**: gcc/clang, make, valgrind, gdb, bats, pytest

## 🧪 Testing

```bash
# Run all tests
make test

# Shell core tests (bats)
make test-shell

# ML engine tests (pytest)
make test-ml

# Memory leak detection
make valgrind
```

## 👥 Team

**Team Name**: Kernel Mind

| Member | Role | Contact |
|--------|------|---------|
| **Anshika Saklani** | Team Lead | anshikasaklani894@gmail.com |
| **Rakhi Bisht** | Developer | rakhibisht24122004@gmail.com |
| **Akriti Rawat** | Developer | akritirawat12345@gmail.com |
| **Ayush Chand** | Developer | ayushchand862@gmail.com |

## 📚 References

- [POSIX Standard - IEEE Std 1003.1](https://pubs.opengroup.org/onlinepubs/9699919799/)
- [Advanced Programming in the UNIX Environment](https://www.apuebook.com/)
- [GNU Readline Library](https://tiswww.case.edu/php/chet/readline/rltop.html)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [RapidFuzz: Fuzzy String Matching](https://maxbachmann.github.io/RapidFuzz/)
- [The Linux Programming Interface](https://man7.org/tlpi/)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🐛 Issues

Found a bug or have a feature request? Please open an issue on our [GitHub repository](https://github.com/kernel-mind/neuroshell/issues).

---

**NeuroShell** - Making the command line smarter, one command at a time.
