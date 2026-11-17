from src.services.core.community_sync.cohorts import Cohort, cohort_for_group
from src.services.core.community_sync.models import Person, display_name, labels_for


def person(first="Ali", last="Valiyev", cohorts=None):
    return Person(key="tg:1", tg_id=1, first_name=first, last_name=last,
                  cohorts=set(cohorts or {"TN7"}))


def test_cohort_tn():
    assert cohort_for_group("TEZ NATIJA 7") == Cohort("TN7", "TN7 Gr", "TEZ NATIJA 7")


def test_cohort_3k():
    c = cohort_for_group("3 kunlik intensiv 7")
    assert (c.code, c.suffix, c.label) == ("3K7", "3K7 Gr", "3K7")


def test_sector_group():
    c = cohort_for_group("Toshkent 7")
    assert c.suffix is None and c.label == "Toshkent 7"


def test_display_name():
    assert display_name(person()) == "Ali Valiyev TN7 Gr"


def test_oldest_cohort_suffix():
    assert display_name(person(cohorts={"TN7", "TN4"})).endswith("TN4 Gr")


def test_existing_other_suffix_kept():
    p = person(cohorts={"TN7"})
    assert display_name(p, existing="Ali Valiyev TN4 Gr") == "Ali Valiyev TN4 Gr"


def test_sector_only_no_suffix():
    p = person(cohorts={"S:Toshkent 7"})
    assert display_name(p) == "Ali Valiyev"


def test_labels():
    assert labels_for(person(cohorts={"TN7", "3K7"})) == ["3K7", "TEZ NATIJA 7"]
