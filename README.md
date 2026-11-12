# 🚀 agy-tracker

> Lightweight session tracker, interactive web dashboard, and fast resume launcher for **Google Antigravity CLI (`agy`)**.

`agy-tracker` keeps a persistent SQLite index of all your Antigravity CLI pair-programming sessions. It generates interactive HTML and Markdown dashboards, registers desktop URL handlers (`agy://resume/...`), and enables resuming any past conversation in the terminal with a single command.

---

## ✨ Features

- **⚡ Fast Session Resuming**: Resume any conversation by list number (`agy-tracker resume 1`) or UUID, either inline in your current terminal or in a new terminal window (`-w`).
- **🛡️ Danger Mode Support**: Pass `--danger` / `-d` directly (`agy-tracker -d resume 3`) to bypass command authorization checks when resuming.
- **📊 Interactive Web Dashboard**: Generates a self-contained, responsive HTML dashboard (`chat_history.html`) with instant full-text search, workspace filtering, and one-click launch buttons.
- **📄 Markdown Catalog (`CHATS.md`)**: Automatically maintained markdown table with direct file links to session transcripts and shortcut scripts.
- **🔗 Custom Protocol Handler (`agy://`)**: Registers a Linux desktop URL scheme handler so clicking any `agy://resume/<ID>` link immediately spawns the conversation in your terminal.
- **🧹 Noise Reduction & Cleaning**: Automatically identifies and filters out subagent delegation loops, system design interview mocks, and ephemeral benchmark traces (`agy-tracker clean`).
- **🏷️ Conversation Renaming**: Custom title editing to keep history readable and organized (`agy-tracker rename 1 "Feature Implementation"`).

---

## 📦 Installation

Clone the repository and run the automated installer:

```bash
git clone https://github.com/singhvi28/agy-tracker.git
cd agy-tracker
./install.sh
```

The installer will:
1. Symlink `agy-tracker` and `agy-open-url` into `~/.local/bin/`.
2. Register the `agy://` and `antigravity://` desktop protocol scheme handlers in `~/.local/share/applications/`.
3. Perform an initial sync of your existing CLI transcripts.

Make sure `~/.local/bin` is in your `PATH` (in `~/.bashrc` or `~/.zshrc`):
```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## 💻 CLI Usage

### List Conversations
Display the most recent sessions with their IDs, last updated times, turn counts, and workspaces:
```bash
agy-tracker list
agy-tracker list -n 25
```

### Resume a Session
Resume right in your current terminal:
```bash
agy-tracker resume 1
```

Resume with dangerous command execution permissions:
```bash
agy-tracker resume 1 --danger
# or
agy-tracker -d resume 1
```

Resume inside a newly spawned terminal window:
```bash
agy-tracker resume 1 --window
agy-tracker resume 1 -w -d
```

### Open the Web Dashboard
Launch the generated search & filter web dashboard in your default browser:
```bash
agy-tracker web
```

### Sync & Index Sessions
Scan Antigravity transcript logs and update SQLite, `CHATS.md`, and `chat_history.html`:
```bash
agy-tracker sync
```

### Clean Noise & Ephemeral Chats
Remove automated subagent runs and ephemeral test conversations:
```bash
agy-tracker clean
```

### Rename a Conversation
```bash
agy-tracker rename 1 "Refactor Authentication Middleware"
```

### Session Statistics
Display total conversations, turn volume, and active workspaces:
```bash
agy-tracker stats
```

---

## 🛠️ Architecture

```text
agy-tracker/
├── bin/
│   ├── agy-tracker         # Main CLI entrypoint
│   └── agy-open-url        # URL protocol scheme handler & terminal spawner
├── tracker/
│   ├── cli.py              # Subcommands & argument parser
│   ├── db.py               # SQLite schema & query operations
│   ├── exporter.py         # HTML dashboard, markdown & .desktop generator
│   ├── filters.py          # Subagent and benchmark filtering heuristics
│   ├── hook.py             # Lifecycle event hook integrations
│   └── scanner.py          # JSONL transcript parser
├── .gitignore              # Data exclusions (databases, transcripts, local HTML)
├── install.sh              # Setup & desktop scheme registration script
├── LICENSE                 # MIT License
└── README.md
```

---

## 🔒 Privacy & Data Boundary

`agy-tracker` code is completely decoupled from your private session data. Conversation databases (`chat_tracker.db`), raw transcripts (`brain/`), and markdown/HTML logs are strictly excluded via `.gitignore` to prevent private prompts or credentials from leaking into source control.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
