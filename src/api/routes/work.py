from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from src.api.deps import DepartmentRepoDep, EmployeeRepoDep
from src.core.entities.work import DepartmentEntity, EmployeeEntity, ExtendedDepartmentEntity
from src.core.repos.work import DepartmentConflictError, DepartmentNotFoundError

router = APIRouter()


@router.get("/deparments/")
async def get_departments(
    department_repo: DepartmentRepoDep,
    limit: int = Query(default=10, ge=0, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DepartmentEntity]:
    return await department_repo.afind_all(limit=limit, offset=offset)


@router.post("/departments/", status_code=status.HTTP_201_CREATED)
async def create_department(
    department_repo: DepartmentRepoDep,
    payload: DepartmentEntity.Creation,
) -> DepartmentEntity:
    try:
        return await department_repo.asave(payload)
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DepartmentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/departments/{id}/employees/", status_code=status.HTTP_201_CREATED)
async def create_employee(
    department_repo: DepartmentRepoDep,
    employee_repo: EmployeeRepoDep,
    id: int,
    payload: EmployeeEntity.NoDepCreation,
):
    department = await department_repo.afind_one(id)
    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    return await employee_repo.asave(EmployeeEntity.Creation(department_id=id, **payload.model_dump()))


@router.get("/departments/{id}")
async def get_department(
    department_repo: DepartmentRepoDep,
    id: int,
    depth: int = Query(default=1, ge=0, le=5),
    include_employees: bool = True,
) -> ExtendedDepartmentEntity:
    department = await department_repo.afind_extended_one(id, depth, include_employees)
    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    return department


@router.patch("/departments/{id}", response_model=DepartmentEntity)
async def update_department(
    department_repo: DepartmentRepoDep,
    id: int,
    payload: DepartmentEntity.SaveUpdate,
):
    try:
        return await department_repo.aupdate(
            DepartmentEntity.Update(**payload.model_dump(exclude_unset=True), id=id)
        )
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DepartmentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete("/departments/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_repo: DepartmentRepoDep,
    employee_repo: EmployeeRepoDep,
    id: int,
    mode: Literal["cascade", "reassign"],
    reassign_to_department_id: int | None = None,
) -> Response:
    department = await department_repo.afind_one(id)
    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    if mode == "reassign" and reassign_to_department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reassign to department id is required",
        )

    if mode == "reassign":
        await employee_repo.areassign(id, reassign_to_department_id)

    await department_repo.adelete(id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
