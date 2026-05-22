# Отчет о найденных ошибках

Дата проверки: 2026-05-21  
Ветка: `правки-ИИ-ассистента`  
Фиксы не вносились, кроме создания этого отчета.

## Что проверялось

- Docker-сервисы: `db`, `backend`, `frontend`, `ollama`, `bot`.
- Frontend: production build, базовая навигация в UI, авторизация.
- Backend API: авторизация, задачи, дерево задач, пользователи, отделы, аналитика, AI endpoints, Telegram endpoints.
- AI-помощник: обычные вопросы, вопросы по задачам, режим доступности модели.
- Telegram bot: логи, обработчики команд, устойчивость к timeout.
- Статический анализ RBAC, обработки ошибок и контрактов frontend/backend.

## Команды и проверки

| Проверка | Результат |
|---|---|
| `docker compose ps` | Все основные контейнеры запущены, backend/db healthy |
| `npm.cmd run build` в `frontend` | Успешно, но есть warning по чанку `index` больше 500 kB |
| `npm.cmd run lint` в `frontend` | Ошибка: `eslint` не установлен |
| `docker compose exec -T backend python -m compileall app` | Успешно |
| `docker compose exec -T bot python -m compileall app` | Успешно |
| Browser smoke через `http://localhost` | Логин и базовая навигация работают, framework overlay не обнаружен |
| API smoke под admin/lead/employee | Авторизация и основные GET endpoints работают, но найдены проблемы RBAC |

## Найденные ошибки

### 1. Сотрудник и руководитель видят общую аналитику всей компании

**Серьезность:** высокая  
**Затронуто:** backend API, Dashboard, Analytics, Team, AI-контекст

Фактическое поведение:

- `dmitry@ttm.local` как `EMPLOYEE` видит только 7 задач через `/api/tasks`.
- Но тот же пользователь получает `analyticsTotal = 49` через `/api/analytics/overview`.
- Также получает 23 строки загрузки сотрудников через `/api/analytics/workload`.
- `lead.pmo@ttm.local` видит 6 задач через `/api/tasks`, но аналитика также показывает 49 задач.

Проблемные места:

- `backend/app/api/analytics.py:14-34` принимает `current_user`, но не передает его в сервис.
- `backend/app/services/analytics_service.py:17`, `97`, `134` используют `db.query(Task).all()`.
- `backend/app/services/analytics_service.py:82`, `135` используют всех активных пользователей.

Ожидаемое поведение:

- `ADMIN` видит всю компанию.
- `LEAD` видит аналитику своего отдела/подотделов.
- `EMPLOYEE` видит только разрешенный ему scope.

### 2. `/api/users` и `/api/departments` отдают весь справочник любому пользователю

**Серьезность:** высокая  
**Затронуто:** backend API, формы назначения, AI-контекст

Фактическое поведение:

- `EMPLOYEE` получает 23 пользователя через `/api/users`.
- `EMPLOYEE` получает 11 отделов через `/api/departments`.

Проблемные места:

- `backend/app/api/users.py:36-48` строит `db.query(User)` без ограничения по роли.
- `backend/app/api/departments.py:28-30` возвращает все отделы.
- `backend/app/services/assistant_agent.py:425-426` кладет все отделы и всех пользователей в контекст LLM.
- `backend/app/services/assistant_agent.py:493-496` read-tools `list_departments` и `list_users` тоже не scoped.

Ожидаемое поведение:

- Минимум: явно определить, какие роли могут видеть полный справочник.
- Если справочник нужен для назначения, сотруднику не стоит отдавать всю организационную структуру и всех пользователей без необходимости.

### 3. REST API удаления задач не соответствует требуемой RBAC-логике

**Серьезность:** высокая  
**Затронуто:** backend API, потенциально UI

Требование по проекту:

- Админ может удалять любые задачи.
- Руководитель может удалять задачи своего отдела.
- Сотрудник не может удалять задачи.

Фактическая логика в REST API:

- `backend/app/api/tasks.py:273-281`
- Удаление разрешено админу или создателю задачи.

Следствие:

- Сотрудник может удалить задачу, если он ее создал.
- Руководитель не сможет удалить задачу своего отдела, если он не ее создатель.
- AI-инструмент удаления реализует другую логику через `_can_delete_task`, поэтому REST API и AI-помощник расходятся.

### 4. AI-помощник неправильно отвечает о своей модели

**Серьезность:** высокая  
**Затронуто:** AI assistant

Текущая конфигурация окружения:

- `LLM_PROVIDER=openai_compatible`
- `OPENAI_COMPATIBLE_MODEL=openai/gpt-oss-120b:free`

Фактический ответ на вопрос `Какая ты модель?`:

