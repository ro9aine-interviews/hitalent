from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import Field, PositiveInt, StringConstraints

from .base import BaseEntity

NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class DepartmentEntity(BaseEntity):
    id: int
    name: NonEmptyStr
    parent_id: PositiveInt | None = None
    created_at: dt.datetime | None = None

    class Creation(BaseEntity.Creation):
        name: NonEmptyStr
        parent_id: PositiveInt | None = None

    class SaveUpdate(BaseEntity.Update):
        name: NonEmptyStr | None = None
        parent_id: PositiveInt | None = None

    class Update(SaveUpdate):
        id: int


class EmployeeEntity(BaseEntity):
    id: int
    department_id: PositiveInt
    full_name: NonEmptyStr
    position: NonEmptyStr
    hired_at: dt.date | None = None
    created_at: dt.datetime | None = None

    class NoDepCreation(BaseEntity.Creation):
        full_name: NonEmptyStr
        position: NonEmptyStr
        hired_at: dt.date | None = None

    class Creation(NoDepCreation):
        department_id: PositiveInt

    class Update(BaseEntity.Update):
        department_id: PositiveInt | None = None
        full_name: NonEmptyStr | None = None
        position: NonEmptyStr | None = None
        hired_at: dt.date | None = None


class ExtendedDepartmentEntity(DepartmentEntity):
    employees: list[EmployeeEntity] = Field(default_factory=list)
    children: list[DepartmentEntity] = Field(default_factory=list)
