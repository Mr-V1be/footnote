# Выкатка на сервер

Продакшен-сборка Footnote — один сервер с Docker Compose: [`docker-compose.prod.yml`](../docker-compose.prod.yml). Снаружи открыт только Caddy (80 и 443), он выпускает TLS-сертификаты Let's Encrypt сам; остальные сервисы общаются во внутренней сети.

```mermaid
flowchart LR
  user([Браузер, интеграции]) -->|HTTPS| caddy[Caddy]
  caddy -->|/api/*| api[API ×N процессов]
  caddy --> web[Web, Next.js]
  caddy -->|auth.домен| kc[Keycloak]
  web -->|BFF| api
  web -. токены, ключи .-> kc
  api -. ключи подписи .-> kc
  api --> pg[(PostgreSQL + pgvector)]
  api --> redis[(Redis)]
  worker[Воркер] --> pg
  worker --> redis
  worker -->|HTTPS| llm[[Внешний API модели]]
  backup[Резервные копии] --> pg
```

| Сервис | Что делает |
| --- | --- |
| `caddy` | TLS, HTTP/3, обратный прокси; консоль администратора Keycloak снаружи закрыта |
| `web` | Next.js (standalone), BFF: токены остаются на сервере |
| `api` | FastAPI, `FOOTNOTE_API_WORKERS` процессов |
| `worker` | разбор документов, проверки, вебхуки, периодические задачи |
| `migrate` | миграции базы при каждой выкатке, до старта API и воркера |
| `keycloak` | вход, организации и роли; браузер ходит на `auth.домен`, серверы — на `keycloak:8080`; образ собирается заранее (`infra/keycloak/Dockerfile`): realm и тема входа внутри, `start --optimized` |
| `postgres`, `redis` | данные (RLS по тенантам) и очередь задач, сессии |
| `backup` | ночные копии обеих баз и файлов, хранятся 14 дней |
| `demo-reset` | только демо-стенд (профиль `demo`): ночной возврат к сиду |

Образы: `backend/Dockerfile` (один образ для API, воркера и команд; Python 3.13, Tesseract для сканов), `frontend/Dockerfile` (Node 24) и `infra/keycloak/Dockerfile` (Keycloak с зафиксированными параметрами сборки: PostgreSQL, проверка здоровья, без неиспользуемых возможностей — CIBA, device flow, PAR, Kerberos, impersonation). Оба многоступенчатые, процессы работают не от root (uid 10001), у каждого сервиса есть healthcheck. Журналы контейнеров ротируются: не больше 5 файлов по 10 МБ на сервис.

## Требования к серверу

| | Минимум | Рекомендуется |
| --- | --- | --- |
| CPU | 2 vCPU | 4 vCPU |
| Память | 4 ГБ | 8 ГБ |
| Диск | 30 ГБ SSD | 60 ГБ SSD |
| ОС | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |

Откуда цифры: стек в работе занимает около 1,5 ГБ памяти (замер локально: Keycloak 540 МБ, API с двумя процессами 400 МБ, воркер 150 МБ, PostgreSQL 100 МБ, web 100 МБ, остальное — десятки мегабайт); сборка образа web на сервере требует ещё около 2 ГБ; лимиты памяти сервисов в сумме — 6 ГБ. Диск: образы около 1,5 ГБ с базовыми слоями, база и файлы растут с документами, копии за 14 дней. Модели на сервере не работают — только внешний API.

### Маленький сервер

На сервере с 4 ГБ, который Footnote делит с другими сервисами, память и соединения задаются в `.env.prod`:

