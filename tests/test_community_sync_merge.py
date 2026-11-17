from src.services.core.community_sync.merge import (
    Change, absorb, merge_field, plan, resolve,
)
from src.services.core.community_sync.models import Person


def P(key, **kw):
    return Person(key=key, **kw)


def test_resolve_by_tg_id_then_phone_then_username():
    people = [P("a", tg_id=1), P("b", phone="+998901112233"), P("c", username="ali")]
    assert resolve(people, P("x", tg_id=1)).key == "a"
    assert resolve(people, P("x", phone="+998901112233")).key == "b"
    assert resolve(people, P("x", username="ALI")).key == "c"
    assert resolve(people, P("x", first_name="Ali")) is None


def test_merge_across_groups():
    people: list[Person] = []
    for cohort, phone in (("TN7", ""), ("3K7", "+998901112233"), ("S:Toshkent 7", "")):
        inc = P("tg:5", tg_id=5, first_name="Ali", phone=phone, cohorts={cohort})
        hit = resolve(people, inc)
        if hit:
            absorb(hit, inc)
        else:
            people.append(inc)
    assert len(people) == 1
    assert people[0].phone == "+998901112233"
    assert people[0].cohorts == {"TN7", "3K7", "S:Toshkent 7"}


def test_one_system_changed():
    assert merge_field({"g": "Ali", "a": "Ali"}, {"g": "Aliy", "a": "Ali"}) == ("Aliy", None)


def test_no_change():
    assert merge_field({"g": "Ali"}, {"g": "Ali"}) == (None, None)


def test_same_change_two_systems():
    assert merge_field({"g": "A", "a": "A"}, {"g": "B", "a": "B"}) == ("B", None)


def test_conflict_two_systems():
    v, c = merge_field({"g": "A", "a": "A"}, {"g": "B", "a": "C"})
    assert v is None and c == {"g": "B", "a": "C"}


def test_empty_never_overwrites():
    assert merge_field({"g": "A"}, {"g": ""}) == (None, None)


def test_plan_propagates():
    canon = {"k": P("k", first_name="Ali", phone="+998901112233")}
    snaps = {s: {"k": {"phone": "+998901112233"}} for s in ("google", "amocrm")}
    reads = {
        "google": {"k": {"phone": "+998907778899"}},
        "amocrm": {"k": {"phone": "+998901112233"}},
        "telegram": {},
    }
    changes, conflicts = plan(canon, snaps, reads)
    phone = [c for c in changes if c.field == "phone"]
    assert {c.system for c in phone} == {"amocrm", "telegram"}
    assert all(c.value == "+998907778899" for c in phone)
    assert canon["k"].phone == "+998907778899" and not conflicts


def test_plan_conflict_blocks_field():
    canon = {"k": P("k", first_name="A")}
    snaps = {s: {"k": {"first_name": "A"}} for s in ("google", "amocrm")}
    reads = {"google": {"k": {"first_name": "B"}}, "amocrm": {"k": {"first_name": "C"}}}
    changes, conflicts = plan(canon, snaps, reads)
    assert not [c for c in changes if c.field == "first_name"]
    assert conflicts[0].field == "first_name" and canon["k"].first_name == "A"


def test_plan_idempotent():
    canon = {"k": P("k", first_name="A")}
    snaps = {"google": {"k": {"first_name": "A"}}}
    reads = {"google": {"k": {"first_name": "A"}}}
    assert plan(canon, snaps, reads) == ([], [])
