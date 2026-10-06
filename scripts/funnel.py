#!/usr/bin/env python3
"""elephant-mode: make Claude Code save its memory BEFORE it auto-compacts.

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


DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "elephant-mode")
SAVE_PCT = float(opt("save_pct", 80))
LIMIT_PCT = float(opt("limit_pct", 85))
WINDOW = int(opt("context_window", 200_000))
BACKUPS = str(opt("backups", "false")).lower() == "true"  # off by default: no conversation copies unless asked
KEEP = int(opt("backup_keep", 10))
BIG_WINDOW = 1_000_000
CODEX = "PLUGIN_ROOT" in os.environ  # Codex sets PLUGIN_ROOT (and CLAUDE_PLUGIN_ROOT for compat); Claude Code only the latter
LIMIT_LABELS = {300: "5-hour usage limit", 10080: "weekly usage limit"}  # Codex limit windows, in minutes

# This exact text is what Claude receives. It is also quoted in the README: no hidden instructions.
INSTRUCTION = """[elephant-mode] {reason}. Claude Code will auto-compact soon and the details of this conversation will be summarized away. Before continuing:
1. Save to your memory ({memory}) anything from this session worth keeping across sessions: new rules or corrections from the user, decisions made, and facts about the project. Update existing entries instead of duplicating them.
2. Overwrite {continuity} with continuity notes: what you are working on, what is half-done, the exact next step, files touched, and any pending user requests.
3. Do this quietly, then carry on with the task. Do not ask the user about it."""


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)  # atomic: a crash never leaves half a file


def last_usage(transcript):
    """Tokens in context at the last model call, and on Codex the window size and usage limits too.
    Claude Code: usage of the last assistant message. Codex: its last token_count event."""
    used, window, limits = 0, None, None
    try:
        with open(transcript, "rb") as f:
            f.seek(max(0, os.path.getsize(transcript) - 512_000))  # the last message is always near the end
            for line in f.read().decode("utf-8", errors="ignore").splitlines():
                try:
                    j = json.loads(line)
                    u = j.get("message", {}).get("usage")
                    tc = j.get("payload") or {}
                    tc = tc if tc.get("type") == "token_count" else None
                except (ValueError, AttributeError):
                    continue
                if u:
                    used = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                       "cache_read_input_tokens", "output_tokens"))
                elif tc:
                    # ponytail: Codex's own meter also subtracts a 12K fixed baseline; ignored, so we read ~1-3 % higher
                    info = tc.get("info") or {}
                    used = (info.get("last_token_usage") or {}).get("total_tokens") or used
                    window = info.get("model_context_window") or window
                    limits = tc.get("rate_limits") or limits
    except OSError:
        pass
    return used, window, limits


def window_size(sid, used, window=None):
    """Codex logs the exact size; Claude Code's comes from this session's statusline snapshot;
    else the configured size. Claude's hook input doesn't carry it, and the model id doesn't reveal it."""
    size = window or read_json(DATA / "sessions" / f"{sid}.json").get("context_window", {}).get("context_window_size")
    size = size or WINDOW
    return BIG_WINDOW if used > size else size  # usage beyond the configured size proves a bigger window


def usage_limits(codex_limits):
    """(key, label, used %, resets_at) per limit. Codex logs them in the transcript;
    Claude Code's come from the statusline snapshot."""
    if codex_limits is not None:
        return [(k, LIMIT_LABELS.get(w.get("window_minutes"), f"{w.get('window_minutes')}-minute usage limit"),
                 w.get("used_percent"), w.get("resets_at"))
                for k in ("primary", "secondary") if (w := codex_limits.get(k) or {})]
    limits = read_json(DATA / "latest.json").get("rate_limits") or {}
    return [(k, label, (limits.get(k) or {}).get("used_percentage"), (limits.get(k) or {}).get("resets_at"))
            for k, label in (("five_hour", "5-hour usage limit"), ("seven_day", "weekly usage limit"))]


def memory_path(transcript):
    """Claude Code keeps memory next to the transcript. Codex's own memory is internal, so it gets a file here."""
    return DATA / "memory.md" if CODEX else Path(transcript).parent / "memory"


def check(h, event):
    if h.get("stop_hook_active"):  # Claude is already acting on our reason: don't loop
        return
    sid = h.get("session_id") or "unknown"
    transcript = h.get("transcript_path") or ""
    flag_file = DATA / "flags" / f"{sid}.json"
    flags = read_json(flag_file)
    reasons = []

    used, window, codex_limits = last_usage(transcript)
    pct = 100 * used / window_size(sid, used, window)
    if pct >= SAVE_PCT and not flags.get("ctx"):
        flags["ctx"] = True
        reasons.append(f"Context is {pct:.0f}% full")

    for key, label, used_pct, resets_at in usage_limits(codex_limits):
        if (used_pct or 0) >= LIMIT_PCT and flags.get(key) != resets_at:
            flags[key] = resets_at  # once per limit window
            reasons.append(f"{label} is at {used_pct:.0f}% and the session may be cut off")

    if not reasons:
        return
    write_json(flag_file, flags)
    msg = INSTRUCTION.format(reason="; ".join(reasons),
                             memory=memory_path(transcript),
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
        memory = DATA / "memory.md" if CODEX else "your memory"
        print(f"[elephant-mode] The conversation was just compacted. Read {notes} "
              f"and {memory} before continuing, then pick up where you left off.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows defaults to cp1252
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    hook = json.loads(sys.stdin.buffer.read() or b"{}")
    if mode in ("Stop", "PostToolUse"):
        check(hook, mode)
    elif mode == "PreCompact":
        precompact(hook)
    elif mode == "compact":
        compact(hook)
    else:
        sys.exit(f"usage: funnel.py Stop|PostToolUse|PreCompact|compact  (got {mode!r})")