> Я — AI‑ассистент, построенный на модели GPT‑4 от OpenAI...

Проблемные места:

- `backend/app/services/assistant_agent.py:135` системный промпт не заставляет модель использовать фактический `model.name`.
- `backend/app/services/assistant_agent.py:194-203` backend знает реальную модель, но это не закреплено как обязательный факт в ответе ассистента.

Ожидаемое поведение:

- Ассистент должен отвечать фактическим значением из backend model state: `openai/gpt-oss-120b:free`.
- Если модель не знает маркетинговое имя, нужно говорить технический id, а не выдумывать GPT-4.

### 5. Доступность AI-модели нестабильна и определяется по состоянию диалога, а не по реальному healthcheck

**Серьезность:** высокая  
**Затронуто:** AI assistant, UI-индикаторы, Telegram bot

Фактическое поведение при smoke-проверке:

- Admin: ответ normal, `available=true`.
- Lead: до сообщения conversation API показывал `available=false`, после вопроса модель ответила normal.
- Employee: на общий вопрос `Что ты умеешь?` ассистент ушел в degraded mode, хотя тот же provider только что отвечал admin/lead.

Проблемные места:

- `backend/app/services/assistant_agent.py:751-785` degraded mode выставляет `conversation.llm_status = "down"`.
- `backend/app/api/ai.py` возвращает `available` из `conversation.llm_status`, а не из фактического запроса к provider.
- `backend/app/services/llm/openai_compatible_provider.py` гасит исключения и возвращает `None`, поэтому причина деградации теряется для UI.

Ожидаемое поведение:

- Отдельный health/status для LLM provider.
- В conversation status не стоит хранить глобальную доступность модели.
- UI должен отличать "модель недоступна", "модель вернула невалидный JSON", "таймаут", "ошибка провайдера".

### 6. Telegram bot падает в обработчике при backend timeout

**Серьезность:** высокая  
**Затронуто:** Telegram bot

Фактическое поведение по логам `ttm-telegram-bot`:

- Есть `httpx.ReadTimeout`.
- Update помечается как `is not handled`.
- Пользователь может не получить нормальное сообщение об ошибке.

Проблемные места:

- `bot/app/backend_client.py:25` timeout на команду равен 60 секундам.
- `bot/app/handlers.py:80-81` `free_text` напрямую ожидает `client.command(...)` без `try/except`.
- Аналогично команды `/my`, `/week`, `/deadlines`, `/risks`, `/team`, `/overload` тоже не обрабатывают сетевые исключения.

Ожидаемое поведение:

- Любой timeout/backend error должен превращаться в понятный ответ пользователю.
- Длинные AI-запросы лучше сопровождать промежуточным сообщением и/или увеличенным backend timeout с graceful fallback.

### 7. В Telegram bot не зарегистрировано меню команд

**Серьезность:** средняя  
**Затронуто:** Telegram UX

Фактическое состояние:

- В `bot/app/main.py` создается `Bot`, подключается router и сразу запускается polling.
- `bot.set_my_commands(...)` не вызывается.

Проблемное место:

- `bot/app/main.py:16-19`

Следствие:

- В Telegram не появится нормальное меню команд у поля ввода.
- Пользователь должен знать команды вручную.

### 8. `/clear` есть в backend-логике, но отсутствует как явная Telegram-команда

**Серьезность:** средняя  
**Затронуто:** Telegram bot

Фактическое состояние:

- Backend распознает `/clear` в `backend/app/api/telegram.py`.
- В `bot/app/handlers.py` нет `@router.message(Command("clear"))`.
- Сейчас `/clear` может пройти через общий `free_text`, но команда не видна явно в help/menu и зависит от порядка router matching.

Ожидаемое поведение:

- Явный handler `/clear`.
- Команда должна быть в `/help` и в Telegram command menu.

### 9. Некорректные UUID в API дают 500 вместо 422/400

**Серьезность:** средняя  
**Затронуто:** backend API

Воспроизведение:

- `GET /api/tasks?parent_id=bad-id` возвращает `500 Internal Server Error`.
- `POST /api/ai/goal-summary` с `{ "goal_id": "bad-id" }` возвращает `500 Internal Server Error`.

Проблемные места:

- `backend/app/api/tasks.py:94` вызывает `uuid.UUID(parent_id)` без обработки `ValueError`.
- `backend/app/api/ai.py:166` вызывает `uuid.UUID(str(body.get("goal_id")))` без обработки `ValueError`.

Ожидаемое поведение:

- Возвращать `422 Unprocessable Entity` или `400 Bad Request` с понятным сообщением.

### 10. `npm run lint` не работает

**Серьезность:** средняя  
**Затронуто:** frontend developer workflow, CI readiness

