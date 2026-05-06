#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = repo_root / "sensor_data.db"
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    tables = [
        "annotations",
        "work_order_filling_attachments",
        "work_order_fillings",
        "escalations",
        "approval_tasks",
        "work_order_messages",
        "retrieval_snapshots",
        "work_order_events",
        "attachments",
        "knowledge_articles",
        "audit_logs",
        "work_orders",
    ]

    def exists(t: str) -> bool:
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,))
        return cur.fetchone() is not None

    def count(t: str) -> int:
        if t == "attachments":
            cur.execute("SELECT COUNT(*) FROM attachments WHERE work_order_id IS NOT NULL")
        elif t == "knowledge_articles":
            cur.execute("SELECT COUNT(*) FROM knowledge_articles WHERE source_work_order_id IS NOT NULL")
        elif t == "audit_logs":
            cur.execute("SELECT COUNT(*) FROM audit_logs WHERE resource_type='work_order'")
        else:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
        return int(cur.fetchone()[0])

    before: dict[str, int] = {}
    for t in tables:
        if exists(t):
            before[t] = count(t)

    # delete children first
    if exists("annotations"):
        cur.execute("DELETE FROM annotations")
    if exists("work_order_filling_attachments"):
        cur.execute("DELETE FROM work_order_filling_attachments")
    if exists("work_order_fillings"):
        cur.execute("DELETE FROM work_order_fillings")
    if exists("escalations"):
        cur.execute("DELETE FROM escalations")
    if exists("approval_tasks"):
        cur.execute("DELETE FROM approval_tasks")
    if exists("work_order_messages"):
        cur.execute("DELETE FROM work_order_messages")
    if exists("retrieval_snapshots"):
        cur.execute("DELETE FROM retrieval_snapshots")
    if exists("work_order_events"):
        cur.execute("DELETE FROM work_order_events")
    if exists("attachments"):
        cur.execute("DELETE FROM attachments WHERE work_order_id IS NOT NULL")
    if exists("knowledge_articles"):
        cur.execute("DELETE FROM knowledge_articles WHERE source_work_order_id IS NOT NULL")
    if exists("audit_logs"):
        cur.execute("DELETE FROM audit_logs WHERE resource_type='work_order'")
    if exists("work_orders"):
        cur.execute("DELETE FROM work_orders")

    conn.commit()

    after = {t: count(t) for t in before}
    print("BEFORE=", before)
    print("AFTER=", after)


if __name__ == "__main__":
    main()

