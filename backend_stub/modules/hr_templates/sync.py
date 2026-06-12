"""Sync platform HR templates from catalog — auto version bumps when law/content changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.hr_templates.catalog import TEMPLATE_CATALOG
from modules.hr_templates.versioning import content_sha256, version_gt


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_platform_row(cur: Any, template_id: str) -> tuple | None:
    cur.execute(
        """
        SELECT id, version, content_sha256, content_markdown, title
        FROM hr_process_templates WHERE id = %s
        """,
        (template_id,),
    )
    return cur.fetchone()


def _insert_revision(cur: Any, entry: dict[str, Any], *, published_at: datetime) -> None:
    cur.execute(
        """
        INSERT INTO hr_template_revisions (
          template_id, version, title, content_markdown, legal_basis,
          change_summary, content_sha256, published_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (template_id, version) DO UPDATE SET
          title = EXCLUDED.title,
          content_markdown = EXCLUDED.content_markdown,
          legal_basis = EXCLUDED.legal_basis,
          change_summary = EXCLUDED.change_summary,
          content_sha256 = EXCLUDED.content_sha256,
          published_at = EXCLUDED.published_at
        """,
        (
            entry["id"],
            entry["version"],
            entry["title"],
            entry["content_markdown"],
            entry.get("legal_basis", ""),
            entry.get("change_summary", ""),
            content_sha256(entry["content_markdown"]),
            published_at,
        ),
    )


def sync_catalog_entry(cur: Any, entry: dict[str, Any], *, published_at: datetime | None = None) -> str:
    """Upsert one catalog template. Returns: created | updated | unchanged."""
    published = published_at or _utcnow()
    digest = content_sha256(entry["content_markdown"])
    existing = _fetch_platform_row(cur, entry["id"])

    if not existing:
        cur.execute(
            """
            INSERT INTO hr_process_templates (
              id, category, title, description, content_markdown, sort_order, version,
              legal_basis, change_summary, published_at, content_sha256,
              source, source_url, source_label
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry["id"],
                entry["category"],
                entry["title"],
                entry["description"],
                entry["content_markdown"],
                entry["sort_order"],
                entry["version"],
                entry.get("legal_basis", ""),
                entry.get("change_summary", ""),
                published,
                digest,
                entry.get("source", "shiftswift"),
                entry.get("source_url"),
                entry.get("source_label"),
            ),
        )
        _insert_revision(cur, entry, published_at=published)
        return "created"

    _existing_id, old_version, old_digest, old_content, old_title = existing
    version_changed = version_gt(entry["version"], old_version) or entry["version"] != old_version
    content_changed = digest != old_digest

    if not version_changed and not content_changed:
        return "unchanged"

    if content_changed or version_changed:
        _insert_revision(cur, entry, published_at=published)

    cur.execute(
        """
        UPDATE hr_process_templates SET
          category = %s,
          title = %s,
          description = %s,
          content_markdown = %s,
          sort_order = %s,
          version = %s,
          legal_basis = %s,
          change_summary = %s,
          published_at = %s,
          content_sha256 = %s,
          source = %s,
          source_url = %s,
          source_label = %s,
          updated_at = NOW()
        WHERE id = %s
        """,
        (
            entry["category"],
            entry["title"],
            entry["description"],
            entry["content_markdown"],
            entry["sort_order"],
            entry["version"],
            entry.get("legal_basis", ""),
            entry.get("change_summary", ""),
            published,
            digest,
            entry.get("source", "shiftswift"),
            entry.get("source_url"),
            entry.get("source_label"),
            entry["id"],
        ),
    )

    return "updated"


def sync_all_templates(*, conn: Any) -> dict[str, Any]:
    summary = {"created": 0, "updated": 0, "unchanged": 0, "templates": []}
    published_at = _utcnow()
    with conn.cursor() as cur:
        for entry in TEMPLATE_CATALOG:
            result = sync_catalog_entry(cur, entry, published_at=published_at)
            summary[result] += 1
            summary["templates"].append({"id": entry["id"], "version": entry["version"], "status": result})
    conn.commit()
    return summary


def list_template_revisions(*, template_id: str, conn: Any, limit: int = 20) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT version, title, legal_basis, change_summary, published_at
            FROM hr_template_revisions
            WHERE template_id = %s
            ORDER BY published_at DESC, version DESC
            LIMIT %s
            """,
            (template_id, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "version": row[0],
            "title": row[1],
            "legal_basis": row[2],
            "change_summary": row[3],
            "published_at": row[4].isoformat() if row[4] else None,
        }
        for row in rows
    ]


def build_download_markdown(
    *,
    title: str,
    content_markdown: str,
    version: str,
    variant: str,
    legal_basis: str,
    change_summary: str,
    published_at: str | None,
    platform_version: str | None = None,
    based_on_version: str | None = None,
    update_available: bool = False,
) -> str:
    lines = [
        f"# {title}",
        "",
        "## Document information",
        "",
        f"- **Publisher:** ShiftSwift HR (shiftswifthr.co.uk)",
        f"- **Template version:** v{version}",
        f"- **Download type:** {'Platform latest (recommended)' if variant == 'platform' else 'Your organisation copy'}",
    ]
    if published_at:
        lines.append(f"- **Published:** {published_at[:10]}")
    if legal_basis:
        lines.append(f"- **Legal / guidance reference:** {legal_basis}")
    if change_summary:
        lines.append(f"- **What changed in this version:** {change_summary}")
    if variant == "custom" and platform_version and based_on_version:
        lines.append(f"- **Based on platform release:** v{based_on_version}")
        if update_available and version_gt(platform_version, based_on_version):
            lines.append(
                f"- **⚠ Platform update available:** v{platform_version} — apply update in admin before relying on this copy"
            )
    lines.extend(
        [
            "",
            "_This template supports HR administration only. It is not legal advice. Review with qualified counsel._",
            "",
            "---",
            "",
            content_markdown,
            "",
        ]
    )
    return "\n".join(lines)
