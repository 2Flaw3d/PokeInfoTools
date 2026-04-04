#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FLAWMERALD_ROOT = ROOT.parent / "Flawmerald"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("exp_export", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build site data for PokeInfoTools.")
    parser.add_argument("--flawmerald-root", default=str(DEFAULT_FLAWMERALD_ROOT))
    parser.add_argument("--expansion-root")
    parser.add_argument("--tracker-root")
    return parser.parse_args()


def parse_numeric_defines(path: Path, prefix: str) -> tuple[dict[str, int], dict[int, str]]:
    values: dict[str, int] = {}
    aliases: dict[str, str] = {}
    first_token_by_id: dict[int, str] = {}

    for raw_line in read_text(path).splitlines():
        line = re.sub(r"//.*$", "", raw_line).strip()
        if not line:
            continue
        numeric = re.match(rf"^#define\s+({re.escape(prefix)}[A-Z0-9_]+)\s+([0-9]+)\s*$", line)
        if numeric:
            token = numeric.group(1)
            value = int(numeric.group(2))
            values[token] = value
            first_token_by_id.setdefault(value, token)
            continue
        alias = re.match(
            rf"^#define\s+({re.escape(prefix)}[A-Z0-9_]+)\s+({re.escape(prefix)}[A-Z0-9_]+)\s*$",
            line,
        )
        if alias:
            aliases[alias.group(1)] = alias.group(2)

    for _ in range(64):
        changed = False
        for token, alias in list(aliases.items()):
            if alias in values:
                values[token] = values[alias]
                first_token_by_id.setdefault(values[alias], alias)
                del aliases[token]
                changed = True
        if not changed:
            break

    return values, first_token_by_id


def humanize_token(token: str, prefix: str | None = None) -> str:
    if prefix and token.startswith(prefix):
        token = token[len(prefix) :]
    words = token.replace("_", " ").lower().split()
    fixed = []
    specials = {
        "hp": "HP",
        "pp": "PP",
        "hm": "HM",
        "tm": "TM",
        "sp": "Sp.",
        "atk": "Atk",
        "def": "Def",
        "spe": "Spe",
        "spa": "SpA",
        "spd": "SpD",
        "gmax": "Gmax",
    }
    for word in words:
        fixed.append(specials.get(word, word.capitalize()))
    return " ".join(fixed)


def safe_extract_identifier(export_mod, expr: str, prefix: str) -> str | None:
    try:
        return export_mod.extract_identifier_token(expr, prefix)
    except Exception:
        match = re.search(rf"\b({re.escape(prefix)}[A-Z0-9_]+)\b", expr or "")
        return match.group(1) if match else None


def safe_resolve_numeric(export_mod, expr: str) -> int | None:
    try:
        return export_mod.resolve_numeric_field(expr)
    except Exception:
        match = re.search(r"-?\d+", expr or "")
        return int(match.group(0)) if match else None


