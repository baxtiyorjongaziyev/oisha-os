"""
Autonomous Skill Generator (Hermes Agent Learning Loop for Oisha-OS)
Allows the agent to distill repeatable operational workflows into
standardized .agents/skills/<skill-name>/SKILL.md files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / ".agents" / "skills"


def slugify(text: str) -> str:
    """Converts a phrase into a clean kebab-case skill identifier."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def build_skill_content(name: str, description: str, steps: list[str], verify: str) -> str:
    """Constructs compliant markdown text for SKILL.md with standard YAML frontmatter."""
    formatted_steps = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps)) if steps else "1. Standart bajarish qadamlari."
    verify_block = verify.strip() if verify else "Harness pre-flight yoki buyruq natijasi tekshirilgan bo'lishi kerak."

    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        "## 1. Maqsad va Qo'llanilish doirasi\n"
        f"- {description}\n\n"
        "## 2. Kiruvchi talablar va Muhit\n"
        "- Kerakli skriptlar va o'zgaruvchilar mavjudligini tekshiring (`.env`).\n"
        "- Sirlar va tokenlarni hech qachon matnda ochiq yozmang.\n\n"
        "## 3. Qadamma-qadam Amallar (Step-by-step Execution)\n"
        f"{formatted_steps}\n\n"
        "## 4. Xatolar va Bartaraf etish (Troubleshooting)\n"
        "- API xatosi yoki tarmoq uzilsa: eksponensial backoff bilan qayta urinish.\n"
        "- Format noto'g'ri bo'lsa: kiruvchi ma'lumotlarni sanitizatsiya qilish.\n\n"
        "## 5. Tekshiruv va Dalil (Verification Gate)\n"
        f"```bash\n{verify_block}\n```\n"
    )


def generate_skill(
    skill_name: str,
    description: str,
    steps: list[str] | None = None,
    verify_cmd: str = "",
    overwrite: bool = False,
) -> Path:
    """Creates a new skill directory and SKILL.md file."""
    slug = slugify(skill_name)
    target_dir = SKILLS_DIR / slug
    target_file = target_dir / "SKILL.md"

    if target_file.exists() and not overwrite:
        print(f"⚠️ Skill '{slug}' already exists at {target_file}. Use --overwrite to replace.")
        return target_file

    target_dir.mkdir(parents=True, exist_ok=True)
    content = build_skill_content(
        name=slug,
        description=description,
        steps=steps or [],
        verify=verify_cmd,
    )
    target_file.write_text(content, encoding="utf-8")
    print(f"✅ Skill successfully generated: {target_file.relative_to(ROOT)}")
    return target_file


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Oisha-OS Skill Evolution Generator")
    parser.add_argument("--name", required=True, help="Skill name (e.g. 'amocrm-contact-enrich')")
    parser.add_argument("--desc", required=True, help="Skill description for model prompt matching")
    parser.add_argument("--step", action="append", help="Step item (can be repeated)")
    parser.add_argument("--verify", default="", help="Verification command or procedure")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite if skill already exists")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    generate_skill(
        skill_name=args.name,
        description=args.desc,
        steps=args.step,
        verify_cmd=args.verify,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
