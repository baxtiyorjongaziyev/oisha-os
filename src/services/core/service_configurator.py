"""
Facade for Service Configurator.
Delegates to modular subpackage in src.services.core.service_config.
"""
from src.services.core.service_config.models import ServiceModule, ServiceType
from src.services.core.service_config.configurator import (
    ServiceConfigurator,
    get_service_configurator,
)

__all__ = [
    "ServiceType",
    "ServiceModule",
    "ServiceConfigurator",
    "get_service_configurator",
]
