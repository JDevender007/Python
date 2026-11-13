<div align="center">

# 🚀 REST API with FastAPI

### A complete REST API for task management built with FastAPI, featuring JWT authentication, SQLite database, and automatic OpenAPI documentation.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

REST API with FastAPI is a complete, production-ready REST API for task management built with modern Python technologies.

The API provides:
- **Full CRUD Operations**: Create, read, update, delete tasks and users
- **JWT Authentication**: Secure token-based authentication with access tokens
- **Role-Based Access Control**: Admin and regular user permissions
- **Automatic API Documentation**: Interactive Swagger UI and ReDoc
- **Data Validation**: Pydantic models for request/response validation
- **SQLite Database**: Lightweight, file-based database with SQLAlchemy ORM
- **Pagination & Filtering**: Efficient data retrieval for large datasets

---

# ✨ Features

## Authentication & Authorization
- **User Registration**: Secure password hashing with PBKDF2-SHA256
- **JWT Tokens**: Stateless authentication with configurable expiry
- **Role-Based Access**: Admin and regular user permissions
- **Protected Routes**: Dependency injection for auth checks

## Task Management
- **Full CRUD**: Create, read, update, delete tasks
- **Task Attributes**: Title, description, status, priority, due date
- **Status Tracking**: Pending, In Progress, Completed, Cancelled
- **Priority Levels**: Low, Medium, High, Urgent
- **Ownership**: Tasks belong to users with ownership enforcement

## Advanced Features
- **Pagination**: Efficient large dataset handling
- **Filtering**: Filter by status, priority, search terms
- **Sorting**: Automatic sorting by creation date
- **Statistics**: Task counts by status and priority
- **Special Queries**: Overdue tasks, upcoming tasks
- **Export Ready**: Structured JSON responses

---

# 🛠 Technologies Used

- **Python 3.13**
- **FastAPI** - Modern, fast web framework
- **SQLAlchemy 2.0** - SQL toolkit and ORM
- **Pydantic v2** - Data validation and serialization
- **SQLite** - Lightweight embedded database
- **JWT (python-jose)** - Token-based authentication
- **Passlib (PBKDF2-SHA256)** - Secure password hashing
- **Uvicorn** - ASGI server
- **Pytest** - Testing framework

---

# 📂 Project Structure

```text
05_REST_API_with_FastAPI/
│
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app & routes
│   ├── config.py            # Configuration settings
│   ├── database.py          # SQLAlchemy models & DB setup
│   ├── schemas.py           # Pydantic validation models
│   ├── auth.py              # JWT authentication
│   ├── crud.py              # Database operations
│
├── tests/
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_auth.py
│   └── test_crud.py
│
├── data/                    # SQLite database file
├── logs/                    # Application logs
├── README.md
├── requirements.txt
├── .gitignore
└── .env.example
```

---

# ⚙️ Environment Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Edit `.env` with your settings:

```env
SECRET_KEY=your-super-secret-key-change-in-production
DATABASE_URL=sqlite:///data/app.db
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

# ▶️ Run

Start the development server:

```bash
python -m src.main
```

Or with Uvicorn directly:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

# 🌐 API Endpoints

## Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login and get JWT token |
| GET | `/auth/me` | Get current user info |

## Users (Admin only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List all users (paginated) |
| GET | `/users/{id}` | Get user with task count |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user |

## Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Create new task |
| GET | `/tasks` | List tasks (paginated, filtered) |
| GET | `/tasks/stats` | Get task statistics |
| GET | `/tasks/overdue` | Get overdue tasks |
| GET | `/tasks/upcoming` | Get upcoming tasks |
| GET | `/tasks/{id}` | Get task details |
| PUT | `/tasks/{id}` | Update task |
| DELETE | `/tasks/{id}` | Delete task |

## Enums
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/enums/statuses` | Get task statuses |
| GET | `/enums/priorities` | Get task priorities |

## Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

---

# 📊 Request/Response Examples

## Register User
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "email": "john@example.com", "full_name": "John Doe", "password": "SecurePass123"}'
```

## Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john&password=SecurePass123"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

## Create Task (with auth)
```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"title": "Learn FastAPI", "description": "Build a REST API", "priority": "high", "due_date": "2024-12-31T23:59:59"}'
```

## List Tasks with Filters
```bash
curl -X GET "http://localhost:8000/tasks?status=pending&priority=high&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

# 🧪 Testing

Run tests with pytest:

```bash
pytest tests/ -v
```

Or run specific test modules:

```bash
pytest tests/test_schemas.py -v
pytest tests/test_auth.py -v
pytest tests/test_crud.py -v
```

**Test Coverage**: 43 tests passing covering schemas, auth, and CRUD operations.

---

# 📋 Requirements

```text
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
pydantic>=2.5.0
pydantic[email]>=2.5.0
python-jose[cryptography]>=3.3.0
passlib>=1.7.4
python-multipart>=0.0.6
python-dotenv>=1.0.0
httpx>=0.26.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

Install all requirements:

```bash
pip install -r requirements.txt
```

---

# 🎯 Learning Outcomes

- FastAPI application structure and best practices
- JWT authentication with access tokens
- SQLAlchemy 2.0 with async support
- Pydantic v2 data validation
- Dependency injection in FastAPI
- Role-based access control
- Pagination and filtering strategies
- Automatic OpenAPI documentation
- Testing with pytest and httpx
- Password hashing with PBKDF2-SHA256
- SQLite database management
- CORS middleware configuration

---

# 🔄 Application Workflow

```text
Client Request
      ↓
CORS Middleware
      ↓
Route Handler
      ↓
Dependency Injection (DB, Auth)
      ↓
CRUD Operations
      ↓
Pydantic Validation
      ↓
JSON Response
      ↓
Client
```

---

# 🚀 Future Improvements

- **Async Database**: Migrate to async SQLAlchemy with asyncpg
- **Redis Caching**: Cache frequent queries
- **WebSocket Support**: Real-time notifications
- **File Uploads**: Attach files to tasks
- **Email Notifications**: Task reminders and alerts
- **Rate Limiting**: API throttling
- **Audit Logging**: Track all changes
- **API Versioning**: Multiple API versions
- **Docker Support**: Containerized deployment
- **CI/CD Pipeline**: Automated testing and deployment

---

# ⚠️ Production Considerations

- **Change SECRET_KEY**: Use a strong, random secret key
- **Use PostgreSQL**: Replace SQLite for production
- **HTTPS Only**: Enforce TLS in production
- **Rate Limiting**: Implement API rate limits
- **Monitoring**: Add health checks and metrics
- **Backups**: Regular database backups
- **Secrets Management**: Use environment variables or vault

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python API Development Project

</div>