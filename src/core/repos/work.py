from sqlalchemy import distinct, select, union_all, update
from sqlalchemy.orm import aliased, joinedload

from .base import DbRepo
from src.core.entities.work import DepartmentEntity, EmployeeEntity, ExtendedDepartmentEntity
from src.db.models import Department, Employee
from src.db.session import asession_factory, AsyncSession


class DepartmentNotFoundError(ValueError):
    pass


class DepartmentConflictError(ValueError):
    pass


class DepartmentRepo(DbRepo[DepartmentEntity]):
    model = Department
    entity_model = DepartmentEntity

    @asession_factory
    async def asave(
        self,
        obj: DepartmentEntity.Creation,
        *,
        session: AsyncSession,
    ) -> DepartmentEntity | None:
        await self._avalidate_department_save(obj, session)
        return await super().asave(obj, session=session)

    @asession_factory
    async def aupdate(
        self,
        obj: DepartmentEntity.Update,
        consider_all: bool = False,
        *,
        session: AsyncSession,
    ) -> DepartmentEntity | None:
        await self._avalidate_department_update(obj, consider_all, session)
        return await super().aupdate(obj, consider_all=consider_all, session=session)

    @asession_factory
    async def afind_extended_one(
        self,
        id: int,
        depth: int = 1,
        include_employees: bool = True,
        *,
        session: AsyncSession,
    ) -> ExtendedDepartmentEntity | None:
        query = (
            select(self.model)
            .where(self.model.id == id)
        )
        if include_employees:
            query = query.options(joinedload(Department.employees))
        result = await session.execute(query)
        department = result.unique().scalar_one_or_none()
        if department is None:
            return None
        children_query = select(self.model).where(self.model.id.in_(self.build_depth_query(depth, department.id)))
        children = await session.execute(children_query)
        return ExtendedDepartmentEntity.model_validate(dict(
            id=department.id,
            name=department.name,
            employees=department.employees if include_employees else [],
            children=[self.entity_model.model_validate(child) for child in children.scalars().all()],
        ))

    def build_depth_query(self, depth: int, root_p_id: int):
        assert 0 <= depth <= 5

        aliases = [aliased(self.model, flat=True) for _ in range(depth + 1)]
        root = aliases[0]

        query = (
            select(root.id.label("id0"))
            .select_from(root)
            .where(root.parent_id == root_p_id)
        )

        for i in range(1, depth + 1):
            prev = aliases[i - 1]
            curr = aliases[i]

            query = query.add_columns(curr.id.label(f"id{i}"))
            query = query.join(
                curr,
                curr.parent_id == prev.id,
                isouter=True,
            )

        cte = query.cte("base")

        unpivoted = union_all(
            *[
                select(getattr(cte.c, f"id{i}").label("id"))
                for i in range(depth + 1)
            ]
        ).subquery("unpivoted")

        return (
            select(distinct(unpivoted.c.id).label("id"))
            .where(unpivoted.c.id.is_not(None))
        )

    async def _avalidate_department_save(
        self,
        obj: DepartmentEntity.Creation,
        session: AsyncSession,
    ) -> None:
        if obj.parent_id is not None:
            parent = await session.scalar(
                select(Department.id).where(Department.id == obj.parent_id)
            )
            if parent is None:
                raise DepartmentNotFoundError("Parent department not found")

        await self._aensure_unique_name(
            name=obj.name,
            parent_id=obj.parent_id,
            session=session,
        )

    async def _avalidate_department_update(
        self,
        obj: DepartmentEntity.Update,
        consider_all: bool,
        session: AsyncSession,
    ) -> None:
        department = await session.scalar(
            select(Department).where(Department.id == obj.id)
        )
        if department is None:
            raise DepartmentNotFoundError("Department not found")

        update_data = obj.model_dump(exclude_unset=not consider_all)
        new_parent_id = update_data.get("parent_id", department.parent_id)
        new_name = update_data.get("name", department.name)

        if new_parent_id == obj.id:
            raise DepartmentConflictError("Department cannot be parent of itself")

        if new_parent_id is not None:
            parent = await session.scalar(
                select(Department.id).where(Department.id == new_parent_id)
            )
            if parent is None:
                raise DepartmentNotFoundError("Parent department not found")

            if await self._ais_descendant(
                department_id=obj.id,
                possible_descendant_id=new_parent_id,
                session=session,
            ):
                raise DepartmentConflictError(
                    "Department cannot be moved inside its subtree"
                )

        await self._aensure_unique_name(
            name=new_name,
            parent_id=new_parent_id,
            session=session,
            exclude_id=obj.id,
        )

    async def _aensure_unique_name(
        self,
        name: str,
        parent_id: int | None,
        session: AsyncSession,
        exclude_id: int | None = None,
    ) -> None:
        query = select(Department.id).where(Department.name == name)
        if parent_id is None:
            query = query.where(Department.parent_id.is_(None))
        else:
            query = query.where(Department.parent_id == parent_id)
        if exclude_id is not None:
            query = query.where(Department.id != exclude_id)

        existing_id = await session.scalar(query)
        if existing_id is not None:
            raise DepartmentConflictError(
                "Department name must be unique within the same parent"
            )

    async def _ais_descendant(
        self,
        department_id: int,
        possible_descendant_id: int,
        session: AsyncSession,
    ) -> bool:
        descendants_query = (
            select(Department.id)
            .where(Department.parent_id == department_id)
            .cte("descendants", recursive=True)
        )
        child_department = aliased(Department)
        descendants_query = descendants_query.union_all(
            select(child_department.id)
            .where(child_department.parent_id == descendants_query.c.id)
        )
        descendant_id = await session.scalar(
            select(descendants_query.c.id)
            .where(descendants_query.c.id == possible_descendant_id)
        )
        return descendant_id is not None


class EmployeeRepo(DbRepo[EmployeeEntity]):
    model = Employee
    entity_model = EmployeeEntity

    @asession_factory
    async def areassign(self, from_id: int, to_id: int, *, session: AsyncSession) -> list[EmployeeEntity]:
        query = (
            update(self.model)
            .where(self.model.department_id == from_id)
            .values(department_id=to_id)
            .returning(self.model)
        )
        db_model = await session.execute(query)
        await session.commit()
        return [
            self.entity_model.model_validate(employee)
            for employee in db_model.scalars().all()
        ]
