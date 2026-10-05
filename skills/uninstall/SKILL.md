---
name: uninstall
description: Undo compact-autopilot's settings changes (statusline, auto-compact threshold) and close its gauge, before removing the plugin. Use when the user wants to remove or disable compact-autopilot.
---

1. Run: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py" remove`
   It removes only what the plugin added (its statusline and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`), leaves anything the user set themselves, and closes the floating gauge.
2. Tell the user to finish with `/plugin uninstall compact-autopilot`.
   The pre-install settings backup is in the plugin data directory as `settings.backup.json` until then.
