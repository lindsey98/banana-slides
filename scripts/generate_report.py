#!/usr/bin/env python3
"""
generate_report.py
──────────────────
Scrapes GitHub Trending (Python, weekly) and generates a formatted report.
Usage: python3 generate_report.py [output_path] [github_output_path]
"""
import sys
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime


def get_trending(since="weekly", limit=5):
    url = f"https://github.com/trending/python?since={since}"
    resp = requests.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    })
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    repos = []

    for article in soup.select("article.Box-row")[:limit]:
        # Name
        h2 = article.select_one("h2 a")
        if not h2:
            continue
        full_name = h2["href"].strip("/")

        # Description
        p = article.select_one("p")
        desc = p.get_text(strip=True) if p else "No description provided."

        # Stars this week
        stars_span = article.select_one("span.d-inline-block.float-sm-right")
        stars_week = "N/A"
        if stars_span:
            raw = stars_span.get_text(strip=True).replace(",", "")
            stars_week = raw.replace("stars this week", "").strip()

        # Total stars
        total_stars = "?"
        for a in article.select("a.Link--muted"):
            if "stargazers" in a.get("href", ""):
                total_stars = a.get_text(strip=True).replace(",", "")
                break

        repos.append({
            "full_name": full_name,
            "url": f"https://github.com/{full_name}",
            "desc": desc,
            "stars_week": stars_week,
            "total_stars": total_stars,
        })

    return repos


def build_report(repos, since="weekly"):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    period = "周榜" if since == "weekly" else ("月榜" if since == "monthly" else "日榜")
    lines = [
        f"🐍 GitHub Python {period} TOP {len(repos)} | {today}",
        "",
    ]

    for i, r in enumerate(repos, 1):
        if r["stars_week"] != "N/A":
            stars_str = f"+{int(r['stars_week']):,} stars this week"
        else:
            stars_str = f"{r['total_stars']} stars total"

        lines += [
            f"{i}. ⭐ {r['full_name']} ({stars_str})",
            f"🔗 {r['url']}",
            f"📝 {r['desc']}",
            "",
            "---",
            "",
        ]

    return "\n".join(lines)


if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/report.txt"
    gh_output   = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GITHUB_OUTPUT", "")

    print("Fetching GitHub Trending Python (weekly)...")
    repos = get_trending(since="weekly", limit=5)

    if not repos:
        print("ERROR: no repos found"); sys.exit(1)

    report = build_report(repos, since="weekly")

    with open(output_path, "w") as f:
        f.write(report)

    print(report)

    # Write top repo info to GITHUB_OUTPUT for email subject
    if gh_output and repos:
        top = repos[0]
        stars_str = top["stars_week"] if top["stars_week"] != "N/A" else top["total_stars"]
        with open(gh_output, "a") as fh:
            fh.write(f"top_name={top['full_name']}\n")
            fh.write(f"top_stars={stars_str}\n")
