# Транстелематика - Фронтенд

Система управления задачами с AI-помощником.

## Стек

- React 18 + TypeScript 5
- Vite 5
- Tailwind CSS 3 + shadcn/ui
- TanStack Query v5
- React Router v6
- React Hook Form + Zod
- Recharts
- @dnd-kit (Kanban)
- Zustand (auth)

## Быстрый старт

```bash
npm install
npm run dev       # http://localhost:3000
```

## Docker

```bash
docker build -t ttm-frontend .
docker run -p 80:80 ttm-frontend
```

## Маршруты

| Путь | Страница |
|------|----------|
| `/login` | Авторизация |
| `/` | Дашборд |
| `/tasks` | Список задач |
| `/tasks/:id` | Детали задачи |
| `/kanban` | Канбан-доска |
| `/roadmap` | Стратегический Roadmap |
| `/analytics` | Аналитика |
| `/team` | Команда |
| `/ai` | AI-помощник |

## Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `VITE_API_BASE` | `/api` | Базовый URL API |
