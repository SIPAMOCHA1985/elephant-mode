#!/usr/bin/env python3
"""Claude Code statusLine command: snapshot the session data for the funnel and the screen,
then print one short line. Installed by the setup skill next to the plugin's data directory."""
import json
import os
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent  # setup copies this file into the plugin data dir
ALERT = 85


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


sys.stdout.reconfigure(encoding="utf-8")  # Windows defaults to cp1252
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
try:
    j = json.loads(raw)
except ValueError:
    sys.exit(0)
save(DATA / "latest.json", raw)  # the screen and the account-wide limits read this
sid = j.get("session_id") or j.get("sessionId")  # Grok may use camelCase
if sid:
    save(DATA / "sessions" / f"{sid}.json", raw)  # exact window size per session

ctx = (j.get("context_window") or {}).get("used_percentage") or 0
rl = j.get("rate_limits") or {}
parts = [f"ctx {ctx:.0f}%"] + [f"{name} {rl[k]['used_percentage']:.0f}%"
                                for k, name in (("five_hour", "5h"), ("seven_day", "7d"))
                                if (rl.get(k) or {}).get("used_percentage") is not None]
hot = max([ctx] + [(rl.get(k) or {}).get("used_percentage") or 0 for k in ("five_hour", "seven_day")]) >= ALERT
line = " · ".join(parts)
print(f"\033[31m⚠ {line}\033[0m" if hot else line)
