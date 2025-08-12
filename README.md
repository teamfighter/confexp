![confexp social preview](docs/social_preview.png)
# confexp

Interactive CLI tool to export Confluence pages to **HTML** or **Markdown** with a tree-based page picker, caching, parallel fetching, and clean UX.  
Prebuilt binaries and a Docker image are available — you don’t have to install Python unless you want to run from source.

---

## ✨ Features

- First-run interactive setup (**Base URL, username, API token, space key**)
- Config saved to `~/.confluence_exporter.json` (plain text)
- Space picker from API if space key isn’t provided
- Parallel BFS page tree indexing with live progress bars
- Tree cache in `~/.confluence_tree_cache.json` (configurable TTL)
- Export to **HTML** or **Markdown** with page titles & separators
- Error logging to `errors.log`, graceful exit on `Ctrl+C`

---

## 🚀 Quick Start

### Option A — Use prebuilt binaries (recommended)
Download the latest release for **Windows / macOS / Linux**:  
https://github.com/teamfighter/confexp/releases/latest

Linux / macOS:
```bash
chmod +x ./confexp
./confexp
```

Windows (PowerShell):
```powershell
.\confexp.exe
```

> On first run, you’ll be asked for: Base URL, Username, API token, Space key.  
> Settings are saved to `~/.confluence_exporter.json` for future runs.

---

### Option B — Run via Docker (no local install)
```bash
docker run -it --rm \
  -v $HOME/.confluence_exporter.json:/root/.confluence_exporter.json \
  -v $HOME/.confluence_tree_cache.json:/root/.confluence_tree_cache.json \
  -v "$(pwd)":/work -w /work \
  ghcr.io/teamfighter/confexp:latest
```

Environment variables (optional overrides inside the container):
- `CONFLUENCE_URL` — your Confluence base URL (e.g. `https://example.atlassian.net/wiki`)
- `CONFLUENCE_USER` — login (usually email)
- `CONFLUENCE_TOKEN` — API token

---

### Option C — Build from source (Python 3.10+)
```bash
git clone https://github.com/teamfighter/confexp.git
cd confexp
pip install -r requirements.txt
python main.py
```

---

## 🧭 Usage examples

Interactive selection and export to **Markdown**:
```bash
./confexp --format md
```

Rebuild the page tree (ignore cache):
```bash
./confexp --refresh
```

Override base URL & space (skip prompts):
```bash
./confexp --base https://your.atlassian.net/wiki --space OPS
```

---

## ⚙ CLI Arguments

| Param              | Description                                             |
|--------------------|---------------------------------------------------------|
| `--base`           | Confluence base URL                                     |
| `--space`          | Space key                                               |
| `-r`, `--refresh`  | Ignore tree cache and rebuild                           |
| `--ttl`            | Tree cache TTL in hours (default: 24)                   |
| `--workers`        | Number of threads (default: 5)                          |
| `--format`         | Export format: `html` or `md` (default: `html`)         |

**Files used/created locally**
- `~/.confluence_exporter.json` — saved credentials & defaults
- `~/.confluence_tree_cache.json` — page tree cache
- `errors.log` — error log for diagnostics

---

## 🐳 Docker cheat-sheet

Build locally:
```bash
docker build -t confexp:dev .
```

Run:
```bash
docker run -it --rm \
  -v $HOME/.confluence_exporter.json:/root/.confluence_exporter.json \
  -v $HOME/.confluence_tree_cache.json:/root/.confluence_tree_cache.json \
  -v "$(pwd)":/work -w /work \
  confexp:dev --format md
```

Pull prebuilt image:
```bash
docker pull ghcr.io/teamfighter/confexp:latest
```

---

## 🔧 Releases & Binaries

- Prebuilt binaries for **Linux**, **macOS**, **Windows** are attached to each release:  
  https://github.com/teamfighter/confexp/releases
- Docker image is published to GHCR:  
  `ghcr.io/teamfighter/confexp:latest`

---

## 📝 License

MIT
