"""CV export domain entities.

Dataclass definitions for CVTemplate and RegionConfig.
These are imported by app/cv_export/adapters/template_registry.py and can be
used directly by any code that needs the entity types without importing the
full registry data.

TODO: Extract CVTemplate and RegionConfig from template_registry.py into this
module and update template_registry.py to import them from here. Currently the
dataclasses live in template_registry.py and this file serves as a placeholder
documenting that intent.
"""

from app.cv_export.adapters.template_registry import CVTemplate, RegionConfig

__all__ = ["CVTemplate", "RegionConfig"]
