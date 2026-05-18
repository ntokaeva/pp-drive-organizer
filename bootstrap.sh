#!/bin/bash
# bootstrap.sh — интерактивный сетап OAuth для pp-drive-organizer.
#
# Проводит пользователя через шаги:
#   1. Google Cloud Project + Drive API + OAuth Client
#   2. OAuth Playground → refresh_token
#   3. Сохранение tokens.json + проверка соединения с Drive
#
# Безопасно перезапускать: если tokens.json уже есть и работает, скрипт
# просто проверит и закроется.

set -eu
TOKENS_DIR="$HOME/.config/mcp-gdrive"
TOKENS_FILE="$TOKENS_DIR/tokens.json"

# ANSI
B="\033[1m"; G="\033[32m"; Y="\033[33m"; R="\033[31m"; N="\033[0m"
say() { printf "${B}$1${N}\n"; }
ok()  { printf "${G}✓ $1${N}\n"; }
warn(){ printf "${Y}⚠ $1${N}\n"; }
err() { printf "${R}✗ $1${N}\n" >&2; }

pause() { printf "\n${B}↩ Нажми Enter когда выполнил эти шаги...${N}"; read -r _; }

open_url() {
  local url="$1"
  case "$(uname -s)" in
    Darwin) open "$url" 2>/dev/null || echo "Открой: $url" ;;
    Linux)  xdg-open "$url" 2>/dev/null || echo "Открой: $url" ;;
    *)      echo "Открой: $url" ;;
  esac
}

# ─── Шаг 0: пререквизиты ──────────────────────────────────────────────────
say "🔧 Шаг 0/5 — проверка окружения"
for cmd in python3 curl git; do
  if ! command -v $cmd >/dev/null 2>&1; then
    err "Не найден $cmd. Установи и попробуй снова."
    exit 1
  fi
done
ok "python3, curl, git — все на месте"

# ─── Если tokens.json уже есть — проверяем ────────────────────────────────
if [ -f "$TOKENS_FILE" ]; then
  say "🔑 Найден существующий $TOKENS_FILE — проверяю..."
  if python3 -c "
import sys; sys.path.insert(0, '$(dirname "$0")')
from gdrive_lib import get_access_token
t = get_access_token()
print(f'OK, длина токена {len(t)}')
" 2>/dev/null; then
    ok "tokens.json валиден, можно работать"
    echo ""
    echo "Если хочешь пересоздать с нуля — удали ~/.config/mcp-gdrive/tokens.json и перезапусти."
    exit 0
  else
    warn "tokens.json не работает (истёк или повреждён). Сейчас пересоздадим."
  fi
fi

# ─── Шаг 1: Google Cloud Project + Drive API ─────────────────────────────
say ""
say "📦 Шаг 1/5 — Google Cloud Project + Drive API"
cat <<'STEP1'
1. Сейчас откроется Google Cloud Console.
2. Создай новый проект (или выбери существующий) — например 'pp-drive-tools'.
3. В верхнем поиске набери 'Google Drive API' → открой страницу API → ENABLE.
STEP1
open_url "https://console.cloud.google.com/projectcreate"
pause

# ─── Шаг 2: OAuth Consent Screen ─────────────────────────────────────────
say ""
say "🛂 Шаг 2/5 — OAuth Consent Screen"
cat <<'STEP2'
1. Открой меню → APIs & Services → OAuth consent screen.
2. User Type: External → Create.
3. App name: pp-drive-organizer (или любое).
   Support email + Developer email: твой email.
4. Save and Continue (скоупы пропусти).
5. Test users → Add Users → добавь СВОЙ рабочий email PP. Save.
STEP2
open_url "https://console.cloud.google.com/apis/credentials/consent"
pause

# ─── Шаг 3: OAuth Client ─────────────────────────────────────────────────
say ""
say "🔐 Шаг 3/5 — OAuth Client (получим client_id / client_secret)"
cat <<'STEP3'
1. APIs & Services → Credentials → Create credentials → OAuth client ID.
2. Application type: Desktop app.
3. Name: pp-drive-organizer.
4. Create.
5. Появится окно с CLIENT ID и CLIENT SECRET — скопируй их сейчас.
STEP3
open_url "https://console.cloud.google.com/apis/credentials"
echo ""
printf "${B}Вставь client_id (заканчивается на .apps.googleusercontent.com):${N} "
read -r CLIENT_ID
printf "${B}Вставь client_secret (GOCSPX-...):${N} "
read -r CLIENT_SECRET

if [ -z "${CLIENT_ID:-}" ] || [ -z "${CLIENT_SECRET:-}" ]; then
  err "Пустые client_id/secret. Прерываю."
  exit 1
fi

# ─── Шаг 4: OAuth Playground → refresh_token ─────────────────────────────
say ""
say "🎫 Шаг 4/5 — OAuth Playground (получим refresh_token)"
cat <<'STEP4'
1. Откроется https://developers.google.com/oauthplayground/
2. В правом верхнем углу — шестерёнка (settings).
   Поставь галку 'Use your own OAuth credentials'.
   Вставь свой CLIENT ID и CLIENT SECRET (из шага 3). Close.
3. Слева в списке скоупов найди 'Drive API v3'.
   Выбери 'https://www.googleapis.com/auth/drive' (ПОЛНЫЙ доступ к Drive).
4. Authorize APIs → войди СВОИМ рабочим аккаунтом PP → Allow.
5. Откроется шаг 2: 'Exchange authorization code for tokens' → нажми эту кнопку.
6. Появится JSON с access_token и refresh_token. Скопируй refresh_token.
STEP4
open_url "https://developers.google.com/oauthplayground/"
echo ""
printf "${B}Вставь refresh_token (начинается с 1//):${N} "
read -r REFRESH_TOKEN

if [ -z "${REFRESH_TOKEN:-}" ]; then
  err "Пустой refresh_token. Прерываю."
  exit 1
fi

# ─── Шаг 5: Сохранение + проверка ────────────────────────────────────────
say ""
say "💾 Шаг 5/5 — сохранение и проверка"
mkdir -p "$TOKENS_DIR"
cat > "$TOKENS_FILE" <<JSON
{
  "client_id": "$CLIENT_ID",
  "client_secret": "$CLIENT_SECRET",
  "refresh_token": "$REFRESH_TOKEN"
}
JSON
chmod 600 "$TOKENS_FILE"
ok "Записал $TOKENS_FILE (chmod 600)"

echo ""
say "🧪 Тест: пробую обновить access_token..."
if python3 -c "
import sys; sys.path.insert(0, '$(dirname "$0")')
from gdrive_lib import get_access_token
t = get_access_token()
print(f'  access_token prefix: {t[:25]}...')
" ; then
  ok "Готово! Drive API работает от твоего имени."
  echo ""
  echo "Попробуй прямо сейчас:"
  echo "  python3 gdrive_upload.py путь/к/файлу.docx --dry-run"
  echo "  python3 gdrive_create.py 'Тест' --project 'Бургер Кинг' --dry-run"
else
  err "Что-то пошло не так. Проверь client_id / client_secret / refresh_token."
  exit 1
fi
