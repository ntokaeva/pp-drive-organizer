# Настройка OAuth-токенов для Google Drive

Этот шаг делается **один раз** на свой Google аккаунт. Дальше скрипты сами
обновляют access_token, тебе ничего делать не надо.

## 🚀 Быстрый путь — через `bootstrap.sh`

В корне репо лежит интерактивный мастер, который сам открывает нужные страницы
и собирает токены:

```bash
./bootstrap.sh
```

Скрипт:

1. Проверит, что Python/curl/git установлены.
2. Откроет Google Cloud Console → попросит создать Project и включить Drive API.
3. Откроет OAuth Consent Screen → попросит добавить себя в Test Users.
4. Откроет страницу OAuth Client → попросит вставить `client_id` и `client_secret`.
5. Откроет OAuth Playground → попросит вставить `refresh_token`.
6. Сохранит `~/.config/mcp-gdrive/tokens.json` и проверит соединение.

На каждом шаге — короткая инструкция в терминале и кнопка «↩ Нажми Enter».

Если ты уже знаком с Google Cloud — пройдёшь за 5–7 минут. Если первый раз —
~15 минут.

---

## 📚 Ручной путь — если хочешь понимать, что делаешь

Ниже подробная инструкция с тем, **что ты увидишь на каждом экране**.

### Шаг 1. Google Cloud Project

> 📍 **Открой:** https://console.cloud.google.com/projectcreate

1. **Project name:** `pp-drive-tools` (или что угодно).
2. **Organization:** оставь как есть.
3. Нажми **Create**.
4. Подожди ~10 секунд — справа вверху появится плашка «Project created».
   Кликни **Select Project** в этой плашке (или в шапке выбери его в выпадающем списке).

### Шаг 2. Включить Google Drive API

> 📍 **Открой:** https://console.cloud.google.com/apis/library/drive.googleapis.com

1. Убедись, что в шапке выбран **твой** проект (тот, который создал в шаге 1).
2. Нажми синюю кнопку **Enable**.
3. Через ~10 секунд страница перезагрузится и кнопка станет «**Manage**» — это значит API включён.

### Шаг 3. OAuth Consent Screen

Этот экран нужен, чтобы Google пускал твоё приложение к Drive.

> 📍 **Открой:** https://console.cloud.google.com/apis/credentials/consent

1. **User Type:** выбери **External** → **Create**.
2. Заполни обязательные поля:
   - **App name:** `pp-drive-organizer`
   - **User support email:** свой email
   - **Developer contact email:** свой email
3. **Save and Continue.**
4. Экран **Scopes** — ничего не добавляй, **Save and Continue**.
5. Экран **Test users**:
   - **Add Users** → введи **свой рабочий email PP** (тот же, под которым
     работаешь в Google Drive).
   - **Add** → **Save and Continue**.
6. **Summary** → **Back to Dashboard**.

> ⚠️ Если пропустишь добавление себя в Test users — на шаге 5 (OAuth Playground)
> Google скажет «Access blocked: app has not completed verification». Лечится
> возвращением сюда и добавлением себя.

### Шаг 4. Создать OAuth Client

Это пара «логин-пароль» для твоего приложения.

> 📍 **Открой:** https://console.cloud.google.com/apis/credentials

1. Сверху нажми **+ Create Credentials** → **OAuth client ID**.
2. **Application type:** выбери **Desktop app**.
3. **Name:** `pp-drive-organizer` (или что угодно).
4. **Create.**
5. Появится модалка **OAuth client created** с двумя значениями:
   - **Your Client ID** — длинная строка, заканчивается на `.apps.googleusercontent.com`
   - **Your Client Secret** — короче, начинается с `GOCSPX-`
6. **Скопируй оба и сохрани куда-нибудь временно** (текстовый редактор).
   После закрытия модалки их можно посмотреть кнопкой 🖉 (Edit) на той же странице.

### Шаг 5. Получить refresh_token через OAuth Playground

Refresh_token — это «вечный пропуск», по которому скрипты обновляют доступ
без твоего участия.

> 📍 **Открой:** https://developers.google.com/oauthplayground/

