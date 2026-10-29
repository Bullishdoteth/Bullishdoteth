#!/usr/bin/env python3
"""
generate.py - Generates terminal-style GitHub profile README SVGs and animated contribution snake.
Standard Library Only (no external dependencies).

Outputs:
  - dark.svg   (Cyber Dark Terminal Profile Card)
  - light.svg  (Clean Light Terminal Profile Card)
  - snake.svg  (Animated Contribution Snake)
"""

import os
import sys
import json
import urllib.request
import re
import datetime

USERNAME = "Bullishdoteth"

def esc(txt):
    """Escapes special XML characters."""
    return str(txt).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# ----------------------------------------------------------------------
# 1. LIVE STATS FETCHER (Standard Library Only)
# ----------------------------------------------------------------------

def fetch_github_data(username):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    stats = {
        "username": username,
        "public_repos": 0,
        "total_stars": 0,
        "total_contributions": 0,
        "current_streak": 0,
        "days": []
    }

    if token:
        # 1A. Authenticated GraphQL Query
        print(f"[*] Querying GitHub GraphQL API for {username} using GH_TOKEN...")
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    contributionCount
                    contributionLevel
                    date
                    weekday
                  }
                }
              }
            }
            repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
              totalCount
              nodes {
                stargazerCount
              }
            }
          }
        }
        """
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Bullishdoteth-Profile-Card",
                "Content-Type": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "errors" in data:
                    raise RuntimeError(f"GraphQL returned errors: {data['errors']}")
                user = data["data"]["user"]
                if not user:
                    raise RuntimeError(f"GitHub user '{username}' not found in GraphQL response.")
                
                cal = user["contributionsCollection"]["contributionCalendar"]
                stats["total_contributions"] = cal["totalContributions"]
                stats["public_repos"] = user["repositories"]["totalCount"]
                stats["total_stars"] = sum(node["stargazerCount"] for node in user["repositories"]["nodes"])
                
                level_map = {
                    "NONE": 0,
                    "FIRST_QUARTILE": 1,
                    "SECOND_QUARTILE": 2,
                    "THIRD_QUARTILE": 3,
                    "FOURTH_QUARTILE": 4
                }
                for week in cal["weeks"]:
                    for day in week["contributionDays"]:
                        stats["days"].append({
                            "date": day["date"],
                            "count": day["contributionCount"],
                            "level": level_map.get(day["contributionLevel"], 0),
                            "weekday": day["weekday"]
                        })
        except Exception as e:
            raise RuntimeError(f"GitHub GraphQL API query failed: {e}")
    else:
        # 1B. Public Fallback Pipeline (REST + Contributions Calendar HTML)
        print(f"[*] GH_TOKEN not found. Fetching public data for {username}...")
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Bullishdoteth-Profile-Card/1.0)"}
        
        # Public Repos
        try:
            u_req = urllib.request.Request(f"https://api.github.com/users/{username}", headers=headers)
            with urllib.request.urlopen(u_req, timeout=15) as resp:
                u_data = json.loads(resp.read().decode("utf-8"))
                stats["public_repos"] = u_data.get("public_repos", 0)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch public profile for {username}: {e}")
        
        # Public Stars
        try:
            r_req = urllib.request.Request(f"https://api.github.com/users/{username}/repos?per_page=100", headers=headers)
            with urllib.request.urlopen(r_req, timeout=15) as resp:
                repos = json.loads(resp.read().decode("utf-8"))
                stats["total_stars"] = sum(r.get("stargazers_count", 0) for r in repos)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch public repos for {username}: {e}")
            
        # Public Contribution Calendar
        try:
            c_req = urllib.request.Request(f"https://github.com/users/{username}/contributions", headers=headers)
            with urllib.request.urlopen(c_req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
                
                m_total = re.search(r"([0-9,]+)\s+contributions\s+in", html)
                stats["total_contributions"] = int(m_total.group(1).replace(",", "")) if m_total else 0
                
                matches = re.findall(r'data-date="([0-9-]+)"[^>]*data-level="([0-9])"', html)
                if not matches:
                    matches = re.findall(r'data-level="([0-9])"[^>]*data-date="([0-9-]+)"', html)
                    matches = [(d, l) for l, d in matches]
                
                for d_str, lvl_str in sorted(matches, key=lambda x: x[0]):
                    try:
                        dt = datetime.date.fromisoformat(d_str)
                        gh_weekday = (dt.weekday() + 1) % 7
                    except Exception:
                        gh_weekday = 0
                    stats["days"].append({
                        "date": d_str,
                        "count": int(lvl_str),
                        "level": int(lvl_str),
                        "weekday": gh_weekday
                    })
        except Exception as e:
            raise RuntimeError(f"Failed to fetch public contribution calendar for {username}: {e}")

    # Compute current streak
    days = stats["days"]
    streak = 0
    for day in reversed(days):
        if day["count"] > 0 or day["level"] > 0:
            streak += 1
        elif streak > 0:
            break
    stats["current_streak"] = streak
    
    print(f"[✓] Stats loaded: Repos={stats['public_repos']}, Stars={stats['total_stars']}, Contributions={stats['total_contributions']}, Streak={stats['current_streak']}")
    return stats


# ----------------------------------------------------------------------
# 2. PROFILE CARD BUILDER (dark.svg & light.svg)
# ----------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "card_border": "#30363d",
        "header_bg": "#161b22",
        "header_title": "#8b949e",
        "text_primary": "#e6edf3",
        "text_dim": "#484f58",
        "text_secondary": "#8b949e",
        "prompt_user": "#58a6ff",
        "prompt_at": "#8b949e",
        "prompt_host": "#7ee787",
        "prompt_cmd": "#f0883e",
        "section_tag": "#58a6ff",
        "key_color": "#79c0ff",
        "dot_leader": "#30363d",
        "val_highlight": "#58a6ff",
        "stat_bg": "#161b22",
        "stat_border": "#30363d",
        "stat_num": "#3fb950",
        "stat_label": "#8b949e",
        "stat_sub": "#58a6ff",
        "pill_bg": "#1f2937",
        "pill_border": "#374151",
        "pill_text": "#a5f3fc",
        "pill_web3_bg": "#2e1065",
        "pill_web3_border": "#6b21a8",
        "pill_web3_text": "#d8b4fe",
        "portrait_frame": "#30363d",
        "portrait_feat": "#67e8f9",
        "portrait_fill": "#34d399",
        "cursor": "#58a6ff"
    },
    "light": {
        "bg": "#ffffff",
        "card_border": "#d0d7de",
        "header_bg": "#f6f8fa",
        "header_title": "#57606a",
        "text_primary": "#1f2328",
        "text_dim": "#afb8c1",
        "text_secondary": "#57606a",
        "prompt_user": "#0969da",
        "prompt_at": "#57606a",
        "prompt_host": "#1a7f37",
        "prompt_cmd": "#bc4c00",
        "section_tag": "#0969da",
        "key_color": "#0550ae",
        "dot_leader": "#d0d7de",
        "val_highlight": "#0969da",
        "stat_bg": "#f6f8fa",
        "stat_border": "#d0d7de",
        "stat_num": "#1a7f37",
        "stat_label": "#57606a",
        "stat_sub": "#0969da",
        "pill_bg": "#f1f5f9",
        "pill_border": "#cbd5e1",
        "pill_text": "#0369a1",
        "pill_web3_bg": "#f3e8ff",
        "pill_web3_border": "#d8b4fe",
        "pill_web3_text": "#7e22ce",
        "portrait_frame": "#d0d7de",
        "portrait_feat": "#0891b2",
        "portrait_fill": "#059669",
        "cursor": "#0969da"
    }
}

def build_card_svg(theme_name, stats, dots_data):
    theme = THEMES[theme_name]
    width = 980
    height = 690

    # Keyframe styles for portrait dots
    css_keyframes = []
    for i, grp in enumerate(dots_data["scatter_groups"]):
        dx = grp["dx"]
        dy = grp["dy"]
        delay = grp["delay"]
        css_keyframes.append(f"""
          @keyframes sc_{i} {{
            0%, 100% {{ transform: translate({dx}px, {dy}px); opacity: 0.15; }}
            25%, 75% {{ transform: translate(0px, 0px); opacity: 0.95; }}
          }}
          .g{i} {{
            animation: sc_{i} 7.5s cubic-bezier(0.4, 0, 0.2, 1) infinite;
            animation-delay: {delay}s;
          }}
        """)

    # Cascading line fade-in animations with animation-fill-mode: both
    css_lines = []
    for l_idx in range(1, 26):
        delay = round(0.04 * l_idx, 2)
        css_lines.append(f"""
          .ln-{l_idx} {{
            animation: fadeRow 0.4s ease {delay}s forwards;
          }}
        """)

    css_block = f"""
      <style>
        .mono {{ font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Fira Code', Menlo, Consolas, monospace; }}
        @keyframes fadeRow {{
          0% {{ opacity: 0; transform: translateY(3px); }}
          100% {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes blink {{
          0%, 49% {{ opacity: 1; }}
          50%, 100% {{ opacity: 0; }}
        }}
        .cursor {{
          animation: blink 1s infinite;
        }}
        {"".join(css_keyframes)}
        {"".join(css_lines)}
        @media (prefers-reduced-motion: reduce) {{{{
          .mono * {{{{ animation: none !important; opacity: 1 !important; transform: none !important; }}}}
        }}}}
      </style>
    """

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="auto" class="mono">')
    
    # Clip path to keep portrait dots framed inside the panel
    p_x, p_y = 26, 56
    p_w, p_h = 246, 296
    svg.append('<defs>')
    svg.append(f'<clipPath id="portrait-clip"><rect x="{p_x}" y="{p_y}" width="{p_w}" height="{p_h}" rx="6"/></clipPath>')
    svg.append('</defs>')

    svg.append(css_block)
    
    # Outer Background & Rounded Card
    svg.append(f'<rect width="{width}" height="{height}" rx="12" fill="{theme["bg"]}" stroke="{theme["card_border"]}" stroke-width="1.5"/>')
    
    # Terminal Title Bar
    svg.append(f'<path d="M 0 12 Q 0 0 12 0 L {width-12} 0 Q {width} 0 {width} 12 L {width} 38 L 0 38 Z" fill="{theme["header_bg"]}"/>')
    svg.append(f'<line x1="0" y1="38" x2="{width}" y2="38" stroke="{theme["card_border"]}" stroke-width="1"/>')
    
    # Mac Window Buttons
    svg.append('<circle cx="20" cy="19" r="6" fill="#ff5f56"/>')
    svg.append('<circle cx="40" cy="19" r="6" fill="#ffbd2e"/>')
    svg.append('<circle cx="60" cy="19" r="6" fill="#27c93f"/>')
    
    # Title Bar Text
    svg.append(f'<text x="{width/2}" y="24" text-anchor="middle" font-size="12" font-weight="600" fill="{theme["header_title"]}">bullishdoteth — zsh — 980x690</text>')

    # ------------------------------------------------------------------
    # LEFT PANEL: VISUAL.MAP + STAT TILES
    # ------------------------------------------------------------------
    # Portrait Box Frame
    svg.append(f'<rect x="{p_x}" y="{p_y}" width="{p_w}" height="{p_h}" rx="6" fill="{theme["header_bg"]}" stroke="{theme["portrait_frame"]}" stroke-width="1.2"/>')
    
    # Corner Accents
    corner_len = 10
    svg.append(f'<path d="M {p_x} {p_y+corner_len} L {p_x} {p_y} L {p_x+corner_len} {p_y}" stroke="{theme["prompt_user"]}" stroke-width="2" fill="none"/>')
    svg.append(f'<path d="M {p_x+p_w-corner_len} {p_y} L {p_x+p_w} {p_y} L {p_x+p_w} {p_y+corner_len}" stroke="{theme["prompt_user"]}" stroke-width="2" fill="none"/>')
    svg.append(f'<path d="M {p_x} {p_y+p_h-corner_len} L {p_x} {p_y+p_h} L {p_x+corner_len} {p_y+p_h}" stroke="{theme["prompt_user"]}" stroke-width="2" fill="none"/>')
    svg.append(f'<path d="M {p_x+p_w-corner_len} {p_y+p_h} L {p_x+p_w} {p_y+p_h} L {p_x+p_w} {p_y+p_h-corner_len}" stroke="{theme["prompt_user"]}" stroke-width="2" fill="none"/>')

    # Portrait Dots (Clipped to Box Frame)
    dot_offset_x = p_x + 13
    dot_offset_y = p_y + 35
    svg.append(f'<g clip-path="url(#portrait-clip)">')
    svg.append(f'<g transform="translate({dot_offset_x}, {dot_offset_y})">')
    for dot in dots_data["dots"]:
        dot_color = theme["portrait_feat"] if dot["feat"] else theme["portrait_fill"]
        svg.append(f'<circle class="g{dot["g"]}" cx="{dot["x"]}" cy="{dot["y"]}" r="{dot["r"]}" fill="{dot_color}"/>')
    svg.append('</g>')
    svg.append('</g>')

    # Portrait Header Tag (Drawn above dots)
    svg.append(f'<rect x="{p_x+10}" y="{p_y+8}" width="168" height="18" rx="3" fill="{theme["bg"]}" stroke="{theme["card_border"]}" stroke-width="1"/>')
    svg.append(f'<circle cx="{p_x+18}" cy="{p_y+17}" r="3" fill="#22c55e"/>')
    svg.append(f'<text x="{p_x+28}" y="{p_y+21}" font-size="10" font-weight="700" fill="{theme["prompt_user"]}">VISUAL.MAP // BIO-FEED</text>')
    svg.append(f'<text x="{p_x+p_w-12}" y="{p_y+21}" text-anchor="end" font-size="9" fill="{theme["text_secondary"]}">LIVE</text>')

    # 4 Live Stat Tiles (2x2 grid under portrait)
    stat_x = p_x
    stat_y = p_y + p_h + 14
    tile_w = 118
    tile_h = 68
    gap_x = 10
    gap_y = 10

    stat_tiles = [
        {"label": "CONTRIBUTIONS", "val": str(stats["total_contributions"]), "sub": "This Year"},
        {"label": "STREAK", "val": f"{stats['current_streak']}d", "sub": "Active Activity"},
        {"label": "PUBLIC REPOS", "val": str(stats["public_repos"]), "sub": "Open Source"},
        {"label": "PRODUCTION", "val": "2+ YRS", "sub": "Web3 / Systems"}
    ]

    for idx, tile in enumerate(stat_tiles):
        row = idx // 2
        col = idx % 2
        tx = stat_x + col * (tile_w + gap_x)
        ty = stat_y + row * (tile_h + gap_y)

        svg.append(f'<rect x="{tx}" y="{ty}" width="{tile_w}" height="{tile_h}" rx="5" fill="{theme["stat_bg"]}" stroke="{theme["stat_border"]}" stroke-width="1"/>')
        svg.append(f'<text x="{tx+8}" y="{ty+16}" font-size="9" font-weight="700" fill="{theme["stat_label"]}">{esc(tile["label"])}</text>')
        svg.append(f'<text x="{tx+8}" y="{ty+42}" font-size="20" font-weight="800" fill="{theme["stat_num"]}">{esc(tile["val"])}</text>')
        svg.append(f'<text x="{tx+8}" y="{ty+58}" font-size="8.5" fill="{theme["stat_sub"]}">{esc(tile["sub"])}</text>')

    # ------------------------------------------------------------------
    # RIGHT PANEL: TERMINAL READOUT (whoami)
    # ------------------------------------------------------------------
    rx = 296
    ry = 68
    line_h = 21

    # Top Prompt Line
    svg.append(f'<g class="ln-1">')
    svg.append(f'<text x="{rx}" y="{ry}" font-size="13.5" font-weight="700">')
    svg.append(f'<tspan fill="{theme["prompt_user"]}">{esc(USERNAME.lower())}</tspan>')
    svg.append(f'<tspan fill="{theme["prompt_at"]}">@</tspan>')
    svg.append(f'<tspan fill="{theme["prompt_host"]}">github</tspan>')
    svg.append(f'<tspan fill="{theme["text_primary"]}">:~$ </tspan>')
    svg.append(f'<tspan fill="{theme["prompt_cmd"]}">whoami --verbose --identity</tspan>')
    svg.append('</text></g>')

    # Helper function for aligned dot leader row
    def render_row(svg_list, ln_id, y_pos, key_text, val_text, target_len=44, val_color=theme["text_primary"], val_bold=False):
        svg_list.append(f'<g class="ln-{ln_id}">')
        dots_count = max(2, target_len - len(key_text))
        dots_str = "." * dots_count
        svg_list.append(f'<text x="{rx}" y="{y_pos}" font-size="12.5">')
        svg_list.append(f'<tspan fill="{theme["key_color"]}" font-weight="600">{esc(key_text)} </tspan>')
        svg_list.append(f'<tspan fill="{theme["dot_leader"]}">{esc(dots_str)} </tspan>')
        weight = 'font-weight="700"' if val_bold else ''
        svg_list.append(f'<tspan fill="{val_color}" {weight}>{esc(val_text)}</tspan>')
        svg_list.append('</text></g>')

    # Helper to render pill badges
    def render_pills_row(svg_list, ln_id, y_pos, key_text, pills, is_web3=False):
        svg_list.append(f'<g class="ln-{ln_id}">')
        dots_str = "...."
        svg_list.append(f'<text x="{rx}" y="{y_pos}" font-size="12.5">')
        svg_list.append(f'<tspan fill="{theme["key_color"]}" font-weight="600">{esc(key_text)} </tspan>')
        svg_list.append(f'<tspan fill="{theme["dot_leader"]}">{esc(dots_str)} </tspan>')
        svg_list.append('</text>')
        
        curr_x = rx + len(key_text) * 7.6 + len(dots_str) * 7.6 + 18
        p_bg = theme["pill_web3_bg"] if is_web3 else theme["pill_bg"]
        p_border = theme["pill_web3_border"] if is_web3 else theme["pill_border"]
        p_text = theme["pill_web3_text"] if is_web3 else theme["pill_text"]
        
        for pill in pills:
            pill_w = len(pill) * 7.2 + 14
            svg_list.append(f'<rect x="{curr_x}" y="{y_pos-13}" width="{pill_w}" height="17" rx="3.5" fill="{p_bg}" stroke="{p_border}" stroke-width="0.9"/>')
            svg_list.append(f'<text x="{curr_x + pill_w/2}" y="{y_pos-1}" text-anchor="middle" font-size="10.5" font-weight="600" fill="{p_text}">{esc(pill)}</text>')
            curr_x += pill_w + 6
        svg_list.append('</g>')

    curr_y = ry + 26
    ln = 2

    # SECTION 1: IDENTITY
    svg.append(f'<g class="ln-{ln}"><text x="{rx}" y="{curr_y}" font-size="11" font-weight="800" fill="{theme["section_tag"]}">// 01. IDENTITY &amp; STATUS</text></g>')
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Role", "Web3 Product Design & Software Engineering", 18, theme["text_primary"], True)
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Status", "Available for work  ●  [OPEN TO CONTRACTS]", 18, "#22c55e", True)
    curr_y += line_h + 4
    ln += 1

    # SECTION 2: DAILY ARSENAL
    svg.append(f'<g class="ln-{ln}"><text x="{rx}" y="{curr_y}" font-size="11" font-weight="800" fill="{theme["section_tag"]}">// 02. DAILY ARSENAL</text></g>')
    curr_y += line_h
    ln += 1

    daily_tools = ["VS Code", "Docker", "Figma", "GitHub", "Git", "Antigravity IDE"]
    render_pills_row(svg, ln, curr_y, "Tools", daily_tools, False)
    curr_y += line_h + 4
    ln += 1

    # SECTION 3: TECH STACK
    svg.append(f'<g class="ln-{ln}"><text x="{rx}" y="{curr_y}" font-size="11" font-weight="800" fill="{theme["section_tag"]}">// 03. FULL-STACK &amp; WEB3 STACK</text></g>')
    curr_y += line_h
    ln += 1

    render_pills_row(svg, ln, curr_y, "Frontend", ["React", "Next.js", "TypeScript", "Tailwind CSS"], False)
    curr_y += line_h - 1
    ln += 1

    render_pills_row(svg, ln, curr_y, "Backend", ["Node.js", "Solidity", "Ethers.js", "Python"], True)
    curr_y += line_h - 1
    ln += 1

    render_pills_row(svg, ln, curr_y, "Database", ["PostgreSQL", "MongoDB", "Redis"], False)
    curr_y += line_h - 1
    ln += 1

    render_pills_row(svg, ln, curr_y, "Cloud", ["Ethereum", "Vercel", "Docker", "IPFS"], True)
    curr_y += line_h + 4
    ln += 1

    # SECTION 4: FEATURED SHIPMENTS
    svg.append(f'<g class="ln-{ln}"><text x="{rx}" y="{curr_y}" font-size="11" font-weight="800" fill="{theme["section_tag"]}">// 04. FEATURED SHIPMENTS</text></g>')
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Oncollably", "Web3 collaboration tool -> oncollable.vercel.app", 18, theme["val_highlight"], False)
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Splendo", "Scan-to-order SaaS platform -> splendoqr.vercel.app", 18, theme["val_highlight"], False)
    curr_y += line_h + 4
    ln += 1

    # SECTION 5: TRACK RECORD
    svg.append(f'<g class="ln-{ln}"><text x="{rx}" y="{curr_y}" font-size="11" font-weight="800" fill="{theme["section_tag"]}">// 05. TRACK RECORD</text></g>')
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Experience", "2+ Years in Production building dApps & full-stack apps", 18, theme["text_primary"], False)
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Discipline", "Web3 UI/UX Design, Smart Contracts & Cloud Deployment", 18, theme["text_primary"], False)
    curr_y += line_h + 4
    ln += 1

    # SECTION 6: TRANSMISSION
    svg.append(f'<g class="ln-{ln}"><text x="{rx}" y="{curr_y}" font-size="11" font-weight="800" fill="{theme["section_tag"]}">// 06. TRANSMISSION / CONTACT</text></g>')
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Website", "https://bullishdoteth.com", 18, theme["val_highlight"], False)
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "X / Twitter", "https://x.com/bullishdoteth  [@bullishdoteth]", 18, theme["text_primary"], False)
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Discord", "discord.gg/bullishdoteth", 18, theme["text_primary"], False)
    curr_y += line_h
    ln += 1

    render_row(svg, ln, curr_y, "Email", "contact@bullishdoteth.com", 18, theme["prompt_host"], True)
    curr_y += line_h + 10
    ln += 1

    # Bottom Prompt & Blinking Cursor
    svg.append(f'<g class="ln-{ln}">')
    svg.append(f'<text x="{rx}" y="{curr_y}" font-size="13.5" font-weight="700">')
    svg.append(f'<tspan fill="{theme["prompt_user"]}">{esc(USERNAME.lower())}</tspan>')
    svg.append(f'<tspan fill="{theme["prompt_at"]}">@</tspan>')
    svg.append(f'<tspan fill="{theme["prompt_host"]}">github</tspan>')
    svg.append(f'<tspan fill="{theme["text_primary"]}">:~$ </tspan>')
    svg.append(f'</text>')
    cursor_x = rx + (len(USERNAME.lower()) + len("@github:~$ ")) * 8.2 + 8
    svg.append(f'<rect class="cursor" x="{cursor_x}" y="{curr_y-13}" width="8" height="15" fill="{theme["cursor"]}"/>')
    svg.append('</g>')

    svg.append('</svg>')
    return "".join(svg)


# ----------------------------------------------------------------------
# 3. ANIMATED CONTRIBUTION SNAKE (snake.svg)
# ----------------------------------------------------------------------

def build_snake_svg(stats):
    width = 880
    height = 200
    
    cell_size = 11
    pitch = 14.5
    start_x = 52
    start_y = 48

    palette = {
        0: "#161b22",
        1: "#0e4429",
        2: "#006d32",
        3: "#26a641",
        4: "#39d353"
    }

    days_data = stats.get("days", [])
    total_days = len(days_data)
    
    needed_cells = 53 * 7
    if total_days < needed_cells:
        padding = [{"count": 0, "level": 0, "weekday": i % 7} for i in range(needed_cells - total_days)]
        grid_days = padding + days_data
    else:
        grid_days = days_data[-needed_cells:]

    cells_svg = []
    
    # Path of waypoints for snake
    waypoints = [
        (4, 1), (10, 1), (10, 5), (18, 5), (18, 2), (24, 2),
        (24, 6), (32, 6), (32, 1), (38, 1), (38, 4), (44, 4),
        (44, 1), (50, 1), (50, 5), (46, 5), (46, 6), (36, 6),
        (36, 3), (28, 3), (28, 0), (14, 0), (14, 4), (4, 4)
    ]
    wp_set = set(waypoints)

    for idx, d in enumerate(grid_days):
        col = idx // 7
        row = idx % 7
        cx = start_x + col * pitch
        cy = start_y + row * pitch
        lvl = d.get("level", 0)
        c_fill = palette.get(lvl, palette[0])
        cid = f"c_{col}_{row}"

        cell_class = "c-cell"
        if (col, row) in wp_set and lvl > 0:
            cell_class += " eaten-cell"

        cells_svg.append(f'<rect id="{cid}" class="{cell_class}" x="{cx}" y="{cy}" width="{cell_size}" height="{cell_size}" rx="2" fill="{c_fill}"/>')

    keyframe_steps = []
    num_wp = len(waypoints)
    for i, (w_col, w_row) in enumerate(waypoints):
        pct = round((i / num_wp) * 100, 1)
        px = start_x + w_col * pitch
        py = start_y + w_row * pitch
        keyframe_steps.append(f"{pct}% {{ transform: translate({px}px, {py}px); }}")
    
    first_px = start_x + waypoints[0][0] * pitch
    first_py = start_y + waypoints[0][1] * pitch
    keyframe_steps.append(f"100% {{ transform: translate({first_px}px, {first_py}px); }}")

    num_segments = 7
    segment_tags = []
    for s_idx in range(num_segments):
        delay = -round(s_idx * 0.16, 2)
        if s_idx == 0:
            fill = "#38bdf8"
            stroke = "#ffffff"
            r = 2.5
        else:
            alpha = max(0.3, 1.0 - (s_idx / num_segments))
            fill = f"rgba(56, 189, 248, {alpha:.2f})"
            stroke = "#0284c7"
            r = 2.0

        segment_tags.append(
            f'<rect class="snake-seg" style="animation-delay: {delay}s;" width="{cell_size}" height="{cell_size}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="0.8"/>'
        )

    css = f"""
      <style>
        .snake-mono {{ font-family: ui-monospace, 'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace; }}
        @keyframes snakePatrol {{
          {" ".join(keyframe_steps)}
        }}
        .snake-seg {{
          animation: snakePatrol 18s linear infinite;
        }}
        @keyframes pulseGlow {{
          0%, 100% {{ opacity: 0.85; filter: drop-shadow(0 0 3px #38bdf8); }}
          50% {{ opacity: 1; filter: drop-shadow(0 0 6px #38bdf8); }}
        }}
        .snake-head-glow {{
          animation: pulseGlow 2s ease-in-out infinite;
        }}
        @keyframes respawn {{
          0%, 100% {{ opacity: 1; }}
          40% {{ opacity: 0.2; }}
          70% {{ opacity: 0.7; }}
        }}
        .eaten-cell {{
          animation: respawn 18s ease-in-out infinite;
        }}
        .day-label {{ font-size: 8.5px; fill: #6e7681; }}
        .month-label {{ font-size: 9px; fill: #6e7681; }}
      </style>
    """

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="auto" class="snake-mono">')
    svg.append(css)
    
    # Outer Frame
    svg.append(f'<rect width="{width}" height="{height}" rx="10" fill="#0d1117" stroke="#30363d" stroke-width="1.2"/>')
    
    # Header bar
    svg.append(f'<path d="M 0 10 Q 0 0 10 0 L {width-10} 0 Q {width} 0 {width} 10 L {width} 30 L 0 30 Z" fill="#161b22"/>')
    svg.append(f'<line x1="0" y1="30" x2="{width}" y2="30" stroke="#30363d" stroke-width="1"/>')
    
    # Header Title
    svg.append(f'<text x="24" y="19" font-size="11" font-weight="700" fill="#58a6ff">🐍 BULLISHDOTETH // CONTRIBUTION SNAKE</text>')
    svg.append(f'<text x="{width-24}" y="19" text-anchor="end" font-size="10" fill="#8b949e">{esc(stats["total_contributions"])} Contributions in the Last Year</text>')

    # Month Labels
    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    for m_i, m_name in enumerate(months):
        m_x = start_x + (m_i * 4.4) * pitch
        svg.append(f'<text class="month-label" x="{m_x}" y="42">{esc(m_name)}</text>')

    # Day of week labels (Mon, Wed, Fri)
    svg.append(f'<text class="day-label" x="{start_x-26}" y="{start_y + 1*pitch + 9}">Mon</text>')
    svg.append(f'<text class="day-label" x="{start_x-26}" y="{start_y + 3*pitch + 9}">Wed</text>')
    svg.append(f'<text class="day-label" x="{start_x-26}" y="{start_y + 5*pitch + 9}">Fri</text>')

    # Render Board Cells
    svg.append('<g class="board-cells">')
    svg.extend(cells_svg)
    svg.append('</g>')

    # Render Snake Segments
    svg.append('<g class="snake-team snake-head-glow">')
    svg.extend(reversed(segment_tags))
    svg.append('</g>')

    # Footer Status & Legend
    footer_y = height - 16
    svg.append(f'<text x="24" y="{footer_y}" font-size="9.5" fill="#8b949e">STATUS: SNAKE PATROL ACTIVE  ●  AUTONOMOUS TRAVERSAL</text>')
    
    # Legend
    legend_start_x = width - 150
    svg.append(f'<text x="{legend_start_x - 30}" y="{footer_y}" font-size="9" fill="#6e7681">Less</text>')
    for l_idx in range(5):
        lx = legend_start_x + l_idx * 14
        svg.append(f'<rect x="{lx}" y="{footer_y-8}" width="10" height="10" rx="2" fill="{palette[l_idx]}"/>')
    svg.append(f'<text x="{legend_start_x + 5*14 + 6}" y="{footer_y}" font-size="9" fill="#6e7681">More</text>')

    svg.append('</svg>')
    return "".join(svg)


# ----------------------------------------------------------------------
# MAIN EXECUTION
# ----------------------------------------------------------------------

def main():
    dots_file = sys.argv[1] if len(sys.argv) > 1 else "dots.json"
    if not os.path.exists(dots_file):
        raise FileNotFoundError(f"'{dots_file}' not found. Please run portrait.py first to generate dots.json.")

    with open(dots_file, "r") as f:
        dots_data = json.load(f)

    # 1. Fetch live GitHub stats
    stats = fetch_github_data(USERNAME)

    # 2. Build dark.svg
    dark_svg = build_card_svg("dark", stats, dots_data)
    with open("dark.svg", "w", encoding="utf-8") as f:
        f.write(dark_svg)
    print(f"[✓] Successfully generated dark.svg ({len(dark_svg)} bytes)")

    # 3. Build light.svg
    light_svg = build_card_svg("light", stats, dots_data)
    with open("light.svg", "w", encoding="utf-8") as f:
        f.write(light_svg)
    print(f"[✓] Successfully generated light.svg ({len(light_svg)} bytes)")

    # 4. Build snake.svg
    snake_svg = build_snake_svg(stats)
    with open("snake.svg", "w", encoding="utf-8") as f:
        f.write(snake_svg)
    print(f"[✓] Successfully generated snake.svg ({len(snake_svg)} bytes)")


if __name__ == "__main__":
    main()
