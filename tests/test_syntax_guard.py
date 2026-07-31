"""Import-time crash guard.

Oracle prod (systemd `oisha-os.service`) `src/main.py` ni ishga tushiradi.
Agar `src/` ichidagi biror modulda SyntaxError/IndentationError bo'lsa,
main.py import bosqichida yiqiladi va servis cheksiz restart loop'ga tushadi
(bir marta restart counter 1586 ga yetgan — IndentationError src/api_server.py:597).

Bu testlar aynan shu klassni CI'da ushlaydi: har bir fayl kompilyatsiya
bo'lishi va prod import zanjiri yuklanishi shart.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

# Ishlab chiqarishda import qilinmaydigan, tashqarida qolgan kataloglar.
EXCLUDED_PARTS = {"debug", "legacy", "__pycache__"}


def _python_files() -> list[Path]:
    return [
        p
        for p in SRC.rglob("*.py")
        if not EXCLUDED_PARTS & set(p.relative_to(SRC).parts)
        and not p.name.endswith(".bak")
    ]


@pytest.mark.parametrize(
    "path", _python_files(), ids=lambda p: str(p.relative_to(SRC)).replace("\\", "/")
)
def test_module_parses(path: Path) -> None:
    """Har bir src/ fayli sintaktik jihatdan to'g'ri bo'lishi kerak.

    IndentationError ham SyntaxError'ning bo'lagi — ast.parse ikkalasini ham ushlaydi.
    """
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # IndentationError shu yerga tushadi
        pytest.fail(
            f"{path.relative_to(SRC)}:{exc.lineno} — {type(exc).__name__}: {exc.msg}\n"
            f"    {(exc.text or '').rstrip()}"
        )


def test_prod_entrypoint_imports() -> None:
    """`src/main.py` import zanjiri to'liq yuklanishi kerak.

    Faqat parse emas — haqiqiy import. Bu `admin_bot -> crm_night_shift ->
    api_server` kabi zanjirdagi buzilishni ushlaydi. Alohida process'da
    ishlaydi, chunki main.py import paytida global state yaratadi.
    """
    code = (
        "import ast, pathlib, sys\n"
        "src = pathlib.Path('src/main.py')\n"
        "tree = ast.parse(src.read_text(encoding='utf-8'), filename=str(src))\n"
        # main.py o'zini ishga tushirmasdan, faqat uning import'larini bajaramiz.
        "mods = []\n"
        "for node in tree.body:\n"
        "    if isinstance(node, ast.Import):\n"
        "        mods += [a.name for a in node.names]\n"
        "    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:\n"
        "        mods.append(node.module)\n"
        "import importlib\n"
        "for m in mods:\n"
        "    if m.startswith('src.'):\n"
        "        importlib.import_module(m)\n"
        "print('IMPORT_OK')\n"
    )
    result = subprocess.run(  # noqa: S603 - sobit argumentlar, foydalanuvchi kiritmaydi
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=SRC.parent,
        timeout=180,
    )
    assert "IMPORT_OK" in result.stdout, (
        "src/main.py import zanjiri yiqildi — prod systemd shu sababdan "
        f"restart loop'ga tushadi:\n{result.stderr[-3000:]}"
    )
