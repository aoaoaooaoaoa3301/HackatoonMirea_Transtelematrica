# Транстелематика — Суверенная система управления задачами

Веб-приложение для планирования, контроля и анализа задач внутри компании с многоуровневой иерархией (год → квартал → месяц → неделя), интерактивными дашбордами и AI-помощником.

Разработано в рамках хакатона МИРЭА × Транстелематика.

---

## Что внутри

| Возможность | Реализация |
|---|---|
| Иерархия задач | 4 уровня (GOAL → EPIC → TASK → SUBTASK), произвольная глубина, авто-каскад прогресса |
| Поток делегирования | Отдел → руководитель → исполнитель, события в `task_history`, визуализация в виде потока |
| Планирование | start_date + due_date, авто-определение горизонта (год/квартал/месяц/неделя) |
| Статусы | NEW / IN_PROGRESS / REVIEW / DONE / OVERDUE с авто-просрочкой |
| Дашборды | Recharts: распределение по статусам, отделам, выполнение по периодам, загрузка |
| Канбан | Drag-and-drop через @dnd-kit |
| Roadmap | Древовидный + Gantt-like вид только GOAL/EPIC для CEO |
| AI-помощник | 7 функций (см. ниже), LLM provider abstraction, rule-based fallback |
| Telegram-бот | Optional adapter через backend API, без прямого доступа к БД. Ссылка на бота - @TranstelematikaAIassistant_bot, для подключения введите в чат боту /link [код из приложения]
| RBAC | 3 роли (EMPLOYEE / LEAD / ADMIN) + scoping по отделу |

### AI-функции

1. **Дайджест недели** — `/api/ai/digest`
2. **Детектор рисков** — `/api/ai/risks`
3. **Анализ перегрузки + рекомендации** — `/api/ai/overload`
4. **Парсинг задачи из текста** — `/api/ai/parse-task`
5. **AI-матчинг исполнителя** — `/api/ai/suggest-assignee` (по навыкам + загрузке)
6. **Чат с контекстом задач** — `/api/ai/chat`
7. **Сводка по стратегической цели** — `/api/ai/goal-summary`

Все AI-функции имеют **rule-based fallback** — система работает даже без LLM. LLM не имеет прямого доступа к БД и не генерирует SQL: backend сам собирает разрешенный контекст задач с учетом RBAC.

### Архитектура AI-помощника

- **Backend tools**: операции чтения/изменения задач выполняются только backend-сервисами.
- **LLM provider abstraction**: `ollama`, `openai_compatible`, `docker_model`, `none`.
- **Rule-based fallback**: если модель недоступна или вернула невалидный JSON, ответ строится локальными правилами.
- **Telegram adapter**: отдельный bot service вызывает только HTTP API backend и передает `X-Telegram-Internal-Token`.
- **Безопасная память**: `telegram_sessions` хранит последние показанные задачи и pending action для подтверждений.
- **RBAC scope**: выборки задач проходят через общий `apply_task_scope`.

---

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│   Nginx (статика + reverse-proxy /api)              │
└────────────┬─────────────────────────┬──────────────┘
             │                         │
             ▼                         ▼
   ┌──────────────────┐      ┌──────────────────────┐
   │  React SPA       │      │  FastAPI Backend     │
   │  Vite + TS       │      │  - JWT Auth + RBAC   │
   │  Tailwind +      │      │  - Tasks + иерархия  │
   │  shadcn/ui       │      │  - Analytics         │
   │  TanStack Query  │      │  - AI orchestrator   │
   │  Recharts        │      │                      │
   └──────────────────┘      └──┬────────────────┬──┘
                                │                │
                                ▼                ▼
                       ┌──────────────┐  ┌─────────────────┐
                       │ PostgreSQL   │  │ Ollama          │
                       │ 16           │  │ gemma4:e4b      │
                       └──────────────┘  └─────────────────┘
```

Подробности — в `backend/README.md` и `frontend/README.md`.

---

## Быстрый старт

### Требования
- Docker Desktop / Docker Engine 24+ с включённым Compose v2
- ~3 ГБ свободного места на диске (без AI), +5 ГБ если поднимать локальную LLM
- 4+ ГБ RAM (8+ если с LLM)

### 1. Клонирование

```bash
git clone git@github.com:aoaoaooaoaoa3301/HackatoonMirea_Transtelematrica.git
cd HackatoonMirea_Transtelematrica
```

### 2. Запуск (без AI — быстро, ≈3-5 мин на первый build)

```bash
docker compose up -d
```

Что произойдёт автоматически:
1. Поднимется PostgreSQL и пройдёт healthcheck
2. Backend применит миграции и засеет 45 демо-задач + 20 пользователей
3. Frontend соберётся (nginx со статикой) и зашлёт `/api` на backend

После запуска (≈30 сек до полной готовности):
- **UI:** http://localhost
- **API:** http://localhost:8080/api
- **Swagger:** http://localhost:8080/docs

AI-функции работают на rule-based фоллбэках и возвращают осмысленные ответы на русском (детектор рисков, дайджест, парсинг задач, матчинг исполнителя).

### 3. Опционально — локальная LLM

```bash
docker compose --profile ai up -d
```

Дополнительно поднимется Ollama и `ollama-bootstrap` проверит/скачает `gemma4:e4b`. После этого AI-эндпоинты пойдут через локальную LLM.

Сменить модель:
```bash
OLLAMA_MODEL=gemma4:e4b docker compose --profile ai up -d
```

### 4. Опционально — OpenRouter/OpenAI-compatible API

```env
LLM_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=https://openrouter.ai/api/v1
OPENAI_COMPATIBLE_API_KEY=...
OPENAI_COMPATIBLE_MODEL=qwen/qwen-2.5-7b-instruct
```

```bash
docker compose up -d --build
```

Для vLLM можно использовать тот же режим, если vLLM поднят как OpenAI-compatible server.

### 5. Опционально — Telegram-бот

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_INTERNAL_TOKEN=replace-with-random-token
```

