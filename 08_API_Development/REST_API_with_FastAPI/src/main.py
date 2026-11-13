"""
REST API with FastAPI - Main Application Module
FastAPI application with all routes and configuration.
"""

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .config import (
    API_TITLE, API_VERSION, API_DESCRIPTION, CORS_ORIGINS,
    TASK_STATUSES, TASK_PRIORITIES
)
from .database import engine, Base, get_db, init_db, User
from .schemas import (
    UserCreate, UserUpdate, UserResponse, UserWithTasks,
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    TaskFilterParams, UserFilterParams, Token, MessageResponse,
    HealthResponse, PaginatedResponse
)
from .auth import (
    create_access_token, get_current_user, get_current_active_user,
    get_current_admin_user, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from .crud import (
    create_user, get_user, get_user_by_username, get_user_by_email,
    get_users, update_user, delete_user, get_user_with_task_count,
    create_task, get_task, get_tasks, update_task, delete_task,
    get_task_stats, get_overdue_tasks, get_upcoming_tasks
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        database=db_status,
    )


# Authentication endpoints
@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    return create_user(db, user)


@app.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token)


@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user info."""
    return current_user


# User endpoints
@app.get("/users", response_model=PaginatedResponse, tags=["Users"])
async def list_users(
    filters: UserFilterParams = Depends(),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all users (admin only)."""
    users, total = get_users(db, filters)
    total_pages = (total + filters.page_size - 1) // filters.page_size

    return PaginatedResponse(
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        total_pages=total_pages,
    )


@app.get("/users/{user_id}", response_model=UserWithTasks, tags=["Users"])
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user profile with task count."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user_data = get_user_with_task_count(db, user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    user = user_data["user"]
    response = UserWithTasks.model_validate(user)
    response.tasks_count = user_data["tasks_count"]
    return response


@app.put("/users/{user_id}", response_model=UserResponse, tags=["Users"])
async def update_user_profile(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user profile."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    updated_user = update_user(db, user_id, user_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user


@app.delete("/users/{user_id}", response_model=MessageResponse, tags=["Users"])
async def delete_user_account(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete user account (admin only)."""
    if not delete_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return MessageResponse(message="User deleted successfully")


# Task endpoints
@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
async def create_new_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new task."""
    return create_task(db, task, current_user.id)


@app.get("/tasks", response_model=TaskListResponse, tags=["Tasks"])
async def list_tasks(
    filters: TaskFilterParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List tasks with filtering and pagination."""
    tasks, total = get_tasks(db, filters, current_user.id)
    total_pages = (total + filters.page_size - 1) // filters.page_size

    return TaskListResponse(
        tasks=tasks,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        total_pages=total_pages,
    )


@app.get("/tasks/stats", tags=["Tasks"])
async def get_task_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get task statistics for current user."""
    return get_task_stats(db, current_user.id)


@app.get("/tasks/overdue", response_model=list[TaskResponse], tags=["Tasks"])
async def list_overdue_tasks(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get overdue tasks for current user."""
    return get_overdue_tasks(db, current_user.id)


@app.get("/tasks/upcoming", response_model=list[TaskResponse], tags=["Tasks"])
async def list_upcoming_tasks(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get upcoming tasks due within specified days."""
    return get_upcoming_tasks(db, current_user.id, days)


@app.get("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
async def get_task_details(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get task details."""
    task = get_task(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
async def update_task_details(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update task."""
    task = update_task(db, task_id, task_update, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}", response_model=MessageResponse, tags=["Tasks"])
async def delete_task_item(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete task."""
    if not delete_task(db, task_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    return MessageResponse(message="Task deleted successfully")


# Enum endpoints
@app.get("/enums/statuses", response_model=list[str], tags=["Enums"])
async def get_task_statuses():
    """Get available task statuses."""
    return TASK_STATUSES


@app.get("/enums/priorities", response_model=list[str], tags=["Enums"])
async def get_task_priorities():
    """Get available task priorities."""
    return TASK_PRIORITIES


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)