| Переменная | Значение | Зачем |
| --- | --- | --- |
| `FOOTNOTE_API_WORKERS` | `1` | один процесс API вместо двух |
| `FOOTNOTE_WORKER_THREADS` | `2` | воркер разбирает два документа одновременно; бесплатный тариф модели всё равно ограничивает темп |
| `FOOTNOTE_DB_POOL_SIZE`, `FOOTNOTE_DB_MAX_OVERFLOW` | `3`, `2` | до 5 соединений с PostgreSQL на процесс |
| `KEYCLOAK_HEAP_OPTIONS` | `-Xms64m -Xmx192m` | потолок кучи JVM вместо 70% лимита контейнера |
| `KEYCLOAK_JAVA_OPTIONS` | `-XX:TieredStopAtLevel=1 -Xss512k -XX:ReservedCodeCacheSize=64m -XX:MaxMetaspaceSize=192m` | только быстрый JIT, меньше памяти на стеки и код |
| `KEYCLOAK_DB_POOL_MAX_SIZE` | `8` | соединения Keycloak с базой |

Замер локально: Keycloak с этими настройками после импорта realm занимает около 370 МБ (с настройками по умолчанию — около 540 МБ). Keycloak всегда работает с локальным кэшем (`KC_CACHE=local`): один узел, без поиска соседей по кластеру.

### Одно имя: Keycloak под путём

Keycloak может жить не на своём имени, а под путём имени продукта, например
`https://footnote.example.ru/auth`. В `.env.prod`:

```bash
FOOTNOTE_KEYCLOAK_URL=https://footnote.example.ru/auth
KEYCLOAK_PATH=/auth
```

Образ Keycloak собирается с этим путём (`KEYCLOAK_HTTP_RELATIVE_PATH` — параметр сборки,
проверка здоровья на порту управления остаётся на `/health/ready`), серверы обращаются к
`http://keycloak:8080/auth`, а издатель токенов, адреса входа и выхода, redirect URI клиентов
из импорта realm (`${FOOTNOTE_WEB_URL}/auth/callback`) следуют за `FOOTNOTE_KEYCLOAK_URL` и
`FOOTNOTE_WEB_URL` сами. Прокси перед стеком отдаёт Keycloak только его публичные пути —
`/auth/realms/*` и `/auth/resources/*`; `/auth/login`, `/auth/callback`, `/auth/logout` и
`/auth/demo` — маршруты веб-приложения, консоль `/auth/admin` снаружи закрыта. Встроенный Caddy
этого файла настроен на отдельное имя Keycloak.

## Что нужно от владельца

- домен и две DNS-записи A (и AAAA, если есть IPv6) на сервер: `footnote.<домен>` и `auth.footnote.<домен>`;
- сервер с SSH-доступом по ключу;
- почтовый ящик для рассылки (SMTP с логином и паролем, STARTTLS): приглашения, сброс пароля, уведомления о новой редакции закона;
- ключ API модели и решение о тарифе: бесплатный — 50 запросов в день, юридические проверки сверх лимита ждут следующего дня; платный снимает ограничение;
- для приёма денег — договор с платёжным провайдером и его адаптер (сейчас подключён тестовый провайдер, деньги не списываются);
- e-mail для уведомлений Let's Encrypt.

## Выкатка на чистую Ubuntu 24.04

1. **Система и пользователь.**

   ```bash
   sudo apt update && sudo apt -y upgrade
   sudo adduser --disabled-password --gecos "" footnote && sudo usermod -aG sudo footnote
   sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
   sudo ufw enable
   ```

2. **Docker Engine и Compose** из репозитория Docker:

   ```bash
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
     https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
     | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt update && sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo usermod -aG docker footnote
   ```

   Перезайти пользователем `footnote`.

3. **Код и конфигурация.**

   ```bash
   git clone <адрес репозитория> footnote && cd footnote
   cp infra/prod/env.example .env.prod && chmod 600 .env.prod
   ```

   Заполнить `.env.prod`: адреса, почту, ключ модели. Каждый секрет — случайный: `openssl rand -hex 32`. `FOOTNOTE_SECRETS_KEY` после первого запуска не меняется (иначе секреты вебхуков станут нечитаемыми). `FOOTNOTE_DEMO_MODE=false` для настоящей установки.