```bash
docker compose --profile telegram up -d --build bot
```

Как подключить Telegram:

1. Войти в веб-интерфейс.
2. Открыть страницу `Telegram`.
3. Нажать «Получить код подключения».
4. Отправить боту `/link CODE`.

После привязки бот понимает команды `/my`, `/week`, `/deadlines`, `/risks`, `/team`, `/overload` и свободный текст вроде «Что у меня горит на этой неделе?». Опасные действия, например комментарий или завершение задачи, требуют подтверждения inline-кнопкой.

### Демо-аккаунты

Все пароли: `password`

| Email | Роль | ФИО | Отдел |
|---|---|---|---|
| `admin@ttm.local` | ADMIN | Анна Смирнова | — |
| `lead.pmo@ttm.local` | LEAD | Иван Петров | Проектный офис |
| `lead.rnd@ttm.local` | LEAD | Сергей Кузнецов | НИОКР |
| `lead.tech@ttm.local` | LEAD | Михаил Воронов | Технический отдел |
| `lead.it@ttm.local` | LEAD | Дмитрий Орлов | ИТ-инфраструктура |
| `lead.prod@ttm.local` | LEAD | Виктор Зайцев | Производство |
| `lead.support@ttm.local` | LEAD | Ольга Иванова | Тех. поддержка |
| `lead.sales@ttm.local` | LEAD | Андрей Соколов | Отдел продаж |
| `lead.fin@ttm.local` | LEAD | Татьяна Зайцева | Финансы |
| `lead.hr@ttm.local` | LEAD | Мария Соколова | HR |
| `lead.mkt@ttm.local` | LEAD | Екатерина Белова | Маркетинг |
| `dmitry@ttm.local` | EMPLOYEE | Дмитрий Лебедев | ИТ — **перегружен 230%** |
| `pavel@ttm.local` | EMPLOYEE | Павел Соловьёв | НИОКР |
| `anna.hr@ttm.local` | EMPLOYEE | Анна Лебедева | HR |
| `elena@ttm.local` | EMPLOYEE | Елена Васильева | Тех. поддержка |
| ...ещё несколько | EMPLOYEE | | |

Полный список — в `backend/app/seed.py`.

---

## Конфигурация (опционально)

Все параметры имеют разумные дефолты. Если хочешь что-то переопределить — скопируй `.env.example` в `.env`:

```bash
cp .env.example .env
# отредактируй нужные значения
docker compose up -d
```

### Что чаще всего нужно поменять

**Порты заняты другим софтом:**
```bash
# .env
TTM_WEB_PORT=8000        # вместо 80 (если 80 занят другим nginx)
TTM_API_PORT=18000       # вместо 8080
TTM_DB_PORT=15433        # вместо 5433
```
Или одной строкой без `.env`:
```bash
TTM_WEB_PORT=8000 TTM_API_PORT=18000 docker compose up -d
```

**JWT secret для продакшна:**
```bash
JWT_SECRET=$(openssl rand -hex 32)
```

---

## Troubleshooting

### Проверяемые сценарии AI/Telegram/RBAC

1. **RBAC**: зайти под `dmitry@ttm.local`, открыть список задач и убедиться, что нет задач вне доступного отдела/исполнителя. Под `admin@ttm.local` видны все задачи.
2. **LLM fallback**: выставить `LLM_PROVIDER=none`, перезапустить backend и спросить в AI-чате про риски или загрузку. Ответ должен строиться rule-based логикой.
3. **OpenAI-compatible**: выставить `LLM_PROVIDER=openai_compatible` и `OPENAI_COMPATIBLE_API_KEY`, запустить backend без профиля `ai`. Backend не должен зависеть от Ollama.
4. **Telegram linking**: на странице `Telegram` получить код, отправить боту `/link CODE`, повторная отправка того же кода должна вернуть ошибку.
5. **Telegram assistant**: отправить `/deadlines`, затем «Добавь ко второй комментарий: жду согласование от отдела». Бот должен попросить подтверждение и после нажатия «Да» добавить комментарий.

