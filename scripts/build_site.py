#!/usr/bin/env python3
"""
Build the GitHub Pages site (index.html) from the curated tables in README.md.

The README is the single source of truth: this parser walks its section/sub-section
headings and markdown tables, normalizes each row into {name, desc, year, links},
and renders a static, dependency-free single-page site with live search + filtering.

Re-run after editing README.md to regenerate the site:
    python scripts/build_site.py
"""

import json
import re
from pathlib import Path
from html import escape

README = Path("README.md")
OUTPUT = Path("index.html")

# Top-level sections (## ...) to include, in display order. Others are skipped.
INCLUDE_SECTIONS = [
    "Surveys",
    "Vision-Language-Action (VLA) Models",
    "World & World-Action Models",
    "Action Representations & Tokenization",
    "Foundational Robot Policies",
    "Resources",
]

YEAR_RE = re.compile(r"^(19|20|21)\d{2}$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
EMOJI_RE = re.compile(r"[^\w\s&/()+,.\-]")  # strip leading emoji from headings


def strip_emoji(text: str) -> str:
    return EMOJI_RE.sub("", text).strip()


def clean_name(cell: str) -> str:
    return cell.replace("**", "").replace("`", "").strip()


def parse_links(cell: str):
    """Return dict of link-type -> url, classifying by emoji label then by host."""
    links = {}
    for label, url in LINK_RE.findall(cell):
        if "arxiv.org" in url or "📄" in label:
            links.setdefault("paper", url)
        elif "github.com" in url or "💻" in label:
            links.setdefault("code", url)
        else:
            links.setdefault("project", url)
    return links


def parse_readme(text: str):
    sections = []
    current_top = None
    current_sub = None
    header = []  # table column headers for the table currently being read
    cur_section_obj = None
    cur_group = None

    lines = text.splitlines()
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        if line.startswith("## "):
            name = strip_emoji(line[3:])
            current_sub = None
            header = []
            if name in INCLUDE_SECTIONS:
                cur_section_obj = {"title": name, "groups": []}
                sections.append(cur_section_obj)
                # default group (rows directly under the ## with no ###)
                cur_group = {"title": None, "items": []}
                cur_section_obj["groups"].append(cur_group)
            else:
                cur_section_obj = None
            continue

        if (line.startswith("### ") or line.startswith("#### ")) and cur_section_obj:
            sub = strip_emoji(line.lstrip("#").strip())
            header = []
            cur_group = {"title": sub, "items": []}
            cur_section_obj["groups"].append(cur_group)
            continue

        if line.startswith("|") and cur_section_obj is not None:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # header row
            if not header:
                header = [c.lower() for c in cells]
                continue
            # separator row
            if set("".join(cells)) <= set("-: "):
                continue
            if len(cells) < 2:
                continue

            name = clean_name(cells[0])
            links = parse_links(cells[-1])
            year = ""
            desc_cells = cells[1:-1]
            # pull a year out of the middle columns if present
            kept = []
            for c in desc_cells:
                if YEAR_RE.match(c.strip()):
                    year = c.strip()
                else:
                    kept.append(c.strip())
            desc = " · ".join(x for x in kept if x)
            # strip markdown emphasis from description, keep plain text
            desc = re.sub(r"\*([^*]+)\*", r"\1", desc)
            item = {
                "name": name,
                "desc": desc,
                "year": year,
                "links": links,
                "group": cur_group["title"] or cur_section_obj["title"],
            }
            cur_group["items"].append(item)
            continue

        # blank line between tables resets the header so the next table re-reads it
        if not line.strip():
            header = []

    # drop empty groups
    for s in sections:
        s["groups"] = [g for g in s["groups"] if g["items"]]
    return [s for s in sections if s["groups"]]


def count_items(sections):
    return sum(len(g["items"]) for s in sections for g in s["groups"])


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Awesome World Action Models</title>
<meta name="description" content="A curated, survey-grounded reading list of World Action Models (WAM), Vision-Language-Action (VLA) models, and Embodied AI." />
<style>
:root {{
  --bg: #0d1117; --panel: #161b22; --panel-2: #1c2330; --border: #2a3340;
  --txt: #e6edf3; --muted: #9aa7b4; --accent: #6ea8fe; --accent-2: #a78bfa;
  --chip: #21303f; --shadow: 0 6px 24px rgba(0,0,0,.35);
}}
@media (prefers-color-scheme: light) {{
  :root {{
    --bg:#f6f8fa; --panel:#fff; --panel-2:#f0f3f7; --border:#d8dee4;
    --txt:#1f2328; --muted:#5a6470; --accent:#0969da; --accent-2:#8250df;
    --chip:#eaeef2; --shadow:0 6px 24px rgba(140,149,159,.2);
  }}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin:0; background:var(--bg); color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.55;
}}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.hero {{
  padding:64px 20px 40px; text-align:center;
  background:radial-gradient(1200px 400px at 50% -10%, rgba(110,168,254,.18), transparent 70%);
  border-bottom:1px solid var(--border);
}}
.hero h1 {{ font-size:clamp(2rem,5vw,3.2rem); margin:0 0 .3em; letter-spacing:-.02em; }}
.hero p {{ color:var(--muted); max-width:760px; margin:0 auto 1.2em; font-size:1.05rem; }}
.badges {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-bottom:8px; }}
.badges img {{ height:22px; }}
.stats {{ display:flex; gap:28px; justify-content:center; flex-wrap:wrap; margin-top:18px; }}
.stat b {{ display:block; font-size:1.6rem; color:var(--accent-2); }}
.stat span {{ color:var(--muted); font-size:.85rem; }}
.toolbar {{
  position:sticky; top:0; z-index:20; backdrop-filter:blur(10px);
  background:color-mix(in srgb, var(--bg) 88%, transparent);
  border-bottom:1px solid var(--border); padding:12px 16px;
}}
.toolbar-inner {{ max-width:1080px; margin:0 auto; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
#search {{
  flex:1; min-width:220px; padding:10px 14px; border-radius:10px;
  border:1px solid var(--border); background:var(--panel); color:var(--txt); font-size:.95rem;
}}
#search:focus {{ outline:2px solid var(--accent); border-color:transparent; }}
.chips {{ display:flex; gap:6px; flex-wrap:wrap; }}
.chip {{
  padding:6px 12px; border-radius:999px; border:1px solid var(--border);
  background:var(--chip); color:var(--muted); cursor:pointer; font-size:.82rem; white-space:nowrap;
}}
.chip.active {{ background:var(--accent); color:#fff; border-color:transparent; }}
main {{ max-width:1080px; margin:0 auto; padding:8px 16px 60px; }}
.section {{ margin-top:40px; }}
.section > h2 {{ font-size:1.5rem; border-bottom:1px solid var(--border); padding-bottom:8px; }}
.group > h3 {{ font-size:1.05rem; color:var(--accent-2); margin:22px 0 10px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }}
.card {{
  background:var(--panel); border:1px solid var(--border); border-radius:12px;
  padding:14px 16px; box-shadow:var(--shadow); transition:transform .12s ease, border-color .12s ease;
}}
.card:hover {{ transform:translateY(-2px); border-color:var(--accent); }}
.card .top {{ display:flex; justify-content:space-between; gap:10px; align-items:baseline; }}
.card .name {{ font-weight:700; }}
.card .year {{ color:var(--muted); font-size:.8rem; flex:none; }}
.card .desc {{ color:var(--muted); font-size:.9rem; margin:6px 0 10px; }}
.card .links {{ display:flex; gap:8px; flex-wrap:wrap; }}
.card .links a {{
  font-size:.78rem; padding:3px 9px; border-radius:7px; border:1px solid var(--border);
  background:var(--panel-2);
}}
.empty {{ text-align:center; color:var(--muted); padding:60px 0; display:none; }}
footer {{ text-align:center; color:var(--muted); padding:34px 16px; border-top:1px solid var(--border); font-size:.9rem; }}
.hidden {{ display:none !important; }}
</style>
</head>
<body>
<header class="hero">
  <h1>🤖 Awesome World Action Models</h1>
  <p>A curated, survey-grounded reading list of <b>World Action Models (WAM)</b>,
     <b>Vision-Language-Action (VLA)</b> models, and <b>Embodied AI</b>.</p>
  <div class="badges">
    <a href="https://github.com/HyperbolicCurve/Awesome-World-Action-Model"><img alt="Repo" src="https://img.shields.io/badge/GitHub-Repository-181717?logo=github"></a>
    <a href="https://github.com/HyperbolicCurve/Awesome-World-Action-Model/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/HyperbolicCurve/Awesome-World-Action-Model?style=flat"></a>
    <img alt="Awesome" src="https://awesome.re/badge-flat.svg">
  </div>
  <div class="stats">
    <div class="stat"><b>{n_papers}</b><span>curated entries</span></div>
    <div class="stat"><b>{n_sections}</b><span>categories</span></div>
    <div class="stat"><b>{n_groups}</b><span>sub-topics</span></div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-inner">
    <input id="search" type="search" placeholder="🔎 Search models, papers, keywords…" autocomplete="off" />
    <div class="chips" id="chips"></div>
  </div>
</div>

<main id="content"></main>
<div class="empty" id="empty">No entries match your search.</div>

<footer>
  Generated from <a href="https://github.com/HyperbolicCurve/Awesome-World-Action-Model/blob/main/README.md">README.md</a>
  · Built with <code>scripts/build_site.py</code> · Licensed under MIT.<br>
  Found something missing? <a href="https://github.com/HyperbolicCurve/Awesome-World-Action-Model/pulls">Open a PR</a> ⭐
</footer>

<script>
const DATA = {data_json};
const LINK_LABEL = {{ paper: "📄 arXiv", project: "🌐 Project", code: "💻 Code" }};

const content = document.getElementById("content");
const chipsEl = document.getElementById("chips");
const searchEl = document.getElementById("search");
const emptyEl = document.getElementById("empty");

let activeSection = "All";

function render() {{
  const q = searchEl.value.trim().toLowerCase();
  content.innerHTML = "";
  let visible = 0;

  DATA.forEach(section => {{
    if (activeSection !== "All" && section.title !== activeSection) return;
    const secEl = document.createElement("section");
    secEl.className = "section";
    secEl.innerHTML = `<h2>${{section.title}}</h2>`;
    let secVisible = 0;

    section.groups.forEach(group => {{
      const groupEl = document.createElement("div");
      groupEl.className = "group";
      if (group.title) groupEl.innerHTML = `<h3>${{group.title}}</h3>`;
      const grid = document.createElement("div");
      grid.className = "grid";

      group.items.forEach(item => {{
        const hay = (item.name + " " + item.desc + " " + (group.title||"") + " " + section.title).toLowerCase();
        if (q && !hay.includes(q)) return;
        secVisible++; visible++;
        const links = Object.entries(item.links)
          .map(([k,u]) => `<a href="${{u}}" target="_blank" rel="noopener">${{LINK_LABEL[k]||k}}</a>`).join("");
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
          <div class="top"><span class="name">${{item.name}}</span>${{item.year?`<span class="year">${{item.year}}</span>`:""}}</div>
          ${{item.desc?`<div class="desc">${{item.desc}}</div>`:""}}
          <div class="links">${{links}}</div>`;
        grid.appendChild(card);
      }});

      if (grid.children.length) {{ groupEl.appendChild(grid); secEl.appendChild(groupEl); }}
    }});

    if (secVisible) content.appendChild(secEl);
  }});

  emptyEl.style.display = visible ? "none" : "block";
}}

function buildChips() {{
  const names = ["All", ...DATA.map(s => s.title)];
  names.forEach(name => {{
    const c = document.createElement("button");
    c.className = "chip" + (name === "All" ? " active" : "");
    c.textContent = name;
    c.onclick = () => {{
      activeSection = name;
      [...chipsEl.children].forEach(x => x.classList.remove("active"));
      c.classList.add("active");
      render();
    }};
    chipsEl.appendChild(c);
  }});
}}

searchEl.addEventListener("input", render);
buildChips();
render();
</script>
</body>
</html>
"""


def main():
    text = README.read_text(encoding="utf-8")
    sections = parse_readme(text)
    n_papers = count_items(sections)
    n_groups = sum(len(s["groups"]) for s in sections)
    html = PAGE_TEMPLATE.format(
        n_papers=n_papers,
        n_sections=len(sections),
        n_groups=n_groups,
        data_json=json.dumps(sections, ensure_ascii=False),
    )
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT} — {n_papers} entries across {len(sections)} sections / {n_groups} groups.")


if __name__ == "__main__":
    main()
