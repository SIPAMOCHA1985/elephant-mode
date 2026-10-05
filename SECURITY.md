# Security

Please report vulnerabilities **privately** through GitHub: *Security → Report a vulnerability* on this repository (private vulnerability reporting). Do not open a public issue for security problems.

You can expect a first reply within 7 days. Supported version: the latest release.

## Verifying the gauge binary

`widget/bin/Gauge` is built from `widget/Gauge.swift` by GitHub Actions and carries a build-provenance attestation. Verify it with:

```
gh attestation verify widget/bin/Gauge --repo SIPAMOCHA1985/elephant-mode
```

Or build it yourself on a Mac: `widget/build.sh`.
