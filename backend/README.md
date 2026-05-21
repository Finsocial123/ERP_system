# Phase 1 ERP Backend - FastAPI

This backend includes:

- Multi-school registration
- JWT login/logout-ready auth
- Role-based access foundation
- School profile setup
- Academic sessions
- Departments
- Classes
- Sections
- Subjects
- Dashboard overview
- Tenant isolation using `school_id`

## Run locally

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
uvicorn app.main:app --reload
```

API docs:

```txt
http://127.0.0.1:8000/docs
```

## Database

For fastest testing, set this in `.env`:

```txt
DATABASE_URL=sqlite:///./erp_phase1.db
```

For PostgreSQL, run:

```bash
docker compose up -d
```

Then use:

```txt
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/school_erp_phase1
```

## Production note

This starter uses `Base.metadata.create_all()` for quick development. In production, replace it with Alembic migrations.
