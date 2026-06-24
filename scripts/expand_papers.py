#!/usr/bin/env python3
"""
Generate the "Extended Paper Index" section of README.md from the scraped
paper pool (data/*.json), classified into a fine-grained taxonomy and sorted
newest-first. Papers already cited in the curated highlights are skipped, so
this section only adds *new* references.

The section body is written between the markers:
    <!-- EXT-PAPERS:start -->  ...  <!-- EXT-PAPERS:end -->

Re-run after the daily scraper updates data/papers.json:
    python scripts/expand_papers.py
"""

import json
import re
from pathlib import Path

README = Path("README.md")
DATA_FILES = ["data/papers.json", "data/papers_extended.json", "data/additional_papers.json"]
START = "<!-- EXT-PAPERS:start -->"
END = "<!-- EXT-PAPERS:end -->"

# (header, auto_category set, keyword->bucket rules applied in order)
# Buckets are emitted in this order; only non-empty ones are rendered.
BUCKET_ORDER = [
    "VLA — General & Manipulation",
    "VLA — Reasoning, Planning & Dual-System",
    "VLA — Autonomous Driving",
    "VLA — Dexterous & Humanoid",
    "VLA — 3D / 4D & Spatial",
    "VLA — RL & Post-Training",
    "VLA — Efficient & Real-Time",
    "VLA — Safety, Robustness & Evaluation",
    "World Models — General & Foundation",
    "World Models — Video Generation & WAM",
    "World Models — Latent & JEPA",
    "World Models — Driving & Navigation",
    "Policies — Diffusion & Flow",
    "Policies — Imitation & Behavior Learning",
    "Policies — Robot Learning & Manipulation",
]

VLA_CATS = {"VLA", "VLA with Reasoning", "Efficient VLA"}
WM_CATS = {"World Model"}
POLICY_CATS = {"Action Learning", "Diffusion Policy", "Robotics", "Policy", "Imitation Learning"}


def has(t, *kws):
    return any(k in t for k in kws)


def classify(paper):
    t = (paper.get("title", "") + " " + paper.get("summary", "")[:200]).lower()
    cat = paper.get("auto_category", "")

    if cat in VLA_CATS or "vision-language-action" in t or "vla" in t:
        if has(t, "driv", "autonomous driving", "lane", "ego vehicle", "ego-vehicle"):
            return "VLA — Autonomous Driving"
        if has(t, "reason", "chain-of-thought", "chain of thought", "cot ", "think",
               "dual-system", "dual system", "system-2", "system 2", "slow-fast", "planning"):
            return "VLA — Reasoning, Planning & Dual-System"
        if has(t, "attack", "adversarial", "safety", "safe ", "robust", "failure",
               "uncertainty", "defense", "backdoor", "jailbreak", "benchmark", "evaluat"):
            return "VLA — Safety, Robustness & Evaluation"
        if has(t, "dexterous", "humanoid", "dexter", "bimanual", "dual-arm", "dual arm",
               "grasp", "in-hand", "whole-body", "loco-manipulation"):
            return "VLA — Dexterous & Humanoid"
        if has(t, "3d", "4d", "point cloud", "pointcloud", "occupancy", "spatial",
               "geometr", "depth"):
            return "VLA — 3D / 4D & Spatial"
        if has(t, "reinforcement", " rl ", "rl-", "rl ", "reward", "grpo", "ppo",
               "policy optimization", "post-training", "preference", "rlhf"):
            return "VLA — RL & Post-Training"
        if has(t, "efficient", "fast", "real-time", "realtime", "acceler", "prune",
               "pruning", "quantiz", "distill", "cache", "caching", "latency",
               "streaming", "lightweight", "tiny", "compact", "edge", "sparse", "token"):
            return "VLA — Efficient & Real-Time"
        return "VLA — General & Manipulation"

    if cat in WM_CATS or "world model" in t or "world-model" in t:
        if has(t, "driv", "navigation", "navigat"):
            return "World Models — Driving & Navigation"
        if has(t, "jepa", "joint-embedding", "joint embedding", "latent dynamics"):
            return "World Models — Latent & JEPA"
        if has(t, "video", "generat", "diffusion", "imagine", "dream", "predict frame"):
            return "World Models — Video Generation & WAM"
        return "World Models — General & Foundation"

    # policies / action learning / robotics
    if has(t, "diffusion", "flow matching", "flow-matching"):
        return "Policies — Diffusion & Flow"
    if has(t, "imitation", "behavior cloning", "behaviour cloning", "demonstration", "teleop"):
        return "Policies — Imitation & Behavior Learning"
    return "Policies — Robot Learning & Manipulation"


