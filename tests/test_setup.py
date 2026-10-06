#!/usr/bin/env python3
"""Self-check for scripts/setup.py against a throwaway settings.json. Run: python3 tests/test_setup.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    plugin = tmp / "plugin"  # copy without widget/: no gauge window during tests
    shutil.copytree(ROOT / "scripts", plugin / "scripts")
    cfg, data = tmp / "cfg", tmp / "data"
    cfg.mkdir()
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfg), "CLAUDE_PLUGIN_DATA": str(data)}
    run = lambda mode, **o: subprocess.run(
        [sys.executable, str(plugin / "scripts" / "setup.py"), mode], capture_output=True, text=True, encoding="utf-8", check=True,
        env={**env, **{f"CLAUDE_PLUGIN_OPTION_{k.upper()}": str(v) for k, v in o.items()}}).stdout
    settings = lambda: json.loads((cfg / "settings.json").read_text())

    original = {"model": "opus", "env": {"FOO": "1"}}
    (cfg / "settings.json").write_text(json.dumps(original))

    out = run("ensure")
    s = settings()
    assert s["model"] == "opus" and s["env"]["FOO"] == "1", "keeps the user's own settings"
    assert s["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "85"
    assert (data / "statusline.py").as_posix() in s["statusLine"]["command"] and (data / "statusline.py").is_file()
    assert (data / "py").is_file(), "the launcher is copied next to the statusline"
    assert json.loads((data / "settings.backup.json").read_text()) == original, "backup before changing"
    assert "First run" in out and "uninstall" in out, "tells the user once"
    assert run("ensure") == "", "second session: silent, no changes"

    run("remove")
    assert settings() == original, "remove restores exactly what was there"

    # a user with their own statusline and threshold keeps both; quiet stays silent
    mine = {"statusLine": {"type": "command", "command": "my-line"}, "env": {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "70"}}
    (cfg / "settings.json").write_text(json.dumps(mine))
    shutil.rmtree(data)
    assert run("ensure", quiet="true") == ""
    assert settings() == mine, "never overrides the user's statusline or threshold"
    run("remove")
    assert settings() == mine, "remove doesn't touch what it didn't add"

    # a settings.json that isn't valid JSON (comments, typo) is never rewritten, by ensure or by remove
    broken = '{"model": "opus", // my comment\n}'
    (cfg / "settings.json").write_text(broken)
    shutil.rmtree(data)
    assert "isn't valid JSON" in run("ensure")
    assert (cfg / "settings.json").read_text() == broken, "ensure leaves an invalid settings.json alone"
    assert subprocess.run([sys.executable, str(plugin / "scripts" / "setup.py"), "remove"], capture_output=True,
                          env=env).returncode != 0 and (cfg / "settings.json").read_text() == broken, "so does remove"

print("ok: all setup checks passed")
