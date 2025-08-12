#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Confluence tree picker + HTML/Markdown export (GitHub-ready)

Features:
- First-run interactive setup (base URL, username, API token, space key)
- Plain-text config saved to ~/.confluence_exporter.json
- Space picker from API if space key not provided
- Builds full page tree (parallel BFS) with live progress bars
- Caches the tree to ~/.confluence_tree_cache.json (TTL configurable)
- Parallel export by page IDs; preserves selection order in the output
- Robust HTTP retries with exponential backoff; respects 429
- Immediate exit on 401/403 (bad credentials)
- Error logging to errors.log; warnings printed in console
- Comfortable fullscreen-like picker (height=90%)
- Graceful exit on Ctrl+C
- Exports to HTML or Markdown (--format html|md) with per-page separators
"""

import os
import json
import time
import argparse
import requests
from pathlib import Path
from requests.auth import HTTPBasicAuth
from InquirerPy import inquirer
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime
from markdownify import markdownify as md
from getpass import getpass

# ===================== Defaults & paths =====================
DEFAULT_BASE_URL = "https://your-domain.atlassian.net/wiki"  # placeholder default
DEFAULT_SPACE_KEY = ""  # empty -> trigger space picker
CONFIG_PATH = Path.home() / ".confluence_exporter.json"
TREE_CACHE_PATH = Path.home() / ".confluence_tree_cache.json"
ERROR_LOG = Path("errors.log")

# ===================== CLI args =====================
ap = argparse.ArgumentParser(description="Confluence export with cached tree & CLI picker")
ap.add_argument("--base", default=None, help="Confluence base URL, e.g. https://<org>.atlassian.net/wiki")
ap.add_argument("--space", default=None, help="Space key, e.g. DVP")
ap.add_argument("-r", "--refresh", action="store_true", help="Ignore tree cache and rebuild")
ap.add_argument("--ttl", type=int, default=24, help="Tree cache TTL in hours (default: 24)")
ap.add_argument("--workers", type=int, default=5, help="Thread pool size (default: 5)")
ap.add_argument("--cache", default=str(TREE_CACHE_PATH), help="Path to tree cache file")
ap.add_argument("--format", choices=["html", "md"], default="html", help="Export format: html or md (default: html)")
args = ap.parse_args()

# Will be filled after config load/prompt
BASE_URL = None
SPACE_KEY = None
CACHE_PATH = Path(args.cache)

# ===================== Logging =====================
def log_error(message: str) -> None:
    """Append error message to errors.log with timestamp."""
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with ERROR_LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

# ===================== Config helpers =====================
def load_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log_error(f"CONFIG READ ERROR: {e}")
        return None

def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Config saved to {CONFIG_PATH}")

def prompt_config(existing: dict | None):
    """
    Prompt for base_url, username, api_token (hidden), space_key.
    If space_key empty -> let user pick from API.
    """
    cfg = {
        "base_url": existing.get("base_url") if existing else DEFAULT_BASE_URL,
        "username": existing.get("username") if existing else "",
        "api_token": existing.get("api_token") if existing else "",
        "space_key": existing.get("space_key") if existing else DEFAULT_SPACE_KEY,
    }

    print("\n🔧 Initial setup (press Enter to keep value shown in [brackets])")

    base_url = input(f"Base URL [{cfg['base_url']}]: ").strip()
    if base_url:
        cfg["base_url"] = base_url
    # Normalize trailing slash removal
    cfg["base_url"] = cfg["base_url"].rstrip("/")

    username = input(f"Username (email) [{cfg['username']}]: ").strip()
    if username:
        cfg["username"] = username

    token_prompt = "API Token [***** hidden *****]: " if cfg["api_token"] else "API Token: "
    api_token = getpass(token_prompt)
    if api_token:
        cfg["api_token"] = api_token

    space_key = input(f"Space key (leave empty to pick) [{cfg['space_key']}]: ").strip()
    if space_key:
        cfg["space_key"] = space_key

    # If no space key, fetch spaces and let user pick
    if not cfg["space_key"]:
        print("📚 Fetching spaces...")
        try:
            spaces = list_spaces(cfg["base_url"], cfg["username"], cfg["api_token"])
        except Exception as e:
            print(f"❌ Failed to list spaces: {e}")
            raise SystemExit(1)
        if not spaces:
            print("❌ No spaces available for your account.")
            raise SystemExit(1)
        # Build choices: "KEY — Name"
        space_choices = [
            {"name": f"{s['key']} — {s['name']}", "value": s["key"]}
            for s in sorted(spaces, key=lambda x: x["key"].lower())
        ]
        cfg["space_key"] = inquirer.select(
            message="Select Confluence space:",
            choices=space_choices,
            height="90%",
            instruction="↑/↓ to move, Enter to select"
        ).execute()

    return cfg

# ===================== Confluence utils (need base_url + creds) =====================
def make_auth(username, token):
    return HTTPBasicAuth(username, token)

def _get(base_url, auth, url_path, params=None, retry=5, backoff=1.7, timeout=30):
    """
    GET with retries/backoff and auth handling. base_url + url_path must form a valid URL.
    Immediate exit on 401/403; prints wait time for 429; logs all failed attempts.
    """
    err = None
    url = f"{base_url}{url_path}"
    for i in range(retry):
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, auth=auth, params=params, timeout=timeout)
            if r.status_code in (401, 403):
                log_error(f"AUTH ERROR {r.status_code}: {url}")
                print(f"\n❌ Authorization failed ({r.status_code}). Check username/token/permissions.")
                raise SystemExit(1)
            if r.status_code == 429:
                wait = backoff ** i
                print(f"⚠️  429 Too Many Requests, sleeping {wait:.1f}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            log_error(f"HTTP ERROR (try {i+1}/{retry}) {url} -> {e}")
            err = e
            time.sleep(backoff ** i)
    raise err

def list_spaces(base_url, username, token):
    """Return list of spaces: [{key, name}]"""
    auth = make_auth(username, token)
    spaces = []
    start, limit = 0, 100
    while True:
        r = _get(base_url, auth, "/rest/api/space", params={"start": start, "limit": limit})
        data = r.json()
        for s in data.get("results", []):
            spaces.append({"key": s.get("key", ""), "name": s.get("name", "")})
        if not data.get("_links", {}).get("next"):
            break
        start += limit
    return spaces

# ===================== Tree building & export (use global config later) =====================
def get_root_pages(base_url, space_key, auth):
    """True root pages via /content?expand=ancestors and filter where ancestors is empty."""
    roots, start, limit = [], 0, 100
    while True:
        r = _get(base_url, auth, "/rest/api/content",
                 params={"spaceKey": space_key, "type": "page", "expand": "ancestors", "start": start, "limit": limit})
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        for p in results:
            if not p.get("ancestors"):
                roots.append({"id": p["id"], "title": p["title"]})
        start += limit
        if not data.get("_links", {}).get("next"):
            break
    roots.sort(key=lambda x: x["title"].lower())
    return roots

def get_children(base_url, page_id, auth):
    """Yield child pages for page_id."""
    start, limit = 0, 100
    while True:
        r = _get(base_url, auth, f"/rest/api/content/{page_id}/child/page", params={"start": start, "limit": limit})
        data = r.json()
        results = data.get("results", [])
        for p in results:
            yield {"id": p["id"], "title": p["title"]}
        if not data.get("_links", {}).get("next"):
            break
        start += limit

def build_tree_with_progress(base_url, space_key, auth, workers: int):
    """Parallel BFS tree build. Returns (tree, id_to_title)."""
    visited = set()
    visited_lock = Lock()
    id_to_title = {}
    tree = []

    roots = get_root_pages(base_url, space_key, auth)
    for r in roots:
        tree.append({"id": r["id"], "title": r["title"], "children": []})

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        pbar = tqdm(desc=f"Indexing tree (workers={workers})", unit="pg")
        futures = {ex.submit(list, get_children(base_url, node["id"], auth)): node for node in tree}

        while futures:
            for future in as_completed(list(futures.keys())):
                node = futures.pop(future)
                try:
                    children_list = future.result()
                except Exception as e:
                    log_error(f"CHILD ERROR {node['title']} ({node['id']}): {e}")
                    children_list = []

                with visited_lock:
                    if node["id"] not in visited:
                        visited.add(node["id"])
                        id_to_title[node["id"]] = node["title"]

                child_nodes = []
                for c in sorted(children_list, key=lambda x: x["title"].lower()):
                    child_node = {"id": c["id"], "title": c["title"], "children": []}
                    child_nodes.append(child_node)
                    futures[ex.submit(list, get_children(base_url, c["id"], auth))] = child_node

                node["children"] = child_nodes
                pbar.update(1)
        pbar.close()

    return tree, id_to_title

def flatten_tree_for_choices(tree, prefix=""):
    """Convert nested tree to flat choices with icons."""
    items = []
    for node in tree:
        icon = "📂" if node["children"] else "📄"
        items.append({"name": f"{prefix}{icon} {node['title']}", "value": node["id"]})
        if node["children"]:
            items.extend(flatten_tree_for_choices(node["children"], prefix + "  "))
    return items

def export_pages_html(base_url, page_ids, id_to_title, auth, workers: int):
    """Parallel export to HTML with per-page separators."""
    def fetch(pid):
        try:
            r = _get(base_url, auth, f"/rest/api/content/{pid}", params={"expand": "body.view"})
            data = r.json()
            title = data.get("title") or id_to_title.get(pid, pid)
            html = data.get("body", {}).get("view", {}).get("value", "")
            return pid, title, html, None
        except Exception as e:
            log_error(f"EXPORT ERROR {pid}: {e}")
            return pid, id_to_title.get(pid, pid), None, str(e)

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(fetch, pid): pid for pid in page_ids}
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Exporting pages (HTML)", unit="pg"):
            pass
        for fut, pid in futures.items():
            pid, title, html, err = fut.result()
            results[pid] = (title, html, err)

    combined_html = "<html><head><meta charset='utf-8'><title>Combined Report</title></head><body>"
    for pid in page_ids:
        title, html, err = results.get(pid, (id_to_title.get(pid, pid), None, "No data"))
        if err:
            print(f"\033[93m⚠️  Failed to export: {title} ({err})\033[0m")
            html = html or f"<p><em>Export error: {err}</em></p>"
        combined_html += f"<h1>{title}</h1>\n{html or ''}\n<hr>\n<!-- End of page: {title} -->\n"
    combined_html += "</body></html>"

    with open("combined_report.html", "w", encoding="utf-8") as f:
        f.write(combined_html)
    print("\n✅ Done: combined_report.html")

def export_pages_md(base_url, page_ids, id_to_title, auth, workers: int):
    """Parallel export to Markdown with per-page separators."""
    def fetch(pid):
        try:
            r = _get(base_url, auth, f"/rest/api/content/{pid}", params={"expand": "body.view"})
            data = r.json()
            title = data.get("title") or id_to_title.get(pid, pid)
            html = data.get("body", {}).get("view", {}).get("value", "")
            markdown = md(html, heading_style="ATX")
            return pid, title, markdown, None
        except Exception as e:
            log_error(f"EXPORT ERROR {pid}: {e}")
            return pid, id_to_title.get(pid, pid), None, str(e)

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(fetch, pid): pid for pid in page_ids}
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Exporting pages (Markdown)", unit="pg"):
            pass
        for fut, pid in futures.items():
            pid, title, md_text, err = fut.result()
            results[pid] = (title, md_text, err)

    combined_md = ""
    for pid in page_ids:
        title, md_text, err = results.get(pid, (id_to_title.get(pid, pid), None, "No data"))
        if err:
            print(f"\033[93m⚠️  Failed to export: {title} ({err})\033[0m")
            md_text = md_text or f"*Export error: {err}*"
        combined_md += f"# {title}\n\n{md_text or ''}\n\n---\n*End of page: {title}*\n\n"

    with open("combined_report.md", "w", encoding="utf-8") as f:
        f.write(combined_md)
    print("\n✅ Done: combined_report.md")

# ===================== Cache (tree) =====================
def load_tree_cache(base_url, space_key, ttl_hours: int):
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("base_url") != base_url or data.get("space_key") != space_key:
        return None
    ts = data.get("created_at", 0)
    if (time.time() - ts) / 3600.0 > max(0, ttl_hours):
        return None
    return data.get("tree"), data.get("id_to_title")

def save_tree_cache(base_url, space_key, tree, id_to_title):
    payload = {
        "created_at": time.time(),
        "base_url": base_url,
        "space_key": space_key,
        "tree": tree,
        "id_to_title": id_to_title,
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

# ===================== Main flow =====================
def main():
    # 1) Load or prompt config
    existing = load_config()
    cfg = None

    if existing:
        print("🗃️ Found existing config:")
        print(f"  base_url:  {existing.get('base_url')}")
        print(f"  username:  {existing.get('username')}")
        print(f"  space_key: {existing.get('space_key') or '(empty)'}")
        use_it = inquirer.confirm(
            message="Use this config?",
            default=True
        ).execute()
        if use_it:
            cfg = existing
        else:
            cfg = prompt_config(existing)
            save_config(cfg)
    else:
        cfg = prompt_config(None)
        save_config(cfg)

    # 2) Merge CLI overrides (if provided)
    base_from_cli = args.base.strip() if isinstance(args.base, str) and args.base else None
    space_from_cli = args.space.strip() if isinstance(args.space, str) and args.space else None

    base_url = (base_from_cli or cfg["base_url"]).rstrip("/")
    username = cfg["username"]
    api_token = cfg["api_token"]
    space_key = space_from_cli or cfg["space_key"]

    # expose for downstream functions
    global BASE_URL, SPACE_KEY, CACHE_PATH
    BASE_URL = base_url
    SPACE_KEY = space_key
    CACHE_PATH = Path(args.cache)

    # 3) Auth
    auth = make_auth(username, api_token)

    # 4) Load or build tree
    tree = id_to_title = None
    if not args.refresh:
        cached = load_tree_cache(BASE_URL, SPACE_KEY, args.ttl)
        if cached:
            tree, id_to_title = cached
            print(f"🗃️  Using tree cache {CACHE_PATH} (TTL {args.ttl}h).")

    if tree is None:
        print("🔎 Building tree (first run may take a while)...")
        tree, id_to_title = build_tree_with_progress(BASE_URL, SPACE_KEY, auth, args.workers)
        save_tree_cache(BASE_URL, SPACE_KEY, tree, id_to_title)
        print(f"💾 Tree cache saved to {CACHE_PATH}")

    # 5) Pick pages
    choices = flatten_tree_for_choices(tree)
    selected_ids = inquirer.checkbox(
        message="Select pages to export (Space to toggle, Enter to confirm):",
        choices=choices,
        height="90%",
        instruction="↑/↓ to move, Space to toggle, Enter to confirm",
        transformer=lambda result: f"{len(result)} selected"
    ).execute()

    if not selected_ids:
        print("ℹ️ Nothing selected — exiting.")
        return

    # 6) Export
    if args.format == "html":
        export_pages_html(BASE_URL, selected_ids, id_to_title, auth, args.workers)
    else:
        export_pages_md(BASE_URL, selected_ids, id_to_title, auth, args.workers)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user. Exiting...")
        raise SystemExit(0)
