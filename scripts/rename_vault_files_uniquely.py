# -*- coding: utf-8 -*-
"""
Rename all duplicate files across Obsidian Vault so that every single file has a unique, beautiful name.
"""
import os
import shutil
import subprocess
from collections import defaultdict

VAULTS = [
    r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
]

README_RENAMES = {
    os.path.join("00-Inbox", "ChatGPT Imports", "README.md"): "ChatGPT Imports — Qo'llanma.md",
    os.path.join("40-Archive", "README.md"): "Archive — Qo'llanma.md",
    os.path.join("60-Wiki", "README.md"): "Wiki — Qo'llanma.md",
    os.path.join("60-Wiki", "sources", "README.md"): "Wiki Sources — Qo'llanma.md",
    os.path.join("60-Wiki", "sources", "airtable", "README.md"): "Airtable Wiki — Qo'llanma.md",
    os.path.join("60-Wiki", "sources", "amocrm", "README.md"): "AmoCRM Wiki — Qo'llanma.md",
    os.path.join("60-Wiki", "sources", "telegram", "README.md"): "Telegram Wiki — Qo'llanma.md",
}

EXPORT_RENAMES = {
    "ME.md": "Export — ME.md",
    "NOW.md": "Export — NOW.md",
    "PLAYBOOK.md": "Export — PLAYBOOK.md",
    "SKILLS.md": "Export — SKILLS.md",
    "VAULT-MAP.md": "Export — VAULT-MAP.md",
}

MIJOZ_360_RENAMES = [
    "Beyaz.md", "Kamila Pardalari.md", "Ledir.md",
    "Melav.md", "Sadiya Cakes.md", "Shirona.md", "Yasira.md"
]


def process_vault(vault):
    print(f"=== Processing {vault} ===")
    if not os.path.exists(vault):
        print("Path does not exist, skipping.")
        return

    # 1. Rename 20-CLIENTS/ files uniquely
    clients_dir = os.path.join(vault, "20-CLIENTS")
    if os.path.exists(clients_dir):
        for item in os.listdir(clients_dir):
            c_path = os.path.join(clients_dir, item)
            if not os.path.isdir(c_path):
                continue

            client_name = item
            prof_old = os.path.join(c_path, "PROFILE.md")
            hist_old = os.path.join(c_path, "HISTORY.md")
            note_old = os.path.join(c_path, "NOTES.md")

            prof_new = os.path.join(c_path, f"{client_name} — Profil.md")
            hist_new = os.path.join(c_path, f"{client_name} — Tarix.md")
            note_new = os.path.join(c_path, f"{client_name} — Qaydlar.md")

            if os.path.exists(prof_old):
                content = open(prof_old, "r", encoding="utf-8").read()
                content = content.replace(f"[[20-CLIENTS/{client_name}/HISTORY|Loyiha Tarixi]]", f"[[{client_name} — Tarix|Loyiha Tarixi]]")
                content = content.replace(f"[[20-CLIENTS/{client_name}/NOTES|Qaydlar va Kelishuvlar]]", f"[[{client_name} — Qaydlar|Qaydlar va Kelishuvlar]]")
                content = content.replace(f"[[20-CLIENTS/{client_name}/NOTES#Telegram Muloqoti|Muloqot qaydlari]]", f"[[{client_name} — Qaydlar#Telegram Muloqoti|Muloqot qaydlari]]")
                with open(prof_new, "w", encoding="utf-8") as f:
                    f.write(content)
                os.remove(prof_old)

            if os.path.exists(hist_old):
                content = open(hist_old, "r", encoding="utf-8").read()
                content = content.replace(f"[[20-CLIENTS/{client_name}/PROFILE|Mijoz Profili]]", f"[[{client_name} — Profil|Mijoz Profili]]")
                with open(hist_new, "w", encoding="utf-8") as f:
                    f.write(content)
                os.remove(hist_old)

            if os.path.exists(note_old):
                content = open(note_old, "r", encoding="utf-8").read()
                content = content.replace(f"[[20-CLIENTS/{client_name}/PROFILE|Mijoz Profili]]", f"[[{client_name} — Profil|Mijoz Profili]]")
                with open(note_new, "w", encoding="utf-8") as f:
                    f.write(content)
                os.remove(note_old)

    # 2. Rename README files
    for rel_path, new_name in README_RENAMES.items():
        full_old = os.path.join(vault, rel_path)
        if os.path.exists(full_old):
            full_new = os.path.join(os.path.dirname(full_old), new_name)
            shutil.move(full_old, full_new)
            print(f"Renamed: {rel_path} -> {new_name}")

    # 3. Rename 00-SYSTEM/_EXPORT files
    export_dir = os.path.join(vault, "00-SYSTEM", "_EXPORT")
    if os.path.exists(export_dir):
        for old_f, new_f in EXPORT_RENAMES.items():
            full_old = os.path.join(export_dir, old_f)
            if os.path.exists(full_old):
                full_new = os.path.join(export_dir, new_f)
                shutil.move(full_old, full_new)
                print(f"Renamed Export: {old_f} -> {new_f}")

    # 4. Rename 70-Mijozlar duplicates
    mijozlar_dir = os.path.join(vault, "70-Mijozlar")
    if os.path.exists(mijozlar_dir):
        for m_file in MIJOZ_360_RENAMES:
            full_old = os.path.join(mijozlar_dir, m_file)
            if os.path.exists(full_old):
                base_name = m_file[:-3]
                full_new = os.path.join(mijozlar_dir, f"{base_name} — Mijoz 360.md")
                shutil.move(full_old, full_new)
                print(f"Renamed 70-Mijozlar: {m_file} -> {base_name} — Mijoz 360.md")

    # 5. Check remaining duplicates
    files_by_name = defaultdict(list)
    for root, dirs, files in os.walk(vault):
        if '.git' in root or '.obsidian' in root:
            continue
        for f in files:
            files_by_name[f].append(os.path.relpath(os.path.join(root, f), vault))

    dups = {k: v for k, v in files_by_name.items() if len(v) > 1 and k != '.gitkeep'}
    print(f"[{vault}] Remaining duplicates count (excluding .gitkeep): {len(dups)}")
    for k, v in dups.items():
        print(f"   Duplicate: {k} -> {v}")


if __name__ == "__main__":
    for v in VAULTS:
        process_vault(v)
