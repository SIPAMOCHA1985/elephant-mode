# Changelog

## 0.2.0 — 2026-10-05

- Codex CLI support (beta, 0.160+): `.codex-plugin/plugin.json`, `hooks/codex-hooks.json` and a Codex marketplace in `.agents/plugins/`. The same funnel reads context, window size and 5-hour/weekly limits from Codex's session log (`token_count` events). Memory goes to `memory.md` in the plugin data folder. Codex hooks never run `setup.py`, which edits Claude Code's settings.
- `scripts/py.cmd`: Windows launcher for Codex, which runs hooks through cmd.exe.
- `log.jsonl` in the plugin data folder: one line per save request and per compaction, saying whether the continuity notes were actually written in between. The save is a request to the model, not a guaranteed write; this shows whether it obeyed.
- A `settings.json` that isn't valid JSON (comments, a typo) is never rewritten: setup and uninstall leave it alone and say so.
- Removed a stray 0-byte file from `widget/bin/`.

## 0.1.1 — 2026-10-05

- Windows support for the memory save and statusline: a small launcher (`scripts/py`) finds a working Python 3.9+ (`python3`, `python` or `py -3`) instead of hitting the Microsoft Store `python3` stub.
- All files and hook I/O are UTF-8, so a Windows (cp1252) console or an accented user folder no longer crashes the statusline.
- `.gitattributes` keeps LF line endings, so the launcher runs after a Windows checkout.
- CI now also runs on Windows.

## 0.1.0 — 2026-10-05

- Saves memory and continuity notes at a context threshold (default 80 %), also mid-turn.
- Saves memory when the 5-hour or weekly usage limit reaches 85 %.
- Auto-compacts earlier (default 85 %) via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, set on first run only if unset.
- Points Claude to its continuity notes after compaction.
- Optional local transcript backups (off by default).
- Floating transparent gauge for macOS (universal binary), English/Spanish.
- `/elephant-mode:uninstall` restores the settings it changed.