def load_pool():
    pool = {}
    for f in DATA_FILES:
        p = Path(f)
        if not p.exists():
            continue
        for rec in json.loads(p.read_text(encoding="utf-8")):
            base = rec["id"].split("v")[0]
            if base not in pool or rec.get("published", "") >= pool[base].get("published", ""):
                pool[base] = rec
    return pool


def existing_ids(readme_text):
    """arXiv base IDs already cited in README outside the EXT section."""
    before = readme_text.split(START)[0]
    after = readme_text.split(END)[-1] if END in readme_text else ""
    ids = set()
    for m in re.findall(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", before + after):
        ids.add(m)
    return ids


def fmt_authors(authors):
    if not authors:
        return "—"
    if len(authors) <= 2:
        return ", ".join(authors)
    return f"{authors[0]}, {authors[1]} et al."


def fmt_links(p):
    parts = []
    if p.get("code_url"):
        parts.append(f"[💻]({p['code_url']})")
    if p.get("project_url"):
        parts.append(f"[🌐]({p['project_url']})")
    return " ".join(parts)


def row(p):
    title = p["title"].replace("|", "\\|").replace("\n", " ").strip()
    url = p.get("url") or f"https://arxiv.org/abs/{p['id']}"
    return f"| [{title}]({url}) | {fmt_authors(p.get('authors', []))} | {p.get('published','')} | {fmt_links(p)} |"


def build_section(buckets, total, latest):
    out = []
    out.append("## 🗂️ Extended Paper Index (Auto-Curated, Newest First)")
    out.append("")
    out.append(
        f"> A broader, continuously-mined index of recent arXiv work that complements the curated "
        f"highlights above — **{total} additional papers**, newest first. Last updated: {latest}. "
        f"Auto-generated from `data/*.json` by [`scripts/expand_papers.py`](scripts/expand_papers.py); "
        f"papers already highlighted above are omitted here to avoid duplication."
    )
    out.append("")
    for name in BUCKET_ORDER:
        items = buckets.get(name)
        if not items:
            continue
        items.sort(key=lambda x: x.get("published_iso", x.get("published", "")), reverse=True)
        out.append(f"<details>")
        out.append(f"<summary><b>{name}</b> · {len(items)} papers</summary>")
        out.append("")
        out.append("| Paper | Authors | Date | Links |")
        out.append("|-------|---------|------|-------|")
        out.extend(row(p) for p in items)
        out.append("")
        out.append("</details>")
        out.append("")
    return "\n".join(out).rstrip()


def main():
    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"Markers {START} / {END} not found in README.md — add them first.")

    pool = load_pool()
    skip = existing_ids(text)
    buckets = {}
    used = 0
    latest = ""
    for base, p in pool.items():
        if base in skip:
            continue
        b = classify(p)
        buckets.setdefault(b, []).append(p)
        used += 1
        latest = max(latest, p.get("published", ""))

    section = build_section(buckets, used, latest)
    replacement = START + "\n" + section + "\n" + END
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _m: replacement,  # function repl avoids backslash-escape processing
        text,
        flags=re.DOTALL,
    )
    README.write_text(new, encoding="utf-8")
    print(f"Extended index: {used} papers across {sum(1 for b in buckets.values() if b)} buckets "
          f"(skipped {len(skip)} already-cited). Latest: {latest}")
    for name in BUCKET_ORDER:
        if buckets.get(name):
            print(f"  {len(buckets[name]):3d}  {name}")


if __name__ == "__main__":
    main()
