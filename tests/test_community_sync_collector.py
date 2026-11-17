from types import SimpleNamespace as NS

from src.services.core.community_sync.collector import collect

INTRO = (
    "Исм: Али\nФамилия: Валиев\nТелефон: +998 90 123 45 67\n"
    "Компания: Nur\nҲудуд: Тошкент"
)


class FakeClient:
    def __init__(self):
        self.chats = {
            "p1": NS(id=101, title="TEZ NATIJA 7"),
            "p2": NS(id=102, title="Toshkent 7"),
        }
        self.members = {
            101: [
                NS(id=1, bot=False, deleted=False, first_name="Ali", last_name="V", username="ali", phone=None),
                NS(id=9, bot=True, deleted=False, first_name="Bot", last_name="", username="b_bot", phone=None),
            ],
            102: [NS(id=2, bot=False, deleted=False, first_name="Vali", last_name=None, username=None, phone=None)],
        }
        self.msgs = {101: [NS(sender_id=1, message=INTRO), NS(sender_id=1, message="salom")], 102: []}

    async def __call__(self, request):
        f = NS(id=13, include_peers=["p1", "p2"])
        return NS(filters=[NS(id=2, include_peers=[]), f])

    async def get_entity(self, peer):
        return self.chats[peer]

    async def iter_participants(self, chat):
        for m in self.members[chat.id]:
            yield m

    async def iter_messages(self, chat, limit=None):
        for m in self.msgs[chat.id]:
            yield m


async def test_collect():
    people = await collect(FakeClient(), 13)
    by = {p.tg_id: p for p in people}
    assert set(by) == {1, 2}
    ali = by[1]
    assert ali.cohorts == {"TN7"} and ali.phone == "+998901234567"
    assert (ali.first_name, ali.last_name, ali.company, ali.region) == ("Али", "Валиев", "Nur", "Тошкент")
    assert ali.username == "ali" and ali.key == "tg:1"
    assert by[2].cohorts == {"S:Toshkent 7"} and by[2].first_name == "Vali"


async def test_missing_folder_returns_empty():
    assert await collect(FakeClient(), 99) == []
