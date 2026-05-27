# Zcheck

**Async email → accounts OSINT.** Give it an email address; Zcheck tells you where that
person has accounts — holehe-style, but **data-driven** and **self-checking** so it scales
past 690 sites and doesn't quietly rot when a site changes.

> Built from scratch. Not a re-skin of holehe or Sherlock. The email oracles are original;
> the username sweep speaks the community **WhatsMyName** dataset so coverage stays current.

```
   ____      _               _
  |_  /__ __| |_  ___ __ __ | |__
   / / _/ _| ' \/ -_) _| / /| / /
  /___\__\__|_||_\___\__|_\_\|_\_\   OSINT
```

## Why it's different from holehe

| | holehe | **Zcheck** |
|---|---|---|
| Sites | ~120 email oracles | **3 email oracles + 690+ username sites** |
| Adding a site | write a Python module | **edit one JSON entry** (or drop a plugin) |
| Site changes its response | checker silently breaks | **`update` pulls the fix; `doctor` flags drift; canary suppresses false positives** |
| False positives | trust the module | **every hit is re-validated against a throwaway canary** |

## How it works

Two engines feed one runner:

1. **Email oracles** — a site's *"is this email already registered?"* endpoint (signup / reset).
   Simple ones live as JSON in [`email_sites.json`](src/zcheck/data/email_sites.json); the ones
   that need a CSRF token or multi-step flow are Python plugins in
   [`sites/plugins/`](src/zcheck/sites/plugins/).
2. **Username sweep** — derives a username from the email's local part and checks it against the
   **WhatsMyName** dataset (690+ sites), using each site's `e_code` / `e_string` / `m_string`
   contract. Redirects are **not** followed, so a redirect to a generic page can't be mistaken
   for a hit.

### Not lying to you — the three guarantees against false positives

- **Canary validation.** After a scan, every site that claimed a hit is re-probed with a
  *guaranteed non-existent* identifier. If it "finds" that too, it's an over-matching oracle and
  the result is downgraded to `unknown`. (In testing this caught *Arch Linux GitLab* on a live run.)
- **Negative markers.** Username checks require the positive marker **and** the absence of the
  site's "not found" marker — kills soft-404s.
- **`zcheck doctor`.** Self-test: probes each checker with a known-good control + a canary and
  flags anything that reports phantom accounts. Wire it into CI to catch drift automatically.

### Self-updating

`zcheck update` refreshes the datasets into your user cache, which takes precedence over the
bundled snapshot. When a site changes and the dataset is fixed upstream, you get the fix **without
a new release** — no code touched.

## Install

```powershell
git clone https://github.com/Zeyneell/Zcheck.git
cd Zcheck
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

On Windows you can also just double-click **`Zcheck.bat`** — it builds the venv and installs on
first run, then drops you into the interactive menu.

## Usage

Interactive menu (same feel as Zloc):

```powershell
zcheck
```

One-shot:

```powershell
zcheck scan someone@example.com                 # email oracles + username sweep
zcheck scan someone@example.com --mode email    # just the email oracles
zcheck scan someone@example.com -u customhandle  # override the guessed username
zcheck scan someone@example.com --nsfw --json out.json --csv out.csv
zcheck sites                                     # what Zcheck can check, by category
zcheck doctor --cat coding                       # health-check a category
zcheck update                                    # refresh the site datasets
```

Useful flags: `--mode email|username|both`, `--only site,site`, `--cat cat,cat`, `--nsfw`,
`--concurrency N`, `--timeout S`, `--no-canary`.

## Extending

Adding a site is data, not code — see [CONTRIBUTING.md](CONTRIBUTING.md) for the email-oracle and
username schemas. Complex sites get a small Python plugin in `sites/plugins/` (auto-discovered).

## Ethics & scope

Zcheck is for **authorised** OSINT, security assessments, and CTF/research. It only *reads* public
account-existence oracles — it never resets a password, never emails the target, never logs in.
Don't use it to harass, dox, or investigate people without a lawful basis.

## Credits & licensing

- Code: **MIT** (see [LICENSE](LICENSE)).
- Username dataset: **WhatsMyName** by Micah "WebBreacher" Hoffman, **CC BY-SA 4.0** — see
  [DATA_SOURCES.md](DATA_SOURCES.md).
