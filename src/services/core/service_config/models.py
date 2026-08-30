"""
Data models and Enums for Service Configurator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ServiceType(Enum):
    """Jon.Branding xizmat turlari"""

    BRAND_AUDIT = "brand_audit"
    NAMING_CHECK = "naming_check"
    NAMING = "naming"
    LOGO = "logo"
    VISUAL_IDENTITY = "visual_identity"
    BRANDBOOK = "brandbook"
    PACKAGING = "packaging"
    PATENT_SUPPORT = "patent_support"


@dataclass
class ServiceModule:
    """Xizmat moduli"""

    id: str
    name: str
    name_uz: str
    service_type: ServiceType
    base_price: int
    estimated_days: int
    deliverables: List[str] = field(default_factory=list)
    includes_phases: List[str] = field(default_factory=list)
    total_steps: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_uz": self.name_uz,
            "type": self.service_type.value,
            "price": self.base_price,
            "days": self.estimated_days,
            "deliverables": self.deliverables,
            "total_steps": self.total_steps,
        }