4. **Сборка и запуск.**

   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
   docker compose -f docker-compose.prod.yml --env-file .env.prod ps
   ```

   Все сервисы должны стать `healthy` (Keycloak — за 1–2 минуты при первом старте), `migrate` — завершиться с кодом 0. Caddy получит сертификаты, как только DNS указывает на сервер.

5. **Корпус норм и индекс.**

   ```bash
   alias footnote='docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api footnote'
   footnote corpus sync --source snapshot   # 152-ФЗ из поставки; раз в неделю воркер сверяет с официальным порталом
   footnote corpus reindex                  # эмбеддинги корпуса во внешнем API (центы)
   footnote checks benchmark                # необязательно: точность и время на эталонном наборе
   ```

6. **Оператор платформы и первая организация.**

   ```bash
   footnote tenants operator --email ops@<домен> --first-name Имя --last-name Фамилия   # пароль спросит
   footnote tenants create romashka --name "ООО «Ромашка»" --domain romashka.ru \
     --owner-email ivanova@romashka.ru --owner-first-name Мария --owner-last-name Иванова
   ```

   Владелец получит письмо-приглашение и задаст пароль; дальше участников приглашают из продукта. Тариф организации назначает оператор в разделе «Платформа».

7. **Проверка.** `https://footnote.<домен>` — лендинг; вход владельцем; загрузка документа доходит до результата проверки; `https://footnote.<домен>/api/health/ready` отвечает 200; `https://auth.footnote.<домен>/admin/` — 404 (консоль закрыта).

## Обновление

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Миграции применяются сервисом `migrate` до старта новых API и воркера. Откат — `git checkout <тег>` и та же команда; миграции пишутся совместимыми с предыдущей версией кода.

### Переход с прежнего имени продукта (миграция 0014)

Продукт назывался «Сноска», в коде — `snoska`. Установка, развёрнутая под этим именем, переходит на новое один раз, в окне обслуживания. Данные, участники, их пароли, секреты клиентов и вебхуков остаются, публичный адрес не меняется. Сессии входа обрываются: издатель токенов меняется вместе с realm, все входят заново. Установка, которой ещё нужна миграция 0013, сначала проходит этот переход, а затем шаги следующего раздела.

| Что | Было | Стало |
| --- | --- | --- |
| Переменные окружения | `SNOSKA_*` | `FOOTNOTE_*`, окончания те же |
| Образы | `snoska-backend`, `snoska-web`, `snoska-keycloak` (`SNOSKA_IMAGE_PREFIX`) | `footnote-backend`, `footnote-web`, `footnote-keycloak` (`FOOTNOTE_IMAGE_PREFIX`) |
| Проект Compose | `snoska-prod`, у разработки `snoska` | `footnote-prod`, `footnote` |
| Сервисы Compose | — | без изменений |
| Тома | `snoska-prod_pgdata`, `_redisdata`, `_blobs`, `_caddydata`, `_caddyconfig`; у разработки `snoska_pgdata`, `_redisdata`, `_miniodata` | `footnote-prod_…`, `footnote_…` |
| Базы | `snoska`, у разработки ещё `snoska_test` | `footnote`, `footnote_test` |
| Роли | `snoska_owner`, `snoska_app` | `footnote_owner`, `footnote_app` |
| Настройка тенанта и каналы уведомлений | `snoska.tenant_id`, `snoska_outbox`, `snoska_check_runs` | `footnote.tenant_id`, `footnote_outbox`, `footnote_check_runs` (переписывает миграция 0014) |
| Realm | `snoska`, отображаемое имя «Сноска» | `footnote`, Footnote |
| Темы входа и писем | `snoska` | `footnote` |
| Клиенты Keycloak | `snoska-api`, `snoska-web`, `snoska-demo`, `snoska-directory`; мапперы `snoska-api-audience` | `footnote-api`, `footnote-web`, `footnote-demo`, `footnote-directory`; `footnote-api-audience` |
| Префикс ключей Redis | `snoska:` — очередь Dramatiq, бюджет модели `snoska:ai:…`, сессии `snoska:web:…` | `footnote:` |
| Бакет S3 | `snoska` | `footnote` |
| Cookie | `snoska_session`, `snoska_locale`, `snoska_theme` | `footnote_session`, `footnote_locale`, `footnote_theme` |
| Метрики, трассировка | `snoska_http_requests_total` и другие `snoska_*`; сервисы `snoska-api`, `snoska-worker` | `footnote_*`; `footnote-api`, `footnote-worker` |
| Заголовки вебхуков | `Snoska-Event`, `Snoska-Delivery`, `Snoska-Signature`, `User-Agent: Snoska-Webhooks/1.0` | `Footnote-Event`, `Footnote-Delivery`, `Footnote-Signature`, `Footnote-Webhooks/1.0` |
| Резервная копия базы | `snoska.dump` | `footnote.dump` |
| Демо-стенд | `operator@snoska.example`, пароль `Snoska-Demo-2026` | `operator@footnote.example`, `Footnote-Demo-2026` |

