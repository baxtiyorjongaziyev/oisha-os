"""
Data models for Contract Generation and Legal Automation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ContractTemplate:
    """Shartnoma shabloni"""

    name: str
    service_type: str
    base_template: str
    clauses: List[Dict[str, str]]
    variables: List[str]
