#!/usr/bin/env python3
"""
Visual helpers shared by the notebook generator and the lab-guide generator, so
a "Step 3" banner looks identical in the Colab notebook and its printed guide.

Everything renders on free Google Colab and GitHub markdown: banners and badges
are inline data-URI SVGs (no external files to fetch), callouts are simple
blockquotes with emoji so they survive any renderer.
"""
import base64

# Palette — matches the book's decks and diagrams.
INK = "#1B2733"
AMBER = "#F2A900"
GREEN = "#2FA84F"
BLUE = "#3D7EDB"
RED = "#E5484D"
PANEL = "#F4F6F8"
MUTE = "#6B7885"


def _data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def step_banner(num: int, title: str, subtitle: str = "", accent: str = AMBER) -> str:
    """A wide numbered banner headlining a step. Returns a markdown image line."""
    sub = ""
    if subtitle:
        sub = (f'<text x="86" y="43" font-family="Arial,Helvetica,sans-serif" '
               f'font-size="13" fill="#C9D3DC">{_esc(subtitle)}</text>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="60">'
        f'<rect width="720" height="60" rx="10" fill="{INK}"/>'
        f'<rect x="0" y="0" width="6" height="60" rx="3" fill="{accent}"/>'
        f'<circle cx="42" cy="30" r="19" fill="{accent}"/>'
        f'<text x="42" y="37" font-family="Arial,Helvetica,sans-serif" font-size="20" '
        f'font-weight="bold" fill="{INK}" text-anchor="middle">{num}</text>'
        f'<text x="86" y="{27 if subtitle else 37}" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="19" font-weight="bold" fill="#FFFFFF">{_esc(title)}</text>'
        f'{sub}</svg>'
    )
    return f"![Step {num}: {title}]({_data_uri(svg)})"


def pill(label: str, color: str = BLUE) -> str:
    """A small inline badge, e.g. a tier label."""
    w = 22 + len(label) * 8
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="26">'
        f'<rect width="{w}" height="26" rx="13" fill="{color}"/>'
        f'<text x="{w/2}" y="18" font-family="Arial,Helvetica,sans-serif" font-size="13" '
        f'font-weight="bold" fill="#FFFFFF" text-anchor="middle">{_esc(label)}</text></svg>'
    )
    return f"![{label}]({_data_uri(svg)})"


def progress_bar(done: int, total: int, caption: str = "") -> str:
    """A lab-progress strip: `done` of `total` steps filled."""
    seg_w, gap, h = 60, 6, 16
    width = total * seg_w + (total - 1) * gap
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h+20}">']
    for i in range(total):
        x = i * (seg_w + gap)
        fill = GREEN if i < done else "#D5DCE3"
        parts.append(f'<rect x="{x}" y="0" width="{seg_w}" height="{h}" rx="4" fill="{fill}"/>')
        parts.append(f'<text x="{x + seg_w/2}" y="{h-3}" font-family="Arial" font-size="10" '
                     f'fill="#FFFFFF" text-anchor="middle">{i+1}</text>')
    if caption:
        parts.append(f'<text x="0" y="{h+15}" font-family="Arial" font-size="11" '
                     f'fill="{MUTE}">{_esc(caption)}</text>')
    parts.append('</svg>')
    return f"![progress]({_data_uri(''.join(parts))})"


def callout(kind: str, text: str) -> list[str]:
    """A blockquote callout. kind: 'tip' | 'watch' | 'check' | 'why' | 'help'."""
    icon = {"tip": "💡 **Tip**", "watch": "👀 **Watch for**",
            "check": "✅ **Checkpoint**", "why": "🧠 **Why this matters**",
            "help": "🛟 **If it breaks**"}[kind]
    return [f"> {icon} — {text}"]


def expected_output(lines: list[str]) -> list[str]:
    """A 'you should see this' panel built from real captured output."""
    body = ["> 📟 **You should see something like this:**", ">", "> ```text"]
    body += ["> " + ln for ln in lines]
    body += ["> ```"]
    return body


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
