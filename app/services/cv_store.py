"""Store and retrieve generated CV content as sanitized markdown.

Converts rendered HTML CVs to clean markdown and stores them in the database
alongside the structured cv_data JSON. This allows reusing content without
re-generating via AI, saving API costs.
"""

import json
import logging
import re

import markdownify
import nh3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SavedCV

logger = logging.getLogger(__name__)

# nh3 allowlist — strip everything to get pure text structure
_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "strong", "em", "b", "i",
    "a", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td",
}
_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href"},
}


def html_to_markdown(rendered_html: str) -> str:
    """Convert rendered CV HTML to clean, sanitized markdown.

    1. Strip <style> blocks (CSS from CV templates)
    2. Sanitize HTML with nh3 (remove scripts, event handlers, etc.)
    3. Convert to markdown
    4. Clean up whitespace
    """
    # Remove style blocks before sanitization
    html = re.sub(r'<style[^>]*>.*?</style>', '', rendered_html, flags=re.DOTALL)

    # Sanitize — removes scripts, onclick, onerror, data URIs, etc.
    clean_html = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener",
        url_schemes={"http", "https", "mailto"},
    )

    # Convert to markdown
    md = markdownify.markdownify(
        clean_html,
        heading_style="ATX",
        bullets="-",
        strip=["img"],
    )

    # Clean up excessive whitespace
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = md.strip()

    return md


async def save_cv(
    db: AsyncSession,
    *,
    attempt_id: str,
    source: str,
    region: str,
    template_id: str,
    rendered_html: str,
    cv_data: dict,
    user_id: str | None = None,
    label: str = "",
    job_title: str = "",
) -> SavedCV:
    """Convert rendered HTML to markdown and store in database."""
    markdown = html_to_markdown(rendered_html)

    # Strip internal metadata from stored JSON
    data_copy = {k: v for k, v in cv_data.items() if not k.startswith("_")}

    saved = SavedCV(
        user_id=user_id,
        attempt_id=attempt_id,
        source=source,
        label=label,
        job_title=job_title,
        region=region,
        template_id=template_id,
        markdown=markdown,
        cv_data_json=json.dumps(data_copy, default=str),
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)

    logger.info("Saved CV %s (source=%s, attempt=%s)", saved.id, source, attempt_id)
    return saved


async def update_cv(
    db: AsyncSession,
    *,
    cv_id: str,
    region: str,
    template_id: str,
    rendered_html: str,
    cv_data: dict,
    label: str = "",
    job_title: str = "",
) -> SavedCV | None:
    """Update an existing saved CV."""
    result = await db.execute(select(SavedCV).where(SavedCV.id == cv_id))
    saved = result.scalar_one_or_none()
    if not saved:
        return None

    markdown = html_to_markdown(rendered_html)
    data_copy = {k: v for k, v in cv_data.items() if not k.startswith("_")}

    saved.region = region
    saved.template_id = template_id
    saved.markdown = markdown
    saved.cv_data_json = json.dumps(data_copy, default=str)
    if label:
        saved.label = label
    if job_title:
        saved.job_title = job_title

    await db.commit()
    await db.refresh(saved)
    logger.info("Updated CV %s", saved.id)
    return saved


async def get_saved_cv(db: AsyncSession, saved_cv_id: str) -> SavedCV | None:
    """Retrieve a saved CV by ID."""
    result = await db.execute(select(SavedCV).where(SavedCV.id == saved_cv_id))
    return result.scalar_one_or_none()


async def list_saved_cvs(
    db: AsyncSession,
    user_id: str | None = None,
    attempt_id: str | None = None,
) -> list[SavedCV]:
    """List saved CVs, optionally filtered by user or attempt."""
    query = select(SavedCV).order_by(SavedCV.created_at.desc())
    if user_id:
        query = query.where(SavedCV.user_id == user_id)
    if attempt_id:
        query = query.where(SavedCV.attempt_id == attempt_id)
    result = await db.execute(query)
    return list(result.scalars().all())
