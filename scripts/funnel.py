#!/usr/bin/env python3
"""compact-autopilot: make Claude Code save its memory BEFORE it auto-compacts.

Hook events (wired in hooks/hooks.json):
  Stop, PostToolUse     check()      once context passes SAVE_PCT (or the 5-hour / weekly limit
                                     passes LIMIT_PCT), tell Claude to write memory + continuity
                                     notes. PostToolUse catches long turns that never reach Stop.
  PreCompact            precompact() re-arm the trigger; optional local transcript backup.
  SessionStart:compact  compact()    point Claude at its continuity notes after compaction.

Compaction itself is Claude Code's built-in auto-compact, moved earlier with
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE by the setup skill. Nothing here touches the network.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path


def opt(key, default):
    """Plugin userConfig values arrive as CLAUDE_PLUGIN_OPTION_<KEY>."""
    v = os.environ.get(f"CLAUDE_PLUGIN_OPTION_{key.upper()}", "")
    return v if v != "" else default


DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "compact-autopilot")
SAVE_PCT = float(opt("save_pct", 80))
LIMIT_PCT = float(opt("limit_pct", 85))
WINDOW = int(opt("context_window", 200_000))
BACKUPS = str(opt("backups", "false")).lower() == "true"  # off by default: no conversation copies unless asked
KEEP = int(opt("backup_keep", 10))
BIG_WINDOW = 1_000_000

# This exact text is what Claude receives. It is also quoted in the README: no hidden instructions.
INSTRUCTION = """[compact-autopilot] {reason}. Claude Code will auto-compact soon and the details of this conversation will be summarized away. Before continuing:
1. Save to your memory ({memory}) anything from this session worth keeping across sessions: new rules or corrections from the user, decisions made, and facts about the project. Update existing entries instead of duplicating them.
2. Overwrite {continuity} with continuity notes: what you are working on, what is half-done, the exact next step, files touched, and any pending user requests.
3. Do this quietly, then carry on with the task. Do not ask the user about it."""


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default if default is not None else {}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)  # atomic: a crash never leaves half a file


def last_usage(transcript):
    """Tokens in context at the last model call = the usage of the last assistant message."""
    used = 0
    try:
        with open(transcript, "rb") as f:
            f.seek(max(0, os.path.getsize(transcript) - 512_000))  # the last message is always near the end
            for line in f.read().decode(errors="ignore").splitlines():
                try:
                    u = json.loads(line).get("message", {}).get("usage")
                except (ValueError, AttributeError):
                    continue
                if u:
                    used = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                       "cache_read_input_tokens", "output_tokens"))
    except OSError:
        pass
    return used


def window_size(sid, used):
    """Exact size from this session's statusline snapshot; else the configured size.
    No hook input carries the window size, and the model id doesn't reveal it either."""
    size = read_json(DATA / "sessions" / f"{sid}.json").get("context_window", {}).get("context_window_size")
    size = size or WINDOW
    return BIG_WINDOW if used > size else size  # usage beyond the configured size proves a bigger window


def check(h, event):
    if h.get("stop_hook_active"):  # Claude is already acting on our reason: don't loop
        return
    sid = h.get("session_id") or "unknown"
    transcript = h.get("transcript_path") or ""
    flag_file = DATA / "flags" / f"{sid}.json"
    flags = read_json(flag_file)
    reasons = []

    used = last_usage(transcript)
    pct = 100 * used / window_size(sid, used)
    if pct >= SAVE_PCT and not flags.get("ctx"):
        flags["ctx"] = True
        reasons.append(f"Context is {pct:.0f}% full")

    limits = read_json(DATA / "latest.json").get("rate_limits") or {}
    for key, label in (("five_hour", "5-hour usage limit"), ("seven_day", "weekly usage limit")):
        lim = limits.get(key) or {}
        if (lim.get("used_percentage") or 0) >= LIMIT_PCT and flags.get(key) != lim.get("resets_at"):
            flags[key] = lim.get("resets_at")  # once per limit window
            reasons.append(f"{label} is at {lim['used_percentage']:.0f}% and the session may be cut off")

    if not reasons:
        return
    write_json(flag_file, flags)
    msg = INSTRUCTION.format(reason="; ".join(reasons),
                             memory=Path(transcript).parent / "memory",
                             continuity=DATA / "continuity" / f"{sid}.md")
    (DATA / "continuity").mkdir(parents=True, exist_ok=True)
    if event == "Stop":
        print(json.dumps({"decision": "block", "reason": msg}))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": msg}}))


def precompact(h):
    sid = h.get("session_id") or "unknown"
    flag_file = DATA / "flags" / f"{sid}.json"
    flags = read_json(flag_file)
    flags.pop("ctx", None)  # after compaction the context threshold counts again
    write_json(flag_file, flags)

    src = Path(h.get("transcript_path") or "")
    if BACKUPS and src.is_file():
        dest = DATA / "backups"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / f"{time.strftime('%Y-%m-%d_%H%M%S')}_{sid[:8]}.jsonl")
        for old in sorted(dest.glob("*.jsonl"))[:-KEEP]:  # names sort by date: keep the newest KEEP
            old.unlink()


def compact(h):
    notes = DATA / "continuity" / f"{h.get('session_id') or 'unknown'}.md"
    if notes.is_file():
        print(f"[compact-autopilot] The conversation was just compacted. Read {notes} "
              "and your memory before continuing, then pick up where you left off.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    hook = json.loads(sys.stdin.read() or "{}")
    if mode in ("Stop", "PostToolUse"):
        check(hook, mode)
    elif mode == "PreCompact":
        precompact(hook)
    elif mode == "compact":
        compact(hook)
    else:
        sys.exit(f"usage: funnel.py Stop|PostToolUse|PreCompact|compact  (got {mode!r})")
