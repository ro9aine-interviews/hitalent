from typing import Generic, TypeVar, Iterable
from sqlalchemy import delete, update, select, and_, true

from src.core.entities.base import BaseEntity
from src.db.models import Base as DbBase
from src.db.session import asession_factory, AsyncSession

T = TypeVar("T", bound=BaseEntity)


class DbRepo(Generic[T]):
    model: type[DbBase]
    entity_model: type[T]
    SAVE_EXCLUDE: set[str] = {'id'}
    UPDATE_EXCLUDE: set[str] = {'id'}

    @asession_factory
    async def afind_one(self, id: int, *, session: AsyncSession) -> T | None:
        db_model = await self._afind_one(id, session)
        return self.entity_model.model_validate(db_model) if db_model else None

    @asession_factory
    async def afind_all(self, params: dict | None = None, limit: int = 10, offset: int = 0, *, session: AsyncSession) -> list[T]:
        db_models = await self._afind_all(params=params, limit=limit, offset=offset, session=session)
        return [self.entity_model.model_validate(db_model) for db_model in db_models]

    @asession_factory
    async def adelete(self, id: int, *, session: AsyncSession) -> bool:
        db_model = await self._adelete(id, session)
        await session.commit()
        return await self.apost_delete(id, db_model)

    @asession_factory
    async def aupdate(
        self,
        obj: BaseEntity,
        consider_all: bool = False,
        *,
        session: AsyncSession,
    ) -> BaseEntity | None:
        db_model = await self._aupdate(obj=obj, consider_all=consider_all, session=session)
        await session.commit()
        return await self.apost_update(obj, db_model)

    @asession_factory
    async def asave(self, obj: BaseEntity, *, session: AsyncSession) -> BaseEntity | None:
        db_model = await self._asave(obj, session)
        await session.commit()
        return await self.apost_save(obj, db_model)

    @asession_factory
    async def asave_many(
        self,
        objs: Iterable[BaseEntity],
        *,
        session: AsyncSession,
    ) -> list[BaseEntity]:
        db_models = await self._asave_many(objs, session)
        await session.commit()
        return [await self.apost_save(obj, db_model) for obj, db_model in zip(objs, db_models)]

    async def apost_save(self, obj: BaseEntity, db_model: DbBase):
        return self.entity_model.model_validate(db_model)

    def post_save(self, obj: BaseEntity, db_model: DbBase):
        return self.entity_model.model_validate(db_model)

    async def apost_update(self, obj: BaseEntity, db_model):
        return self.entity_model.model_validate(db_model)

    def post_update(self, obj: BaseEntity, db_model: DbBase):
        return self.entity_model.model_validate(db_model, from_attributes=True)

    async def apost_delete(self, id: int, db_model) -> bool:
        return db_model is not None

    async def _afind_all(self, params: dict | None, limit: int, offset: int, session: AsyncSession):
        if params is None:
            params = {}
        query = (
            select(self.model)
            .limit(limit)
            .offset(offset)
            .where(self._build_where(params))
        )
        db_models = await session.execute(query)
        return db_models.scalars().all()

    async def _afind_one(self, id: int, session: AsyncSession):
        db_model = await session.scalar(select(self.model).where(self.model.id == id))
        return db_model

    async def _adelete(self, id: int, session: AsyncSession):
        query = (
            delete(self.model)
            .where(self.model.id == id)
            .returning(self.model)
        )
        db_model = await session.execute(query)
        await session.flush()
        return db_model.scalar_one_or_none()

    async def _asave_many(self, objs: Iterable[BaseEntity], session: AsyncSession) -> list[BaseEntity]:
        db_models = []
        for obj in objs:
            db_model = await self._asave(obj, session)
            db_models.append(db_model)
        return db_models

    async def _aupdate(self, obj: BaseEntity, consider_all: bool = False, session: AsyncSession | None = None):
        if obj.id is None:
            raise ValueError('id cannot be None')
        model_dump = self._get_update_model_dump(obj, consider_all)
        query = (
            update(self.model)
            .where(self.model.id == obj.id)
            .values(model_dump)
            .returning(self.model)
        )
        db_model = await session.execute(query)
        await session.flush()
        return db_model.unique().scalar_one()

    async def _asave(self, obj: BaseEntity, session: AsyncSession):
        model_dump = self._get_model_dump(obj)
        db_model = self.model(**model_dump)
        session.add(db_model)
        await session.flush()
        try:
            obj.id = db_model.id
        except ValueError:
            pass  # TODO: need to log here
        return db_model

    def _get_update_model_dump(self, obj: BaseEntity, consider_all: bool = False) -> dict:
        return obj.model_dump(exclude=self.UPDATE_EXCLUDE, exclude_unset=not consider_all)

    def _get_model_dump(self, obj: BaseEntity) -> dict:
        return obj.model_dump(exclude=self.SAVE_EXCLUDE)

    def _build_where(self, params: dict):
        if not params:
            return true()
        return and_(
            *(getattr(self.model, key) == value for key, value in params.items())
        )
