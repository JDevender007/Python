"""
REST API with FastAPI - Unit Tests for Schemas
"""

import pytest
from datetime import datetime, timedelta
from src.schemas import (
    UserCreate, UserUpdate, UserResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    TaskFilterParams, UserFilterParams,
    TaskStatus, TaskPriority, Token,
)


class TestUserSchemas:
    def test_user_create_valid(self):
        user = UserCreate(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            password="SecurePass123",
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"

    def test_user_create_invalid_password_short(self):
        with pytest.raises(ValueError, match="at least 8 characters"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="Short1",
            )

    def test_user_create_invalid_password_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="securepass123",
            )

    def test_user_create_invalid_password_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="SECUREPASS123",
            )

    def test_user_create_invalid_password_no_digit(self):
        with pytest.raises(ValueError, match="digit"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="SecurePass",
            )

    def test_user_create_invalid_email(self):
        with pytest.raises(ValueError):
            UserCreate(
                username="testuser",
                email="invalid-email",
                password="SecurePass123",
            )

    def test_user_create_invalid_username(self):
        with pytest.raises(ValueError):
            UserCreate(
                username="ab",
                email="test@example.com",
                password="SecurePass123",
            )

    def test_user_update(self):
        update = UserUpdate(
            email="new@example.com",
            full_name="New Name",
        )
        assert update.email == "new@example.com"
        assert update.full_name == "New Name"


class TestTaskSchemas:
    def test_task_create_valid(self):
        task = TaskCreate(
            title="Test Task",
            description="Test description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            due_date=datetime.now() + timedelta(days=7),
        )
        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.HIGH

    def test_task_create_minimal(self):
        task = TaskCreate(title="Minimal Task")
        assert task.title == "Minimal Task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM

    def test_task_create_invalid_title_empty(self):
        with pytest.raises(ValueError):
            TaskCreate(title="")

    def test_task_create_invalid_title_too_long(self):
        with pytest.raises(ValueError):
            TaskCreate(title="x" * 201)

    def test_task_update(self):
        update = TaskUpdate(
            title="Updated Title",
            status=TaskStatus.COMPLETED,
        )
        assert update.title == "Updated Title"
        assert update.status == TaskStatus.COMPLETED

    def test_task_filter_params(self):
        filters = TaskFilterParams(
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            search="test",
            page=1,
            page_size=20,
        )
        assert filters.status == TaskStatus.PENDING
        assert filters.priority == TaskPriority.HIGH
        assert filters.search == "test"
        assert filters.page == 1
        assert filters.page_size == 20

    def test_task_filter_params_defaults(self):
        filters = TaskFilterParams()
        assert filters.page == 1
        assert filters.page_size == 20
        assert filters.status is None
        assert filters.priority is None


class TestUserFilterParams:
    def test_user_filter_params(self):
        filters = UserFilterParams(
            search="test",
            is_active=True,
            is_admin=False,
            page=2,
            page_size=10,
        )
        assert filters.search == "test"
        assert filters.is_active is True
        assert filters.is_admin is False
        assert filters.page == 2
        assert filters.page_size == 10


class TestTokenSchema:
    def test_token(self):
        token = Token(access_token="test_token_123")
        assert token.access_token == "test_token_123"
        assert token.token_type == "bearer"


from datetime import datetime, timedelta