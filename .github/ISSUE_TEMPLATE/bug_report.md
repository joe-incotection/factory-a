---
name: Bug report
about: Something crashed, wrong verdict, false positive/negative in a gate
title: '[bug] '
labels: bug
---

## Minimal reproduction
Paste the exact commands you ran and the output. Include:
- OS + Python version (`python --version`)
- Factory-A version (`vsce` extension version or the tag you cloned)
- MCP client + version if the bug is in an MCP call

## What you expected
One sentence.

## What actually happened
The error message + last 10 lines of output.

## Which gate (if it's a false positive/negative)
- [ ] Hallucination gate (Check for Hallucinated Names)
- [ ] Gate I.1 / I.2 (schema)
- [ ] Gate I.3 (toolchain digest)
- [ ] Gate I.4 (reason code collision)
- [ ] Gate I.5 (cross-module shape)
- [ ] Gate I.6 (cross-module import)
- [ ] G-Score threshold
- [ ] Receipt / replay
- [ ] Other: ______
