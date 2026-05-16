#!/usr/bin/env python3
"""Заливает локальный файл в правильную Drive-папку проекта.

Определяет проект автоматически по имени файла (через project_map.json) или
по явному флагу --project.

Использование:
    # автоопределение проекта из имени файла:
    python3 gdrive_upload.py путь/к/БК_отчёт_май.docx

    # явно указать проект:
    python3 gdrive_upload.py путь/к/файл.docx --project "Бургер Кинг / Burger King"

    # указать конкретную подпапку:
    python3 gdrive_upload.py путь/к/файл.docx --subfolder "Финальные файлы"

    # сухой прогон:
    python3 gdrive_upload.py путь/к/файл.docx --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gdrive_lib import (
    detect_project,
    get_access_token,
    load_project_map,
    upload_file,
)


def find_project_by_name(projects: list[dict], name: str) -> dict | None:
    n = name.lower()
    for p in projects:
        if p["name"].lower() == n:
            return p
        for a in p["aliases"]:
            if a.lower() == n:
                return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="Путь к локальному файлу")
    ap.add_argument("--project", help="Имя проекта или алиас (если автоопределение не сработало)")
    ap.add_argument("--subfolder", help="Имя подпапки внутри проекта (по умолчанию — default_subfolder из project_map)")
    ap.add_argument("--no-convert", action="store_true", help="Не конвертировать xlsx/docx/pptx в Google формат")
    ap.add_argument("--dry-run", action="store_true", help="Показать что будет сделано, не заливать")
    ap.add_argument("--project-map", default=None, help="Путь к project_map.json")
    args = ap.parse_args()

    local = Path(args.file)
    if not local.exists():
        print(f"Файл не найден: {local}", file=sys.stderr)
        return 2

    projects = load_project_map(args.project_map)

    if args.project:
        project = find_project_by_name(projects, args.project)
        if not project:
            print(f"Проект {args.project!r} не найден в project_map.json.", file=sys.stderr)
            print(f"Доступные: {[p['name'] for p in projects]}", file=sys.stderr)
            return 2
    else:
        project = detect_project(local.name, projects)
        if not project:
            print(
                f"Не смог определить проект по имени файла {local.name!r}.\n"
                f"Передайте явно через --project.\n"
                f"Доступные проекты: {[p['name'] for p in projects]}",
                file=sys.stderr,
            )
            return 2

    # резолвим подпапку
    sub_name = args.subfolder or project.get("default_subfolder")
    if sub_name:
        if sub_name not in project.get("subfolders", {}):
            print(
                f"Подпапка {sub_name!r} не найдена в проекте {project['name']}. "
                f"Доступные: {list(project.get('subfolders', {}))}",
                file=sys.stderr,
            )
            return 2
        target_id = project["subfolders"][sub_name]
        target_label = f"{project['name']} / {sub_name}"
    else:
        target_id = project["drive_folder_id"]
        target_label = project["name"]

    print(f"Файл:      {local}")
    print(f"Проект:    {project['name']}")
    print(f"Назначение: {target_label}")
    print(f"Drive ID:  {target_id}")

    if args.dry_run:
        print("\nDry-run. Для реальной заливки уберите --dry-run.")
        return 0

    token = get_access_token()
    result = upload_file(
        token,
        local,
        target_id,
        convert_to_google=not args.no_convert,
    )
    print(f"\n✓ Загружено. Drive file id: {result['id']}")
    print(f"  https://drive.google.com/file/d/{result['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