def parse_token_list_from_comment_block(text: str, header: str) -> set[str]:
    pattern = re.compile(rf"{re.escape(header)}\s*//(.*?)// \*+", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return set()
    return set(re.findall(r"(MOVE_[A-Z0-9_]+)", match.group(1)))


def parse_move_array_file(path: Path) -> dict[str, list[str]]:
    arrays: dict[str, list[str]] = {}
    content = read_text(path)
    pattern = re.compile(r"static const u16 ([A-Za-z0-9_]+)\[\] = \{(.*?)\};", re.DOTALL)
    for match in pattern.finditer(content):
        symbol = match.group(1)
        tokens = [
            token
            for token in re.findall(r"(MOVE_[A-Z0-9_]+)", match.group(2))
            if token != "MOVE_UNAVAILABLE"
        ]
        arrays[symbol] = tokens
    return arrays


def parse_tmhm_move_lists(path: Path) -> tuple[list[str], list[str]]:
    text = read_text(path)
    tm_match = re.search(r"#define FOREACH_TM\(F\)\s*\\(.*?)#define FOREACH_HM\(F\)", text, re.DOTALL)
    hm_match = re.search(r"#define FOREACH_HM\(F\)\s*\\(.*?)#define FOREACH_TMHM\(F\)", text, re.DOTALL)
    tm_tokens = re.findall(r"F\(([A-Z0-9_]+)\)", tm_match.group(1)) if tm_match else []
    hm_tokens = re.findall(r"F\(([A-Z0-9_]+)\)", hm_match.group(1)) if hm_match else []
    return tm_tokens, hm_tokens


def parse_showdown_trainers(
    path: Path,
    species_id_by_name: dict[str, int],
) -> list[dict]:
    content = read_text(path)
    pattern = re.compile(r"^===\s+([A-Z0-9_]+)\s+===\s*$", re.MULTILINE)
    matches = list(pattern.finditer(content))
    trainers: list[dict] = []

    def resolve_species_name(raw_name: str) -> tuple[str, int | None]:
        cleaned = raw_name.strip()
        if cleaned.startswith("SPECIES_"):
            display = humanize_token(cleaned, "SPECIES_")
        else:
            display = cleaned
        species_id = species_id_by_name.get(display.lower())
        return display, species_id

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        block = content[start:end].strip()
        if not block:
            continue

        groups = [group.strip() for group in re.split(r"\r?\n\s*\r?\n", block) if group.strip()]
        if not groups:
            continue

        trainer_meta: dict[str, str] = {}
        for line in groups[0].splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                trainer_meta[key.strip()] = value.strip()

        pokemon_entries = []
        for mon_block in groups[1:]:
            lines = [line.rstrip() for line in mon_block.splitlines() if line.strip()]
            if not lines:
                continue

            first = lines[0]
            species_raw = first
            if "(" in first and ")" in first:
                groups_in_line = re.findall(r"\(([^)]+)\)", first)
                if groups_in_line:
                    species_raw = groups_in_line[-1]
            held_item = first.split("@", 1)[1].strip() if "@" in first else ""

            species_name, species_id = resolve_species_name(species_raw.split("@", 1)[0].strip())
            mon = {
                "speciesName": species_name,
                "speciesId": species_id,
                "level": None,
                "ability": "",
                "item": held_item,
                "moves": [],
            }
            for line in lines[1:]:
                if line.startswith("- "):
                    mon["moves"].append(line[2:].strip())
                    continue
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "level":
                    try:
                        mon["level"] = int(value)
                    except ValueError:
                        mon["level"] = None
                elif key == "ability":
                    mon["ability"] = value
                elif key == "ball":
                    mon["ball"] = value
                elif key == "nature":
                    mon["nature"] = value
            pokemon_entries.append(mon)

        trainers.append(
            {
                "idToken": match.group(1),
                "name": trainer_meta.get("Name", ""),
                "class": trainer_meta.get("Class", ""),
                "pic": trainer_meta.get("Pic", ""),
                "gender": trainer_meta.get("Gender", ""),
                "music": trainer_meta.get("Music", ""),
                "battleType": trainer_meta.get("Double Battle", "No"),
                "items": [item.strip() for item in trainer_meta.get("Items", "").split("/") if item.strip()],
                "pokemon": pokemon_entries,
            }
        )

    return trainers


def iter_group_paths(parts: list[str]) -> list[str]:
    candidates: list[str] = []

    def helper(start: int, groups_left: int, acc: list[str]) -> None:
        if start == len(parts):
            candidates.append("/".join(acc))
            return
        if groups_left == 0:
            return
        for end in range(start + 1, len(parts) + 1):
            acc.append("_".join(parts[start:end]))
            helper(end, groups_left - 1, acc)
            acc.pop()

    for group_count in (1, 2, 3):
        helper(0, group_count, [])

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def find_icon_source(token: str, icons_by_rel_dir: dict[str, Path]) -> Path | None:
    slug = token.replace("SPECIES_", "").lower()
    if slug in icons_by_rel_dir:
        return icons_by_rel_dir[slug]

    parts = slug.split("_")
    for candidate in iter_group_paths(parts):
        if candidate in icons_by_rel_dir:
            return icons_by_rel_dir[candidate]
    return None


def normalize_species_name_for_icon(species_name: str) -> str:
    key = species_name.lower()
    replacements = {
        "♀": "_f",
        "♂": "_m",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "ä": "a",
        "í": "i",
        "ì": "i",
        "î": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "ö": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ü": "u",
    }
    for source, target in replacements.items():
        key = key.replace(source, target)
    key = re.sub(r"[%'%.:\(\)\[\]\{\}!?,]", "", key)
    key = re.sub(r"[-\s/]+", "_", key)
    key = re.sub(r"[^\w_]", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    aliases = {
        "nidoranf": "nidoran_f",
        "nidoranm": "nidoran_m",
        "mrmime": "mr_mime",
        "mimejr": "mime_jr",
        "typenull": "type_null",
    }
    return aliases.get(key, key)


def build_project_rules() -> dict:
    return {
        "title": "Flawzo IronMon Rules Snapshot",
        "subtitle": "Prima snapshot web orientata al testing. Alcune sezioni, soprattutto trainer e dettagli custom, verranno rifinite piu avanti.",
        "sections": [
            {
                "title": "Core Profile",
                "items": [
                    "Battle data profile impostato a Gen 6.",
                    "Randomizer totale attivo con limite massimo Gen 6 per la randomizzazione.",
                    "Run orientata a testing rapido con intro completamente saltata e start diretto nel truck.",
                ],
            },
            {
                "title": "Kaizo Rules",
                "items": [
                    "No cure fuori lotta.",
                    "Mart disabilitati.",
                    "Hidden items disabilitati.",
                    "Escape Rope, Teleport e Dig fuori lotta disabilitati.",
                    "HM virtuali / auto field moves con badge-check ignorati in testing.",
                    "Sempre giorno.",
                    "Party monosingolo.",
                    "Friendship forzata alta.",
                ],
            },
            {
                "title": "Run Flow",
                "items": [
                    "Starter custom senza fight iniziale Zigzagoon.",
                    "Whiteout in death truck invece del ritorno standard.",
                    "Wild Attract con Scout Ball dedicata.",
                    "Overworld encounters custom in piu zone con pool fissa per run.",
                ],
            },
            {
                "title": "Notes",
                "items": [
                    "La sezione trainer e da considerare snapshot temporanea dello stato attuale.",
                    "Le regole qui riportate vengono dai file di documentazione locali e sono pensate come base iniziale del sito.",
                ],
            },
        ],
        "sources": [
            "pokeemerald-expansion/README.md",
            "pokeemerald-expansion/docs/MODIFICHE_COMPLETE.md",
        ],
    }


def build_site_data(expansion_root: Path, tracker_root: Path) -> dict:
    export_mod = load_module(expansion_root / "tools" / "tracker" / "export_expansion_data.py")
    expansion_json_path = tracker_root / "ironmon_tracker" / "data" / "ExpansionData.json"
    expansion_data = json.loads(read_text(expansion_json_path))

    move_constants = export_mod.parse_enum_constants(
        read_text(expansion_root / "include" / "constants" / "moves.h"),
        "Move",
    )
    species_constants = export_mod.parse_species_constants(expansion_root / "include" / "constants" / "species.h")
    item_constants = export_mod.parse_enum_constants(
        read_text(expansion_root / "include" / "constants" / "items.h"),
        "Item",
    )
    ordered_species_tokens = parse_numeric_defines(
        expansion_root / "include" / "constants" / "species.h",
        "SPECIES_",
    )[1]
    primary_species_tokens = {value: key for key, value in species_constants.items() if value > 0}
    for species_id, token in ordered_species_tokens.items():
        primary_species_tokens[species_id] = token

    ability_id_to_name = {index: ability["name"] for index, ability in enumerate(expansion_data["abilities"], start=1)}
    ability_id_to_description = {index: ability["description"] for index, ability in enumerate(expansion_data["abilities"], start=1)}

    moves_text = read_text(expansion_root / "src" / "data" / "moves_info.h")
    named_move_strings = export_mod.parse_named_string_constants(moves_text)
    move_blocks = export_mod.parse_indexed_initializer_entries(moves_text, "MOVE_")
    move_extra_by_id: dict[int, dict] = {}
    for token, block in move_blocks.items():
        move_id = move_constants.get(token)
        if move_id is None or move_id <= 0:
            continue
        fields = export_mod.parse_top_level_designated_fields(block)
        move_extra_by_id[move_id] = {
            "description": export_mod.resolve_string_field(fields.get("description", ""), named_move_strings) or "",
            "effect": safe_extract_identifier(export_mod, fields.get("effect", ""), "EFFECT_"),
            "target": safe_extract_identifier(export_mod, fields.get("target", ""), "TARGET_"),
            "priority": safe_resolve_numeric(export_mod, fields.get("priority", "")) or 0,
        }

    tmhm_define_path = expansion_root / "include" / "constants" / "tms_hms.h"
    tm_move_names, hm_move_names = parse_tmhm_move_lists(tmhm_define_path)

    tmhm_machine_info: dict[str, dict] = {}
    for number, move_name in enumerate(tm_move_names, start=1):
        move_token = f"MOVE_{move_name}"
        tmhm_machine_info[f"ITEM_TM_{move_name}"] = {
            "numericToken": f"ITEM_TM{number:02d}",
            "machineType": "TM",
            "machineNumber": number,
            "moveId": move_constants.get(move_token),
            "moveName": humanize_token(move_token, "MOVE_"),
        }
    for number, move_name in enumerate(hm_move_names, start=1):
        move_token = f"MOVE_{move_name}"
        tmhm_machine_info[f"ITEM_HM_{move_name}"] = {
            "numericToken": f"ITEM_HM{number:02d}",
            "machineType": "HM",
            "machineNumber": number,
            "moveId": move_constants.get(move_token),
            "moveName": humanize_token(move_token, "MOVE_"),
        }

    items_text = read_text(expansion_root / "src" / "data" / "items.h")
    named_item_strings = export_mod.parse_named_string_constants(items_text)
    item_blocks = export_mod.parse_indexed_initializer_entries(items_text, "ITEM_")
    items: list[dict] = []
    item_name_by_id: dict[int, str] = {}
    for token, block in item_blocks.items():
        machine_info = tmhm_machine_info.get(token)
        item_id = item_constants.get(token)
        if item_id is None and machine_info is not None:
            item_id = item_constants.get(machine_info["numericToken"])
        if item_id is None or item_id <= 0:
            continue
        fields = export_mod.parse_top_level_designated_fields(block)
        machine_type = None
        machine_number = None
        move_id = None
        move_name = None
        item_token = token
        token_match = re.fullmatch(r"ITEM_(TM|HM)(\d{2,3})", token)
        if machine_info is not None:
            item_token = machine_info["numericToken"]
            machine_type = machine_info["machineType"]
            machine_number = machine_info["machineNumber"]
            move_id = machine_info["moveId"]
            move_name = machine_info["moveName"]
        elif token_match:
            machine_type = token_match.group(1)
            machine_number = int(token_match.group(2))
        item = {
            "id": item_id,
            "token": item_token,
            "name": export_mod.resolve_string_field(fields.get("name", ""), named_item_strings) or humanize_token(token, "ITEM_"),
            "description": export_mod.resolve_string_field(fields.get("description", ""), named_item_strings) or "",
            "pocket": safe_extract_identifier(export_mod, fields.get("pocket", ""), "POCKET_"),
            "price": safe_resolve_numeric(export_mod, fields.get("price", "")) or 0,
            "machineType": machine_type,
            "machineNumber": machine_number,
            "moveId": move_id,
            "moveName": move_name,
        }
        items.append(item)
        item_name_by_id[item_id] = item["name"]
    items.sort(key=lambda entry: entry["id"])

    species_symbols: dict[int, dict] = {}
    species_info_dir = expansion_root / "src" / "data" / "pokemon" / "species_info"
    for family_file in sorted(species_info_dir.glob("gen_*_families.h")):
        family_text = read_text(family_file)
        family_blocks = export_mod.parse_indexed_initializer_entries(family_text, "SPECIES_")
        for species_token, block in family_blocks.items():
            species_id = species_constants.get(species_token)
            if not species_id:
                continue
            fields = export_mod.parse_top_level_designated_fields(block)
            species_symbols[species_id] = {
                "teachableSymbol": export_mod.resolve_symbol_identifier(fields.get("teachableLearnset", "")),
                "eggMoveSymbol": export_mod.resolve_symbol_identifier(fields.get("eggMoveLearnset", "")),
            }

    teachable_arrays = parse_move_array_file(expansion_root / "src" / "data" / "pokemon" / "teachable_learnsets.h")
    egg_arrays = parse_move_array_file(expansion_root / "src" / "data" / "pokemon" / "egg_moves.h")
    teachable_text = read_text(expansion_root / "src" / "data" / "pokemon" / "teachable_learnsets.h")

    tmhm_text = read_text(tmhm_define_path)
    tmhm_tokens = {f"MOVE_{token}" for token in re.findall(r"F\(([A-Z0-9_]+)\)", tmhm_text)}
    tutor_tokens = parse_token_list_from_comment_block(
        teachable_text,
        "Tutor moves found from map scripts:",
    )
    special_teachable_tokens = parse_token_list_from_comment_block(
        teachable_text,
        "Near-universal moves found in data/special_movesets.json:",
    )

    icons_by_rel_dir = {
        icon.parent.relative_to(expansion_root / "graphics" / "pokemon").as_posix(): icon
        for icon in (expansion_root / "graphics" / "pokemon").rglob("icon.png")
    }
    tracker_updated_icons = tracker_root / "ironmon_tracker" / "images" / "pokemonUpdated"
    tracker_named_icons = tracker_root / "ironmon_tracker" / "images" / "pokemonByName"
    icons_dir = ROOT / "assets" / "icons"
    for old_icon in icons_dir.glob("*.png"):
        old_icon.unlink()

    abilities_users: dict[int, list[int]] = defaultdict(list)
    species_id_by_name: dict[str, int] = {}
    species_entries: list[dict] = []

    for species_id, raw_species in enumerate(expansion_data["species"], start=1):
        if not raw_species or not raw_species.get("name"):
            continue

        token = primary_species_tokens.get(species_id, f"SPECIES_{species_id}")
        symbol_info = species_symbols.get(species_id, {})
        teachable_tokens = teachable_arrays.get(symbol_info.get("teachableSymbol") or "", [])
        egg_tokens = egg_arrays.get(symbol_info.get("eggMoveSymbol") or "", [])

        updated_icon = tracker_updated_icons / f"{species_id}.png"
        by_name_icon = tracker_named_icons / f"{normalize_species_name_for_icon(raw_species['name'])}.png"
        icon_source = None
        if updated_icon.is_file():
            icon_source = updated_icon
        elif by_name_icon.is_file():
            icon_source = by_name_icon
        else:
            icon_source = find_icon_source(token, icons_by_rel_dir)
        icon_path = None
        if icon_source is not None:
            destination = icons_dir / f"{species_id}.png"
            shutil.copyfile(icon_source, destination)
            icon_path = f"assets/icons/{species_id}.png"

        abilities = []
        for ability_id in raw_species.get("abilities", []):
            if ability_id and ability_id in ability_id_to_name:
                abilities.append(
                    {
                        "id": ability_id,
                        "name": ability_id_to_name[ability_id],
                        "description": ability_id_to_description.get(ability_id, ""),
                    }
                )
                abilities_users[ability_id].append(species_id)

        evolutions = []
        for evo in raw_species.get("evolutions", []):
            target_id = evo.get("targetSpecies")
            target_name = ""
            if target_id and 0 < target_id <= len(expansion_data["species"]):
                target_name = expansion_data["species"][target_id - 1]["name"]

            method = evo.get("method", "")
            param = evo.get("param")
            label = humanize_token(method, "EVO_")
            if method == "EVO_LEVEL" and param:
                label = f"Level {param}"
            elif method == "EVO_ITEM" and param:
                label = f"Use {item_name_by_id.get(param, f'Item {param}')}"
            elif method == "EVO_TRADE_ITEM" and param:
                label = f"Trade holding {item_name_by_id.get(param, f'Item {param}')}"
            elif method == "EVO_TRADE":
                label = "Trade"
            elif method == "EVO_FRIENDSHIP":
                label = "High friendship"
            elif method == "EVO_FRIENDSHIP_DAY":
                label = "High friendship (day)"
            elif method == "EVO_FRIENDSHIP_NIGHT":
                label = "High friendship (night)"

            evolutions.append(
                {
                    "method": method,
                    "param": param,
                    "targetSpecies": target_id,
                    "targetName": target_name,
                    "label": label,
                }
            )

        species_entry = {
            "id": species_id,
            "token": token,
            "name": raw_species["name"],
            "types": [humanize_token(type_token, "TYPE_") for type_token in raw_species.get("typeTokens", []) if type_token],
            "typeTokens": raw_species.get("typeTokens", []),
            "bst": raw_species.get("bst"),
            "weight": (raw_species.get("weight") or 0) / 10 if raw_species.get("weight") else None,
            "moveLevels": raw_species.get("moveLevels", []),
            "abilities": abilities,
            "evolutions": evolutions,
            "icon": icon_path,
            "teachable": {
                "all": [move_constants[token] for token in teachable_tokens if token in move_constants],
                "tmhm": [move_constants[token] for token in teachable_tokens if token in tmhm_tokens and token in move_constants],
                "tutor": [move_constants[token] for token in teachable_tokens if token in tutor_tokens and token in move_constants],
                "special": [move_constants[token] for token in teachable_tokens if token in special_teachable_tokens and token in move_constants],
            },
            "eggMoves": [move_constants[token] for token in egg_tokens if token in move_constants],
        }
        species_entries.append(species_entry)
        species_id_by_name.setdefault(species_entry["name"].lower(), species_id)

    moves = []
    for move_id, raw_move in enumerate(expansion_data["moves"], start=1):
        if not raw_move or not raw_move.get("name"):
            continue
        extra = move_extra_by_id.get(move_id, {})
        moves.append(
            {
                "id": move_id,
                "name": raw_move["name"],
                "type": humanize_token(raw_move.get("typeToken") or "", "TYPE_") if raw_move.get("typeToken") else "",
                "typeToken": raw_move.get("typeToken"),
                "category": humanize_token(raw_move.get("categoryToken") or "", "DAMAGE_CATEGORY_") if raw_move.get("categoryToken") else "",
                "categoryToken": raw_move.get("categoryToken"),
                "power": raw_move.get("power"),
                "accuracy": raw_move.get("accuracy"),
                "pp": raw_move.get("pp"),
                "description": extra.get("description", ""),
                "effect": extra.get("effect"),
                "target": extra.get("target"),
                "priority": extra.get("priority", 0),
            }
        )

    abilities = []
    for ability_id, raw_ability in enumerate(expansion_data["abilities"], start=1):
        if not raw_ability or not raw_ability.get("name"):
            continue
        abilities.append(
            {
                "id": ability_id,
                "name": raw_ability["name"],
                "description": raw_ability.get("description", ""),
                "speciesIds": sorted(abilities_users.get(ability_id, [])),
            }
        )

    trainers = parse_showdown_trainers(expansion_root / "src" / "data" / "trainers.party", species_id_by_name)

    return {
        "generatedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": build_project_rules(),
        "species": species_entries,
        "moves": moves,
        "abilities": abilities,
        "items": items,
        "trainers": trainers,
        "indexes": {
            "tmhmMoveIds": sorted({move_constants[token] for token in tmhm_tokens if token in move_constants}),
            "tutorMoveIds": sorted({move_constants[token] for token in tutor_tokens if token in move_constants}),
            "specialTeachableMoveIds": sorted({move_constants[token] for token in special_teachable_tokens if token in move_constants}),
        },
    }


def main() -> int:
    args = parse_args()
    flaw_root = Path(args.flawmerald_root).resolve()
    expansion_root = Path(args.expansion_root).resolve() if args.expansion_root else flaw_root / "pokeemerald-expansion"
    tracker_root = Path(args.tracker_root).resolve() if args.tracker_root else flaw_root / "Ironmon-Tracker-flawzo"

    site_data = build_site_data(expansion_root, tracker_root)
    output = ROOT / "data" / "site-data.json"
    output.write_text(json.dumps(site_data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
