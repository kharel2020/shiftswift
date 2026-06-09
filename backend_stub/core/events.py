"""Domain event outbox — cross-module triggers for compliance and grievance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from modules.events.listeners import dispatch_event


def emit_event(
    *,
    conn: Any,
    tenant_id: int,
    event_type: str,
    payload: dict[str, Any],
    actor_username: str | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    process_immediately: bool = True,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO domain_events (
              tenant_id, event_type, entity_type, entity_id, payload,
              actor_username, actor_role
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (
                tenant_id,
                event_type,
                entity_type,
                entity_id,
                json.dumps(payload),
                actor_username,
                actor_role,
            ),
        )
        event_id = int(cur.fetchone()[0])
    conn.commit()

    if process_immediately:
        process_event(
            conn=conn,
            event_id=event_id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
            actor_username=actor_username,
            actor_role=actor_role,
        )
    return event_id


def process_event(
    *,
    conn: Any,
    event_id: int,
    tenant_id: int,
    event_type: str,
    payload: dict[str, Any],
    actor_username: str | None,
    actor_role: str | None,
) -> None:
    dispatch_event(
        conn=conn,
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
        actor_username=actor_username,
        actor_role=actor_role,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE domain_events
            SET processed = TRUE, processed_at = %s
            WHERE id = %s
            """,
            (datetime.now(timezone.utc), event_id),
        )
    conn.commit()


def process_pending_events(*, conn: Any, limit: int = 100) -> int:
    processed = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, event_type, entity_type, entity_id, payload,
                   actor_username, actor_role
            FROM domain_events
            WHERE processed = FALSE
            ORDER BY created_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        )
        rows = cur.fetchall()

    for row in rows:
        event_id, tenant_id, event_type, _entity_type, _entity_id, payload, actor_username, actor_role = row
        if isinstance(payload, str):
            payload = json.loads(payload)
        process_event(
            conn=conn,
            event_id=event_id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload or {},
            actor_username=actor_username,
            actor_role=actor_role,
        )
        processed += 1
    return processed
