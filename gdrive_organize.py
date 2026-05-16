#!/usr/bin/env python3
"""Раскладывает сваленные в одной Drive-папке файлы по проектным папкам.

Сценарий: вы (или кто-то ещё) залили кучу файлов в общую папку на Drive
(например в корень «4. Производство»), а они должны лежать в подпапках конкретных
проектов. Скрипт определяет проект по имени файла (по реестру project_map.json)
и перемещает каждый файл в правильное место.

Использование:
    # сухой прогон (показать что будет перемещено, не трогать):
    python3 gdrive_organize.py <source_folder_id>

    # реальное перемещение:
    python3 gdrive_organize.py <source_folder_id> --execute

    # переопределить subfolder по умолчанию для конкретного проекта:
    python3 gdrive_organize.py <source_folder_id> --execute --subfolder "БК=Финальные файлы"

Пример:
    python3 gdrive_organize.py 1LbbERfpfZ4O2Xa4OPPmP2rK4z6Rk5hxk --execute
"""
from __future__ import annotations

import argparse
import sys

from gdrive_lib import (
    detect_project,
    discover_project_folder,
    get_access_token,
    list_folder,
    load_project_map,
    move_file,
)


def parse_subfolder_overrides(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"--subfolder ожидает формат 'alias=имя_подпапки', получил: {it!r}")
        k, v = it.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def resolve_target(project: dict, overrides: dict[str, str]) -> tuple[str, str]:
    """Возвращает (target_folder_id, human_label)."""
    # override по любому из алиасов
    for alias in project["aliases"]:
        if alias.lower() in overrides:
            sub = overrides[alias.lower()]
            sf = project.get("subfolders", {})
            if sub not in sf:
                raise SystemExit(
                    f"Подпапка {sub!r} не найдена в project_map для {project['name']}. "
                    f"Доступные: {list(sf)}"
                )
            return sf[sub], f"{project['name']} / {sub}"

    # дефолтная подпапка
    default_sub = project.get("default_subfolder")
    if default_sub:
        sf = project["subfolders"][default_sub]
        return sf, f"{project['name']} / {default_sub}"

    # плоская структура — корень папки проекта
    return project["drive_folder_id"], project["name"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_folder_id", help="ID Drive-папки, где сейчас лежит свалка")
    ap.add_argument("--execute", action="store_true", help="Реально переместить (без флага — dry-run)")
    ap.add_argument(
        "--subfolder",
        action="append",
        default=[],
        help="Переопределить подпапку для проекта, формат: 'alias=Имя подпапки'",
    )
    ap.add_argument("--project-map", default=None, help="Путь к project_map.json")
    args = ap.parse_args()

    overrides = parse_subfolder_overrides(args.subfolder)
    projects = load_project_map(args.project_map)
    token = get_access_token()

    files = [f for f in list_folder(token, args.source_folder_id) if "folder" not in f["mimeType"]]
    if not files:
        print(f"В папке {args.source_folder_id} нет файлов (только подпапки или пусто).")
        return 0

    print(f"Файлов на разбор: {len(files)}\n")
    plan: list[tuple[dict, dict, str, str]] = []  # (file, project, target_id, label)
    unmatched: list[dict] = []
    for f in files:
        proj = detect_project(f["name"], projects)
        if proj is None:
            unmatched.append(f)
            continue
        target_id, label = resolve_target(proj, overrides)
        plan.append((f, proj, target_id, label))

    for f, _proj, target_id, label in plan:
        print(f"  → {label}")
        print(f"      {f['name']}")
    if unmatched:
        print(f"\nНе определён проект ({len(unmatched)}):")
        for f in unmatched:
            print(f"  ? {f['name']}")
        # Discover-режим: для небольшого числа unmatched пробуем найти папку на Drive
        if len(unmatched) <= 5 and not args.execute:
            print("\nDiscover (поиск папок на Drive по словам из имени файла):")
            for f in unmatched:
                cands = discover_project_folder(token, f["name"])[:3]
                if not cands:
                    print(f"  {f['name']}: ничего не нашёл")
                    continue
                print(f"  {f['name']}:")
                for c in cands:
                    flag = "★" if c["under_root"] else " "
                    print(f"    {flag} {c['name']}  ({c['id']})")
            print(
                "\n  ★ = лежит под '4. Производство'. Если нужный клиент здесь —\n"
                "    запустите 'python3 rebuild_project_map.py' чтобы добавить его в реестр,\n"
                "    либо используйте gdrive_upload.py --project '<имя>' для разовой заливки."
            )
        else:
            print(
                "  (добавьте алиас в project_map.json, запустите 'python3 rebuild_project_map.py',\n"
                "   или используйте gdrive_upload.py с явным проектом)"
            )

    if not args.execute:
        print("\nDry-run. Для реального перемещения добавьте --execute.")
        return 0

    print("\n=== Перемещение ===")
    ok, fail = 0, 0
    for f, _proj, target_id, label in plan:
        try:
            move_file(token, f["id"], target_id, args.source_folder_id)
            print(f"  ✓ {f['name']} → {label}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {f['name']}: {e}")
            fail += 1
    print(f"\nИтого: перемещено {ok}, ошибок {fail}, не определено {len(unmatched)}.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
