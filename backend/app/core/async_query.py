from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sa_delete, func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession


class AsyncQuery:
    """Compact async adapter for old SQLAlchemy query-style route code.

    This executes through AsyncSession + await db.execute(...). It is not using
    route-level sync wrappers, so endpoints remain clean async functions.
    """

    def __init__(self, db: AsyncSession, *entities: Any):
        if not entities:
            raise ValueError("async_query requires at least one entity")
        self.db = db
        self.entities = entities
        self.statement = select(*entities)
        self._criteria: list[Any] = []

    def _primary_entity(self) -> Any:
        return self.entities[0]

    def _single_orm_entity(self) -> bool:
        return len(self.entities) == 1 and hasattr(self.entities[0], "__mapper__")

    def filter(self, *criteria: Any) -> "AsyncQuery":
        if criteria:
            self._criteria.extend(criteria)
            self.statement = self.statement.where(*criteria)
        return self

    def where(self, *criteria: Any) -> "AsyncQuery":
        return self.filter(*criteria)

    def filter_by(self, **kwargs: Any) -> "AsyncQuery":
        self.statement = self.statement.filter_by(**kwargs)
        return self

    def order_by(self, *clauses: Any) -> "AsyncQuery":
        self.statement = self.statement.order_by(*clauses)
        return self

    def group_by(self, *clauses: Any) -> "AsyncQuery":
        self.statement = self.statement.group_by(*clauses)
        return self

    def having(self, *criteria: Any) -> "AsyncQuery":
        self.statement = self.statement.having(*criteria)
        return self

    def limit(self, value: int | None) -> "AsyncQuery":
        self.statement = self.statement.limit(value)
        return self

    def offset(self, value: int | None) -> "AsyncQuery":
        self.statement = self.statement.offset(value)
        return self

    def options(self, *opts: Any) -> "AsyncQuery":
        self.statement = self.statement.options(*opts)
        return self

    def join(self, *args: Any, **kwargs: Any) -> "AsyncQuery":
        self.statement = self.statement.join(*args, **kwargs)
        return self

    def outerjoin(self, *args: Any, **kwargs: Any) -> "AsyncQuery":
        self.statement = self.statement.outerjoin(*args, **kwargs)
        return self

    def distinct(self, *expr: Any) -> "AsyncQuery":
        self.statement = self.statement.distinct(*expr)
        return self

    def with_entities(self, *entities: Any) -> "AsyncQuery":
        self.entities = entities
        self.statement = self.statement.with_only_columns(*entities, maintain_column_froms=True)
        return self

    async def all(self):
        result = await self.db.execute(self.statement)
        if self._single_orm_entity():
            return result.scalars().all()
        return result.all()

    async def first(self):
        result = await self.db.execute(self.statement.limit(1))
        if self._single_orm_entity():
            return result.scalars().first()
        return result.first()

    async def scalar(self):
        result = await self.db.execute(self.statement)
        return result.scalar()

    async def one(self):
        result = await self.db.execute(self.statement)
        if self._single_orm_entity():
            return result.scalars().one()
        return result.one()

    async def one_or_none(self):
        result = await self.db.execute(self.statement)
        if self._single_orm_entity():
            return result.scalars().one_or_none()
        return result.one_or_none()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.statement.order_by(None).subquery())
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def update(self, values: dict[str, Any], **kwargs: Any) -> int:
        stmt = sa_update(self._primary_entity()).where(*self._criteria).values(**values)
        result = await self.db.execute(stmt.execution_options(**kwargs) if kwargs else stmt)
        return int(result.rowcount or 0)

    async def delete(self, **kwargs: Any) -> int:
        stmt = sa_delete(self._primary_entity()).where(*self._criteria)
        result = await self.db.execute(stmt.execution_options(**kwargs) if kwargs else stmt)
        return int(result.rowcount or 0)


def async_query(db: AsyncSession, *entities: Any) -> AsyncQuery:
    return AsyncQuery(db, *entities)
