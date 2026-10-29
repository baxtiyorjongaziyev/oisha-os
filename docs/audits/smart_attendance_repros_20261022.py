"""Synthetic, isolated audit reproductions; no operational data or network."""
from datetime import date, datetime

import pytest

from test_attendance_flow import ALI, TZ5, _full, _fix, _qr, env, run
from src.services.core.attendance import admin, repo, summary
from src.services.core.attendance.service import AttendanceError


def test_overnight_db_assignment_checkout(env):
    db, svc, clock, _ = env
    run(admin.set_schedule(db, actor='synthetic-reviewer', employee_id=1,
                          weekdays=[1,2,3,4,5,6,7], start='22:00', end='06:00',
                          valid_from='2026-10-01'))
    clock.t = datetime(2026,10,22,22,0,tzinfo=TZ5)
    _full(svc,db,clock,key='synthetic-night-in')
    clock.t = datetime(2026,10,23,2,0,tzinfo=TZ5)
    session = run(svc.start(ALI,'check_out','synthetic-night-out'))
    assert session['work_date'] == '2026-10-22'


def test_pending_review_hours_excluded(env):
    db,svc,clock,_ = env
    clock.t = datetime(2026,10,22,10,0,tzinfo=TZ5)
    _full(svc,db,clock,key='synthetic-pending-in',mocked=True)
    clock.t = datetime(2026,10,22,19,0,tzinfo=TZ5)
    _full(svc,db,clock,kind='check_out',key='synthetic-pending-out',mocked=True)
    db.conn.execute("UPDATE geofences SET created_at='2026-10-01 00:00:00'")
    rows=run(summary.period_summary(db,date(2026,10,22),date(2026,10,22),today=date(2026,10,22)))
    ali=next(r for r in rows if r['employee_id']==1)
    assert ali['worked_minutes']==0, ali


def test_failed_gps_not_reported_as_passed(env):
    db,svc,clock,_=env
    _full(svc,db,clock,key='synthetic-gps-review',mocked=True)
    import json
    event=db.conn.execute('SELECT verification_summary FROM attendance_events').fetchone()
    assert json.loads(event[0])['gps'] is False


def test_other_request_commit_cannot_orphan_confirm(env):
    db,svc,clock,_=env
    s=run(svc.start(ALI,'check_in','synthetic-atomic'))
    run(svc.submit_location(s['id'],ALI,_fix(clock)))
    run(svc.submit_qr(s['id'],ALI,_qr(db,clock)))
    original=db.execute
    async def interleaving_commit(sql,p=None):
        if sql.startswith('INSERT INTO attendance_events'):
            await db.commit()  # models another request committing the same pool connection
            raise RuntimeError('synthetic write failure after concurrent commit')
        return await original(sql,p)
    db.execute=interleaving_commit
    with pytest.raises(RuntimeError):
        run(svc.confirm(s['id'],ALI))
    db.execute=original
    retry=run(svc.confirm(s['id'],ALI))
    assert db.conn.execute('SELECT count(*) FROM attendance_events').fetchone()[0]==1, retry


def test_qr_recovery_after_session_update_failure(env):
    db,svc,clock,_=env
    s=run(svc.start(ALI,'check_in','synthetic-qr-retry'))
    run(svc.submit_location(s['id'],ALI,_fix(clock)))
    token=_qr(db,clock)
    original=db.execute
    async def fail_transition(sql,p=None):
        if sql.startswith('UPDATE attendance_sessions SET state'):
            raise RuntimeError('synthetic transient write failure')
        return await original(sql,p)
    db.execute=fail_transition
    with pytest.raises(RuntimeError):
        run(svc.submit_qr(s['id'],ALI,token))
    db.execute=original
    run(svc.submit_qr(s['id'],ALI,_qr(db,clock)))
    assert run(repo.get_session(db,s['id']))['state']=='qr_ok'


def test_correction_absent_removes_presence_and_hours(env):
    db,svc,clock,_=env
    from src.services.core.attendance import reports, rules
    clock.t=datetime(2026,10,22,10,0,tzinfo=TZ5)
    _full(svc,db,clock,key='synthetic-correction-in')
    clock.t=datetime(2026,10,22,19,0,tzinfo=TZ5)
    _full(svc,db,clock,kind='check_out',key='synthetic-correction-out')
    event=db.conn.execute("SELECT id FROM attendance_events WHERE kind='check_in'").fetchone()[0]
    run(admin.apply_correction(db,actor='synthetic-reviewer',employee_id=1,
        work_date='2026-10-22',new_status='ABSENT',reason='synthetic rejected evidence',event_id=event))
    dashboard=run(reports.dashboard(db,date(2026,10,22),rules.Calendar()))
    assert dashboard['present']==0, dashboard


def test_approved_leave_removed_from_dashboard_absence(env):
    db,svc,clock,_=env
    from src.services.core.attendance import reports,rules
    run(admin.apply_correction(db,actor='synthetic-reviewer',employee_id=1,
        work_date='2026-10-22',new_status='APPROVED_LEAVE',reason='synthetic leave approval'))
    dashboard=run(reports.dashboard(db,date(2026,10,22),rules.Calendar()))
    assert dashboard['absent']==1, dashboard  # only second synthetic employee expected
