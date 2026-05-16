# Настройка OAuth-токенов для Google Drive

Скриптам нужен файл `~/.config/mcp-gdrive/tokens.json` вида:

```json
{
  "client_id": "...apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",
  "refresh_token": "1//0g..."
}
```

Скрипты сами обновляют access_token через refresh_token — настройка нужна
только один раз.

## Способ 1: если у вас уже настроен mcp-gdrive

У многих в Paper Planes уже установлен MCP-сервер для Google Drive
(`@modelcontextprotocol/server-gdrive` или `mcp-gdrive`). Если файл
`~/.config/mcp-gdrive/tokens.json` уже существует — ничего делать не нужно,
скрипты подхватят его автоматически.

Проверка:

```bash
ls -la ~/.config/mcp-gdrive/tokens.json
```

## Способ 2: создать новый OAuth Client с нуля

### 1. Создать Google Cloud Project

1. Зайти в [console.cloud.google.com](https://console.cloud.google.com/).
2. Создать новый проект (или использовать существующий) — например
   `pp-drive-tools`.
3. В разделе **APIs & Services → Library** включить **Google Drive API**.

### 2. Создать OAuth Client

1. **APIs & Services → Credentials → Create credentials → OAuth client ID**.
2. Тип приложения: **Desktop app**.
3. Имя: `pp-drive-organizer` (или любое).
4. Скачать JSON с `client_id` и `client_secret`.

### 3. Получить refresh_token

Самый простой способ — Google OAuth Playground:

1. Откройте [developers.google.com/oauthplayground](https://developers.google.com/oauthplayground/).
2. В правом верхнем углу — шестерёнка → **Use your own OAuth credentials**.
   Вставьте `client_id` и `client_secret` из шага 2.
3. В списке слева найдите **Drive API v3** → выберите
   `https://www.googleapis.com/auth/drive` (полный доступ к Drive).
4. **Authorize APIs** → войдите своим рабочим Google-аккаунтом → разрешите доступ.
5. **Exchange authorization code for tokens** — получите `refresh_token`.

### 4. Сохранить токены

```bash
mkdir -p ~/.config/mcp-gdrive
cat > ~/.config/mcp-gdrive/tokens.json <<'JSON'
{
  "client_id": "ВАШЕ_CLIENT_ID.apps.googleusercontent.com",
  "client_secret": "GOCSPX-ВАШ_SECRET",
  "refresh_token": "1//0gВАШ_REFRESH_TOKEN"
}
JSON
chmod 600 ~/.config/mcp-gdrive/tokens.json
```

### 5. Проверить

```bash
cd pp-drive-organizer
python3 -c "from gdrive_lib import get_access_token; print('OK,', get_access_token()[:20], '...')"
```

Если видите `OK, ya29.xxx ...` — настройка завершена.

## Безопасность

- `tokens.json` даёт **полный доступ** к Google Drive аккаунта. Не комитьте
  его никуда, не отправляйте в чатах.
- Файл должен иметь права `600` (читает только владелец).
- Если refresh_token утёк — отзовите его в
  [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
  и сгенерируйте новый.
- Для каждого сотрудника — свой `tokens.json`, привязанный к **его** рабочему
  аккаунту PP. Так в логах Drive будет видно, кто что переместил.

## Проблемы

**`invalid_grant`** — refresh_token истёк или отозван. Повторите шаг 3.

**`403 insufficientPermissions`** — в OAuth Client включён неполный scope.
Убедитесь что в шаге 3 выбран `https://www.googleapis.com/auth/drive`, а не
`drive.file` или `drive.readonly`.

**`File not found`** при перемещении — у вашего аккаунта нет доступа к
исходной или целевой папке на Shared Drive. Попросите доступ у владельца.
