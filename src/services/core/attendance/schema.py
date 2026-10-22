"""Smart Attendance jadvallari (Turso/SQLite).

Mavjud ``employees`` jadvaliga (finance/erp_schema.py) faqat FK orqali bog'lanadi,
unga tegilmaydi. Barcha DDL idempotent: ``IF NOT EXISTS``.

Himoya cheklovlari:
- dublikat check-in: ``attendance_sessions`` da UNIQUE(employee_id, work_date, kind)
- QR replay: ``qr_challenges.nonce`` UNIQUE + ``qr_redemptions`` UNIQUE(challenge, employee)
- parallel so'rov: sessiya ``version`` ustuni bilan shartli UPDATE
"""
from __future__ import annotations

SESSION_KINDS = ("check_in", "check_out")
SESSION_STATES = ("created", "location_ok", "qr_ok", "face_ok", "confirmed", "rejected", "expired")
ATTENDANCE_STATUSES = (
    "ON_TIME", "LATE", "EARLY_LEAVE", "ABSENT",
    "APPROVED_LEAVE", "DAY_OFF", "PENDING_REVIEW",
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


_CREATE_BRANCHES = """
CREATE TABLE IF NOT EXISTS attendance_branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Tashkent',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_GEOFENCES = """
CREATE TABLE IF NOT EXISTS geofences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER NOT NULL REFERENCES attendance_branches(id),
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    radius_m INTEGER NOT NULL CHECK (radius_m BETWEEN 10 AND 5000),
    max_accuracy_m INTEGER NOT NULL DEFAULT 50,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_POLICIES = """
CREATE TABLE IF NOT EXISTS attendance_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER REFERENCES attendance_branches(id),
    grace_minutes INTEGER NOT NULL DEFAULT 10 CHECK (grace_minutes BETWEEN 0 AND 120),
    early_leave_grace_minutes INTEGER NOT NULL DEFAULT 0,
    require_face INTEGER NOT NULL DEFAULT 1,
    qr_ttl_seconds INTEGER NOT NULL DEFAULT 30 CHECK (qr_ttl_seconds BETWEEN 10 AND 300),
    session_ttl_seconds INTEGER NOT NULL DEFAULT 300,
    biometric_retention_days INTEGER NOT NULL DEFAULT 365,
    location_retention_days INTEGER NOT NULL DEFAULT 90,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_SHIFTS = """
CREATE TABLE IF NOT EXISTS attendance_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER NOT NULL REFERENCES attendance_branches(id),
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    crosses_midnight INTEGER NOT NULL DEFAULT 0,
    weekdays TEXT NOT NULL DEFAULT '1,2,3,4,5,6',
    optional_weekdays TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    UNIQUE (branch_id, name)
)
"""

_CREATE_SHIFT_ASSIGNMENTS = """
CREATE TABLE IF NOT EXISTS shift_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    shift_id INTEGER NOT NULL REFERENCES attendance_shifts(id),
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (employee_id, shift_id, valid_from)
)
"""

_CREATE_SESSIONS = f"""
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id TEXT PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    branch_id INTEGER NOT NULL REFERENCES attendance_branches(id),
    shift_id INTEGER REFERENCES attendance_shifts(id),
    kind TEXT NOT NULL CHECK (kind IN ({_in(SESSION_KINDS)})),
    work_date TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'created' CHECK (state IN ({_in(SESSION_STATES)})),
    status TEXT CHECK (status IS NULL OR status IN ({_in(ATTENDANCE_STATUSES)})),
    idempotency_key TEXT UNIQUE,
    version INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    confirmed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

# Faqat tasdiqlangan sessiya dublikatni bloklaydi — muvaffaqiyatsiz urinishlar qayta boshlanishi mumkin.
_IDX_ONE_CONFIRMED = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_attendance_sessions_confirmed
ON attendance_sessions (employee_id, work_date, kind) WHERE state = 'confirmed'
"""

_CREATE_EVENTS = f"""
CREATE TABLE IF NOT EXISTS attendance_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE REFERENCES attendance_sessions(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    branch_id INTEGER NOT NULL REFERENCES attendance_branches(id),
    shift_id INTEGER REFERENCES attendance_shifts(id),
    kind TEXT NOT NULL CHECK (kind IN ({_in(SESSION_KINDS)})),
    work_date TEXT NOT NULL,
    server_ts TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ({_in(ATTENDANCE_STATUSES)})),
    minutes_late INTEGER NOT NULL DEFAULT 0,
    minutes_early INTEGER NOT NULL DEFAULT 0,
    verification_summary TEXT NOT NULL DEFAULT '{{}}'
)
"""

_CREATE_VERIFICATIONS = """
CREATE TABLE IF NOT EXISTS attendance_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES attendance_sessions(id),
    method TEXT NOT NULL CHECK (method IN ('gps', 'qr', 'face', 'manual')),
    passed INTEGER NOT NULL,
    score REAL,
    reason TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_QR_CHALLENGES = """
CREATE TABLE IF NOT EXISTS qr_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER NOT NULL REFERENCES attendance_branches(id),
    nonce TEXT NOT NULL UNIQUE,
    kiosk_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
)
"""

# Monitordagi bitta QR ni ko'p xodim skanerlaydi, lekin har xodim uni faqat bir marta ishlata oladi.
_CREATE_QR_REDEMPTIONS = """
CREATE TABLE IF NOT EXISTS qr_redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id INTEGER NOT NULL REFERENCES qr_challenges(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    session_id TEXT NOT NULL UNIQUE REFERENCES attendance_sessions(id),
    redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (challenge_id, employee_id)
)
"""

