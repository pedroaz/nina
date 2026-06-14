from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from nina_core.models.models import KanbanColumn, Task

COLUMN_STATUS = {
    "Backlog": "backlog",
    "Todo": "todo",
    "Doing": "doing",
    "Review": "review",
    "Done": "done",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_kanban_board(db: Session) -> dict[str, Any]:
    columns = db.query(KanbanColumn).order_by(KanbanColumn.position).all()
    tasks = db.query(Task).filter(Task.status.notin_(["deleted", "archived"])).order_by(Task.kanban_position).all()
    board: dict[str, Any] = {}
    for col in columns:
        board[col.name] = []
    for task in tasks:
        if task.kanban_column in board:
            board[task.kanban_column].append(task)
    return board


def move_task(db: Session, task_id: str, to_column: str, to_position: int) -> Task | None:
    if to_column not in COLUMN_STATUS:
        return None
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None
    to_position = max(0, to_position)
    from_column = task.kanban_column
    from_position = task.kanban_position
    if from_column == to_column and from_position == to_position:
        return task
    if from_column == to_column:
        if from_position < to_position:
            tasks_between = (
                db.query(Task)
                .filter(Task.kanban_column == from_column)
                .filter(Task.kanban_position > from_position)
                .filter(Task.kanban_position <= to_position)
                .all()
            )
            for t in tasks_between:
                t.kanban_position -= 1
        else:
            tasks_between = (
                db.query(Task)
                .filter(Task.kanban_column == from_column)
                .filter(Task.kanban_position >= to_position)
                .filter(Task.kanban_position < from_position)
                .all()
            )
            for t in tasks_between:
                t.kanban_position += 1
    else:
        tasks_after = (
            db.query(Task)
            .filter(Task.kanban_column == from_column)
            .filter(Task.kanban_position > from_position)
            .all()
        )
        for t in tasks_after:
            t.kanban_position -= 1
        tasks_at_target = (
            db.query(Task)
            .filter(Task.kanban_column == to_column)
            .filter(Task.kanban_position >= to_position)
            .all()
        )
        for t in tasks_at_target:
            t.kanban_position += 1
    task.kanban_column = to_column
    task.kanban_position = to_position
    task.status = COLUMN_STATUS[to_column]
    task.updated_at = _now()
    db.commit()
    return task
