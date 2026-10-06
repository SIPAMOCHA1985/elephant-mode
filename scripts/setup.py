#!/usr/bin/env python3
"""elephant-mode setup, run by the SessionStart hook on every session (and by the uninstall skill).

ensure  - first run: back up ~/.claude/settings.json, then
            * statusLine -> our statusline.py, ONLY if the user has no statusline of their own
            * env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE -> compact_pct, ONLY if not already set
          and ask Claude to tell the user once what changed (skipped with the `quiet` option).
          every run: open the floating gauge (macOS) if it isn't open.
remove  - undo exactly what ensure changed and close the gauge.
"""
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "elephant-mode")
SETTINGS = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
STATE = DATA / "setup.json"  # what we changed, so remove() undoes only that
ENV_KEY = "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"


def opt(key, default):
    v = os.environ.get(f"CLAUDE_PLUGIN_OPTION_{key.upper()}", "")
    return v if v != "" else default


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_settings():
    """The user's settings, {} if there are none, or None if the file exists but isn't a JSON object
    (comments, a typo, half-written): then it must not be rewritten, or the user's settings are lost."""
    if not SETTINGS.exists():
        return {}
    try:
        s = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return s if isinstance(s, dict) else None


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def statusline_cmd():
    return f'sh "{(DATA / "py").as_posix()}" "{(DATA / "statusline.py").as_posix()}"'


LEGACY_CMD = f'python3 "{DATA / "statusline.py"}"'  # written by 0.1.0; remove() still recognizes it


def ensure():
    DATA.mkdir(parents=True, exist_ok=True)
    for name in ("statusline.py", "py"):  # stable paths across plugin updates
        shutil.copy2(ROOT / "scripts" / name, DATA / name)
    state = load(STATE)
    notes = []
    s = None if state.get("configured") else load_settings()
    if not state.get("configured") and s is None:
        print(f"[elephant-mode] {SETTINGS} isn't valid JSON, so the plugin left it untouched: no statusline and no "
              "earlier auto-compact yet (the memory save still works). Tell the user briefly; the setup runs "
              "on the first session after the file is fixed.")
    elif not state.get("configured"):
        if SETTINGS.exists() and not (DATA / "settings.backup.json").exists():
            shutil.copy2(SETTINGS, DATA / "settings.backup.json")
        if not s.get("statusLine"):
            s["statusLine"] = {"type": "command", "command": statusline_cmd(), "refreshInterval": 5}
            state["statusLine"] = True
            notes.append("added a statusline that shows context and usage-limit percentages")
        else:
            notes.append("left your existing statusline alone (the gauge will show less data)")
        env = s.setdefault("env", {})
        if ENV_KEY not in env:
            env[ENV_KEY] = str(opt("compact_pct", 85))
            state["env"] = True
            notes.append(f"set {ENV_KEY}={env[ENV_KEY]} so auto-compact runs earlier (takes effect next session)")
        dump(SETTINGS, s)
        state["configured"] = True
        dump(STATE, state)

    open_gauge()

    quiet = str(opt("quiet", "false")).lower() == "true"
    if notes and not quiet:
        print("[elephant-mode] First run: the plugin " + "; ".join(notes) +
              f". A backup of the previous settings is at {DATA / 'settings.backup.json'}. "
              "Tell the user this once, briefly, and that /elephant-mode:uninstall undoes it.")


def gauge_pid():
    if os.name == "nt":  # on Windows os.kill(pid, 0) terminates the process instead of probing it
        return None
    try:
        pid = int((DATA / "gauge.pid").read_text(encoding="utf-8"))
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def open_gauge():
    binary = ROOT / "widget" / "bin" / "Gauge"
    if platform.system() != "Darwin" or not binary.is_file() or gauge_pid():
        return
    p = subprocess.Popen([str(binary), str(DATA)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)  # outlives the hook
    (DATA / "gauge.pid").write_text(str(p.pid))


def remove():
    state = load(STATE)
    s = load_settings()
    if s is None:
        sys.exit(f"elephant-mode: {SETTINGS} isn't valid JSON, so it was left untouched. Fix it and run this again.")
    if state.get("statusLine") and (s.get("statusLine") or {}).get("command") in (statusline_cmd(), LEGACY_CMD):
        del s["statusLine"]
    if state.get("env") and ENV_KEY in s.get("env", {}):
        del s["env"][ENV_KEY]
        if not s["env"]:
            del s["env"]
    if SETTINGS.exists():
        dump(SETTINGS, s)
    pid = gauge_pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
    STATE.unlink(missing_ok=True)
    print("elephant-mode: settings restored and gauge closed. Now run: /plugin uninstall elephant-mode")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows defaults to cp1252
    {"ensure": ensure, "remove": remove}[sys.argv[1] if len(sys.argv) > 1 else "ensure"]()
