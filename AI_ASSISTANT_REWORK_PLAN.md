# План переделки ИИ-помощника в AI-first архитектуру

## Цель

ИИ-помощник должен быть ассистентом, который понимает свободный текст, ведет диалог, помнит контекст, сам выбирает инструменты и уточняет недостающие данные. Backend не должен подменять это поведение большим набором `if/else` и regex-правил.

Новая архитектура разделяет ответственность:

- LLM понимает намерение, строит следующий шаг и решает, нужен ли инструмент.
- Backend дает модели компактный контекст, исполняет read-tools, валидирует write-actions и защищает БД подтверждением.
- Fallback не имитирует ИИ: при недоступной модели включается честный ограниченный режим.

## Принятые решения

- Архитектура provider-agnostic: один runtime работает с OpenRouter, Ollama и Docker Model Runner.
- Все изменения БД выполняются только после подтверждения пользователя.
- При недоступной LLM доступны только простые read-only сценарии и отмена действий.
- После восстановления LLM помощник сообщает: "Вам помогает ИИ-помощник".
- Web и Telegram должны использовать один и тот же assistant runtime.
- История и рабочая память хранятся на backend, а не только в localStorage или TelegramSession.

## Новая архитектура

### Agent runtime

Основной runtime находится в `backend/app/services/assistant_agent.py`.

Pipeline сообщения:

1. Найти или создать conversation по пользователю, каналу и external chat id.
2. Сохранить сообщение пользователя.
3. Собрать context для модели:
   - профиль пользователя;
   - текущая дата;
   - отделы с алиасами;
   - активные пользователи;
   - статистика задач;
   - рабочая память;
   - последние сообщения;
   - релевантные задачи;
   - результаты уже вызванных инструментов.
4. Передать context в LLM через JSON protocol.
5. Если модель попросила read-tool, выполнить инструмент и повторно вызвать модель.
6. Если модель предложила write-action, backend валидирует payload и создает pending action.
7. Если данных не хватает, backend сохраняет active draft и просит указать только недостающие поля.
8. После подтверждения pending action выполняется идемпотентным executor.

### JSON protocol модели

Модель возвращает один из режимов:

```json
{
  "mode": "answer | tool_call | action_proposal | clarification",
  "message": "текст для пользователя",
  "tool_call": {
    "name": "search_tasks",
    "arguments": {}
  },
  "action": {
    "type": "create_task",
    "payload": {}
  },
  "memory_patch": {},
  "confidence": 0.0
}
```

Модель не пишет в БД напрямую. Любое изменение превращается в pending action с кнопками подтверждения.

### Read tools

- `search_tasks`
- `get_task_details`
- `list_departments`
- `list_users`
- `get_team_risks`
- `get_team_overload`
- `get_task_tree`
- `get_recent_context`

Read-tools можно выполнять без подтверждения.

### Write actions

- `create_task`
- `create_subtask`
- `update_task_assignment`
- `update_task_progress`
- `complete_task`
- `add_task_comment`

Write-actions всегда проходят валидацию, проверку прав и подтверждение.

## Серверная память

Добавлены таблицы:

- `assistant_conversations`
- `assistant_messages`
- `assistant_pending_actions`

Рабочая память conversation хранит:

- последние показанные задачи;
- активную задачу;
- активный черновик действия;
- статус LLM;
- флаг уведомления о восстановлении LLM.

Это позволяет web и Telegram работать через одну модель поведения.

## Degraded mode

Если LLM недоступна или вернула невалидный JSON:

- conversation получает `llm_status = down`;
- включается ограниченный режим;
- пользователь получает честное сообщение о недоступности модели;
- сложные write-команды не выполняются через regex;
- доступны только простые сценарии:
  - "мои задачи";
  - "риски";
  - "дедлайны";
  - "загрузка";
  - "отмена".

Когда LLM снова отвечает, runtime добавляет к первому ответу уведомление:

> Вам помогает ИИ-помощник. Ранее был включён ограниченный режим из-за недоступности модели.

## API

Новые endpoints:

- `GET /api/ai/assistant/conversation`
- `POST /api/ai/assistant/message`
- `POST /api/ai/assistant/actions/{action_id}/confirm`
- `POST /api/ai/assistant/actions/{action_id}/cancel`

Старый endpoint `/api/ai/chat` оставлен для совместимости, но внутри направляет запросы в новый assistant runtime.

Telegram endpoints также используют новый runtime:

- `/api/telegram/command`
- `/api/telegram/confirm-action`

## Frontend

Web-чат использует серверную conversation-память:

- localStorage хранит только `conversation_id`;
- сообщения загружаются из backend;
- ответы помощника могут содержать кнопки подтверждения;
- подтверждение и отмена вызывают новые assistant action endpoints.

## Дальнейшие улучшения

Текущая реализация закладывает AI-first runtime. Следующие полезные шаги:

1. Добавить интеграционные тесты с fake LLM.
2. Добавить отдельный health-check LLM provider.
3. Сократить и затем удалить legacy `assistant_orchestrator.py`.
4. Очистить дубли helper-функций в `assistant_tools.py`.
5. Улучшить retrieval задач: добавить нормализацию слов, ранжирование по отделам, исполнителям и parent-chain.
6. Добавить UI-индикатор normal/degraded mode.
7. Добавить аудит tool calls и action proposals в интерфейсе администратора.

## Acceptance criteria

- Новые формулировки не требуют добавления нового `if` в backend.
- В нормальном режиме намерение определяет LLM.
- Backend не создает задачи без подтверждения пользователя.
- Повторное нажатие confirm не создает дублей.
- Помощник помнит контекст между сообщениями в web и Telegram.
- При недоступной LLM помощник честно сообщает об ограниченном режиме.
- После восстановления LLM помощник сообщает, что снова работает ИИ-помощник.
