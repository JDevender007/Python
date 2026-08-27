"""
REST API with FastAPI - Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / "logs"
DATABASE_DIR = BASE_DIR / "data"
DATABASE_DIR.mkdir(exist_ok=True)

LOGS_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_DIR}/app.db")

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

API_TITLE = "Task Management API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
A complete REST API for task management built with FastAPI.

Features:
- CRUD operations for tasks and users
- JWT authentication
- Pagination and filtering
- Input validation with Pydantic
- Automatic OpenAPI documentation
- SQLite database with SQLAlchemy
"""

LOG_FILE = LOGS_DIR / "api.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

TASK_STATUSES = ["pending", "in_progress", "completed", "cancelled"]
TASK_PRIORITIES = ["low", "medium", "high", "urgent"]