1. Справа вверху — иконка **⚙ шестерёнка** (OAuth 2.0 configuration).
2. Поставь галку **«Use your own OAuth credentials»**.
3. Вставь:
   - **OAuth Client ID** — из шага 4
   - **OAuth Client secret** — из шага 4
4. Кликни **Close** (галку оставь).
5. **Слева** в дереве скоупов прокрути до **Drive API v3** → разверни → выбери
   ровно один scope: **`https://www.googleapis.com/auth/drive`**.

   > Это полный доступ к Drive: создание/перемещение/удаление файлов
   > в любых папках, к которым у тебя есть доступ.

6. Внизу слева — **Authorize APIs** (синяя кнопка).
7. Откроется окно Google. Войди **своим рабочим аккаунтом PP**.
8. Может появиться предупреждение **«Google hasn't verified this app»** —
   нажми **Advanced** → **Go to pp-drive-organizer (unsafe)**. Это нормально:
   ты сам автор приложения, для себя.
9. **Allow** на запрашиваемые разрешения.
10. Тебя вернёт в Playground. Слева теперь есть **Step 2: Exchange
    authorization code for tokens**. Нажми синюю кнопку **Exchange
    authorization code for tokens**.
11. Справа появится JSON примерно такого вида:
    ```json
    {
      "access_token": "ya29....",
      "expires_in": 3599,
      "refresh_token": "1//0g....",
      "scope": "https://www.googleapis.com/auth/drive",
      "token_type": "Bearer"
    }
    ```
12. **Скопируй значение `refresh_token`** (длинная строка, начинается с `1//`).

### Шаг 6. Сохранить tokens.json

В терминале:

```bash
mkdir -p ~/.config/mcp-gdrive
cat > ~/.config/mcp-gdrive/tokens.json <<'JSON'
{
  "client_id": "ВСТАВЬ_CLIENT_ID_ИЗ_ШАГА_4",
  "client_secret": "ВСТАВЬ_CLIENT_SECRET_ИЗ_ШАГА_4",
  "refresh_token": "ВСТАВЬ_REFRESH_TOKEN_ИЗ_ШАГА_5"
}
JSON
chmod 600 ~/.config/mcp-gdrive/tokens.json
```

Замени три плейсхолдера на свои значения. Запусти этот блок в терминале.

### Шаг 7. Проверка

```bash
cd pp-drive-organizer
python3 -c "from gdrive_lib import get_access_token; print('OK,', get_access_token()[:25], '...')"
```

Видишь `OK, ya29.xxx ...` — всё работает. Иди пробовать:

```bash
python3 gdrive_create.py "Тест" --project "Бургер Кинг" --dry-run
```

---

## Что хранится в tokens.json и почему это важно

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
```

- `client_id` + `client_secret` — пара «логин-пароль» твоего OAuth Client.
  Не секрет в строгом смысле, но без них токен не обновишь.
- `refresh_token` — **самое важное**. Это пожизненный (до отзыва) пропуск
  к твоему Google аккаунту со скоупом `drive`. **Никогда** не комить его
  в git, не отправляй в чатах, не давай другим.

Если refresh_token утёк или ушёл не туда:
1. Открой https://myaccount.google.com/permissions
2. Найди свой OAuth Client → **Remove Access**.
3. Перепройди шаг 5 и получи новый.

---

## FAQ

**«Access blocked: app has not completed verification»** на шаге 5.
→ Вернись в шаг 3, добавь свой email в **Test users**.

**`invalid_grant`** при запуске скрипта.
→ `refresh_token` истёк или отозван. Перепройди шаг 5.

**`403 insufficientPermissions`** при попытке что-то сделать.
→ На шаге 5 выбран не тот scope. Должен быть **`/auth/drive`**, а не
`drive.file` или `drive.readonly`. Перепройди шаг 5 с правильным scope.

**`File not found` при перемещении**.
→ У твоего аккаунта нет доступа к исходной или целевой папке Shared Drive.
Попроси доступ у владельца Shared Drive.

**У меня уже стоит mcp-gdrive (MCP-сервер) — у него тоже есть tokens.json. Можно его взять?**
→ Да, эти скрипты используют тот же путь `~/.config/mcp-gdrive/tokens.json`
и тот же формат. Если файл уже есть и работает — пропусти настройку, всё
заработает само.