Получатели вебхуков читают подпись из `Footnote-Signature`; формат подписи и секреты прежние.

Шаги — по порядку, на сервере, из каталога репозитория:

```bash
# 1. Стек под прежним именем останавливается до обновления кода (тома остаются).
docker compose -f docker-compose.prod.yml --env-file .env.prod down

# 2. Код, переменные и образы под новым именем.
git pull
sed -i.snoska 's/^SNOSKA_/FOOTNOTE_/' .env.prod   # прежний файл остаётся в .env.prod.snoska
# в FOOTNOTE_SMTP_SENDER — имя отправителя Footnote
C="docker compose -f docker-compose.prod.yml --env-file .env.prod"
$C build

# 3. Compose создаёт тома нового проекта, данные копируются из прежних.
$C up --no-start
for v in pgdata redisdata blobs caddydata caddyconfig; do
  docker run --rm --entrypoint sh -v "snoska-prod_$v:/from:ro" -v "footnote-prod_$v:/to" \
    pgvector/pgvector:0.8.7-pg18-trixie -c 'cp -a /from/. /to/'
done

# 4. Базы и роли. Пароли ролей (SCRAM) переживают переименование, права и политики привязаны к OID.
$C up -d --wait postgres
$C exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 \
  -c 'ALTER DATABASE snoska RENAME TO footnote' \
  -c 'ALTER ROLE snoska_owner RENAME TO footnote_owner' \
  -c 'ALTER ROLE snoska_app RENAME TO footnote_app'

# 5. Ключи Redis: очередь, сегодняшний бюджет модели (иначе он начнётся с нуля), сессии. Срок жизни ключей сохраняется.
$C up -d --wait redis
$C exec -T redis sh -c 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning --scan --pattern "snoska:*" |
  while read -r key; do
    redis-cli -a "$REDIS_PASSWORD" --no-auth-warning renamenx "$key" "footnote:${key#snoska:}" >/dev/null
  done'

# 6. Keycloak — одноразовым контейнером без импорта realm: обычный старт нового образа
#    создал бы из файла пустой realm footnote рядом с прежним.
$C run -d --name footnote-keycloak-rename keycloak start --optimized
docker logs -f footnote-keycloak-rename   # до строки «Listening on», затем Ctrl+C
docker exec -i -e KC_PATH="$(sed -n 's/^KEYCLOAK_PATH=//p' .env.prod)" footnote-keycloak-rename sh -s <<'EOF'
set -eu
K=/opt/keycloak/bin/kcadm.sh
# Администратор realm master — из KEYCLOAK_ADMIN_* (если его пароль меняли в консоли, указать нынешний).
$K config credentials --server "http://localhost:8080$KC_PATH" --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD"
$K update realms/snoska -s realm=footnote -s displayName=Footnote \
  -s loginTheme=footnote -s emailTheme=footnote \
  -s smtpServer.fromDisplayName=Footnote -s "smtpServer.from=$FOOTNOTE_SMTP_FROM"
client() { $K get clients -r footnote -q clientId="$1" --fields id --format csv --noquotes; }
for pair in "api:Footnote API" "web:Footnote Web" "demo:Footnote Demo Sign-in" "directory:Footnote Directory"; do
  $K update "clients/$(client "snoska-${pair%%:*}")" -r footnote \
    -s clientId="footnote-${pair%%:*}" -s "name=${pair#*:}"
done
$K update "clients/$(client footnote-demo)" -r footnote -s "description=One-click sign-in by role \
on the demo stand (FOOTNOTE_DEMO_MODE). Only the web server knows its secret; an installation \
without the demo may disable it."
# Имя маппера на месте не меняется: сначала новый маппер, затем прежний удаляется.
for c in web demo; do
  id=$(client "footnote-$c")
  old=$($K get "clients/$id/protocol-mappers/models" -r footnote --fields id,name \
    --format csv --noquotes | grep ',snoska-api-audience$' | cut -d, -f1)
  $K create "clients/$id/protocol-mappers/models" -r footnote -s name=footnote-api-audience \
    -s protocol=openid-connect -s protocolMapper=oidc-audience-mapper \
    -s 'config."included.client.audience"=footnote-api' -s 'config."access.token.claim"=true' \
    -s 'config."id.token.claim"=false' -s 'config."introspection.token.claim"=true'
  $K delete "clients/$id/protocol-mappers/models/$old" -r footnote
done
# Только демо-стенд: учётная запись оператора под новым адресом.
operator=$($K get users -r footnote -q username=operator@snoska.example -q exact=true \
  --fields id --format csv --noquotes)
if [ -n "$operator" ]; then
  $K update realms/footnote -s editUsernameAllowed=true
  $K update "users/$operator" -r footnote \
    -s username=operator@footnote.example -s email=operator@footnote.example
  $K update realms/footnote -s editUsernameAllowed=false
fi
EOF
docker rm -f footnote-keycloak-rename

# 7. Новый стек. Сервис migrate применяет миграцию 0014: политики RLS читают footnote.tenant_id,
#    триггеры уведомляют footnote_outbox и footnote_check_runs.
$C up -d                        # демо-стенд: $C --profile demo up -d
$C run --rm api footnote demo seed   # только демо-стенд: новый пароль демо-учётных записей

# 8. Проверка — как шаг 7 выкатки; после неё прежние тома и конфигурация больше не нужны.
docker volume rm snoska-prod_pgdata snoska-prod_redisdata snoska-prod_blobs \
  snoska-prod_caddydata snoska-prod_caddyconfig
rm .env.prod.snoska
```

