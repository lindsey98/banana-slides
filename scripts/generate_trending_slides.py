#!/usr/bin/env python3
"""
generate_trending_slides.py
───────────────────────────
Uses the banana-slides backend API to generate a slide deck about
the hottest GitHub Python repository of the day.

Flow:
  1. Create project  (idea type)
  2. Generate outline          (sync)
  3. Generate descriptions     (async – poll)
  4. Generate images           (async – poll)
  5. Export PPTX               → save to --output path
"""

import argparse
import sys
import time
import json
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:5000"
POLL_INTERVAL = 10   # seconds between status checks
TASK_TIMEOUT  = 900  # 15 minutes max per async task


# ── helpers ───────────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs):
    url = f"{BASE_URL}{path}"
    resp = getattr(requests, method)(url, **kwargs)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"  ❌ HTTP {resp.status_code} {method.upper()} {path}: {resp.text[:300]}")
        raise
    return resp.json()


def poll_task(project_id: str, task_id: str, label: str) -> None:
    """Block until task completes or raise on failure/timeout."""
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > TASK_TIMEOUT:
            raise TimeoutError(f"Task '{label}' timed out after {TASK_TIMEOUT}s")

        data = api("get", f"/api/projects/{project_id}/tasks/{task_id}")["data"]
        status   = data["status"]
        progress = data.get("progress", {})
        done     = progress.get("completed", 0)
        total    = progress.get("total", 0)

        print(f"  [{label}] {status}  {done}/{total}  ({int(elapsed)}s elapsed)")

        if status == "COMPLETED":
            return
        if status == "FAILED":
            raise RuntimeError(f"Task '{label}' failed: {data.get('error_message', 'unknown error')}")

        time.sleep(POLL_INTERVAL)


# ── main logic ────────────────────────────────────────────────────────────────

def build_idea_prompt(repo: str, desc: str, stars: int,
                      url: str, topics: str, readme: str) -> str:
    readme_section = ""
    if readme and len(readme.strip()) > 50:
        # Trim README to keep the prompt manageable
        truncated = readme.strip()[:3000]
        readme_section = f"\n\n### README (excerpt)\n{truncated}"

    return f"""Create a professional and visually engaging presentation about the hottest GitHub Python repository today.

## Repository Info
- **Name:** {repo}
- **Stars:** {stars:,} ⭐
- **URL:** {url}
- **Topics:** {topics or 'N/A'}
- **Description:** {desc}
{readme_section}

## Slide Structure (6–8 slides)
1. **Title slide** — repo name, tagline, star count
2. **What is it?** — core purpose and problem it solves
3. **Key features** — 3–5 standout capabilities
4. **Why it's trending** — what makes it special right now
5. **Technical deep-dive** — architecture, tech stack, design choices
6. **Getting started** — installation, quick example
7. **Use cases / Who uses it** — real-world applications
8. **Community & links** — GitHub stats, contributors, further reading

Keep each slide focused and visually balanced. Use concrete examples where possible.
"""


def main():
    parser = argparse.ArgumentParser(description="Generate trending-repo slides via banana-slides API")
    parser.add_argument("--repo",   required=True,  help="owner/repo name")
    parser.add_argument("--desc",   default="",     help="Short description")
    parser.add_argument("--stars",  default="0",    help="Star count")
    parser.add_argument("--url",    default="",     help="GitHub URL")
    parser.add_argument("--topics", default="",     help="Comma-separated topics")
    parser.add_argument("--readme", default="",     help="Path to README file")
    parser.add_argument("--lang",   default="en",   help="Output language (en/zh/ja)")
    parser.add_argument("--output", required=True,  help="Output .pptx path")
    args = parser.parse_args()

    stars = int(args.stars) if str(args.stars).isdigit() else 0

    # Read README file if provided
    readme_text = ""
    if args.readme:
        readme_path = Path(args.readme)
        if readme_path.exists():
            readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")

    print(f"\n🍌 banana-slides — Generating slides")
    print(f"   Repo   : {args.repo}")
    print(f"   Stars  : {stars:,}")
    print(f"   Lang   : {args.lang}")
    print(f"   Output : {args.output}")
    print()

    # ── Step 1: Create project ────────────────────────────────────────────────
    print("① Creating project...")
    idea_prompt = build_idea_prompt(
        repo=args.repo, desc=args.desc, stars=stars,
        url=args.url, topics=args.topics, readme=readme_text
    )
    template_style = (
        "Modern tech presentation. Dark background (#0d1117 GitHub-dark). "
        "Accent color: #58a6ff (GitHub blue) and #3fb950 (GitHub green). "
        "Clean sans-serif typography. Code blocks in monospace. "
        "GitHub-inspired iconography. Minimal but informative layout. "
        "Each slide has a clear headline and supporting visuals or bullet points."
    )

    result = api("post", "/api/projects", json={
        "creation_type":  "idea",
        "idea_prompt":    idea_prompt,
        "template_style": template_style,
    })
    project_id = result["data"]["project_id"]
    print(f"   Project ID: {project_id}")

    # ── Step 2: Generate outline ──────────────────────────────────────────────
    print("② Generating outline...")
    outline_resp = api("post", f"/api/projects/{project_id}/generate/outline",
                       json={"language": args.lang})
    pages = outline_resp["data"].get("pages", [])
    print(f"   Outline ready — {len(pages)} slides")

    # ── Step 3: Generate descriptions (async) ────────────────────────────────
    print("③ Generating page descriptions (async)...")
    desc_resp = api("post", f"/api/projects/{project_id}/generate/descriptions",
                    json={"language": args.lang, "max_workers": 5})
    desc_task_id = desc_resp["data"]["task_id"]
    poll_task(project_id, desc_task_id, "descriptions")
    print("   Descriptions done ✓")

    # ── Step 4: Generate images (async) ──────────────────────────────────────
    print("④ Generating slide images (async — this takes a while)...")
    img_resp = api("post", f"/api/projects/{project_id}/generate/images",
                   json={"use_template": False, "language": args.lang})
    img_task_id = img_resp["data"]["task_id"]
    poll_task(project_id, img_task_id, "images")
    print("   Images done ✓")

    # ── Step 5: Export PPTX ───────────────────────────────────────────────────
    print("⑤ Exporting PPTX...")
    export_url = f"{BASE_URL}/api/projects/{project_id}/export/pptx"
    export_resp = requests.get(export_url)
    export_resp.raise_for_status()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(export_resp.content)

    size_kb = output_path.stat().st_size // 1024
    print(f"   Saved → {output_path}  ({size_kb} KB)")
    print(f"\n✅ Done!  {args.repo}  ({stars:,} ⭐)\n")


if __name__ == "__main__":
    main()
