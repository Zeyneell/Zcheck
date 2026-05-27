# Security & responsible use

## Acceptable use

Zcheck is an OSINT tool for **authorised** work only: security assessments with permission,
investigations with a lawful basis, CTFs, and research. It reads public account-existence oracles —
it does **not** reset passwords, email targets, log in, or brute-force anything. Using it to harass,
stalk, dox, or profile people without authorisation is out of scope and not supported.

## Reporting a vulnerability

If you find a security issue in Zcheck itself (e.g. an injection in the rules engine, an SSRF via a
crafted site definition, a credential-handling bug), please **do not open a public issue**. Email the
maintainer or use GitHub's private *Security advisories* ("Report a vulnerability") on this repo.

Please include reproduction steps and the affected version. Expect an acknowledgement within a few
days.

## A note on datasets

The bundled username dataset is sourced from the community **WhatsMyName** project and may contain
third-party API keys/tokens that those sites expose publicly for enumeration. These are not Zcheck
secrets; they ship as-is from upstream. See [DATA_SOURCES.md](DATA_SOURCES.md).
