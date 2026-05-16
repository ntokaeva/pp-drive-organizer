#!/usr/bin/env python3
"""Создаёт пустой Google Doc/Sheet/Slides прямо в проектной папке клиента.

Использование:
    # Google Doc в Бургер Кинг → Внедрение (default):
    python3 gdrive_create.py "Артефакты встречи 16.05" --project "Бургер Кинг" --type doc

    # таблица в подпапку Финальные файлы:
    python3 gdrive_create.py "Калькулятор июнь" --project "БК" --subfolder "Финальные файлы" --type sheet

    # презентация с автоопределением проекта по словам в названии:
    python3 gdrive_create.py "БК. Презентация HRM v2" --type slides

    # просто папку:
    python3 gdrive_create.py "Сессия 2026-05" --project "Деафон" --type folder
"""
from __future__ import annotations

import argparse
import sys

from gdrive_lib import (
    GOOGLE_MIME,
    create_drive_file,
    detect_project,
    discover_project_folder,
    get_access_token,
    load_project_map,
)


def find_project_by_name(projects, name):
    n = name.lower()
    for p in projects:
        if p["name"].lower() == n:
            return p
        for a in p["aliases"]:
            if a.lower() == n:
                return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="Название документа")
    ap.add_argument("--type", choices=list(GOOGLE_MIME), default="doc",
                    help="Тип: doc | sheet | slides | folder (default: doc)")
    ap.add_argument("--project", help="Имя проекта или алиас")
    ap.add_argument("--subfolder", help="Подпапка внутри проекта (default — default_subfolder)")
    ap.add_argument("--dry-run", action="store_true", help="Показать план, не создавать")
    ap.add_argument("--project-map", default=None, help="Путь к project_map.json")
    args = ap.parse_args()

    projects = load_project_map(args.project_map)

    if args.project:
        project = find_project_by_name(projects, args.project)
        if not project:
            print(f"Проект {args.project!r} не найден в project_map.json.", file=sys.stderr)
            return 2
    else:
        project = detect_project(args.name, projects)
        if not project:
            print(
                f"Не смог определить проект по названию {args.name!r}.\n"
                f"Ищу папку на Drive по словам...",
                file=sys.stderr,
            )
            token = get_access_token()
            cands = discover_project_folder(token, args.name)[:5]
            if cands:
                print("\nКандидаты:", file=sys.stderr)
                for c in cands:
                    flag = "★" if c["under_root"] else " "
                    print(f"  {flag} {c['name']}  ({c['id']})", file=sys.stderr)
                print(
                    "\nПередайте --project '<имя>' или запустите rebuild_project_map.py.",
                    file=sys.stderr,
                )
            else:
                print("Ничего не нашёл. Передайте --project явно.", file=sys.stderr)
            return 2

    sub_name = args.subfolder or project.get("default_subfolder")
    if sub_name:
        if sub_name not in project.get("subfolders", {}):
            print(
                f"Подпапка {sub_name!r} не найдена в {project['name']}. "
                f"Доступные: {list(project.get('subfolders', {}))}",
                file=sys.stderr,
            )
            return 2
        target_id = project["subfolders"][sub_name]
        target_label = f"{project['name']} / {sub_name}"
    else:
        target_id = project["drive_folder_id"]
        target_label = project["name"]

    print(f"Создаю:    {args.name}")
    print(f"Тип:       {args.type} ({GOOGLE_MIME[args.type]})")
    print(f"Проект:    {project['name']}")
    print(f"Папка:     {target_label}")
    print(f"Drive ID:  {target_id}")

    if args.dry_run:
        print("\nDry-run. Уберите флаг для реального создания.")
        return 0

    token = get_access_token()
    result = create_drive_file(token, args.name, target_id, kind=args.type)
    print(f"\n✓ Создано. {result.get('webViewLink') or 'https://drive.google.com/file/d/' + result['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
