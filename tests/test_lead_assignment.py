import pytest

from src.api.lead_assignment import (
    apply_assignment_backfill,
    assign_lead,
    parse_assignment_map,
)


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0

    async def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

        class Result:
            rowcount = 1

        return Result()

    async def commit(self):
        self.commits += 1


def test_parse_assignment_map_accepts_only_positive_ids_and_nonempty_subjects():
    assert parse_assignment_map('{"10":"seller-a", "20":" seller-b "}') == {
        10: "seller-a",
        20: "seller-b",
    }

    with pytest.raises(ValueError):
        parse_assignment_map('{"0":"seller-a"}')
    with pytest.raises(ValueError):
        parse_assignment_map('{"10":""}')
    with pytest.raises(ValueError):
        parse_assignment_map('[]')


@pytest.mark.asyncio
async def test_assignment_backfill_updates_only_unassigned_rows():
    connection = FakeConnection()
    changed = await apply_assignment_backfill(
        connection,
        {10: "seller-a", 20: "seller-b"},
    )

    assert changed == 2
    assert connection.commits == 1
    assert all("assigned_to IS NULL OR TRIM(assigned_to) = ''" in sql for sql, _ in connection.calls)


@pytest.mark.asyncio
async def test_assign_lead_is_a_canonical_explicit_write():
    connection = FakeConnection()
    changed = await assign_lead(connection, user_id=10, seller_subject="seller-a")

    assert changed is True
    assert connection.commits == 1
    assert connection.calls == [
        ("UPDATE users SET assigned_to = ? WHERE user_id = ?", ("seller-a", 10))
    ]
