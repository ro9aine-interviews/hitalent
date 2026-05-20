from __future__ import annotations

import datetime as dt

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) between 1 and 200",
            name="ck_departments_name_length",
        ),
        CheckConstraint("id != parent_id", name="ck_departments_parent_not_self"),
        UniqueConstraint("parent_id", "name", name="uq_departments_parent_id_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    parent: Mapped[Department | None] = relationship(
        "Department",
        remote_side="Department.id",
        back_populates="children",
        passive_deletes=True,
    )
    children: Mapped[list[Department]] = relationship(
        "Department",
        back_populates="parent",
        passive_deletes=True,
        cascade="all, delete-orphan",
    )
    employees: Mapped[list[Employee]] = relationship(
        "Employee",
        back_populates="department",
        passive_deletes=True,
        cascade="all, delete-orphan",
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "length(trim(full_name)) between 1 and 200",
            name="ck_employees_full_name_length",
        ),
        CheckConstraint(
            "length(trim(position)) between 1 and 200",
            name="ck_employees_position_length",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(200), nullable=False)
    hired_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    department: Mapped[Department] = relationship(
        "Department",
        back_populates="employees",
    )
