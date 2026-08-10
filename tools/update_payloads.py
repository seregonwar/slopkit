#!/usr/bin/env python3
"""slopkit payload updater.

Fetches the latest PS5 ELF payloads from GitHub releases and stores them
under payloads/ with stable, well-known names, so the exploit kit always
ships the newest zftpd and MemDBG builds.

Sources (name on disk -> upstream release asset):
  zftpd-ps5.elf        <- seregonwar/zftpd, newest "zftpd-ps5-vX.Y.Z.elf"
                          (plain FTP ELF)
  zftpd-ps5-zhttp.elf  <- seregonwar/zftpd, newest "zftpd-ps5-zhttp-vX.Y.Z.elf"
                          (FTP + web file explorer; ~3.8 MiB, needs the
                          raised 6 MiB in-browser payload limit)
  MemDBG-ps5.elf       <- seregonwar/MemDBG, asset "MemDBG-ps5.elf"
                          (MemDBG publishes nightly releases)

Usage:
  python3 tools/update_payloads.py            # update changed payloads
  python3 tools/update_payloads.py --force    # re-download everything
  python3 tools/update_payloads.py --check    # report versions only, no writes

Stdlib only (urllib). Unauthenticated GitHub API: 60 req/h, plenty for a
daily cron. Set GITHUB_TOKEN in the environment to raise the limit.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

API = "https://api.github.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_DIR = os.path.join(ROOT, "payloads")
MANIFEST = os.path.join(PAYLOAD_DIR, "manifest.json")

# name on disk -> {repo, asset matcher, description}
SOURCES = [
    {
        "file": "zftpd-ps5.elf",
        "repo": "seregonwar/zftpd",
        "match": re.compile(r"^zftpd-ps5-v[0-9][\w.-]*\.elf$"),
        "exclude": "-zhttp",
        "desc": "zftpd FTP server (replaces the legacy ftpsrv)",
    },
    {
        "file": "zftpd-ps5-zhttp.elf",
        "repo": "seregonwar/zftpd",
        "match": re.compile(r"^zftpd-ps5-zhttp-v[0-9][\w.-]*\.elf$"),
        "desc": "zftpd FTP + web file explorer (zhttp)",
    },
    {
        "file": "MemDBG-ps5.elf",
        "repo": "seregonwar/MemDBG",
        "match": re.compile(r"^MemDBG-ps5\.elf$"),
        "desc": "MemDBG memory debugger / trainer daemon",
    },
]


def http_json(url, headers=None):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "slopkit-payload-updater",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_release(repo):
    url = f"{API}/repos/{repo}/releases/latest"
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return http_json(url, headers)


def download(url, dest):
    """Download url to dest, validating the ELF magic before replacing the
    previous payload so a corrupt response can never delete the last good
    file."""
    req = urllib.request.Request(url, headers={"User-Agent": "slopkit-payload-updater"})
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(tmp, "wb") as fh:
            copy_stream(resp, fh)
    try:
        with open(tmp, "rb") as fh:
            if fh.read(4) != b"\x7fELF":
                raise ValueError("downloaded file is not an ELF")
    except Exception:
        os.remove(tmp)
        raise
    os.replace(tmp, dest)


def copy_stream(src, dst):
    while True:
        chunk = src.read(65536)
        if not chunk:
            break
        dst.write(chunk)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_manifest():
    if not os.path.exists(MANIFEST):
        return {}
    try:
        with open(MANIFEST, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_manifest(manifest):
    manifest["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Update slopkit payloads from GitHub.")
    ap.add_argument("--force", action="store_true", help="re-download even if tag is unchanged")
    ap.add_argument("--check", action="store_true", help="report versions, do not write anything")
    args = ap.parse_args()

    os.makedirs(PAYLOAD_DIR, exist_ok=True)
    manifest = load_manifest()
    current = manifest.get("sources", {})
    any_changed = False

    for src in SOURCES:
        file = src["file"]
        dest = os.path.join(PAYLOAD_DIR, file)
        entry = current.get(file, {})
        try:
            rel = latest_release(src["repo"])
        except Exception as exc:
            print(f"[!] {file}: could not query {src['repo']}: {exc}")
            continue

        tag = rel.get("tag_name", "")
        asset = next((a for a in rel.get("assets", [])
                      if src["match"].match(a.get("name", ""))
                      and (not src.get("exclude")
                           or src["exclude"] not in a.get("name", ""))), None)

        if asset is None:
            print(f"[!] {file}: no PS5 ELF asset in {src['repo']} release {tag}")
            continue

        local_tag = entry.get("tag")
        if not args.force and local_tag == tag and os.path.exists(dest):
            print(f"[=] {file}: up to date at {tag}")
            continue

        print(f"[>] {file}: {entry.get('tag', 'none')} -> {tag} "
              f"({asset['name']}, {asset.get('size', '?')} bytes)")
        if args.check:
            continue

        try:
            download(asset["browser_download_url"], dest)
        except Exception as exc:
            print(f"[!] {file}: download failed, keeping previous payload: {exc}")
            continue

        current[file] = {
            "repo": src["repo"],
            "tag": tag,
            "asset": asset["name"],
            "size": os.path.getsize(dest),
            "sha256": sha256(dest),
            "desc": src["desc"],
        }
        any_changed = True

    if args.check:
        print("\n-- payload versions --")
        for file, e in sorted(current.items()):
            print(f"  {file}: {e.get('tag', '?')} ({e.get('asset', '?')})")
        return

    manifest["sources"] = current
    if any_changed:
        save_manifest(manifest)
        print(f"\nmanifest updated: {MANIFEST}")
    else:
        print("\nno changes.")


if __name__ == "__main__":
    sys.exit(main())
