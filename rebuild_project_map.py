#!/usr/bin/env python3
"""Пересобирает project_map.json обходом папки '4. Производство' на Drive.

Используйте, когда в PP завели нового клиента (появилась новая папка в РГ1/РГ2).
Ручные алиасы существующих проектов сохраняются — переписываются только
subfolders и автоматические алиасы.

    python3 rebuild_project_map.py
    python3 rebuild_project_map.py --root <другой_folder_id>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from gdrive_lib import _SSL_CTX, get_access_token

ROOT_DEFAULT = "1LbbERfpfZ4O2Xa4OPPmP2rK4z6Rk5hxk"  # 4. Производство
MAX_DEPTH = 4  # 0=корень → 1=РГ → 2=клиент → 3=подпапки клиента
MAP_PATH = Path(__file__).parent / "project_map.json"

SUB_TYPE_PATTERNS = [
    "Административные документы",
    "Аналитика (АТС)",
    "Внедрение",
    "Входящие от клиента",
    "Финальные файлы",
]


def list_folders(token: str, folder_id: str) -> list[dict]:
    out = []
    page = None
    for _ in range(20):
        params = {
            "q": (
                f"'{folder_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and trashed=false"
            ),
            "fields": "nextPageToken,files(id,name)",
            "pageSize": 500,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "allDrives",
        }
        if page:
            params["pageToken"] = page
        url = f"https://www.googleapis.com/drive/v3/files?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
            d = json.load(resp)
        out.extend(d.get("files", []))
        page = d.get("nextPageToken")
        if not page:
            break
    return out


def auto_aliases(name):
    aliases = {name}
    for part in re.split(r"\s*/\s*", name):
        p = part.strip()
        if p:
            aliases.add(p)
            no_parens = re.sub(r"\s*\([^)]*\)\s*", " ", p).strip()
            if no_parens and no_parens != p:
                aliases.add(no_parens)
    return sorted(aliases, key=lambda x: (-len(x), x))


def classify_subfolder(sub_name, client_name):
    s = sub_name
    if s.startswith(client_name + "."):
        s = s[len(client_name) + 1:].strip()
    s = re.sub(r"^\d{2}\.\s*", "", s)
    for pat in SUB_TYPE_PATTERNS:
        if pat.lower() in s.lower():
            return pat
    return sub_name


def pick_default(subfolders):
    return "Внедрение" if "Внедрение" in subfolders else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT_DEFAULT, help="ID корневой папки (по умолчанию 4. Производство)")
    ap.add_argument("--dry-run", action="store_true", help="Не записывать, просто показать diff")
    args = ap.parse_args()

    token = get_access_token()
    current = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    existing_by_id = {p["drive_folder_id"]: p for p in current["projects"]}
    existing_by_name = {p["name"].lower(): p for p in current["projects"]}

    print(f"Обход {args.root}...")
    rg_list = list_folders(token, args.root)
    projects = []
    in_tree_ids = set()
    skipped_empty = []

    for rg in rg_list:
        if rg["name"] in ("Материалы четвёрки", "Архив"):
            continue
        if not re.match(r"^РГ\d+", rg["name"]):
            continue
        print(f"  {rg['name']}: ", end="", flush=True)
        clients = list_folders(token, rg["id"])
        print(f"{len(clients)} клиентов")
        for client in clients:
            in_tree_ids.add(client["id"])
            subs_raw = list_folders(token, client["id"])
            if not subs_raw:
                skipped_empty.append(client["name"])
                continue
            subfolders = {}
            for sub in subs_raw:
                key = classify_subfolder(sub["name"], client["name"])
                if key in subfolders:
                    key = sub["name"]
                subfolders[key] = sub["id"]

            existing = existing_by_id.get(client["id"]) or existing_by_name.get(client["name"].lower())
            if existing:
                aliases = list(existing.get("aliases", []))
                for a in auto_aliases(client["name"]):
                    if a not in aliases:
                        aliases.append(a)
            else:
                aliases = auto_aliases(client["name"])

            projects.append({
                "name": client["name"],
                "rg": rg["name"],
                "aliases": aliases,
                "drive_folder_id": client["id"],
                "drive_folder_url": f"https://drive.google.com/drive/folders/{client['id']}",
                "default_subfolder": pick_default(subfolders),
                "subfolders": subfolders,
            })

    # Внешние проекты (не из этого корня) — сохраняем как были
    for p in current["projects"]:
        if p["drive_folder_id"] in in_tree_ids:
            continue
        entry = dict(p)
        entry.setdefault("rg", None)
        projects.append(entry)

    projects.sort(key=lambda x: (x.get("rg") or "ZZ", x["name"]))

    # Сравнение со старым
    old_ids = {p["drive_folder_id"] for p in current["projects"]}
    new_ids = {p["drive_folder_id"] for p in projects}
    added = new_ids - old_ids
    removed = old_ids - new_ids

    print(f"\nИтого проектов: {len(projects)} (было {len(current['projects'])})")
    if added:
        print(f"+ добавлено {len(added)}: {[p['name'] for p in projects if p['drive_folder_id'] in added]}")
    if removed:
        print(f"- удалено {len(removed)} (нет на Drive): "
              f"{[p['name'] for p in current['projects'] if p['drive_folder_id'] in removed]}")
    if skipped_empty:
        print(f"пропущено пустых: {len(skipped_empty)} {skipped_empty}")

    if args.dry_run:
        print("\nDry-run, файл не записан.")
        return

    result = {
        "_comment": current.get("_comment", ""),
        "_updated": __import__("datetime").date.today().isoformat(),
        "_source": f"Автогенерация из дерева {args.root}, глубина {MAX_DEPTH}. Ручные алиасы сохранены.",
        "projects": projects,
    }
    MAP_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Записано: {MAP_PATH}")


if __name__ == "__main__":
    sys.exit(main())