До шага 8 откат прост: прежние тома не тронуты — `$C down`, `git checkout <прежний тег>`, `mv .env.prod.snoska .env.prod` и `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`.

Сервисная учётная запись клиента каталога (`service-account-…-directory`) Keycloak переименовывает сам вместе с клиентом. Хранилище S3 (у стенда разработки — MinIO) переносится в бакет `footnote` перед шагом 7: `mc mb`, `mc mirror --preserve` из бакета `snoska`, затем `mc rb --force` прежнего.

Стенд разработки переходит так же, с отличиями: тома `snoska_pgdata`, `snoska_redisdata`, `snoska_miniodata` копируются после `docker compose up --no-start` (сеть `snoska_default` с той же подсетью удаляется до него: `docker network rm snoska_default`), в шаге 4 ещё `ALTER DATABASE snoska_test RENAME TO footnote_test`, локальный `.env` переименовывается тем же `sed` (и `FOOTNOTE_DB_NAME=footnote`, `FOOTNOTE_KEYCLOAK_REALM=footnote`, `FOOTNOTE_S3_BUCKET=footnote`), Keycloak на шаге 6 — `docker compose run -d --no-deps --name footnote-keycloak-rename keycloak start-dev`, без `KC_PATH`, а адрес отправителя задаётся явно: `-s smtpServer.from=no-reply@footnote.example`; миграция — `make migrate`. Так переведён стенд разработки этого репозитория: все шаги выполнены на его данных, а сценарий Keycloak шага 6 — ещё и на realm, импортированном из прежнего файла, под путём `/auth`.

### Английский интерфейс (миграция 0013)

