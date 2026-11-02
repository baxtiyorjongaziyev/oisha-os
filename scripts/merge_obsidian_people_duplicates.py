"""Surgically merge and deduplicate people notes in Obsidian Second Brain.

Ensures:
  1. No real person has 2 dots / 2 notes in Obsidian ("bitta odamni ma'lumoti 2ta nuqta bo'lmasin").
  2. All duplicate files (Name (2).md, Name (3).md) are merged into the primary note.
  3. Single-name collisions (different people sharing a first name like Abror) are disambiguated
     with their handle (@username) or phone (+998...) instead of ambiguous (2).
  4. Vault-wide wikilinks are updated to point to the canonical notes.
  5. 70-Odamlar/_index.md is updated.
"""
import os
import sys
import re
import glob
from collections import OrderedDict

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VAULT = r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain"
PEOPLE_DIR = os.path.join(VAULT, "70-Odamlar")
INDEX_PATH = os.path.join(PEOPLE_DIR, "_index.md")


def parse_person_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    frontmatter = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].strip()
            curr_key = None
            for line in fm_text.splitlines():
                line = line.rstrip()
                if not line:
                    continue
                m = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
                if m:
                    curr_key = m.group(1)
                    val = m.group(2).strip()
                    if val.startswith("[") and val.endswith("]"):
                        # inline list
                        items = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
                        frontmatter[curr_key] = items
                    elif val:
                        frontmatter[curr_key] = val.strip("'\"")
                    else:
                        frontmatter[curr_key] = []
                elif curr_key and line.strip().startswith("- "):
                    item = line.strip()[2:].strip().strip("'\"")
                    if not isinstance(frontmatter.get(curr_key), list):
                        frontmatter[curr_key] = []
                    frontmatter[curr_key].append(item)

    # Extract sections from body
    phones = set()
    telegrams = set()
    labels = set()
    amo_leads = OrderedDict()
    tg_chats = OrderedDict()

    # Collect from frontmatter
    if "telefon" in frontmatter:
        t = frontmatter["telefon"]
        if isinstance(t, list):
            phones.update(t)
        elif isinstance(t, str):
            phones.add(t)

    if "telegram" in frontmatter:
        t = frontmatter["telegram"]
        if isinstance(t, list):
            telegrams.update(t)
        elif isinstance(t, str):
            telegrams.add(t)

    if "tags" in frontmatter:
        t = frontmatter["tags"]
        if isinstance(t, list):
            for tag in t:
                if tag != "odam":
                    labels.add(tag)

    # Collect from body
    for line in body.splitlines():
        line = line.strip()
        # Phone
        m_ph = re.search(r"📞\s*(\+?\d+)", line)
        if m_ph:
            phones.add(m_ph.group(1))
        # Telegram
        m_tg = re.search(r"✈️\s*(@\w+)", line)
        if m_tg:
            telegrams.add(m_tg.group(1))
        # Label
        m_lb = re.search(r"🏷️\s*(.*)", line)
        if m_lb:
            labels.add(m_lb.group(1).strip())
        # AmoCRM lead links
        if line.startswith("- [[../70-AmoCRM/") or "70-AmoCRM/" in line:
            # e.g. - [[../70-AmoCRM/Mahliyo - (52424219)/_lead|Mahliyo | ]] — 0 qo'ng'iroq
            m_link = re.search(r"(\[\[.*?70-AmoCRM/.*?\]\])(.*)", line)
            if m_link:
                link_part = m_link.group(1)
                desc = m_link.group(2).strip()
                amo_leads[link_part] = desc
        # Telegram chat links
        if line.startswith("- [[../70-Telegram/_Odamlar/"):
            m_link = re.search(r"(\[\[.*?70-Telegram/.*?\]\])(.*)", line)
            if m_link:
                link_part = m_link.group(1)
                desc = m_link.group(2).strip()
                tg_chats[link_part] = desc

    return {
        "nom": frontmatter.get("nom", ""),
        "kompaniya": frontmatter.get("kompaniya", ""),
        "soha": frontmatter.get("soha", ""),
        "phones": phones,
        "telegrams": telegrams,
        "labels": labels,
        "qongiroq": int(frontmatter.get("qongiroq", 0) or 0),
        "summa": int(frontmatter.get("summa", 0) or 0),
        "telegram_xabar": int(frontmatter.get("telegram_xabar", 0) or 0),
        "amo_leads": amo_leads,
        "tg_chats": tg_chats,
        "raw_frontmatter": frontmatter,
    }


