"""
Application boot and initialization logic.
Facade delegating to modular subpackage in src.bootstrap.
Provides init_hisobchi_tables initialization and m.handle_new_message handler setup.
"""
from src.bootstrap import (
    boot_application,
    _command_processor,
    _negotiation_int,
    _surgical_send,
)

__all__ = [
    "boot_application",
    "_command_processor",
    "_negotiation_int",
    "_surgical_send",
]
