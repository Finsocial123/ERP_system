# School / College ERP System

A full-stack multi-school ERP / School Management System built with a **FastAPI backend** and a **Next.js frontend**. The project supports institution registration, role-based login, school-code based tenant isolation, academic setup, student/teacher/parent workflows, attendance, homework, fees, timetable, exams, communication, reports, and library-related features.

---

## 1. Tech Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT authentication
- Pydantic / Pydantic Settings
- Uvicorn

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Lucide React icons

### Database

- PostgreSQL is recommended for this project.
- The backend uses both sync and async database URLs, so both `DATABASE_URL` and `ASYNC_DATABASE_URL` are required.

---

## 2. Main Features Included

### SaaS / Multi-School Foundation

- School / college registration
- School code generation or custom school code
- Owner admin creation during school registration
- JWT login system
- Role-based dashboard routing
- School profile management
- Tenant isolation using `school_id`

### Academic Setup

- Academic sessions
- Departments
- Classes
- Sections
- Subjects

### User Management

- Student create, edit, suspend, activate, delete
- Teacher create, edit, suspend, activate, delete
- Parent / guardian details
- Parent login creation from student guardian details
- Teacher subject assignment
- Class teacher assignment

### Dashboard

- Role-based dashboard pages
- Admin dashboard
- Teacher dashboard
- Student dashboard
- Parent dashboard
- Quick search and overview APIs

### Attendance

- Attendance marking
- Attendance sheet
- Date-wise and class-wise attendance views
- Student attendance view
- Attendance summary

### Homework / Assignment

- Teacher/admin homework creation
- Class, section, and subject-based homework
- Student homework view
- Student submission
- Teacher checking workflow
- Parent read-only homework view

### Fee Management

- Fee dashboard
- Fee categories
- Fee structures
- Fee assignments
- Student fee records
- Manual payment entry
- Receipt endpoint
- Daily collection report
- Expense entry
- Razorpay placeholders are present, but manual fee entry should be treated as the main local workflow.

### Timetable

- Period setup
- Day setup
- Timetable entries
- Class timetable view
- Teacher timetable view
- Student timetable view
- Parent child timetable view

### Exam and Result Management

- Exam creation
- Exam subjects
- Exam timetable
- Auto-schedule exam timetable endpoint
- Marks entry
- Result publishing
- Student report cards
- Parent child report cards
- Class-wise and subject-wise result APIs

### Communication and Support

- Notice board
- Circulars
- Announcements
- Event calendar
- Support tickets
- Complaint system
- In-app notifications

### Reports

- Overview report
- Student report
- Attendance report
- Teacher report
- Homework report
- Fee report

### Library

- Books
- Categories
- Issue book
- Return book
- Fine payment
- Overdue issues
- Student/user issue view
- Library stats

### AI / Curriculum

- Curriculum generation endpoint
- Curriculum approval endpoint

---

## 3. Folder Structure

```txt
ERP_system-main/
├── backend/
│   ├── app/
│   │   ├── core/              # Config, database, migrations, security helpers
│   │   ├── dependencies/      # Auth dependencies and role guards
│   │   ├── models/            # SQLAlchemy database models
│   │   ├── routes/            # FastAPI route modules
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business/service logic
│   │   ├── utils/             # Email, cloudinary, language helpers
│   │   └── main.py            # FastAPI application entry point
│   └── requirements.txt
│
├── frontend/
│   ├── app/                   # Next.js app routes/pages
│   ├── components/            # Shared UI and module components
│   ├── lib/                   # API client and auth helpers
│   ├── types/                 # Shared TypeScript types
│   ├── package.json
│   └── .env.local.example
│
└── README.md
```

---

## 4. Prerequisites

Install these before running the project:

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- npm
- Git, optional but recommended

---

## 5. Backend Setup

Open a terminal in the project root.

```bash
cd backend
```

Create and activate a virtual environment.

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies.

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### If `requirements.txt` gives an encoding error