Фактическое поведение:

```text
'eslint' is not recognized as an internal or external command
```

Проблемное место:

- `frontend/package.json:10` содержит script `lint`.
- В `frontend/package.json` нет `eslint` в `devDependencies`.

Ожидаемое поведение:

- Либо добавить eslint/config в зависимости, либо убрать/заменить неработающий script.

### 11. Kanban: drop в пустую колонку, вероятно, не работает

**Серьезность:** средняя  
**Затронуто:** Kanban drag-and-drop

Проблемное место:

- `frontend/src/components/tasks/KanbanBoard.tsx:137-144` ожидает, что `over.id` может быть id колонки.
- `frontend/src/components/tasks/KanbanBoard.tsx:198` добавляет `data-id={status}`, но не регистрирует droppable zone.
- В файле нет `useDroppable`.

Следствие:

- `COLUMNS.includes(overId as Status)` может не срабатывать для пустой колонки.
- Карточку нельзя надежно перетащить в пустой статус-столбец.

Ожидаемое поведение:

- Каждая колонка должна быть зарегистрирована как droppable area.

### 12. Повторное подтверждение AI action не защищено на уровне БД от гонки

**Серьезность:** средняя  
**Затронуто:** AI assistant write actions

Что уже есть:

- `_create_pending_action` переиспользует pending action с тем же idempotency key.
- `_execute_action` проверяет `action.status == "executed"`.

Проблема:

- В `assistant_pending_actions` есть только index по `idempotency_key`, но нет unique constraint.
- `confirm_action` не берет row-level lock перед выполнением.
- При двух параллельных подтверждениях оба запроса могут прочитать `status="pending"` и выполнить создание/изменение дважды.

Проблемные места:

- `backend/app/services/assistant_agent.py:716-736`
- `backend/app/models/assistant.py` индекс по `idempotency_key` не уникальный.
- `backend/app/services/assistant_agent.py:1023-1064` подтверждение не блокирует строку pending action.

Ожидаемое поведение:

- Атомарное выполнение pending action.
- Например, row lock или atomic update `pending -> executing/executed`.

### 13. Текущая база содержит поврежденные demo-данные пользователей

**Серьезность:** низкая/средняя  
**Затронуто:** UI, аналитика, Telegram/demo

Фактическое поведение:

- `/api/auth/me` для `admin@ttm.local` возвращает `full_name = "?????????????"`.
- В `/api/analytics/delegation-flow` есть пользователи с именами `"?????????????"`, `"????????????"`, `"?????????"`.
- В текущей базе 23 пользователя, хотя seed ожидает меньше demo-пользователей.

Вероятная причина:

- В базе остались созданные ранее тестовые/demo-аккаунты с поврежденной кодировкой.
- `backend/app/seed.py` idempotent и пропускает seed, если admin уже есть, поэтому не чинит поврежденные seeded rows.

Ожидаемое поведение:

- Демо-данные должны быть читаемыми.
- Seed/reset должен уметь приводить demo-окружение к ожидаемому состоянию или иметь отдельную команду reseed.

### 14. В API и frontend types по-прежнему используются технические enum-коды

**Серьезность:** низкая/средняя  
**Затронуто:** API contract, часть AI/интеграций

Фактическое состояние:

- API возвращает `NEW`, `IN_PROGRESS`, `HIGH`, `CRITICAL`, `EMPLOYEE`, `ADMIN`.
- Frontend типы в `frontend/src/types/index.ts` также описаны английскими enum-кодами.
- UI в большинстве мест мапит их в русские labels, но интеграции и raw API остаются англоязычными.

Если требование "поменять все статусы/приоритеты на русские слова" относится и к API, оно выполнено не полностью.

## Дополнительные замечания

- Production build frontend проходит, но Vite предупреждает о чанке `index` размером больше 500 kB. Это не функциональный баг, но риск для загрузки UI.
- README и код местами описывают разные дефолтные LLM-сценарии: в `docker-compose.yml` default provider `docker_model`, в текущем окружении используется `openai_compatible`, а фактическая модель в `.env` отличается от README-примеров.
- В проекте почти нет автоматических тестов на RBAC и AI actions. Большая часть найденных проблем могла бы ловиться API-тестами.

## Рекомендуемый порядок исправления

1. Закрыть RBAC-утечки в analytics/users/departments/AI context.
2. Привести REST delete task к требуемой матрице прав.
3. Исправить AI model identity и сделать отдельный health/status для LLM provider.
4. Добавить graceful error handling в Telegram bot.
5. Исправить 500 на невалидных UUID.
6. Починить lint script и добавить минимальные API-тесты на роли.
7. Проверить Kanban droppable зоны.
8. Очистить/пересеять demo-данные.
