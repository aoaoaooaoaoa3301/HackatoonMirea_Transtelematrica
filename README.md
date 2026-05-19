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
| AI-помощник | 7 функций (см. ниже), локально через Ollama |
| RBAC | 3 роли (EMPLOYEE / LEAD / ADMIN) + scoping по отделу |

### AI-функции

1. **Дайджест недели** — `/api/ai/digest`
2. **Детектор рисков** — `/api/ai/risks`
3. **Анализ перегрузки + рекомендации** — `/api/ai/overload`
4. **Парсинг задачи из текста** — `/api/ai/parse-task`
5. **AI-матчинг исполнителя** — `/api/ai/suggest-assignee` (по навыкам + загрузке)
6. **Чат с контекстом задач** — `/api/ai/chat`
7. **Сводка по стратегической цели** — `/api/ai/goal-summary`

Все AI-функции имеют **rule-based fallback** — система работает даже без LLM.

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
                       │ 16           │  │ qwen2.5:7b      │
                       └──────────────┘  └─────────────────┘
```

Подробности — в `backend/README.md` и `frontend/README.md`.

---

## Быстрый старт

### Требования
- Docker + Docker Compose
- ~10 ГБ свободного места (модель Ollama ~5 ГБ)

### Запуск

```bash
docker compose up -d
```

При первом запуске:
1. Поднимется PostgreSQL
2. Поднимется Ollama, и сервис `ollama-bootstrap` подтянет модель `qwen2.5:7b` (5–10 минут на хорошем интернете)
3. Backend применит миграции и засеет демо-данные
4. Frontend соберётся в nginx

После запуска:
- **UI:** http://localhost
- **API:** http://localhost:8000/api
- **Swagger:** http://localhost:8000/docs

### Демо-аккаунты

Все пароли: `password`

| Email | Роль | Отдел |
|---|---|---|
| `admin@ttm.local` | ADMIN | — |
| `lead.talents@ttm.local` | LEAD | Молодые таланты |
| `lead.hr@ttm.local` | LEAD | HR |
| `lead.aho@ttm.local` | LEAD | АХО |
| `lead.it@ttm.local` | LEAD | ИТ |
| `lead.fin@ttm.local` | LEAD | Финансы |
| `alex@ttm.local` | EMPLOYEE | АХО |
| `anna.hr@ttm.local` | EMPLOYEE | HR |
| `dmitry@ttm.local` | EMPLOYEE | ИТ |
| `elena@ttm.local` | EMPLOYEE | Финансы |
| `pavel@ttm.local` | EMPLOYEE | Молодые таланты |

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
| AI | Локальная модель через **Ollama** (qwen2.5:7b или любая другая). Работает offline. |
| Зависимости | **Только open-source**: PostgreSQL, FastAPI, React, Ollama, Nginx. |
| Платные SaaS | **Ноль обязательных**. Опционально можно подключить YandexGPT/GigaChat через тот же интерфейс `LLMProvider`. |
| Доступ | JWT + RBAC, 3 роли с разграничением по отделам. |
| Аудит | Все изменения задач пишутся в `task_history` (immutable trail). |

### Что нужно для развёртывания в корпоративном контуре

1. Один сервер с Docker (рекомендуется 8+ ГБ RAM, желательно с GPU для ускорения LLM).
2. Открыть порт 80/443 для UI (через nginx или внешний reverse-proxy).
3. Сгенерировать рабочие секреты — `JWT_SECRET` минимум 32 символа.
4. Опционально: настроить TLS через Let's Encrypt / корпоративный CA.
5. Опционально: бэкап volume `db_data` (стандартный pg_dump).

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
