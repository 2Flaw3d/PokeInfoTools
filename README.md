# PokeInfoTools

Minimal dark GitHub Pages site for Flawzo testing data.

## Mandatory Implementation Gate

Do not duplicate ROM/WebApp rules, mappings or data pipelines in this project.
Consume or extend their canonical export/generator; if a separate runtime
representation is unavoidable, keep one canonical source and exact parity
coverage. The authoritative policy is `DEC-020` in
`../docs/PROJECT_DECISIONS.md`.

## Included In This First Version

- Pokemon
- Moves
- Abilities
- Items
- Teachables and egg moves inside each Pokemon page
- Legal fightable trainer snapshot, grouped by zone
  and including trainer AI flags
- Project rules snapshot

## Data Source

The site reads from the local Flawmerald workspace and builds a committed JSON snapshot.

Expected sibling workspace layout:

- `../Flawmerald/pokeemerald-expansion`
- `../Flawmerald/Flawzo-WebApp`

The deprecated standalone Ironmon Tracker repository is not a data source.
The generator reads the canonical ROM export produced in the WebApp workspace.

## Rebuild Data

```powershell
py -3 scripts/build_site_data.py
```
