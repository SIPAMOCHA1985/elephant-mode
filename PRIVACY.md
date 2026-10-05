# Privacy

elephant-mode runs entirely on your computer. **It makes no network requests and sends no data anywhere** — not to the author, not to Anthropic, not to any third party. You can verify this: the code is a few short files in `scripts/` and `widget/Gauge.swift`.

## What it reads

- The **end of your conversation transcript**, to compute how full the context is. It parses those lines in memory and keeps only the token counts; it never stores message text (unless you turn `backups` on).
- The **status data Claude Code passes to the statusline**: context %, 5-hour and weekly limit %, reset times, session duration.

## What it writes (in the plugin data directory, `~/.claude/plugins/data/elephant-mode-*/`)

| File | Contents | Kept |
|---|---|---|
| `latest.json`, `sessions/<id>.json` | The statusline data above (numbers, model name, working directory) | Overwritten on every refresh |
| `flags/<id>.json` | Which thresholds already fired | Small; removed on uninstall |
| `continuity/<id>.md` | Notes **Claude** writes about the current task | Until you delete them or uninstall |
| `settings.backup.json` | Your `settings.json` before the first-run changes | Until uninstall |
| `backups/*.jsonl` | Full conversation copies — **only if you turn `backups` on** | The newest `backup_keep` (default 10) |

Claude also saves notes to **Claude Code's own memory** (`~/.claude/projects/<project>/memory/`), the same place it saves memory without this plugin.

Uninstalling the plugin deletes its data directory (Claude Code does this; pass `--keep-data` to keep it).

## Children

Not directed at users under 18.

## Contact

Questions: open an issue at https://github.com/SIPAMOCHA1985/elephant-mode/issues