Тексты, которые продукт пишет для читателя, хранятся на всех языках интерфейса. Миграция 0013 оставляет прежним строкам их русский текст; английский появляется после перепроверки и синхронизации корпуса. Realm, импортированный раньше, Keycloak не перечитывает — языки, тему писем и адрес возврата из приглашения добавляют один раз:

```bash
footnote corpus sync --source pravo_ips     # названия актов на всех языках (или дождаться еженедельной проверки)
footnote checks recheck                     # последние версии документов — с текстами на всех языках
C="docker compose -f docker-compose.prod.yml --env-file .env.prod"
# пароль администратора Keycloak спросят; к адресу добавить KEYCLOAK_PATH, если он задан
$C exec -it keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin
$C exec keycloak /opt/keycloak/bin/kcadm.sh update realms/footnote \
  -s 'supportedLocales=["en","ru"]' -s defaultLocale=en -s emailTheme=footnote
# В клиенте footnote-web к Valid redirect URIs добавить адрес веба без пути: https://домен
```

Перепроверка юридических проверок тратит запросы к модели (на документ — один запрос на 12 проверок); на бесплатном тарифе её лучше запускать в начале суток по UTC. Записи лендинга для каждого языка лежат в `frontend/public/landing/<язык>/` и снимаются `make demo-refresh`.

## Резервные копии

Сервис `backup` каждую ночь (`FOOTNOTE_BACKUP_HOUR`, по UTC) кладёт в `FOOTNOTE_BACKUP_DIR` каталог с `footnote.dump`, `keycloak.dump` (pg_dump, формат custom) и `blobs.tar.gz` (загруженные файлы) и удаляет копии старше `FOOTNOTE_BACKUP_KEEP_DAYS`. Копию вне расписания: `docker compose -f docker-compose.prod.yml --env-file .env.prod exec backup /usr/local/bin/backup.sh now`. Каталог копий стоит синхронизировать за пределы сервера (rclone, rsync).

Восстановление — в пустые базы, объекты создаются от ролей-владельцев, права роли приложения и политики RLS приходят из дампа:

```bash
C="docker compose -f docker-compose.prod.yml --env-file .env.prod"
D=backups/<дата>
$C stop api worker web keycloak
$C exec -T postgres psql -U postgres \
  -c 'DROP DATABASE footnote WITH (FORCE)' -c 'CREATE DATABASE footnote OWNER footnote_owner' \
  -c 'DROP DATABASE keycloak WITH (FORCE)' -c 'CREATE DATABASE keycloak OWNER keycloak'
$C exec -T postgres psql -U postgres -d footnote -c 'CREATE EXTENSION vector'
$C exec -T postgres pg_restore -U postgres --role=footnote_owner --no-owner --no-comments -d footnote < $D/footnote.dump
$C exec -T postgres pg_restore -U postgres --role=keycloak --no-owner --no-comments -d keycloak < $D/keycloak.dump
$C run --rm --entrypoint sh -v "$PWD/$D:/restore:ro" worker -c 'tar -xzf /restore/blobs.tar.gz -C /app/var/blobs'
$C up -d
```

Проверено локально: дамп разворачивается в пустую базу без ошибок, таблицы принадлежат `footnote_owner`, у `footnote_app` есть права, RLS включена.

## Демо-стенд

То же самое с `FOOTNOTE_DEMO_MODE=true` и профилем `demo`: вход в один клик по ролям, защищённые демо-учётные записи и ночной сброс к сиду (`FOOTNOTE_DEMO_RESET_HOUR`, по Москве).

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile demo up -d --build
footnote demo seed
```

## Проверено локально

Сборка запускалась целиком на этой машине без настоящего деплоя: `FOOTNOTE_DOMAIN=localhost`, `FOOTNOTE_AUTH_DOMAIN=auth.localhost`, порты 46380 и 46381 (TLS от локального центра Caddy), демо-режим. Проверено: все сервисы `healthy`, миграции и сид, лендинг, вход в один клик и обычный вход через Keycloak по HTTPS, выход, документ с результатом проверки, публичный API через Caddy, закрытая консоль Keycloak, резервная копия и её восстановление в отдельную базу (с ролью-владельцем — на базе разработки).
