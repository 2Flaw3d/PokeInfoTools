# PokeInfoTools

Minimal dark GitHub Pages site for Flawzo testing data.

## Included In This First Version

- Pokemon
- Moves
- Abilities
- Items
- Teachables and egg moves inside each Pokemon page
- Trainer snapshot
- Project rules snapshot

## Data Source

The site reads from the local Flawmerald workspace and builds a committed JSON snapshot.

Expected sibling workspace layout:

- `../Flawmerald/pokeemerald-expansion`
- `../Flawmerald/Ironmon-Tracker-flawzo`

## Rebuild Data

```powershell
py -3 scripts/build_site_data.py
```
