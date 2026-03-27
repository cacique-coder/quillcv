"""Ports (interfaces) for the CV export domain."""
from typing import Protocol


class PDFRendererPort(Protocol):
    async def render(self, html: str) -> bytes | None: ...


class DocxRendererPort(Protocol):
    def render(self, cv_data: dict, region_code: str = "AU", template_id: str = "classic") -> bytes: ...
