![confexp social preview](docs/social_preview.png)
# confexp

Interactive CLI tool to export Confluence pages to **HTML** or **Markdown** with a tree-based page picker, caching, parallel fetching, and clean UX.

## ✨ Features
- First-run interactive setup (**Base URL, username, API token, space key**)
- Config saved to `~/.confluence_exporter.json` (plain text)
- Space picker from API if space key isn’t provided
- Parallel BFS page tree indexing with live progress bars
- Tree cache in `~/.confluence_tree_cache.json` (configurable TTL)
- Export to **HTML** or **Markdown** with page titles & separators
- Error logging to `errors.log`, graceful exit on `Ctrl+C`
  

## 📦 Installation
```bash
git clone https://github.com/<yourusername>/confexp.git
cd confexp
pip install -r requirements.txt
```
## 🚀 Usage

First run (interactive setup):
```bash
python main.py
```

Export to **Markdown**:
```bash
    python main.py --format md
```
Rebuild the page tree (ignore cache):
```bash
    python main.py --refresh
```
Override base URL & space:
```bash
    python main.py --base https://your.atlassian.net/wiki --space OPS
```
## ⚙ CLI Arguments

| Param            | Description                                   |
|------------------|-----------------------------------------------|
| `--base`         | Confluence base URL                           |
| `--space`        | Space key                                     |
| `-r`, `--refresh`| Ignore tree cache and rebuild                 |
| `--ttl`          | Tree cache TTL in hours (default: 24)         |
| `--workers`      | Number of threads (default: 5)                |
| `--format`       | Export format: `html` or `md` (default: html) |

## 🐳 Docker

Build locally:

    docker build -t confexp:dev .

Run:

    docker run -it --rm \
      -v $HOME/.confluence_exporter.json:/root/.confluence_exporter.json \
      -v $HOME/.confluence_tree_cache.json:/root/.confluence_tree_cache.json \
      -v "$(pwd)":/work -w /work \
      confexp:dev --format md

## 🔧 Build single-file binaries (via GitHub Actions)

Tag a release:

    git tag v0.1.0
    git push origin v0.1.0

Actions will build binaries for Linux/macOS/Windows and attach them to the release.  
A Docker image will also be built and pushed to GHCR if configured.

## 📝 License
MIT
