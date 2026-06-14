from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Employee:
    id: int
    telegram_id: Optional[int]
    name: str
    role: str
    base_salary: int
    amo_id: Optional[int]
    is_active: bool
    hire_date: Optional[str]
    created_at: str


@dataclass
class Project:
    id: int
    title: str
    client_name: str
    amo_lead_id: Optional[int]
    stage: str
    budget: int
    paid_amount: int
    deadline: Optional[str]
    assigned_to: Optional[int]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str


@dataclass
class Invoice:
    id: int
    client_name: str
    project_id: Optional[int]
    amount: int
    paid_amount: int
    due_date: Optional[str]
    status: str
    notes: Optional[str]
    created_at: str


@dataclass
class Expense:
    id: int
    category: str
    description: Optional[str]
    amount: int
    expense_date: str
    recorded_by: Optional[int]
    created_at: str


@dataclass
class Advance:
    id: int
    employee_id: int
    amount: int
    reason: Optional[str]
    approved_by: Optional[int]
    status: str
    requested_at: str
    processed_at: Optional[str]


@dataclass
class KPIScore:
    id: int
    employee_id: int
    period: str
    leads_handled: int
    deals_closed: int
    revenue_generated: int
    score: float
    notes: Optional[str]
    created_at: str


@dataclass
class ERPSnapshot:
    period: str
    total_revenue: int
    total_expenses: int
    net_profit: int
    outstanding_invoices: int
    outstanding_amount: int
    pending_advances: int
    pending_advance_total: int
    active_projects: int
    active_employees: int
    top_expenses: list[dict] = field(default_factory=list)


_CREATE_EMPLOYEES = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    base_salary INTEGER DEFAULT 0,
    amo_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    hire_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_PROJECTS = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    amo_lead_id INTEGER,
    stage TEXT NOT NULL DEFAULT 'brief',
    budget INTEGER DEFAULT 0,
    paid_amount INTEGER DEFAULT 0,
    deadline TEXT,
    assigned_to INTEGER,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    project_id INTEGER,
    amount INTEGER NOT NULL,
    paid_amount INTEGER DEFAULT 0,
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_EXPENSES = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    description TEXT,
    amount INTEGER NOT NULL,
    expense_date TEXT DEFAULT (date('now')),
    recorded_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_ADVANCES = """
CREATE TABLE IF NOT EXISTS advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT,
    approved_by INTEGER,
    status TEXT DEFAULT 'pending',
    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT
)
"""

_CREATE_KPI_SCORES = """
CREATE TABLE IF NOT EXISTS kpi_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    leads_handled INTEGER DEFAULT 0,
    deals_closed INTEGER DEFAULT 0,
    revenue_generated INTEGER DEFAULT 0,
    score REAL DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_MIGRATIONS = [
    _CREATE_EMPLOYEES,
    _CREATE_PROJECTS,
    _CREATE_INVOICES,
    _CREATE_EXPENSES,
    _CREATE_ADVANCES,
    _CREATE_KPI_SCORES,
]


async def init_erp_tables(db) -> None:
    for ddl in _MIGRATIONS:
        await db.execute(ddl)
    await db.commit()
