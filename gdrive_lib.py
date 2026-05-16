"""Общая библиотека для работы с Google Drive: refresh-токен, поиск, перемещение, загрузка.

Без внешних зависимостей — pure stdlib (urllib).

OAuth-токены ожидаются в `~/.config/mcp-gdrive/tokens.json` в формате:
    {
      "client_id": "...",
      "client_secret": "...",
      "refresh_token": "..."
    }

Как получить tokens.json — см. setup_oauth.md.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

TOKENS_PATH = Path.home() / ".config" / "mcp-gdrive" / "tokens.json"
DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"


class DriveError(RuntimeError):
    pass


def _build_ssl_context() -> ssl.SSLContext:
    """Возвращает SSLContext с CA-сертификатами.

    Framework Python на macOS не цепляет системные CA — приходится искать вручную.
    Порядок: SSL_CERT_FILE → certifi (если есть) → типовые системные пути.
    """
    cafile = os.environ.get("SSL_CERT_FILE")
    if not cafile:
        try:
            import certifi  # type: ignore
            cafile = certifi.where()
        except ImportError:
            for candidate in (
                "/etc/ssl/cert.pem",  # macOS system bundle
                "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
                "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            ):
                if Path(candidate).exists():
                    cafile = candidate
                    break
    if not cafile or not Path(cafile).exists():
        raise DriveError(
            "Не нашёл CA-сертификаты для проверки HTTPS.\n"
            "Решения:\n"
            "  1. macOS: запустите /Applications/Python\\ 3.9/Install\\ Certificates.command\n"
            "  2. Или: pip install certifi\n"
            "  3. Или: export SSL_CERT_FILE=/путь/к/cacert.pem"
        )
    return ssl.create_default_context(cafile=cafile)


_SSL_CTX = _build_ssl_context()


def _load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        raise DriveError(
            f"tokens.json не найден по пути {TOKENS_PATH}. "
            f"Настройте OAuth по инструкции setup_oauth.md."
        )
    return json.loads(TOKENS_PATH.read_text())


def get_access_token() -> str:
    """Обновляет access token через refresh_token и возвращает его."""
    t = _load_tokens()
    data = urllib.parse.urlencode({
        "client_id": t["client_id"],
        "client_secret": t["client_secret"],
        "refresh_token": t["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        body = json.load(resp)
    if "access_token" not in body:
        raise DriveError(f"Не удалось обновить токен: {body}")
    return body["access_token"]


def _api_get(token: str, path: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{DRIVE_API}{path}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
        return json.load(resp)


def _api_patch(token: str, path: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{DRIVE_API}{path}?{qs}"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}, method="PATCH"
    )
    req.add_header("Content-Length", "0")
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
        return json.load(resp)


def list_folder(token: str, folder_id: str, page_size: int = 200) -> list[dict]:
    """Список файлов и подпапок внутри folder_id."""
    return _api_get(
        token,
        "/files",
        {
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "files(id,name,mimeType,parents,modifiedTime)",
            "pageSize": page_size,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "allDrives",
        },
    ).get("files", [])


def find_folders_by_name(token: str, name_substring: str) -> list[dict]:
    """Глобальный поиск по всем доступным Drive-папкам по подстроке имени."""
    return _api_get(
        token,
        "/files",
        {
            "q": (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name contains '{name_substring}' and trashed=false"
            ),
            "fields": "files(id,name,parents,driveId)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "allDrives",
        },
    ).get("files", [])


def move_file(token: str, file_id: str, new_parent: str, old_parent: str) -> dict:
    """Перемещает файл из old_parent в new_parent."""
    return _api_patch(
        token,
        f"/files/{file_id}",
        {
            "addParents": new_parent,
            "removeParents": old_parent,
            "supportsAllDrives": "true",
            "fields": "id,name,parents",
        },
    )


_GOOGLE_FORMATS = {
    ".xlsx": "application/vnd.google-apps.spreadsheet",
    ".xls": "application/vnd.google-apps.spreadsheet",
    ".csv": "application/vnd.google-apps.spreadsheet",
    ".tsv": "application/vnd.google-apps.spreadsheet",
    ".docx": "application/vnd.google-apps.document",
    ".doc": "application/vnd.google-apps.document",
    ".pptx": "application/vnd.google-apps.presentation",
    ".ppt": "application/vnd.google-apps.presentation",
}


def upload_file(
    token: str,
    local_path: str | Path,
    parent_id: str,
    drive_name: str | None = None,
    convert_to_google: bool = True,
) -> dict:
    """Загружает локальный файл в Drive-папку parent_id.

    Если convert_to_google=True и формат поддерживается (xlsx/docx/pptx/csv/tsv) —
    автоматически конвертирует в Google Sheets/Docs/Slides.

    Если в папке уже есть файл с тем же именем — обновляет его (preserves history).
    """
    local = Path(local_path)
    if not local.exists():
        raise DriveError(f"Файл не найден: {local}")

    name = drive_name or local.name
    ext = local.suffix.lower()
    target_mime = _GOOGLE_FORMATS.get(ext) if convert_to_google else None

    # имя в Drive: для конвертируемых форматов убираем расширение
    drive_display_name = Path(name).stem if target_mime else name

    # Проверка дубля
    existing = _api_get(
        token,
        "/files",
        {
            "q": (
                f"name='{drive_display_name}' and '{parent_id}' in parents "
                f"and trashed=false"
            ),
            "fields": "files(id,name)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "allDrives",
        },
    ).get("files", [])

    metadata: dict = {"name": drive_display_name}
    if existing:
        update_id = existing[0]["id"]
        url = f"{UPLOAD_API}/files/{update_id}?uploadType=multipart&supportsAllDrives=true&fields=id,name,parents"
        method = "PATCH"
    else:
        metadata["parents"] = [parent_id]
        url = f"{UPLOAD_API}/files?uploadType=multipart&supportsAllDrives=true&fields=id,name,parents"
        method = "POST"

    if target_mime:
        metadata["mimeType"] = target_mime

    source_mime = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
    boundary = "----pp_drive_org_boundary"
    body_parts = [
        f"--{boundary}".encode(),
        b"Content-Type: application/json; charset=UTF-8",
        b"",
        json.dumps(metadata, ensure_ascii=False).encode(),
        f"--{boundary}".encode(),
        f"Content-Type: {source_mime}".encode(),
        b"",
        local.read_bytes(),
        f"--{boundary}--".encode(),
    ]
    body = b"\r\n".join(body_parts)

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", f"multipart/related; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=300, context=_SSL_CTX) as resp:
        return json.load(resp)


def load_project_map(path: str | Path | None = None) -> list[dict]:
    """Читает project_map.json (по умолчанию — рядом с этим файлом)."""
    if path is None:
        path = Path(__file__).parent / "project_map.json"
    return json.loads(Path(path).read_text(encoding="utf-8"))["projects"]


PROIZVODSTVO_ROOT_ID = "1LbbERfpfZ4O2Xa4OPPmP2rK4z6Rk5hxk"


def discover_project_folder(
    token: str,
    name_hint: str,
    root_id: str = PROIZVODSTVO_ROOT_ID,
    min_len: int = 4,
) -> list[dict]:
    """Нечёткий поиск папки клиента в дереве 4. Производство по подсказке.

    Берёт «значимые» слова из name_hint (>= min_len символов, без префиксов
    типа БК/BK/Док и расширений) и для каждого слова делает Drive-search по
    name contains '<слово>' с фильтром mimeType=folder. Возвращает кандидатов
    с пометкой, лежат ли они под root_id (через path-проверку).

    Применяется когда detect_project() вернул None — то есть клиента нет в
    project_map.json, но папка на Drive скорее всего есть.
    """
    # Чистим от расширения, нумерации, типовых префиксов
    cleaned = re.sub(r"\.\w{1,5}$", "", name_hint)  # расширение
    cleaned = re.sub(r"^\d{4}[-_.]\d{2}[-_.]\d{2}[-_ ]*", "", cleaned)  # дата
    # Разбиваем по разделителям
    tokens = [t for t in re.split(r"[\s_.\-/]+", cleaned) if len(t) >= min_len]
    # Убираем стоп-слова
    stop = {"отчёт", "отчет", "версия", "финал", "draft", "final", "report", "итоги",
            "встречи", "встреча", "follow", "артефакты", "дозвон", "руководство"}
    tokens = [t for t in tokens if t.lower() not in stop]

    seen_ids: set[str] = set()
    candidates: list[dict] = []
    for tok in tokens[:5]:
        try:
            found = find_folders_by_name(token, tok)
        except Exception:
            continue
        for f in found:
            if f["id"] in seen_ids:
                continue
            seen_ids.add(f["id"])
            # под root_id ли?
            under_root = _is_under(token, f["id"], root_id, max_hops=4)
            candidates.append({**f, "matched_token": tok, "under_root": under_root})
    # сначала под root, потом по длине совпавшего токена
    candidates.sort(key=lambda x: (not x["under_root"], -len(x["matched_token"])))
    return candidates


def _is_under(token: str, folder_id: str, root_id: str, max_hops: int = 4) -> bool:
    """Проверяет, является ли folder_id потомком root_id (поднимаясь по parents).
    Ограничено max_hops чтобы не зацикливаться."""
    cur = folder_id
    for _ in range(max_hops):
        if cur == root_id:
            return True
        try:
            info = _api_get(token, f"/files/{cur}", {
                "fields": "parents",
                "supportsAllDrives": "true",
            })
        except Exception:
            return False
        parents = info.get("parents") or []
        if not parents:
            return False
        cur = parents[0]
    return cur == root_id


def detect_project(filename: str, projects: list[dict]) -> dict | None:
    """Определяет проект по подстроке в имени файла. Возвращает запись project_map
    или None если не нашли. Алиасы регистронезависимы, проверяются как substring."""
    lower = filename.lower()
    best: tuple[int, dict] | None = None
    for p in projects:
        for alias in p["aliases"]:
            if alias.lower() in lower:
                # выбираем самый длинный матч — чтобы «БК» не перебивал «БКФинал»
                score = len(alias)
                if best is None or score > best[0]:
                    best = (score, p)
                break
    return best[1] if best else None
