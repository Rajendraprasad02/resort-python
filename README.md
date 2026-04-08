# Resort Booking Application API

## Setup Instructions

1. **Environment Setup**
```powershell
python -m venv venv
# For Windows PowerShell:
.\venv\Scripts\Activate.ps1
# For Windows Command Prompt:
venv\Scripts\activate
# For Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

2. **Database Configuration**
Modify `.env` to match your PostgreSQL instance. Make sure PostgreSQL is running.

3. **Database Migrations**
Run `alembic upgrade head` to apply migrations or `alembic revision --autogenerate -m "Initial"` to generate the initial migration.
*Note: Make sure your postgres DB named `resort_booking` exists.*

4. **Running the Application**
```bash
uvicorn app.main:app --reload
```

## Architecture
- **app/api**: FastAPI routes and endpoints mapping.
- **app/core**: Configuration, JWT settings, etc.
- **app/db**: Database setup and sessions.
- **app/models**: SQLAlchemy DB models.
- **app/schemas**: Pydantic models for validation and serialization.
- **app/services**: Business logic and database operations.

## Features Included:
- JWT Authentication (Admin & User roles with is_superuser).
- Properties & Rooms Management.
- Bookings System.
- Knowledge Base Article Storage (ready for AI workflows).
- Dashboard Endpoints.