_CREATE_FACE_ENROLLMENTS = """
CREATE TABLE IF NOT EXISTS face_enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    provider TEXT NOT NULL,
    template_ciphertext BLOB,
    provider_ref TEXT,
    consent_version TEXT NOT NULL,
    consent_at TEXT NOT NULL,
    revoked_at TEXT,
    expires_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_IDX_ONE_ACTIVE_ENROLLMENT = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_face_enrollments_active
ON face_enrollments (employee_id) WHERE revoked_at IS NULL
"""

_CREATE_CORRECTIONS = f"""
CREATE TABLE IF NOT EXISTS attendance_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    work_date TEXT NOT NULL,
    event_id INTEGER REFERENCES attendance_events(id),
    new_status TEXT NOT NULL CHECK (new_status IN ({_in(ATTENDANCE_STATUSES)})),
    reason TEXT NOT NULL CHECK (length(reason) >= 5),
    requested_by TEXT NOT NULL,
    approved_by TEXT,
    state TEXT NOT NULL DEFAULT 'applied' CHECK (state IN ('pending', 'applied', 'rejected')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

# Audit faqat qo'shiladi (append-only); o'zgartirish/o'chirish triggerlar bilan bloklanadi.
_CREATE_AUDIT = """
CREATE TABLE IF NOT EXISTS attendance_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    ip TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_AUDIT_NO_UPDATE = """
CREATE TRIGGER IF NOT EXISTS trg_attendance_audit_no_update
BEFORE UPDATE ON attendance_audit_logs
BEGIN SELECT RAISE(ABORT, 'attendance_audit_logs is append-only'); END
"""

_AUDIT_NO_DELETE = """
CREATE TRIGGER IF NOT EXISTS trg_attendance_audit_no_delete
BEFORE DELETE ON attendance_audit_logs
BEGIN SELECT RAISE(ABORT, 'attendance_audit_logs is append-only'); END
"""

# Ofis monitori kalitlari: faqat sha256 xeshi saqlanadi, bekor qilish mumkin.
_CREATE_KIOSK_TOKENS = """
CREATE TABLE IF NOT EXISTS attendance_kiosk_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used_at TEXT,
    revoked_at TEXT
)
"""

# Telegram hisobini xodimga bog'lash so'rovlari (owner tasdiqlaydi).
_CREATE_LINK_REQUESTS = """
CREATE TABLE IF NOT EXISTS attendance_link_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'linked', 'rejected')),
    employee_id INTEGER REFERENCES employees(id),
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

# Ofis Wi-Fi: ofis internetining tashqi (public) IP manzillari. Xodim so'rovi shu IP dan
# kelsa — ofis Wi-Fi'siga ulangan hisoblanadi.
_CREATE_OFFICE_NETWORKS = """
CREATE TABLE IF NOT EXISTS attendance_office_networks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_geofences_branch ON geofences (branch_id)",
    "CREATE INDEX IF NOT EXISTS ix_shift_assign_emp ON shift_assignments (employee_id, valid_from)",
    "CREATE INDEX IF NOT EXISTS ix_att_sessions_emp_date ON attendance_sessions (employee_id, work_date)",
    "CREATE INDEX IF NOT EXISTS ix_att_events_date ON attendance_events (work_date, branch_id)",
    "CREATE INDEX IF NOT EXISTS ix_att_events_emp ON attendance_events (employee_id, work_date)",
    "CREATE INDEX IF NOT EXISTS ix_att_verif_session ON attendance_verifications (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_qr_branch_exp ON qr_challenges (branch_id, expires_at)",
    "CREATE INDEX IF NOT EXISTS ix_att_corr_emp ON attendance_corrections (employee_id, work_date)",
    "CREATE INDEX IF NOT EXISTS ix_att_audit_entity ON attendance_audit_logs (entity, entity_id)",
]

def _employees_ddl() -> str:
    # Mavjud ERP jadvali (finance/erp_schema.py) — bazada bo'lmasa yaratiladi, bo'lsa tegilmaydi.
    from src.services.core.finance.erp_schema import _CREATE_EMPLOYEES

    return _CREATE_EMPLOYEES


MIGRATIONS: list[str] = [
    _CREATE_BRANCHES,
    _CREATE_GEOFENCES,
    _CREATE_POLICIES,
    _CREATE_SHIFTS,
    _CREATE_SHIFT_ASSIGNMENTS,
    _CREATE_SESSIONS,
    _IDX_ONE_CONFIRMED,
    _CREATE_EVENTS,
    _CREATE_VERIFICATIONS,
    _CREATE_QR_CHALLENGES,
    _CREATE_QR_REDEMPTIONS,
    _CREATE_FACE_ENROLLMENTS,
    _IDX_ONE_ACTIVE_ENROLLMENT,
    _CREATE_CORRECTIONS,
    _CREATE_AUDIT,
    _AUDIT_NO_UPDATE,
    _AUDIT_NO_DELETE,
    _CREATE_KIOSK_TOKENS,
    _CREATE_LINK_REQUESTS,
    _CREATE_OFFICE_NETWORKS,
    *_INDEXES,
]


async def init_attendance_tables(db=None) -> None:
    """Jadvallarni yaratadi. ``db`` — ``execute``/``commit`` bor obyekt (default: db_pool)."""
    if db is None:
        from src.database_pool import db_pool as db
    for ddl in (_employees_ddl(), *MIGRATIONS):
        await db.execute(ddl)
    await db.commit()
