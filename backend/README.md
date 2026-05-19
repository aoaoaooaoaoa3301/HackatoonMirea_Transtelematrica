# Транстелематика - Task Management Backend

FastAPI backend for the task management system.

## Quick Start (Docker Compose)

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars (copy and edit)
cp .env.example .env

# Run migrations
alembic upgrade head

# Seed demo data
python -m app.seed

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://ttm:ttm@db:5432/ttm` | PostgreSQL connection string |
| `JWT_SECRET` | `change-me-in-prod-32-chars-minimum` | Secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | `1440` | Token expiry (24h) |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `qwen2.5:7b` | LLM model name |
| `OLLAMA_TIMEOUT` | `30` | Ollama request timeout (seconds) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins (comma-separated) |

## API Routes

All routes are under `/api` prefix. Authentication via Bearer JWT token.

### Auth
- `POST /api/auth/login` - Login with email/password
- `GET /api/auth/me` - Current user info

### Users
- `GET /api/users` - List users (filter by department_id, role, q)
- `POST /api/users` - Create user (ADMIN)
- `GET /api/users/{id}` - User detail with workload
- `PATCH /api/users/{id}` - Update user
- `GET /api/users/{id}/workload` - Workload metrics

### Departments
- `GET /api/departments` - List departments
- `POST /api/departments` - Create (ADMIN)
- `GET /api/departments/{id}` - Detail with members
- `PATCH /api/departments/{id}` - Update (ADMIN/LEAD)
- `DELETE /api/departments/{id}` - Delete (ADMIN)

### Tasks
- `GET /api/tasks` - List tasks (many filters)
- `POST /api/tasks` - Create task
- `GET /api/tasks/{id}` - Detail with children, parent chain, comments, history
- `PATCH /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task (cascade)
- `POST /api/tasks/{id}/comments` - Add comment
- `GET /api/tasks/tree` - Task tree (root_id optional)

### Analytics
- `GET /api/analytics/overview` - Dashboard overview
- `GET /api/analytics/workload` - All users workload
- `GET /api/analytics/completion` - Completion buckets by period
- `GET /api/analytics/delegation-flow` - Sankey diagram data

### AI Assistant
- `POST /api/ai/digest` - Task digest (LLM + fallback)
- `POST /api/ai/risks` - Risk analysis
- `POST /api/ai/overload` - Overload detection
- `POST /api/ai/parse-task` - Parse natural language to task
- `POST /api/ai/suggest-assignee` - Suggest assignees
- `POST /api/ai/chat` - Chat with AI assistant
- `POST /api/ai/goal-summary` - Goal progress summary

### Other
- `GET /health` - Health check
- `GET /` - Redirect to Swagger docs

## Default Credentials

| Email | Password | Role |
|---|---|---|
| `admin@ttm.local` | `password` | ADMIN |
| `lead.talents@ttm.local` | `password` | LEAD |
| `lead.hr@ttm.local` | `password` | LEAD |
| `lead.aho@ttm.local` | `password` | LEAD |
| `lead.it@ttm.local` | `password` | LEAD |
| `lead.fin@ttm.local` | `password` | LEAD |
| `alex@ttm.local` | `password` | EMPLOYEE |
| `anna.hr@ttm.local` | `password` | EMPLOYEE |
| `dmitry@ttm.local` | `password` | EMPLOYEE |
| `elena@ttm.local` | `password` | EMPLOYEE |
| `pavel@ttm.local` | `password` | EMPLOYEE |
