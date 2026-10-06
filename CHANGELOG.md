# Changelog

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
