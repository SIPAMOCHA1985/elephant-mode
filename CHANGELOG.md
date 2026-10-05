# Changelog

## 0.1.0 — unreleased

- Saves memory and continuity notes at a context threshold (default 80 %), also mid-turn.
- Saves memory when the 5-hour or weekly usage limit reaches 85 %.
- Auto-compacts earlier (default 85 %) via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, set on first run only if unset.
- Points Claude to its continuity notes after compaction.
- Optional local transcript backups (off by default).
- Floating transparent gauge for macOS (universal binary), English/Spanish.
- `/compact-autopilot:uninstall` restores the settings it changed.
