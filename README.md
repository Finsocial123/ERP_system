# School ERP / College ERP - Phase 1 Starter

This ZIP contains a working Phase 1 SaaS foundation:

## Backend: FastAPI

- School / college registration
- Owner admin creation
- JWT auth
- Current user API
- Role-based admin access
- School profile setup
- Academic sessions
- Departments
- Classes
- Sections
- Subjects
- Dashboard overview
- Tenant isolation using `school_id`

## Frontend: Next.js

- Register school page
- Login page
- Protected dashboard layout
- Sidebar admin panel
- School profile page
- CRUD screens for Phase 1 setup modules

## Start PostgreSQL

```bash
docker compose up -d
```

## Start backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Backend runs at:

```txt
http://127.0.0.1:8000
```

API docs:

```txt
http://127.0.0.1:8000/docs
```

## Start frontend

Open a new terminal:

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Frontend runs at:

```txt
http://localhost:3000
```

## First test flow

1. Open `http://localhost:3000`
2. Click register school
3. Create school/college and owner admin
4. Dashboard opens
5. Add academic session
6. Add department
7. Add class
8. Add section
9. Add subject
10. Update school profile

## Important production upgrades for next phase

- Add Alembic migrations instead of `create_all`
- Add refresh tokens
- Add audit logs
- Add student and teacher modules
- Add pagination and advanced filtering
- Add file upload storage
- Add CI/CD and testing
