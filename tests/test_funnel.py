#!/usr/bin/env python3
"""Self-check for scripts/funnel.py and scripts/statusline.py. Run: python3 tests/test_funnel.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNNEL = ROOT / "scripts" / "funnel.py"


def run(mode, hook, data, **opts):
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data),
           **{f"CLAUDE_PLUGIN_OPTION_{k.upper()}": str(v) for k, v in opts.items()}}
    out = subprocess.run([sys.executable, str(FUNNEL), mode], input=json.dumps(hook),
                         capture_output=True, text=True, encoding="utf-8", env=env, check=True).stdout
    return json.loads(out) if out.strip().startswith("{") else out


def transcript(dir, tokens, name="t.jsonl"):
    p = Path(dir) / name
    p.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n" +
                 json.dumps({"message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": tokens - 1}}}) + "\n")
    return str(p)


with tempfile.TemporaryDirectory() as tmp:
    data = Path(tmp) / "data"
    low, high = transcript(tmp, 100_000, "low.jsonl"), transcript(tmp, 170_000, "high.jsonl")  # 50 % / 85 % of 200K
    hook = lambda t, sid="s1", **kw: {"session_id": sid, "transcript_path": t, **kw}

    assert run("Stop", hook(low), data) == "", "50 %: does nothing"

    out = run("Stop", hook(high), data)
    assert out["decision"] == "block" and "Context is 85% full" in out["reason"], out
    assert str(Path(tmp) / "memory") in out["reason"], "memory dir is derived from the transcript's project dir"
    assert run("Stop", hook(high), data) == "", "fires once per compaction cycle"
    assert run("Stop", hook(high, "s2", stop_hook_active=True), data) == "", "never loops"

    out = run("PostToolUse", hook(high, "s3"), data)
    assert out["hookSpecificOutput"]["additionalContext"].startswith("[elephant-mode]"), "mid-turn path"

    run("PreCompact", hook(high), data)
    assert not (data / "backups").exists(), "backups are OFF by default"
    assert run("Stop", hook(high), data)["decision"] == "block", "re-armed after compaction"

    for i in range(3):
        run("PreCompact", {"session_id": f"b{i}", "transcript_path": high}, data, backups="true", backup_keep=2)
    assert len(list((data / "backups").glob("*.jsonl"))) == 2, "backups ON keep only the newest N"

    # window size: the session snapshot beats the default; usage over the default implies 1M
    (data / "sessions").mkdir()
    (data / "sessions" / "big.json").write_text(json.dumps({"context_window": {"context_window_size": 1_000_000}}))
    assert run("Stop", hook(high, "big"), data) == "", "170K of a 1M window is only 17 %"
    assert run("Stop", hook(transcript(tmp, 300_000, "over.jsonl"), "over"), data) == "", "300K > 200K default -> 1M window, 30 %"

    # usage limits come from the statusline snapshot, once per limit window
    (data / "latest.json").write_text(json.dumps({"rate_limits": {"seven_day": {"used_percentage": 90, "resets_at": 1}}}))
    assert "weekly usage limit is at 90%" in run("Stop", hook(low, "lim"), data)["reason"]
    assert run("Stop", hook(low, "lim"), data) == "", "limit fires once per window"

    (data / "continuity").mkdir(exist_ok=True)
    (data / "continuity" / "s1.md").write_text("notes")
    assert "s1.md" in run("compact", hook(high), data), "points Claude at its notes after compaction"
    assert run("compact", hook(high, "none"), data) == "", "silent when there are no notes"

    # statusline: snapshots + short line
    sl = Path(tmp) / "sl"
    sl.mkdir()
    (sl / "statusline.py").write_text((ROOT / "scripts" / "statusline.py").read_text())
    line = subprocess.run([sys.executable, str(sl / "statusline.py")], capture_output=True, text=True, encoding="utf-8", check=True,
                          input=json.dumps({"session_id": "x", "context_window": {"used_percentage": 90},
                                            "rate_limits": {"five_hour": {"used_percentage": 12}}})).stdout
    assert "ctx 90%" in line and "5h 12%" in line and "\033[31m" in line, line
    assert (sl / "latest.json").is_file() and (sl / "sessions" / "x.json").is_file()

    # Windows: a cp1252 console plus non-ASCII input (accented user folder), run through the launcher
    line = subprocess.run(["sh", str(ROOT / "scripts" / "py"), str(sl / "statusline.py")], capture_output=True,
                          env={**os.environ, "PYTHONIOENCODING": "cp1252"}, check=True,
                          input=json.dumps({"cwd": "C:/Users/José\u0081", "context_window": {"used_percentage": 90}},
                                           ensure_ascii=False).encode("utf-8")).stdout.decode("utf-8")
    assert "ctx 90%" in line and "\u26a0" in line, line
    assert "José" in (sl / "latest.json").read_text(encoding="utf-8")

print("ok: all funnel and statusline checks passed")
