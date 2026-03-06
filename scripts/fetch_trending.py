#!/usr/bin/env python3
"""
fetch_trending.py
─────────────────
Reads /tmp/gh_result.json (GitHub Search API response) and writes
the top repo's metadata to $GITHUB_OUTPUT.

Usage:
    python3 scripts/fetch_trending.py
"""
import json
import os
import sys

result_path = "/tmp/gh_result.json"

try:
    with open(result_path) as f:
        data = json.load(f)
except Exception as e:
    print(f"ERROR reading {result_path}: {e}")
    sys.exit(1)

items = data.get("items")
if not items:
    print("ERROR: No repositories found. API response:")
    print(json.dumps(data, indent=2)[:800])
    sys.exit(1)

repo       = items[0]
name       = repo["full_name"]
desc       = (repo.get("description") or "A popular Python repository").replace("\n", " ")
stars      = repo["stargazers_count"]
url        = repo["html_url"]
topics     = ", ".join(repo.get("topics") or [])
readme_url = f"https://raw.githubusercontent.com/{name}/HEAD/README.md"

github_output = os.environ.get("GITHUB_OUTPUT", "/tmp/github_output.txt")
with open(github_output, "a") as fh:
    fh.write(f"name={name}\n")
    fh.write(f"desc={desc}\n")
    fh.write(f"stars={stars}\n")
    fh.write(f"url={url}\n")
    fh.write(f"topics={topics}\n")
    fh.write(f"readme_url={readme_url}\n")

print(f"Top trending: {name}  (stars: {stars:,})")
print(f"  {desc}")
print(f"  Topics: {topics}")