In the uploaded zip, `backend/requirements.txt` may be saved as UTF-16. If `pip install -r requirements.txt` fails because of encoding, convert it to UTF-8 once:

```bash
python -c "from pathlib import Path; p=Path('requirements.txt'); p.write_text(p.read_text(encoding='utf-16'), encoding='utf-8')"
pip install -r requirements.txt
```

---

## 6. PostgreSQL Database Setup

Create a PostgreSQL database. Example database name:

```txt
school_erp
```

Using pgAdmin:

1. Open pgAdmin.
2. Create a new database named `school_erp`.
3. Keep username/password as per your local PostgreSQL setup.
4. Use those details in the backend `.env` file.

---

## 7. Backend Environment File

Create a file named `.env` inside the `backend/` folder.

```txt
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/school_erp
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/school_erp

SECRET_KEY=change-this-secret-key-before-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Optional AI settings
OPENROUTER_API_KEY=
MODEL=anthropic/claude-sonnet-4.6
TRANSCRIPTION_MODEL=openai/whisper-large-v3
EMBEDDING_MODEL=openai/text-embedding-3-small
TAVILY_API_KEY=

# Optional Cloudinary settings
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

# Optional Google auth / email settings
GOOGLE_CLIENT_ID=
OTP_EXPIRE_MINUTES=10
OTP_MAX_ATTEMPTS=5
EMAIL_OTP_DEBUG=True
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=School ERP
SMTP_USE_TLS=True

# Optional Razorpay settings
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
```

Important: do not commit real API keys, SMTP passwords, Razorpay keys, or Cloudinary secrets to GitHub.

---

## 8. Run Backend

From the `backend/` folder:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL:

```txt
http://127.0.0.1:8000
```

API documentation:

```txt
http://127.0.0.1:8000/docs
```

Health check:

```txt
http://127.0.0.1:8000/health
```

---

## 9. Frontend Setup

Open a second terminal from the project root.

```bash
cd frontend
npm install
```

Create `.env.local` from the example file.

### Windows

```bash
copy .env.local.example .env.local
```

### macOS / Linux

```bash
cp .env.local.example .env.local
```

Make sure `.env.local` contains:

```txt
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Run the frontend:

```bash
npm run dev
```

Frontend URL:

```txt
http://localhost:3000
```

---

## 10. Demo School and Login Credentials

Use the same school code for every user of one institution.

### Recommended Demo School

```txt
School Name: Demo Public School
School Code: DEMO001
Admin Email: admin@gmail.com
Admin Password: 123456
```

When registering the school, enter `DEMO001` as the school code. After registration, use `DEMO001` for admin, teacher, student, and parent login.

### Demo Login Table

| Role | Portal Tab | School Code | Email / Login ID | Password | Notes |
|---|---|---:|---|---|---|
| Admin / Owner | Admin | DEMO001 | admin@gmail.com | 123456 | Created during school registration |
| Teacher | Teacher | DEMO001 | teacher1@gmail.com or TCH001 | 123456 | Create from Admin → Teachers with login enabled |
| Student | Student | DEMO001 | student1@gmail.com or STU001 | 123456 | Create from Admin → Students with login enabled |
| Parent | Parent | DEMO001 | parent1@gmail.com | 123456 | Create from student guardian details with parent login enabled |

### Important Login Notes

- The login page requires three things: school code, login ID/email, and password.
- The selected portal tab must match the account role.
- Admin users are created during school registration.
- Teacher, student, and parent users are created by the admin.
- Teacher/student/parent users may be redirected to the change-password page on first login because the backend sets `must_change_password=True` for those generated accounts.
- For demo testing, you can enter current password `123456` and set the new password as `123456` again, or choose a new password.

---

## 11. How to Create Demo Users

### Step 1: Register School / Admin

Open:

```txt
http://localhost:3000/register-school
```

Use:

```txt
School Name: Demo Public School
School Code: DEMO001
Owner Name: Admin User
Owner Email: admin@gmail.com
Owner Password: 123456
```

After registration, the admin account is ready.

### Step 2: Login as Admin

Open:

```txt
http://localhost:3000/login
```

Use:

```txt
Portal Tab: Admin
School Code: DEMO001
Login ID / Email: admin@gmail.com
Password: 123456
```

### Step 3: Create Teacher Login

Go to the Teachers module and create a teacher using:

```txt
Employee ID: TCH001
Teacher Name: Teacher One
Teacher Email: teacher1@gmail.com
Create Login: Yes
Password: 123456
```

Teacher can login with either:

```txt
teacher1@gmail.com
```

or:

```txt
TCH001
```

### Step 4: Create Student and Parent Login

Go to the Students module and create a student using:

```txt
Admission No: STU001
Student Name: Student One
Student Email: student1@gmail.com
Create Student Login: Yes
Student Password: 123456
```

Add guardian details:

```txt
Guardian Name: Parent One
Guardian Email: parent1@gmail.com
Create Parent Login: Yes
Parent Password: 123456
```

Student can login with either:

```txt
student1@gmail.com
```

or:

```txt
STU001
```

Parent can login with:

```txt
parent1@gmail.com
```

---

## 12. Role-Based User Flow

### Admin

Admin can manage the institution setup and most ERP modules:

- School profile
- Academic sessions
- Departments
- Classes
- Sections
- Subjects
- Students
- Teachers
- Attendance
- Homework
- Fees
- Timetable
- Exams
- Communication
- Reports
- Library

### Teacher

Teacher can access teacher-specific workflows:

- Teacher dashboard
- Assigned classes/subjects
- Homework management
- Attendance-related views
- Timetable
- Exams-related workflow
- Notices/communication where allowed

### Student

Student can access student-specific workflows:

- Student dashboard
- Homework view and submission
- Attendance view
- Fee portal/view
- Timetable
- Exam timetable
- Report cards
- Notices

### Parent

Parent can access child-related views:

- Parent dashboard
- Child homework
- Child timetable
- Child exam timetable
- Child report cards
- Child notices/communication where available

---

## 13. Important Backend API Groups

| Module | Main Prefix / Routes |
|---|---|
| Auth | `/auth/register-school`, `/auth/login`, `/auth/me`, `/auth/change-password` |
| School Profile | `/schools/me` |
| Academic Setup | `/academic-sessions`, `/departments`, `/classes`, `/sections`, `/subjects` |
| Students | `/students` |
| Teachers | `/teachers` |
| Dashboard | `/dashboard/overview`, `/dashboard/quick-search` |
| Attendance | `/attendance/*` |
| Homework | `/homework/*` |
| Fees | `/fees/*` |
| Timetable | `/timetable/*` |
| Exams | `/exams/*` |
| Notices | `/notices/*` |
| Communication | `/communication/*` |
| Reports | `/reports/*` |
| Library | `/library/*` |
| Curriculum | `/curriculum/*` |

For the full and updated API list, always check:

```txt
http://127.0.0.1:8000/docs
```

---

## 14. Important Frontend Pages

| Page | URL |
|---|---|
| Home | `/` |
| Register School | `/register-school` |
| Login | `/login` |
| Admin Dashboard | `/dashboard` |
| Teacher Dashboard | `/teacher-dashboard` |
| Student Dashboard | `/student-dashboard` |
| Parent Dashboard | `/parent-dashboard` |
| Students | `/students` |
| Teachers | `/teachers` |
| Attendance | `/attendance` |
| Homework | `/homework` |
| Student Homework | `/student-homework` |
| Parent Homework | `/parent-homework` |
| Timetable | `/timetable` |
| Student Timetable | `/student-timetable` |
| Parent Timetable | `/parent-timetable` |
| Exams | `/exams` |
| Student Exams | `/student-exams` |
| Parent Exams | `/parent-exams` |
| Fees | `/fees` |
| Communication | `/communication` |
| Reports | `/reports` |
| Library | `/library` |
| School Settings | `/settings/school` |

---

## 15. Database and Migration Notes

The backend currently creates tables automatically with:

```python
Base.metadata.create_all(bind=engine)
```

It also runs startup migration helpers from `app/core/migrations.py`.

This is useful for local development, but for production you should replace this with proper Alembic migrations.

Recommended production upgrade:

```bash
alembic init alembic
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## 16. File Upload Notes

The backend creates an upload folder automatically:

```txt
backend/uploads/
```

Uploaded files are served from:

```txt
http://127.0.0.1:8000/uploads/...
```

For production, use a proper storage service such as S3, Cloudinary, or another managed object storage provider.

---

## 17. Troubleshooting

### 1. Backend does not start because of database error

Check:

- PostgreSQL is running.
- Database `school_erp` exists.
- `DATABASE_URL` is correct.
- `ASYNC_DATABASE_URL` is correct.
- Username/password are correct.

### 2. Frontend cannot call backend

Check frontend `.env.local`:

```txt
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Check backend `.env`:

```txt
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Restart both frontend and backend after changing environment files.

### 3. Login says invalid school code, login ID, or password

Check:

- Correct school code is entered.
- Correct portal tab is selected.
- Correct email/login ID is entered.
- Password is correct.
- User account is active.

### 4. Login says wrong portal tab or role

The backend validates the selected portal tab. For example:

- Admin accounts must use the Admin tab.
- Teacher accounts must use the Teacher tab.
- Student accounts must use the Student tab.
- Parent accounts must use the Parent tab.

### 5. Teacher/student/parent goes to change-password page

This is expected for generated accounts. Use the temporary password as the current password and set a new password.

### 6. Parent dashboard does not show child data

Check:

- Student has guardian details.
- Parent login was created from the student guardian details.
- Parent email/phone matches the guardian record.
- Parent is logging into the correct school code.

---

## 18. Security Notes Before Production

Before deploying this ERP system publicly:

- Replace `SECRET_KEY` with a strong random value.
- Remove all hardcoded secrets from source code.
- Keep API keys only in `.env` or a secure secret manager.
- Rotate any exposed API keys/passwords.
- Use HTTPS.
- Add refresh tokens.
- Add proper audit logs.
- Add rate limiting for login and OTP APIs.
- Add Alembic migrations.
- Add automated tests.
- Add database backups.
- Add proper error monitoring.
- Use production-grade file storage.
- Do not use demo password `123456` in production.

---

## 19. Suggested Demo Order

For best presentation/demo flow:

1. Register a school with code `DEMO001`.
2. Login as admin.
3. Create academic session.
4. Create department.
5. Create class and section.
6. Create subjects.
7. Create teacher login.
8. Create student login and parent login.
9. Add attendance.
10. Add homework.
11. Add fee category, fee structure, and payment.
12. Add timetable periods, days, and entries.
13. Create exam, add subjects, add timetable, enter marks, publish result.
14. Check student and parent dashboards.
15. Add notices, circulars, announcements, events, tickets, and complaints.
16. Open reports.

---

## 20. Default Local URLs

```txt
Frontend: http://localhost:3000
Backend:  http://127.0.0.1:8000
API Docs: http://127.0.0.1:8000/docs
Health:   http://127.0.0.1:8000/health
```

---

## 21. Demo Credentials Summary

Use this for quick testing after creating the demo school and demo users:

```txt
School Code: DEMO001

Admin:
Email/Login ID: admin@gmail.com
Password: 123456

Teacher:
Email/Login ID: teacher1@gmail.com
Alternative Login ID: TCH001
Password: 123456

Student:
Email/Login ID: student1@gmail.com
Alternative Login ID: STU001
Password: 123456

Parent:
Email/Login ID: parent1@gmail.com
Password: 123456
```
