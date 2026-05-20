from src.db.session import AsyncSessionLocal, engine
from src.db.models import Base, Department, Employee
from src.api.routes.work import router
from sqlalchemy import select
from fastapi.testclient import TestClient
from fastapi import FastAPI
import pytest
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_database():
    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def drop_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(init_db())
    yield
    asyncio.run(drop_db())


def create_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_department() -> None:
    client = create_test_client()

    response = client.post(
        "/departments/",
        json={"name": " Engineering ", "parent_id": None},
    )

    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert response.json()["name"] == "Engineering"
    assert response.json()["parent_id"] is None
    assert response.json()["created_at"] is not None

    async def load_department() -> Department | None:
        async with AsyncSessionLocal() as session:
            return await session.scalar(select(Department).where(Department.id == 1))

    department = asyncio.run(load_department())

    assert department is not None
    assert department.name == "Engineering"
    assert department.parent_id is None


def test_create_employee() -> None:
    client = create_test_client()

    department_response = client.post(
        "/departments/",
        json={"name": "Engineering", "parent_id": None},
    )
    department_id = department_response.json()["id"]

    response = client.post(
        f"/departments/{department_id}/employees/",
        json={
            "full_name": " Jane Doe ",
            "position": " Backend Developer ",
            "hired_at": "2026-05-20",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert response.json()["department_id"] == department_id
    assert response.json()["full_name"] == "Jane Doe"
    assert response.json()["position"] == "Backend Developer"
    assert response.json()["hired_at"] == "2026-05-20"
    assert response.json()["created_at"] is not None

    async def load_employee() -> Employee | None:
        async with AsyncSessionLocal() as session:
            return await session.scalar(select(Employee).where(Employee.id == 1))

    employee = asyncio.run(load_employee())

    assert employee is not None
    assert employee.department_id == department_id
    assert employee.full_name == "Jane Doe"
    assert employee.position == "Backend Developer"
    assert employee.hired_at.isoformat() == "2026-05-20"


def test_create_employee_for_missing_department() -> None:
    client = create_test_client()

    response = client.post(
        "/departments/999/employees/",
        json={
            "full_name": "Jane Doe",
            "position": "Backend Developer",
            "hired_at": None,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Department not found"}

    async def count_employees() -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Employee))
            return len(result.scalars().all())

    assert asyncio.run(count_employees()) == 0


def test_get_department_with_employees_and_children() -> None:
    client = create_test_client()

    root_response = client.post(
        "/departments/",
        json={"name": "Engineering", "parent_id": None},
    )
    root_id = root_response.json()["id"]
    child_response = client.post(
        "/departments/",
        json={"name": "Platform", "parent_id": root_id},
    )

    client.post(
        f"/departments/{root_id}/employees/",
        json={
            "full_name": "Jane Doe",
            "position": "Backend Developer",
            "hired_at": "2026-05-20",
        },
    )

    response = client.get(f"/departments/{root_id}?depth=1&include_employees=true")

    assert response.status_code == 200
    assert response.json()["id"] == root_id
    assert response.json()["name"] == "Engineering"
    assert response.json()["employees"][0]["full_name"] == "Jane Doe"
    assert response.json()["children"][0]["id"] == child_response.json()["id"]
    assert response.json()["children"][0]["name"] == "Platform"


def test_get_department_without_employees() -> None:
    client = create_test_client()

    department_response = client.post(
        "/departments/",
        json={"name": "Engineering", "parent_id": None},
    )
    department_id = department_response.json()["id"]
    client.post(
        f"/departments/{department_id}/employees/",
        json={
            "full_name": "Jane Doe",
            "position": "Backend Developer",
            "hired_at": None,
        },
    )

    response = client.get(
        f"/departments/{department_id}?depth=1&include_employees=false"
    )

    assert response.status_code == 200
    assert response.json()["employees"] == []


def test_patch_department() -> None:
    client = create_test_client()

    department_response = client.post(
        "/departments/",
        json={"name": "Engineering", "parent_id": None},
    )
    department_id = department_response.json()["id"]
    new_dep_resp = client.post("/departments/", json={"name": "Development"})
    child_resp = client.post("/departments/", json={"name": "Platform", "parent_id": department_id})

    assert child_resp.json()["parent_id"] == department_id
    new_child_resp = client.patch(
        f"/departments/{child_resp.json()['id']}", json={"parent_id": new_dep_resp.json()["id"]})

    assert new_child_resp.json()["parent_id"] == new_dep_resp.json()["id"]


def test_delete_department() -> None:
    client = create_test_client()

    resp = client.post(
        "/departments/",
        json={"name": "Engineering", "parent_id": None},
    )
    first_id = resp.json()["id"]
    dep_id = resp.json()["id"]
    resp = client.post(
        "/departments/",
        json={"name": "Platform", "parent_id": dep_id},
    )
    dep_id = resp.json()["id"]
    client.post("/departments/", json={"name": "Reps", "parent_id": dep_id})
    client.delete(f"/departments/{dep_id}?mode=cascade")

    response = client.get(f"/departments/{dep_id}")

    assert response.status_code == 404
    root_response = client.get(f"/departments/{first_id}")

    assert root_response.status_code == 200
    assert len(root_response.json()["children"]) == 0
    response = client.get("/departments/")
    assert len(response.json()) == 1


def test_get_department_extended() -> None:
    client = create_test_client()

    root_response = client.post(
        "/departments/",
        json={"name": "Engineering", "parent_id": None},
    )
    root_id = root_response.json()["id"]
    client.post("/departments/", json={"name": "Platform", "parent_id": root_id})
    client.post("/departments/", json={"name": "Platform1", "parent_id": root_id})
    temp = client.post("/departments/", json={"name": "Platform2", "parent_id": root_id})
    temp = client.post("/departments/", json={"name": "Platform3", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform4", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform5", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform6", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform7", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform8", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform9", "parent_id": temp.json()["id"]})
    temp = client.post("/departments/", json={"name": "Platform10", "parent_id": temp.json()["id"]})
    client.post(
        f"/departments/{root_id}/employees/",
        json={
            "full_name": "Jane Doe",
            "position": "Backend Developer",
            "hired_at": None,
        },
    )

    response = client.get(f"/departments/{root_id}?depth=5&include_employees=true")
    resp_json = response.json()

    assert response.status_code == 200
    assert resp_json["id"] == root_id
    assert resp_json["name"] == "Engineering"
    assert len(resp_json["employees"]) == 1
    assert len(resp_json["children"]) == 8


def test_create_duplicate_department_name_in_same_parent() -> None:
    client = create_test_client()

    client.post("/departments/", json={"name": "Backend"})
    response = client.post("/departments/", json={"name": "Backend"})

    assert response.status_code == 409


def test_can_create_same_department_name_in_different_parents() -> None:
    client = create_test_client()

    first_parent = client.post("/departments/", json={"name": "Engineering"}).json()
    second_parent = client.post("/departments/", json={"name": "Product"}).json()

    first_child = client.post(
        "/departments/",
        json={"name": "Backend", "parent_id": first_parent["id"]},
    )
    second_child = client.post(
        "/departments/",
        json={"name": "Backend", "parent_id": second_parent["id"]},
    )

    assert first_child.status_code == 201
    assert second_child.status_code == 201


def test_create_department_name_max_length() -> None:
    client = create_test_client()

    valid_response = client.post("/departments/", json={"name": "A" * 200})
    invalid_response = client.post("/departments/", json={"name": "A" * 201})

    assert valid_response.status_code == 201
    assert invalid_response.status_code == 422


def test_cannot_make_department_parent_of_itself() -> None:
    client = create_test_client()

    department = client.post("/departments/", json={"name": "Engineering"}).json()

    response = client.patch(
        f"/departments/{department['id']}",
        json={"parent_id": department["id"]},
    )

    assert response.status_code == 409


def test_cannot_create_department_cycle() -> None:
    client = create_test_client()

    root = client.post("/departments/", json={"name": "Engineering"}).json()
    child = client.post(
        "/departments/",
        json={"name": "Platform", "parent_id": root["id"]},
    ).json()

    response = client.patch(
        f"/departments/{root['id']}",
        json={"parent_id": child["id"]},
    )

    assert response.status_code == 409


def test_cascade_delete_removes_employees() -> None:
    client = create_test_client()

    department = client.post("/departments/", json={"name": "Engineering"}).json()
    client.post(
        f"/departments/{department['id']}/employees/",
        json={"full_name": "Jane Doe", "position": "Backend Developer"},
    )

    response = client.delete(f"/departments/{department['id']}?mode=cascade")

    assert response.status_code == 204

    async def count_employees() -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Employee))
            return len(result.scalars().all())

    assert asyncio.run(count_employees()) == 0


def test_delete_department_reassigns_employees() -> None:
    client = create_test_client()

    source = client.post("/departments/", json={"name": "Engineering"}).json()
    target = client.post("/departments/", json={"name": "Product"}).json()
    employee = client.post(
        f"/departments/{source['id']}/employees/",
        json={"full_name": "Jane Doe", "position": "Backend Developer"},
    ).json()

    response = client.delete(
        f"/departments/{source['id']}?mode=reassign"
        f"&reassign_to_department_id={target['id']}"
    )

    assert response.status_code == 204
    assert client.get(f"/departments/{source['id']}").status_code == 404

    async def load_employee() -> Employee | None:
        async with AsyncSessionLocal() as session:
            return await session.scalar(
                select(Employee).where(Employee.id == employee["id"])
            )

    reassigned_employee = asyncio.run(load_employee())

    assert reassigned_employee is not None
    assert reassigned_employee.department_id == target["id"]
