#!/usr/bin/env python3
"""O'zbekcha matnda ASCII apostrofni topadigan guard.

Muammo: ``'qo'ng'iroq'`` yozilsa Python qatorni ``'qo'`` da yopadi va
``SyntaxError`` beradi. Ikki tirnoq ichida yozilsa kod ishlaydi, lekin matnda
``oʻ``/``gʻ`` o'rniga ASCII ``'`` qoladi va keyingi tahrirda kodni buzadi.

Qoida:
- o'zbekcha matn faqat ikki tirnoq ichida yoziladi;
- ``oʻ``/``gʻ`` -> ``ö``/``ğ`` (yangi alifbo) yoki ``ʻ`` (U+02BB);
- tutuq belgisi -> ``ʼ`` (U+02BC);
- identifikator, email, teg, username — ASCII, ularga tegilmaydi.

Ishlatish::

    python scripts/check_uzbek_text.py --staged
    python scripts/check_uzbek_text.py --base origin/main
    python scripts/check_uzbek_text.py --all --baseline config/uzbek_text_baseline.txt
    python scripts/check_uzbek_text.py --write-baseline

Baseline (ratchet): mavjud qarz ``config/uzbek_text_baseline.txt`` da qulflanadi.
``--all`` rejimida baseline'dagi sonlardan ortiq uchragan har bir yangi xato
xato hisoblanadi. Qarz tuzatilganda baseline qayta yoziladi — son faqat kamayadi.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

TARGET_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}
# Guard o'z namunasini va test fixture'larini tekshirmaydi.
SKIP_DIRS = {"tests", "venv", ".venv", "node_modules"}
SELF_PATH = Path(__file__).resolve()
DEFAULT_BASELINE = Path("config/uzbek_text_baseline.txt")

# Harf-apostrof-harf: faqat so'z ichidagi apostrofni oladi.
WORD_APOSTROPHE = re.compile(r"(?<=[^\W\d_])'(?=[^\W\d_])", re.UNICODE)
WORD_WITH_APOSTROPHE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)+", re.UNICODE)

# Ingliz tili qisqartmalari: ular qonuniy ASCII apostrof ishlatadi.
ENGLISH_ALLOWLIST = {
    "o'clock",
    "y'all",
    "ma'am",
    "ne'er",
    "e'er",
    "rock'n'roll",
}
# Inglizcha egalik/qisqartma oxirlari: John's, don't, we're, I've, he'll, I'd, I'm.
ENGLISH_SUFFIXES = ("'s", "'t", "'re", "'ve", "'ll", "'d", "'m")


@dataclass(frozen=True)
class Violation:
    """Bitta xavfli apostrof: fayl, qator, ustun va so'z."""

    path: str
    line: int
    column: int
    word: str

    @property
    def key(self) -> str:
        """Baseline kaliti: fayl (qator va so'z siljishidan mustaqil)."""
        return self.path

    def format(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column}: {self.word!r} — ASCII apostrof. "
            "Ikki tirnoq ichida yozing va ö/ğ yoki ʼ (U+02BC) ishlating."
        )


def is_allowed_word(word: str) -> bool:
    """Inglizcha qisqartma/egalik bo'lsa True."""
    low = word.lower()
    if low in ENGLISH_ALLOWLIST:
        return True
    return low.endswith(ENGLISH_SUFFIXES)


def find_violations(line: str) -> List[Tuple[int, str]]:
    """Qatordagi xavfli apostrofii so'zlarni (ustun, so'z) ko'rinishida qaytaradi."""
    found: List[Tuple[int, str]] = []
    for match in WORD_WITH_APOSTROPHE.finditer(line):
        word = match.group(0)
        if not WORD_APOSTROPHE.search(word):
            continue
        if is_allowed_word(word):
            continue
        found.append((match.start() + 1, word))
    return found


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} xato: {result.stderr.strip()}")
    return result.stdout


def _tracked_files() -> List[str]:
    return [
        name
        for name in _git("ls-files").splitlines()
        if Path(name).suffix in TARGET_SUFFIXES
    ]


def parse_added_lines(diff_text: str) -> Dict[str, Set[int]]:
    """``git diff -U0`` dan fayl -> qo'shilgan qatorlar to'plamini oladi."""
    files: Dict[str, Set[int]] = {}
    current: Optional[str] = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
            files.setdefault(current, set())
        elif line.startswith("+++ /dev/null"):
            current = None
        elif line.startswith("@@") and current is not None:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if not match:
                continue
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            if count:
                files[current].update(range(start, start + count))
    return files


def scan_file(path: Path, allowed_lines: Optional[Set[int]] = None) -> List[Violation]:
    """Faylni tekshiradi; ``allowed_lines`` berilsa faqat shu qatorlar."""
    violations: List[Violation] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"{path}: o'qilmadi: {exc}")
    for lineno, line in enumerate(text.splitlines(), 1):
        if allowed_lines is not None and lineno not in allowed_lines:
            continue
        for column, word in find_violations(line):
            violations.append(Violation(path.as_posix(), lineno, column, word))
    return violations


