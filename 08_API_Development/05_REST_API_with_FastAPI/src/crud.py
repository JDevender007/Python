"""
REST API with FastAPI - CRUD Module
Database operations for users and tasks.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from .database import User, Task, TaskStatus, TaskPriority
from .schemas import UserCreate, UserUpdate, TaskCreate, TaskUpdate, TaskFilterParams, UserFilterParams
from .auth import get_password_hash


# User CRUD operations
def create_user(db: Session, user: UserCreate) -> User:
    """Create a new user."""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, filters: UserFilterParams) -> tuple[List[User], int]:
    """Get users with filtering and pagination."""
    query = db.query(User)

    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term),
                User.full_name.ilike(search_term),
            )
        )

    if filters.is_active is not None:
        query = query.filter(User.is_active == filters.is_active)

    if filters.is_admin is not None:
        query = query.filter(User.is_admin == filters.is_admin)

    total = query.count()
    users = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size).all()
    return users, total


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    """Update user."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete user."""
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    db.delete(db_user)
    db.commit()
    return True


def get_user_with_task_count(db: Session, user_id: int) -> Optional[dict]:
    """Get user with task count."""
    user = get_user(db, user_id)
    if not user:
        return None
    task_count = db.query(Task).filter(Task.owner_id == user_id).count()
    return {
        "user": user,
        "tasks_count": task_count,
    }


# Task CRUD operations
def create_task(db: Session, task: TaskCreate, owner_id: int) -> Task:
    """Create a new task."""
    db_task = Task(
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        owner_id=owner_id,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_task(db: Session, task_id: int, owner_id: Optional[int] = None) -> Optional[Task]:
    """Get task by ID, optionally filtered by owner."""
    query = db.query(Task).filter(Task.id == task_id)
    if owner_id is not None:
        query = query.filter(Task.owner_id == owner_id)
    return query.first()


def get_tasks(db: Session, filters: TaskFilterParams, owner_id: Optional[int] = None) -> tuple[List[Task], int]:
    """Get tasks with filtering and pagination."""
    query = db.query(Task)

    if owner_id is not None:
        query = query.filter(Task.owner_id == owner_id)

    if filters.status:
        query = query.filter(Task.status == filters.status)

    if filters.priority:
        query = query.filter(Task.priority == filters.priority)

    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_term),
                Task.description.ilike(search_term),
            )
        )

    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset(
        (filters.page - 1) * filters.page_size
    ).limit(filters.page_size).all()
    return tasks, total


def update_task(db: Session, task_id: int, task_update: TaskUpdate, owner_id: Optional[int] = None) -> Optional[Task]:
    """Update task."""
    db_task = get_task(db, task_id, owner_id)
    if not db_task:
        return None

    update_data = task_update.model_dump(exclude_unset=True)

    # Handle status change to completed
    if "status" in update_data and update_data["status"] == TaskStatus.COMPLETED:
        if db_task.status != TaskStatus.COMPLETED:
            db_task.completed_at = datetime.utcnow()
    elif "status" in update_data and db_task.status == TaskStatus.COMPLETED:
        # If changing from completed to something else, clear completed_at
        db_task.completed_at = None

    for field, value in update_data.items():
        setattr(db_task, field, value)

    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: int, owner_id: Optional[int] = None) -> bool:
    """Delete task."""
    db_task = get_task(db, task_id, owner_id)
    if not db_task:
        return False
    db.delete(db_task)
    db.commit()
    return True


def get_task_stats(db: Session, owner_id: int) -> dict:
    """Get task statistics for a user."""
    stats = db.query(
        Task.status,
        func.count(Task.id)
    ).filter(Task.owner_id == owner_id).group_by(Task.status).all()

    result = {status.value: 0 for status in TaskStatus}
    for status, count in stats:
        result[status.value] = count

    # Priority stats
    priority_stats = db.query(
        Task.priority,
        func.count(Task.id)
    ).filter(Task.owner_id == owner_id).group_by(Task.priority).all()

    for priority, count in priority_stats:
        result[f"priority_{priority.value}"] = count

    result["total"] = sum(result.get(s.value, 0) for s in TaskStatus)
    return result


def get_overdue_tasks(db: Session, owner_id: int) -> List[Task]:
    """Get overdue tasks for a user."""
    now = datetime.utcnow()
    return db.query(Task).filter(
        Task.owner_id == owner_id,
        Task.due_date < now,
        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
    ).all()


def get_upcoming_tasks(db: Session, owner_id: int, days: int = 7) -> List[Task]:
    """Get upcoming tasks due within specified days."""
    now = datetime.utcnow()
    future = now + timedelta(days=days)
    return db.query(Task).filter(
        Task.owner_id == owner_id,
        Task.due_date >= now,
        Task.due_date <= future,
        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
    ).order_by(Task.due_date).all()