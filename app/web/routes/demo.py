from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.content.use_cases.demo_data import get_demo_data, get_role, list_roles
from app.cv_export.adapters.template_registry import (
    get_region,
    get_template,
    list_regions,
    list_templates,
    list_templates_by_category,
)
from app.web.templates import templates

router = APIRouter(prefix="/demo", redirect_slashes=False)


@router.get("")
async def demo_index(request: Request):
    """Browse all available templates by region."""
    return templates.TemplateResponse("demo_index.html", {
        "request": request,
        "regions": list_regions(),
        "templates": list_templates(),
        "roles": list_roles(),
        "page_description": f"Browse QuillCV's {len(list_templates())} professional CV templates across 12 country formats. See how templates adapt to regional conventions like photo requirements, page length, and date formats.",
    })


@router.get("/{country_code}")
async def demo_country(request: Request, country_code: str):
    """Show all templates available for a specific country."""
    country_code = country_code.upper()
    region = get_region(country_code)
    if not region:
        return HTMLResponse(f"Unknown country code: {country_code}", status_code=404)

    country_templates = list_templates(region=country_code)

    # Group by category
    available_ids = {t.id for t in country_templates}
    grouped = {}
    for cat in ["region", "universal", "industry", "specialty"]:
        cat_templates = [t for t in list_templates_by_category(cat) if t.id in available_ids]
        if cat_templates:
            grouped[cat] = cat_templates

    photo_note = (
        "photo required" if region.include_photo == "required"
        else f"photo {region.include_photo}" if region.include_photo != "no"
        else "no photo"
    )
    return templates.TemplateResponse("demo_country.html", {
        "request": request,
        "region": region,
        "templates": country_templates,
        "grouped_templates": grouped,
        "roles": list_roles(),
        "all_regions": list_regions(),
        "page_description": f"See how QuillCV templates adapt to {region.name} CV conventions. {region.page_length}, {region.date_format} dates, {photo_note}.",
    })


@router.get("/{country_code}/{template_id}")
async def demo_preview(
    request: Request,
    country_code: str,
    template_id: str,
    role: str = "software-engineer",
):
    """Render a full CV demo for a specific country + template + role."""
    country_code = country_code.upper()
    region = get_region(country_code)
    template = get_template(template_id)
    selected_role = get_role(role)

    if not region:
        return HTMLResponse(f"Unknown country code: {country_code}", status_code=404)
    if not template:
        return HTMLResponse(f"Unknown template: {template_id}", status_code=404)
    if country_code not in template.regions:
        return HTMLResponse(
            f"Template '{template_id}' is not available for {region.name}",
            status_code=404,
        )

    demo_data = get_demo_data(country_code, role)

    current_role = selected_role or get_role("software-engineer")
    return templates.TemplateResponse("demo_preview.html", {
        "request": request,
        "region": region,
        "template": template,
        "demo": demo_data,
        "roles": list_roles(),
        "current_role": current_role,
        "page_description": f"Preview the {template.name} CV template formatted for {region.name}. {current_role.name} role demo with {region.name}-specific formatting conventions.",
    })


@router.get("/{country_code}/{template_id}/raw")
async def demo_raw(
    request: Request,
    country_code: str,
    template_id: str,
    role: str = "software-engineer",
):
    """Render just the CV template (no wrapper) — for PDF generation or iframe."""
    country_code = country_code.upper()
    region = get_region(country_code)
    template = get_template(template_id)

    if not region or not template:
        return HTMLResponse("Not found", status_code=404)

    demo_data = get_demo_data(country_code, role)

    return templates.TemplateResponse(f"cv_templates/{template_id}.html", {
        "request": request,
        **demo_data,
    })