### `Bind for 0.0.0.0:XXXX failed: port is already allocated`
У тебя что-то слушает порт 80/8080/5433. Проверь чем:
```bash
lsof -nP -iTCP:80 -sTCP:LISTEN
docker ps  # часто это другой docker-проект
```
Решения:
- Освободить порт (`docker stop other-container`)
- Или переопределить порты через `.env` (см. выше)

### `Cannot connect to the Docker daemon`
Docker Desktop не запущен. На macOS:
```bash
open -a Docker
# подожди 30 сек пока поднимется
```

### Дашборд показывает старые/чужие данные
Сброс БД с пересеяванием демо-данных:
```bash
docker compose down
docker volume rm hackatoonmirea_transtelematrica_db_data
docker compose up -d
```

### `npm ci` падает при сборке фронта
Если `package-lock.json` устарел относительно `package.json` — пересобери:
```bash
docker compose build --no-cache frontend
```

### Логи смотреть
```bash
docker compose logs -f backend    # бэкенд
docker compose logs -f frontend   # nginx + сборка
docker compose ps                 # статус контейнеров
```

### Полный сброс (всё с нуля)
```bash
docker compose down -v            # -v убивает volumes (БД, ollama)
docker compose up -d --build      # пересобирает образы
```

---

## Локальная разработка (без Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # отредактировать DATABASE_URL под локальный PG
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173, проксирует /api на :8000
```

---

## Суверенность решения

Это ключевое требование кейса. Что обеспечивает суверенность:

| Аспект | Реализация |
|---|---|
| Развёртывание | Полностью on-premise через `docker compose up`. Любой Linux-сервер с Docker. |
| Хранение данных | Только в локальной PostgreSQL. Никакой передачи во внешние сервисы. |
| AI | Локальная модель через **Ollama/Docker Model Runner** или optional OpenAI-compatible provider. |
| Telegram | Optional adapter. Бот не подключается к PostgreSQL и работает только через backend API. |
| Зависимости | **Только open-source**: PostgreSQL, FastAPI, React, Ollama, Nginx. |
| Платные SaaS | **Ноль обязательных**. Опционально можно подключить OpenRouter/OpenAI-compatible API через `LLMProvider`. |
| Доступ | JWT + RBAC, 3 роли с разграничением по отделам. |
| Аудит | Все изменения задач пишутся в `task_history` (immutable trail). |

### Что нужно для развёртывания в корпоративном контуре

1. Один сервер с Docker (рекомендуется 8+ ГБ RAM, желательно с GPU для ускорения LLM).
2. Открыть порт 80/443 для UI (через nginx или внешний reverse-proxy).
3. Сгенерировать рабочие секреты — `JWT_SECRET` минимум 32 символа.
4. Опционально: настроить TLS через Let's Encrypt / корпоративный CA.
5. Опционально: бэкап volume `db_data` (стандартный pg_dump).

При `LLM_PROVIDER=ollama` или `docker_model` корпоративные данные не уходят внешнему LLM-провайдеру. При `LLM_PROVIDER=openai_compatible` backend отправляет только подготовленный контекст задачи/сводки, а не прямой доступ к БД.

### Что можно дополнительно усилить под продакшн

- Заменить SQLite/SessionStorage JWT на refresh-token flow
- Добавить SSO через LDAP/Keycloak (модуль `python-ldap`)
- Подключить Sentry / Prometheus для мониторинга
- pgvector для RAG (заложена база, но эмбеддинги вне MVP)

---

## Структура репозитория

```
.
├── backend/                  FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/              Роутеры (auth, users, departments, tasks, analytics, ai)
│   │   ├── core/             Конфиг, БД, безопасность, depends
│   │   ├── models/           SQLAlchemy ORM
│   │   ├── schemas/          Pydantic v2
│   │   ├── services/         Логика (task, analytics, ai)
│   │   ├── main.py
│   │   └── seed.py
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 React + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── api/              Типизированные API-клиенты
│   │   ├── components/       UI + tasks + analytics + ai + layout
│   │   ├── pages/            9 страниц
│   │   ├── hooks/, lib/, store/, types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── bot/                      Telegram bot adapter (aiogram, HTTP-only backend access)
├── docker-compose.yml        Полная сборка одной командой
├── README.md                 Этот файл
└── .gitignore
```

---

## Соответствие критериям оценки

| Критерий | Вес | Где реализовано |
|---|---|---|
| Работоспособность прототипа | 20% | docker compose up — всё работает |
| Удобство и интуитивность интерфейса | 20% | shadcn/ui, тёмная тема, скелетоны, иконки, пустые состояния, RU-локализация |
| Качество дашбордов и аналитики | 20% | Recharts: pies, bars, lines, workload, completion, delegation-flow |
| Логика управления задачами по периодам | 15% | 4-уровневая иерархия с авто-каскадом прогресса, period_bucket, roadmap |
| AI-функции и польза подсказок | 15% | 7 AI-функций, локальная LLM + rule-based fallbacks |
| Развёртывание в корпоративном контуре | 10% | См. раздел «Суверенность» выше |

---

## Лицензия

Открытый код для образовательных целей. MIT-style.
