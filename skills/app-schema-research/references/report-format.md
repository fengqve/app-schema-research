# Capability report format

The default report is a decision aid. Omit repeated internal routes, callbacks, account flows, order-management pages, tracking-only fields, and long parameter lists unless they are directly relevant.

For each useful capability, provide:

## Capability name: `scheme://host/path`

- **What it does:** The actual destination or operation, such as “opens the Ctrip AI assistant,” not a generic label like “route.”
- **Current verdict:** production candidate, Debug only, failed, or static-only.
- **Application:** One or two realistic third-party use cases.

### Parameters

| Parameter | Meaning | How to pass | Evidence/status |
|---|---|---|---|
| `query` | Initial question sent to the assistant | URL-encoded UTF-8 text | Example: statically read; iOS not tested |

List only parameters that change the business result. Exclude attribution, analytics, animation, engine, and internal tracing fields by default.

### Copyable example

Give one shortest probe and, when useful, one complete business example. State the expected landing page and which fields are expected versus verified.

### Evidence and boundary

Use at most three decisive source anchors. State observed failures directly—for example, “opens the search input and keyboard, but `keyword` is not consumed.” Do not bury this under a general confidence score.

## App-level summary

At the top, show identity, package version/hash, registered business Schemes, and a one-sentence decision. At the end, mention how many raw routes were omitted and where the JSON audit file is located.
