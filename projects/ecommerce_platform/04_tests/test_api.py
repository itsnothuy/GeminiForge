import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.base import Base
from app.api import deps
from src.main import app
from app.models.user import User
from app import crud


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db():
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    yield db
    db.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def create_user(db):
    user_in = {"email": "test@example.com", "password": "test", "full_name": "Test User"}
    user = crud.user.create(db, obj_in=user_in)
    return user


@pytest.fixture
def superuser_token_headers(client, db):
    user_in = {"email": "superuser@example.com", "password": "test", "full_name": "Super User", "is_superuser": True}
    user = crud.user.create(db, obj_in=user_in)
    login_data = {
        "username": "superuser@example.com",
        "password": "test"
    }
    r = client.post("/api/v1/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


@pytest.fixture
def normal_user_token_headers(client, create_user):
    login_data = {
        "username": "test@example.com",
        "password": "test"
    }
    r = client.post("/api/v1/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_create_item(client, normal_user_token_headers):
    data = {"title": "Test Item", "description": "Test Description"}
    response = client.post("/api/v1/items/", headers=normal_user_token_headers, json=data)
    assert response.status_code == 200
    assert response.json()["title"] == "Test Item"
    assert response.json()["description"] == "Test Description"


def test_read_items(client, normal_user_token_headers):
    response = client.get("/api/v1/items/", headers=normal_user_token_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_item(client, normal_user_token_headers, db, create_user):
    item_data = {"title": "Test Item", "description": "Test Description", "owner_id": create_user.id}
    item = crud.item.create(db, obj_in=item_data, owner_id=create_user.id)
    response = client.get(f"/api/v1/items/{item.id}", headers=normal_user_token_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Test Item"


def test_update_item(client, normal_user_token_headers, db, create_user):
    item_data = {"title": "Test Item", "description": "Test Description", "owner_id": create_user.id}
    item = crud.item.create(db, obj_in=item_data, owner_id=create_user.id)
    update_data = {"title": "Updated Item", "description": "Updated Description"}
    response = client.put(f"/api/v1/items/{item.id}", headers=normal_user_token_headers, json=update_data)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Item"


def test_delete_item(client, normal_user_token_headers, db, create_user):
    item_data = {"title": "Test Item", "description": "Test Description", "owner_id": create_user.id}
    item = crud.item.create(db, obj_in=item_data, owner_id=create_user.id)
    response = client.delete(f"/api/v1/items/{item.id}", headers=normal_user_token_headers)
    assert response.status_code == 200
    # Verify item is deleted
    response = client.get(f"/api/v1/items/{item.id}", headers=normal_user_token_headers)
    assert response.status_code == 404


def test_create_user_open(client):
    data = {"email": "newuser@example.com", "password": "test", "full_name": "New User"}
    response = client.post("/api/v1/users/open", json=data)
    assert response.status_code == 200
    assert response.json()["email"] == "newuser@example.com"


def test_read_users(client, superuser_token_headers):
    response = client.get("/api/v1/users/", headers=superuser_token_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_user_me(client, normal_user_token_headers):
    response = client.get("/api/v1/users/me", headers=normal_user_token_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_update_user_me(client, normal_user_token_headers):
    data = {"full_name": "Updated Name"}
    response = client.patch("/api/v1/users/me", headers=normal_user_token_headers, json=data)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


def test_read_user(client, superuser_token_headers, create_user):
    response = client.get(f"/api/v1/users/{create_user.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_update_user(client, superuser_token_headers, create_user):
    data = {"full_name": "Updated Super User"}
    response = client.put(f"/api/v1/users/{create_user.id}", headers=superuser_token_headers, json=data)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Super User"