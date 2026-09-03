---
name: app-schema-research
description: Investigate a named mobile app's custom URL Schemes, externally callable routes, parameter behavior, and production readiness. Use when the user wants actionable deep-link capability cards from an APK, IPA, .app, decoded package, or prior device-test evidence; exclude Universal Links unless explicitly requested.
---

# App Schema Research

Produce a short decision report, not a reverse-engineering dump. The user should be able to see what each useful Scheme route does, how to call it, which parameters matter, where it could be used, and what remains unverified.

## Use the deterministic scanner

From the repository root, install once with `python3 -m pip install -e .`, then use:

```bash
app-schema inspect "APP NAME" --artifact PATH --jadx /path/to/jadx --output report.json
```

Reuse `--decoded` when a JADX directory already exists. If no artifact is supplied, use only an audited source entry with a pinned SHA-256. Do not guess a Scheme from an App name or download an unaudited package.

The JSON is the audit substrate. The Markdown is the concise first-pass report. Inspect relevant source anchors when parameter meaning, enum values, or route composition remains unclear.

## LLM judgment layer

1. Resolve App identity before scanning. Keep normal, Pro, lite, guide, merchant, and regional editions separate.
2. Separate business Schemes from login, payment, sharing, OAuth callback, push, and test Schemes.
3. Merge duplicate annotations, literal URLs, and builders that point to the same capability.
4. Rank routes by user value and evidence: device-confirmed parameter consumption, correct page, static external visibility, literal URL, then internal-only registration.
5. Explain a parameter only as far as evidence supports. Mark inferred semantics and enum values as hypotheses.
6. Design the smallest A/B probes that distinguish competing parameter names or formats. Change one uncertain field at a time.
7. Treat device observations as stronger than Android static assumptions for an iOS product decision.

Never promote these distinct states into one another:

```text
Scheme registered → route exists → parameter read → correct page → parameter consumed → production-ready
```

Android evidence does not prove iOS path/query support. `canOpenURL` does not prove route or parameter consumption. A page opening with an empty search box is not a successful keyword search.

## Deliverable

Read [references/report-format.md](references/report-format.md) before composing the user-facing result. Default to no more than five useful capability cards. Put complete route inventories and long source excerpts only in an optional audit attachment.

Record new device results with `app-schema record-test`; do not overwrite failures with later static guesses. Generate probe URLs with `app-schema probe`, which rejects parameters lacking static evidence unless the user deliberately requests an experimental field.
