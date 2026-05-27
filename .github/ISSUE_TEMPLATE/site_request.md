---
name: Add / fix a site
about: Request a new site or report that a checker drifted (false positive/negative)
title: "[site] "
labels: site
---

**Site**
- Name / domain:
- Type: [ ] email oracle  [ ] username

**What's wrong** (for an existing checker)
- [ ] false positive (reports accounts that don't exist)
- [ ] false negative (misses real accounts)
- `zcheck doctor --only <site>` verdict:

**Oracle details** (for a new email site)
- Endpoint (method + URL):
- How the response distinguishes "registered" vs "not registered":

> Username sites are best contributed upstream to WhatsMyName, then `zcheck update`.
> See CONTRIBUTING.md for the JSON schema.