def render_person_file(name, p):
    lines = ["---", "type: odam", f'nom: "{name}"']
    if p["phones"]:
        lines.append("telefon:")
        for ph in sorted(p["phones"]):
            if not ph.startswith("+"):
                ph = "+" + ph
            lines.append(f'  - "{ph}"')
    if p["telegrams"]:
        lines.append("telegram:")
        for tg in sorted(p["telegrams"]):
            lines.append(f'  - "{tg}"')
    if p["kompaniya"]:
        lines.append(f'kompaniya: "{p["kompaniya"]}"')
    if p["soha"]:
        lines.append(f'soha: "{p["soha"]}"')
    lines.append(f'telegram_xabar: {p["telegram_xabar"]}')
    lines.append(f'qongiroq: {p["qongiroq"]}')
    if p["summa"]:
        lines.append(f'summa: {p["summa"]}')

    # Calculate sources count
    has_contact = bool(p["phones"] or p["telegrams"] or p["labels"])
    has_amo = bool(p["amo_leads"])
    has_tg = bool(p["tg_chats"] or p["telegram_xabar"] > 0)
    sources = int(has_contact) + int(has_amo) + int(has_tg)
    if sources == 0:
        sources = 1
    lines.append(f"manbalar: {sources}")

    lines.append("tags:")
    lines.append("  - odam")
    seen_tags = {"odam"}
    for lb in sorted(p["labels"]):
        tag_clean = re.sub(r"[^\w-]", "-", lb).strip("-")
        if tag_clean and tag_clean.lower() not in seen_tags:
            seen_tags.add(tag_clean.lower())
            lines.append(f"  - {tag_clean}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")

    subtitle = []
    if p["kompaniya"]:
        subtitle.append(f"**{p['kompaniya']}**")
    if p["soha"]:
        subtitle.append(p["soha"])
    if subtitle:
        lines.append(" · ".join(subtitle))
        lines.append("")

    lines.append("## Aloqa")
    lines.append("")
    for ph in sorted(p["phones"]):
        lines.append(f"- 📞 {ph}")
    for tg in sorted(p["telegrams"]):
        lines.append(f"- ✈️ {tg}")
    seen_lb = set()
    for lb in sorted(p["labels"]):
        norm_lb = re.sub(r"[^\w]", "", lb).lower()
        if norm_lb not in seen_lb:
            seen_lb.add(norm_lb)
            lines.append(f"- 🏷️ {lb}")
    lines.append("")

    if p["tg_chats"]:
        lines.append(f"## 💬 Telegram — {p['telegram_xabar']} xabar")
        lines.append("")
        for link, desc in p["tg_chats"].items():
            lines.append(f"- {link} {desc}".strip())
        lines.append("")

    if p["amo_leads"]:
        lines.append(f"## 📞 AmoCRM — {p['qongiroq']} qo'ng'iroq tahlili")
        lines.append("")
        for link, desc in p["amo_leads"].items():
            lines.append(f"- {link} {desc}".strip())
        lines.append("")

    if sources == 1 and not p["amo_leads"] and not p["tg_chats"]:
        lines.append("> [!note] Faqat kontakt kitobida. Telegram yoki AmoCRM bilan bog'lanmadi.")
        lines.append("")

    lines.append("## Xulosa")
    lines.append("")
    lines.append("_(AI xulosa keyin)_")
    lines.append("")

    return "\n".join(lines)


