"""Maintenance task models."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MaintenanceTaskTemplate(Base):
    """Standard maintenance workflow template."""

    __tablename__ = "maintenance_task_templates"
    __table_args__ = (
        UniqueConstraint(
            "equipment_type",
            "maintenance_level",
            name="uq_maintenance_task_templates_type_level",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    maintenance_level: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="published", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    steps: Mapped[list["MaintenanceTaskTemplateStep"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="MaintenanceTaskTemplateStep.step_order",
    )


class MaintenanceTaskTemplateStep(Base):
    """Template step definition for a maintenance workflow."""

    __tablename__ = "maintenance_task_template_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_task_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction_template: Mapped[str] = mapped_column(Text, nullable=False)
    risk_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    caution: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    required_materials: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    template: Mapped[MaintenanceTaskTemplate] = relationship(back_populates="steps")


class MaintenanceTask(Base):
    """Concrete maintenance task created from a template and knowledge results."""

    __tablename__ = "maintenance_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    work_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    asset_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    report_source: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(30), default="medium", nullable=False, index=True)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    equipment_model: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    maintenance_level: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    fault_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    symptom_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="in_progress", nullable=False, index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_task_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_chunk_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    source_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    execution_timeline: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    diagnosis_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    advice_card: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    steps: Mapped[list["MaintenanceTaskStep"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="MaintenanceTaskStep.step_order",
    )


class MaintenanceTaskStep(Base):
    """Runtime step for a concrete maintenance task."""

    __tablename__ = "maintenance_task_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_task_template_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    risk_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    caution: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    required_materials: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    knowledge_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    task: Mapped[MaintenanceTask] = relationship(back_populates="steps")
