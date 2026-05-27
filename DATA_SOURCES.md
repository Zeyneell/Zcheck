# Data sources & attribution

Zcheck's own **code** is MIT-licensed. The bundled **datasets** have their own terms,
recorded here.

## Username dataset — `src/zcheck/data/username_sites.json`

Derived from the **WhatsMyName** project by Micah "WebBreacher" Hoffman and contributors.

- Source: <https://github.com/WebBreacher/WhatsMyName> (`wmn-data.json`)
- License: **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**
  — <http://creativecommons.org/licenses/by-sa/4.0/>

Per CC BY-SA 4.0: attribution is given above, and this dataset (and modifications to it)
remains under CC BY-SA 4.0 even though Zcheck's code is MIT. `zcheck update` refreshes
this file from the upstream project so site definitions stay current.

## Email oracle dataset — `src/zcheck/data/email_sites.json`

Original to this project (MIT). Contributions welcome — see `CONTRIBUTING.md` for the schema.