def main():
    print("[*] Skaner qilinmoqda: 70-Odamlar...")
    files = glob.glob(os.path.join(PEOPLE_DIR, "*.md"))
    dup_files = sorted([f for f in files if re.search(r"\s\(\d+\)\.md$", f)])
    print(f"[*] Topilgan duplikat fayllar soni: {len(dup_files)}")

    redirect_map = {}
    merged_count = 0
    renamed_count = 0
    deleted_count = 0

    for df in dup_files:
        filename = os.path.basename(df)
        base_name = re.sub(r"\s\(\d+\)\.md$", "", filename)
        orig_file = os.path.join(PEOPLE_DIR, base_name + ".md")

        dup_data = parse_person_file(df)

        if not os.path.exists(orig_file):
            # No primary file exists, just rename df to base_name
            os.rename(df, orig_file)
            redirect_map[filename[:-3]] = base_name
            renamed_count += 1
            print(f"  [RENAME] {filename} -> {base_name}.md")
            continue

        orig_data = parse_person_file(orig_file)

        # Decide whether this is the EXACT SAME PERSON or a DIFFERENT PERSON sharing a name
        words = base_name.split()
        is_full_name = len(words) >= 2 and not words[0].isdigit() and not base_name.startswith("TN")
        
        shared_phones = orig_data["phones"].intersection(dup_data["phones"])
        shared_tg = orig_data["telegrams"].intersection(dup_data["telegrams"])
        is_identical = (
            orig_data["phones"] == dup_data["phones"] and
            orig_data["telegrams"] == dup_data["telegrams"] and
            orig_data["labels"] == dup_data["labels"]
        )

        is_same_person = is_full_name or bool(shared_phones) or bool(shared_tg) or is_identical

        if is_same_person:
            # MERGE INTO orig_file
            orig_data["phones"].update(dup_data["phones"])
            orig_data["telegrams"].update(dup_data["telegrams"])
            orig_data["labels"].update(dup_data["labels"])
            if not orig_data["kompaniya"] and dup_data["kompaniya"]:
                orig_data["kompaniya"] = dup_data["kompaniya"]
            if not orig_data["soha"] and dup_data["soha"]:
                orig_data["soha"] = dup_data["soha"]
            orig_data["qongiroq"] += dup_data["qongiroq"]
            orig_data["summa"] += dup_data["summa"]
            orig_data["telegram_xabar"] += dup_data["telegram_xabar"]

            for lk, desc in dup_data["amo_leads"].items():
                if lk not in orig_data["amo_leads"]:
                    orig_data["amo_leads"][lk] = desc

            for lk, desc in dup_data["tg_chats"].items():
                if lk not in orig_data["tg_chats"]:
                    orig_data["tg_chats"][lk] = desc

            # Write merged back to orig_file
            merged_content = render_person_file(base_name, orig_data)
            with open(orig_file, "w", encoding="utf-8") as f:
                f.write(merged_content)

            # Remove duplicate file
            os.remove(df)
            redirect_map[filename[:-3]] = base_name
            merged_count += 1
            deleted_count += 1
            print(f"  [MERGED] {filename} -> {base_name}.md")
        else:
            # Different person sharing a common first name or tag
            # Disambiguate by creating a descriptive unique filename
            distinguisher = ""
            if dup_data["telegrams"]:
                distinguisher = sorted(dup_data["telegrams"])[0]  # @username
            elif dup_data["phones"]:
                distinguisher = sorted(dup_data["phones"])[0]     # +998...
            elif dup_data["kompaniya"]:
                distinguisher = dup_data["kompaniya"]
            elif dup_data["labels"]:
                distinguisher = sorted(dup_data["labels"])[0]

            if distinguisher:
                new_base = f"{base_name} ({distinguisher})"
            else:
                new_base = f"{base_name} (Profil {filename.split('(')[-1].replace(').md', '')})"

            new_path = os.path.join(PEOPLE_DIR, new_base + ".md")
            # If target already exists, append unique suffix
            k = 2
            while os.path.exists(new_path):
                new_base_k = f"{new_base} - {k}"
                new_path = os.path.join(PEOPLE_DIR, new_base_k + ".md")
                k += 1

            new_content = render_person_file(new_base, dup_data)
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            os.remove(df)
            redirect_map[filename[:-3]] = new_base
            renamed_count += 1
            deleted_count += 1
            print(f"  [DISAMBIGUATED] {filename} -> {new_base}.md")

    print(f"\n[*] Natija: {merged_count} ta fayl birlashtirildi, {renamed_count} ta shaxs aniqlashtirildi, {deleted_count} ta duplikat o'chirildi.")

    # Update Vault wikilinks
    print("[*] Vault bo'ylab wikilinklar tekshirilmoqda va yangilanmoqda...")
    updated_files = 0
    all_vault_md = glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True)
    for md_path in all_vault_md:
        try:
            with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            new_content = content
            for old_name, new_name in redirect_map.items():
                pattern = r"\[\[" + re.escape(old_name) + r"(\]\]|\|)"
                if re.search(pattern, new_content):
                    new_content = re.sub(pattern, r"[[" + new_name + r"\1", new_content)

            if new_content != content:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated_files += 1
        except Exception as e:
            pass

    print(f"[*] {updated_files} ta faylda ichki havolalar (wikilink) yangilandi.")

    # Regenerate _index.md
    print("[*] 70-Odamlar/_index.md qayta shakllantirilmoqda...")
    all_people = []
    for f in glob.glob(os.path.join(PEOPLE_DIR, "*.md")):
        bn = os.path.basename(f)
        if bn.startswith("_"):
            continue
        p = parse_person_file(f)
        has_contact = bool(p["phones"] or p["telegrams"] or p["labels"])
        has_amo = bool(p["amo_leads"])
        has_tg = bool(p["tg_chats"] or p["telegram_xabar"] > 0)
        srcs = int(has_contact) + int(has_amo) + int(has_tg)
        if srcs == 0:
            srcs = 1
        all_people.append({
            "file": bn[:-3],
            "name": p["nom"] or bn[:-3],
            "org": p["kompaniya"],
            "title": p["soha"],
            "srcs": srcs,
            "tg": p["telegram_xabar"],
            "calls": p["qongiroq"],
            "phones": len(p["phones"]),
        })

    all_people.sort(key=lambda x: (-x["srcs"], -x["tg"], -x["calls"]))
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("---\ntype: odamlar-index\ntags:\n  - odam\n---\n\n")
        f.write("# Odamlar\n\n")
        multi = sum(1 for r in all_people if r["srcs"] > 1)
        f.write(f"**{len(all_people)}** odam · **{multi}** tasi bir nechta manbada (kontakt + Telegram + AmoCRM)\n\n")
        f.write("Manba qancha ko'p — odam shuncha markaziy.\n\n")
        f.write("| Odam | Kompaniya | Soha | TG xabar | Qo'ng'iroq | Manba |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in all_people:
            f.write(f"| [[{r['file']}\\|{r['name']}]] | {r['org']} | {r['title']} | "
                    f"{r['tg'] or ''} | {r['calls'] or ''} | {r['srcs']} |\n")

    print(f"[*] _index.md muvaffaqiyatli yangilandi ({len(all_people)} nafar shaxs).")


if __name__ == "__main__":
    main()