def _diff_changes(mode: str, base: str) -> Dict[str, Set[int]]:
    if mode == "staged":
        diff = _git("diff", "--cached", "--unified=0", "--diff-filter=ACM")
    else:
        diff = _git("diff", "--unified=0", "--diff-filter=ACM", f"{base}...HEAD")
    return parse_added_lines(diff)


def _is_skipped(path: Path) -> bool:
    if path.resolve() == SELF_PATH:
        return True
    return bool(SKIP_DIRS.intersection(path.parts))


def load_baseline(path: Path) -> Counter:
    """Baseline faylidan fayl bo'yicha xato sonini qaytaradi.

    Format: ``<son>\\t<path>``; son yo'q bo'lsa 1 deb olinadi.
    """
    if not path.exists():
        return Counter()
    counts: Counter = Counter()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        count_text, sep, key = line.partition("\t")
        if sep and count_text.isdigit():
            counts[key] += int(count_text)
        else:
            counts[line] += 1
    return counts


def write_baseline(path: Path, violations: Sequence[Violation]) -> None:
    """Joriy qarzni baseline fayliga yozadi (fayllar alifbo tartibida)."""
    counts = Counter(v.key for v in violations)
    lines = [f"{count}\t{key}" for key, count in sorted(counts.items())]
    header = (
        "# O'zbekcha matn guard baseline (ratchet).\n"
        "# Format: <son>\\t<path>. Yangi xato qo'shilsa CI qizil.\n"
        "# Qarz tuzatilganda: python scripts/check_uzbek_text.py --write-baseline\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def apply_baseline(
    violations: Sequence[Violation], baseline: Counter
) -> List[Violation]:
    """Baseline'dagi sonlarni iste'mol qilib, ortiqcha (yangi) xatolarni qaytaradi."""
    remaining = Counter(baseline)
    fresh: List[Violation] = []
    for violation in violations:
        if remaining[violation.key] > 0:
            remaining[violation.key] -= 1
            continue
        fresh.append(violation)
    return fresh


def _collect_targets(args: argparse.Namespace) -> Tuple[List[Path], Optional[Dict[str, Set[int]]]]:
    if args.write_baseline:
        # Baseline har doim butun repo bo'yicha yoziladi — qism ro'yxat uni buzadi.
        return [Path(p) for p in _tracked_files()], None
    if args.paths:
        return [Path(p) for p in args.paths if Path(p).suffix in TARGET_SUFFIXES], None
    if args.all:
        return [Path(p) for p in _tracked_files()], None
    mode = "staged" if args.staged else "base"
    line_map = _diff_changes(mode, args.base)
    targets = [Path(p) for p in line_map if Path(p).suffix in TARGET_SUFFIXES]
    return targets, line_map


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Butun repo (mavjud qarzlarni ko'rsatadi; baseline bilan ishlatiladi).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Faqat staged qo'shilgan qatorlar (pre-commit default).",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Shu ref bilan solishtirib, faqat qo'shilgan qatorlarni tekshirish.",
    )
    parser.add_argument(
        "--baseline",
        nargs="?",
        const=str(DEFAULT_BASELINE),
        default=None,
        help="Mavjud qarzni shu fayldan o'qib, faqat yangi xatolarni ko'rsatish.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Butun repo qarzini baseline fayliga yozish (ratchetni yangilash).",
    )
    parser.add_argument("paths", nargs="*", help="Aniq fayllar (ixtiyoriy).")
    args = parser.parse_args(list(argv) if argv is not None else None)

    targets, line_map = _collect_targets(args)
    targets = [target for target in targets if not _is_skipped(target)]

    violations: List[Violation] = []
    for target in targets:
        allowed = None if line_map is None else line_map.get(target.as_posix(), set())
        violations.extend(scan_file(target, allowed))

    if args.write_baseline:
        baseline_path = Path(args.baseline or DEFAULT_BASELINE)
        write_baseline(baseline_path, violations)
        print(
            f"Baseline yozildi: {baseline_path} ({len(violations)} ta mavjud xato, "
            f"{len({v.path for v in violations})} fayl)."
        )
        return 0

    if args.baseline and line_map is None:
        baseline = load_baseline(Path(args.baseline))
        violations = apply_baseline(violations, baseline)

    if violations:
        print("O'zbekcha matn guard: ASCII apostrof topildi.\n", file=sys.stderr)
        for violation in violations:
            print(violation.format(), file=sys.stderr)
        print(
            f"\nJami {len(violations)} ta. Qoida: AGENTS.md / "
            ".agents/skills/uzbek-text/SKILL.md",
            file=sys.stderr,
        )
        return 1

    print(f"O'zbekcha matn guard: toza ({len(targets)} fayl).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
