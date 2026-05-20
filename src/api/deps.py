from typing import Annotated
from fastapi import Depends
from src.core.repos.work import DepartmentRepo, EmployeeRepo


DepartmentRepoDep = Annotated[DepartmentRepo, Depends(DepartmentRepo)]
EmployeeRepoDep = Annotated[EmployeeRepo, Depends(EmployeeRepo)]
