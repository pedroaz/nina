from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from .engine import Base  # type: ignore[import-untyped]
from .seed import seed_scheduled_jobs


def create_database(db_path: str) -> None:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)  # type: ignore[union-attr]
    _apply_lightweight_migrations(engine)
    _drop_legacy_kanban_columns(engine)
    _drop_legacy_task_columns(engine)
    _migrate_removed_task_types(engine)
    SessionLocal: Any = sessionmaker(bind=engine)
    db = SessionLocal()
    seed_scheduled_jobs(db)
    db.commit()
    db.close()


def _apply_lightweight_migrations(engine: Any) -> None:
    """Add columns that exist on ORM models but are missing from the SQLite schema.

    The original database was created with `Base.metadata.create_all` only, which
    does not add new columns to an existing table. This helper inspects each
    model and `ALTER TABLE`s in any missing column with a safe default. It is
    intentionally narrow: only additive column changes are supported, and primary
    keys are never added automatically.
    """

    inspector = inspect(engine)
    with engine.connect() as conn:
        for table_name, table in Base.metadata.tables.items():  # type: ignore[union-attr]
            if not inspector.has_table(table_name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if column.primary_key:
                    raise RuntimeError(
                        f"Refusing to auto-migrate primary key column "
                        f"{table_name}.{column.name}; please add a real migration."
                    )
                default_clause = _default_clause(column)
                type_sql = column.type.compile(engine.dialect)
                statement = (
                    f"ALTER TABLE {table_name} ADD COLUMN {column.name} {type_sql}{default_clause}"
                )
                conn.execute(text(statement))
        conn.commit()


def _drop_legacy_kanban_columns(engine: Any) -> None:
    """Remove the kanban column artifacts from older Nina databases.

    The pre-2026 task model had a `kanban_column` + `kanban_position` pair plus
    a `kanban_columns` table. The new model drops both. SQLite supports
    `ALTER TABLE DROP COLUMN` since 3.35.0; we run best-effort `DROP`s and
    ignore failures on older builds so the rest of the migration still applies.
    """

    inspector = inspect(engine)
    with engine.connect() as conn:
        if inspector.has_table("tasks"):
            existing = {c["name"] for c in inspector.get_columns("tasks")}
            for column in ("kanban_column", "kanban_position"):
                if column in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE tasks DROP COLUMN {column}"))
                    except Exception:  # noqa: BLE001
                        pass
        if inspector.has_table("kanban_columns"):
            try:
                conn.execute(text("DROP TABLE kanban_columns"))
            except Exception:  # noqa: BLE001
                pass
        conn.commit()


def _drop_legacy_task_columns(engine: Any) -> None:
    """Best-effort destructive cleanup for pre-task-type workflow schemas."""

    inspector = inspect(engine)
    with engine.connect() as conn:
        if inspector.has_table("projects"):
            try:
                conn.execute(text("DROP TABLE projects"))
            except Exception:  # noqa: BLE001
                pass

        if inspector.has_table("tasks"):
            existing = {c["name"] for c in inspector.get_columns("tasks")}
            if "status" in existing:
                try:
                    conn.execute(
                        text(
                            "UPDATE tasks SET status = 'idle' "
                            "WHERE status NOT IN ('idle', 'working', 'error')"
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass
            for column in (
                "project_id",
                "opencode_project_id",
                "codex_project_id",
                "codex_worktree",
                "phase",
                "phase_status",
                "phase_note",
                "note_path",
            ):
                if column in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE tasks DROP COLUMN {column}"))
                    except Exception:  # noqa: BLE001
                        pass
        conn.commit()


def _migrate_removed_task_types(engine: Any) -> None:
    """Rewrite task_type values that no longer exist."""

    inspector = inspect(engine)
    with engine.connect() as conn:
        if inspector.has_table("tasks"):
            existing = {c["name"] for c in inspector.get_columns("tasks")}
            if "task_type" in existing:
                conn.execute(
                    text("UPDATE tasks SET task_type = 'reminder' WHERE task_type = 'human'")
                )
        conn.commit()


def _default_clause(column: Any) -> str:
    default = getattr(column, "default", None)
    if default is None:
        default = column.server_default
    if default is None:
        # SQLite needs a default for ADD COLUMN on some versions.
        if _is_string_type(column):
            return " DEFAULT ''"
        if _is_numeric_type(column):
            return " DEFAULT 0"
        return ""
    arg = getattr(default, "arg", None)
    if arg is None:
        return ""
    if isinstance(arg, (int, float)):
        return f" DEFAULT {arg}"
    if isinstance(arg, bool):
        return f" DEFAULT {1 if arg else 0}"
    text_value = str(arg).replace("'", "''")
    return f" DEFAULT '{text_value}'"


def _is_string_type(column: Any) -> bool:
    type_name = type(column.type).__name__.lower()
    return (
        "text" in type_name
        or "string" in type_name
        or "varchar" in type_name
        or "char" in type_name
    )


def _is_numeric_type(column: Any) -> bool:
    type_name = type(column.type).__name__.lower()
    return (
        "int" in type_name
        or "numeric" in type_name
        or "float" in type_name
        or "decimal" in type_name
        or "real" in type_name
    )


def _is_simple_addable(column: Any) -> bool:  # pragma: no cover - kept for future strictness
    return not column.primary_key and not column.foreign_keys and not column.unique
