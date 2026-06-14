"""Write platform master admin actions to master_audit_log."""

from __future__ import annotations

import json
from typing import Any

from config import Settings


def write_master_audit(
    settings: Settings,
    *,
    master_username: str,
    action: str,
    target_tenant_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: dict[str, Any] | None = None,
    conn: Any | None = None,
) -> None:
    if not settings.use_db or not settings.database_url:
        return

    owns_conn = conn is None
    if owns_conn:
        import psycopg2

        conn = psycopg2.connect(settings.database_url)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO master_audit_log
                  (master_username, action, target_tenant_id, ip_address, user_agent, detail)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    master_username,
                    action,
                    target_tenant_id,
                    ip_address,
                    user_agent,
                    json.dumps(detail or {}),
                ),
            )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn and conn is not None:
            conn.close()
