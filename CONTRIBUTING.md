# Contributing

Thanks for helping! Small, focused pull requests are easiest to review.

1. Open an issue first for anything bigger than a bug fix.
2. Keep it dependency-free: Python standard library and Swift/AppKit only.
3. Run the checks before opening a PR:
   ```
   python3 tests/test_funnel.py
   python3 tests/test_setup.py
   claude plugin validate .
   ```
4. Don't commit `widget/bin/Gauge` — CI rebuilds it from `widget/Gauge.swift`.
5. Any text the plugin sends to Claude must stay human-readable in the source and be quoted in the README.

Contributions are accepted under the MIT License. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
