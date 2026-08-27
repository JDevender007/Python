"""
REST API with FastAPI - Unit Tests for CRUD
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base, User, Task, TaskStatus, TaskPriority
from src.crud import (
    create_user, get_user, get_user_by_username, get_user_by_email,
    get_users, update_user, delete_user,
    create_task, get_task, get_tasks, update_task, delete_task,
    get_task_stats,
)
from src.schemas import UserCreate, UserUpdate, TaskCreate, TaskUpdate, TaskFilterParams, UserFilterParams
from src.auth import get_password_hash


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db):
    """Create a test user for task tests."""
    from src.crud import create_user
    from src.schemas import UserCreate
    user = create_user(db, UserCreate(
        username="testuser",
        email="test@example.com",
        password="SecurePass123",
    ))
    return user


class TestUserCRUD:
    def test_create_user(self, db):
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            password="SecurePass123",
        )
        user = create_user(db, user_data)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.hashed_password != "SecurePass123"

    def test_get_user(self, db):
        user_data = UserCreate(
            username="testuser2",
            email="test2@example.com",
            password="SecurePass123",
        )
        created = create_user(db, user_data)
        retrieved = get_user(db, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.username == "testuser2"

    def test_get_user_by_username(self, db):
        user_data = UserCreate(
            username="testuser3",
            email="test3@example.com",
            password="SecurePass123",
        )
        create_user(db, user_data)
        user = get_user_by_username(db, "testuser3")

        assert user is not None
        assert user.username == "testuser3"

    def test_get_user_by_email(self, db):
        user_data = UserCreate(
            username="testuser4",
            email="test4@example.com",
            password="SecurePass123",
        )
        create_user(db, user_data)
        user = get_user_by_email(db, "test4@example.com")

        assert user is not None
        assert user.email == "test4@example.com"

    def test_get_users(self, db):
        for i in range(5):
            create_user(db, UserCreate(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="SecurePass123",
            ))

        filters = UserFilterParams(page=1, page_size=10)
        users, total = get_users(db, filters)

        assert total == 5
        assert len(users) == 5

    def test_get_users_with_search(self, db):
        create_user(db, UserCreate(username="alice", email="alice@example.com", password="SecurePass123"))
        create_user(db, UserCreate(username="bob", email="bob@example.com", password="SecurePass123"))

        filters = UserFilterParams(search="alice", page=1, page_size=10)
        users, total = get_users(db, filters)

        assert total == 1
        assert users[0].username == "alice"

    def test_update_user(self, db):
        user_data = UserCreate(username="updateme", email="updateme@example.com", password="SecurePass123")
        created = create_user(db, user_data)

        update_data = UserUpdate(full_name="Updated Name", email="new@example.com")
        updated = update_user(db, created.id, update_data)

        assert updated is not None
        assert updated.full_name == "Updated Name"
        assert updated.email == "new@example.com"

    def test_delete_user(self, db):
        user_data = UserCreate(username="deleteme", email="deleteme@example.com", password="SecurePass123")
        created = create_user(db, user_data)

        result = delete_user(db, created.id)
        assert result is True

        deleted = get_user(db, created.id)
        assert deleted is None


class TestTaskCRUD:
    @pytest.fixture
    def test_user(self, db):
        user_data = UserCreate(username="taskuser", email="task@example.com", password="SecurePass123")
        return create_user(db, user_data)

    def test_create_task(self, db, test_user):
        task_data = TaskCreate(
            title="Test Task",
            description="Test description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            due_date=datetime.now() + timedelta(days=7),
        )
        task = create_task(db, task_data, test_user.id)

        assert task.id is not None
        assert task.title == "Test Task"
        assert task.owner_id == test_user.id
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.HIGH

    def test_get_task(self, db, test_user):
        task_data = TaskCreate(title="Get Task", priority=TaskPriority.MEDIUM)
        created = create_task(db, task_data, test_user.id)

        retrieved = get_task(db, created.id, test_user.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Get Task"

    def test_get_task_wrong_owner(self, db, test_user):
        # Create another user
        other_user = create_user(db, UserCreate(
            username="other", email="other@example.com", password="SecurePass123"
        ))

        task_data = TaskCreate(title="Private Task")
        created = create_task(db, task_data, test_user.id)

        # Try to get with other user's ID
        retrieved = get_task(db, created.id, other_user.id)
        assert retrieved is None

    def test_get_tasks(self, db, test_user):
        for i in range(10):
            create_task(db, TaskCreate(title=f"Task {i}", priority=TaskPriority.MEDIUM), test_user.id)

        filters = TaskFilterParams(page=1, page_size=5)
        tasks, total = get_tasks(db, filters, test_user.id)

        assert total == 10
        assert len(tasks) == 5

    def test_get_tasks_with_status_filter(self, db, test_user):
        create_task(db, TaskCreate(title="Pending Task", status=TaskStatus.PENDING), test_user.id)
        create_task(db, TaskCreate(title="Completed Task", status=TaskStatus.COMPLETED), test_user.id)

        filters = TaskFilterParams(status=TaskStatus.COMPLETED)
        tasks, total = get_tasks(db, filters, test_user.id)

        assert total == 1
        assert tasks[0].status == TaskStatus.COMPLETED

    def test_get_tasks_with_priority_filter(self, db, test_user):
        create_task(db, TaskCreate(title="High Priority", priority=TaskPriority.HIGH), test_user.id)
        create_task(db, TaskCreate(title="Low Priority", priority=TaskPriority.LOW), test_user.id)

        filters = TaskFilterParams(priority=TaskPriority.HIGH)
        tasks, total = get_tasks(db, filters, test_user.id)

        assert total == 1
        assert tasks[0].priority == TaskPriority.HIGH

    def test_update_task(self, db, test_user):
        task_data = TaskCreate(title="Original Title", status=TaskStatus.PENDING)
        created = create_task(db, task_data, test_user.id)

        update_data = TaskUpdate(title="Updated Title", status=TaskStatus.IN_PROGRESS)
        updated = update_task(db, created.id, update_data, test_user.id)

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.status == TaskStatus.IN_PROGRESS

    def test_update_task_completion_sets_timestamp(self, db, test_user):
        task_data = TaskCreate(title="Task to Complete", status=TaskStatus.PENDING)
        created = create_task(db, task_data, test_user.id)

        assert created.completed_at is None

        update_data = TaskUpdate(status=TaskStatus.COMPLETED)
        updated = update_task(db, created.id, update_data, test_user.id)

        assert updated.status == TaskStatus.COMPLETED
        assert updated.completed_at is not None

    def test_update_task_uncomplete_clears_timestamp(self, db, test_user):
        task_data = TaskCreate(title="Completed Task", status=TaskStatus.COMPLETED)
        created = create_task(db, task_data, test_user.id)

        # Manually set completed_at
        created.completed_at = datetime.utcnow()
        db.commit()

        update_data = TaskUpdate(status=TaskStatus.PENDING)
        updated = update_task(db, created.id, update_data, test_user.id)

        assert updated.status == TaskStatus.PENDING
        assert updated.completed_at is None

    def test_delete_task(self, db, test_user):
        task_data = TaskCreate(title="Task to Delete")
        created = create_task(db, task_data, test_user.id)

        result = delete_task(db, created.id, test_user.id)
        assert result is True

        deleted = get_task(db, created.id, test_user.id)
        assert deleted is None

    def test_delete_task_wrong_owner(self, db, test_user):
        other_user = create_user(db, UserCreate(
            username="other2", email="other2@example.com", password="SecurePass123"
        ))

        task_data = TaskCreate(title="Other's Task")
        created = create_task(db, task_data, other_user.id)

        result = delete_task(db, created.id, test_user.id)
        assert result is False


class TestTaskStats:
    def test_get_task_stats(self, db, test_user):
        create_task(db, TaskCreate(title="Pending 1", status=TaskStatus.PENDING), test_user.id)
        create_task(db, TaskCreate(title="Pending 2", status=TaskStatus.PENDING), test_user.id)
        create_task(db, TaskCreate(title="In Progress", status=TaskStatus.IN_PROGRESS), test_user.id)
        create_task(db, TaskCreate(title="Completed", status=TaskStatus.COMPLETED), test_user.id)
        create_task(db, TaskCreate(title="Cancelled", status=TaskStatus.CANCELLED), test_user.id)

        stats = get_task_stats(db, test_user.id)

        assert stats["pending"] == 2
        assert stats["in_progress"] == 1
        assert stats["completed"] == 1
        assert stats["cancelled"] == 1
        assert stats["total"] == 5