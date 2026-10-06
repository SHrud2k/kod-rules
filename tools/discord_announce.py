"""Post the latest (or a chosen) data/changelog.json entry to Discord via webhook.

Reads DISCORD_WEBHOOK_URL and optional ENTRY_INDEX from the environment.
Never prints the webhook URL — only generic status messages.
"""
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

SITE_ROOT = "https://shrud2k.github.io/kod-rules"
ICON_URL = "https://cdn.discordapp.com/icons/584663327465275417/9e4e813f016f3ad71a982f949082caba.webp?size=256&quality=lossless"
EMBED_COLOR = 5793266

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = ROOT / "data" / "changelog.json"

LINK_RE = re.compile(r'<a href="(#[^"]+)">([^<]*)</a>')
TAG_RE = re.compile(r"<[^>]+>")


def md_link(match):
    anchor, text = match.group(1), match.group(2)
    return f"[{text}]({SITE_ROOT}/{anchor})"


def clean(item):
    item = LINK_RE.sub(md_link, item)
    item = TAG_RE.sub("", item)
    return html.unescape(item)


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL is not set — add it as a repo secret first.", file=sys.stderr)
        sys.exit(1)

    index = int(os.environ.get("ENTRY_INDEX", "0"))

    data = json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
    entries = data["entries"]
    if index >= len(entries):
        print(f"ENTRY_INDEX={index} is out of range ({len(entries)} entries).", file=sys.stderr)
        sys.exit(1)

    entry = entries[index]
    date = entry["date"]
    lines = [f"• {clean(item)}" for item in entry["items"]]
    description = "\n".join(lines)
    if len(description) > 4000:
        description = description[:4000].rsplit("\n", 1)[0] + "\n• …"

    payload = {
        "username": "Kill OR Die | Правила",
        "avatar_url": ICON_URL,
        "embeds": [
            {
                "title": f"📝 Обновление правил — {date}",
                "description": description,
                "color": EMBED_COLOR,
                "fields": [
                    {
                        "name": "📖 Полный список изменений",
                        "value": f"[shrud2k.github.io/kod-rules/changes]({SITE_ROOT}/changes.html)",
                        "inline": False,
                    }
                ],
                "footer": {"text": "Незнание правил не освобождает от ответственности."},
            }
        ],
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            # Discord's edge (Cloudflare) 403s the default Python-urllib UA string.
            "User-Agent": "Mozilla/5.0 (compatible; kod-rules-changelog-bot/1.0; +https://github.com/SHrud2k/kod-rules)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Discord webhook responded with status {resp.status} for entry {date}.")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"Discord webhook failed: HTTP {e.code} {e.reason} — {detail}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
