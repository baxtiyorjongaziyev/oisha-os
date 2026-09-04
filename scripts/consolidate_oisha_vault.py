# -*- coding: utf-8 -*-
"""
OISHA OS v0.1: Full Vault Consolidation & Graph Styling Script.
Merges legacy PARA folders into canonical OISHA OS v0.1 structure:
- 10-Projects -> 30-PROJECTS
- 70-Mijozlar -> 20-CLIENTS
- 70-Odamlar -> 10-BUSINESS/TEAM
- 70-Telegram -> 10-BUSINESS/OPERATIONS
- 20-Areas -> 10-BUSINESS, 40-KNOWLEDGE, 00-SYSTEM, 50-CONTENT
- 30-Resources -> 10-BUSINESS, 60-REFERENCE, 90-ARCHIVE, 40-KNOWLEDGE
- 40-Archive -> 90-ARCHIVE
- 60-Wiki -> 90-ARCHIVE/60-Wiki
Configures .obsidian/graph.json with beautiful OISHA OS color palette.
"""
import json
import os
import shutil

VAULTS = [
    r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
]

def safe_move(src, dst):
    if not os.path.exists(src):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        else:
            os.remove(dst)
    shutil.move(src, dst)
    print(f"Moved: {os.path.basename(src)} -> {dst}")

def safe_copy_tree(src, dst):
    if not os.path.exists(src):
        return
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        dest_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            s_f = os.path.join(root, f)
            d_f = os.path.join(dest_dir, f)
            if not os.path.exists(d_f):
                shutil.copy2(s_f, d_f)
    shutil.rmtree(src)
    print(f"Merged directory tree: {src} -> {dst}")

def consolidate_vault(vault):
    print(f"\n==========================================")
    print(f"Consolidating: {vault}")
    print(f"==========================================")
    if not os.path.exists(vault):
        print("Vault path does not exist, skipping.")
        return

    # 1. Move 10-Projects -> 30-PROJECTS
    p10 = os.path.join(vault, "10-Projects")
    p30 = os.path.join(vault, "30-PROJECTS")
    if os.path.exists(p10):
        for f in os.listdir(p10):
            safe_move(os.path.join(p10, f), os.path.join(p30, f))
        try:
            os.rmdir(p10)
            print("Removed empty 10-Projects folder.")
        except Exception:
            pass

    # 2. Move 70-Mijozlar -> 20-CLIENTS
    m70 = os.path.join(vault, "70-Mijozlar")
    c20 = os.path.join(vault, "20-CLIENTS")
    if os.path.exists(m70):
        for f in os.listdir(m70):
            if f.endswith(".md"):
                # E.g. "Beyaz — Mijoz 360.md"
                client_folder = f.replace(" — Mijoz 360.md", "").strip()
                # find or match client folder in 20-CLIENTS
                target_dir = os.path.join(c20, client_folder)
                if not os.path.exists(target_dir):
                    # Check for partial match e.g. Ledir
                    found = False
                    for existing in os.listdir(c20):
                        if client_folder.lower() in existing.lower():
                            target_dir = os.path.join(c20, existing)
                            found = True
                            break
                    if not found:
                        os.makedirs(target_dir, exist_ok=True)
                safe_move(os.path.join(m70, f), os.path.join(target_dir, f))
        try:
            shutil.rmtree(m70)
            print("Removed 70-Mijozlar folder.")
        except Exception:
            pass

    # 3. Move 70-Odamlar -> 10-BUSINESS/TEAM
    o70 = os.path.join(vault, "70-Odamlar")
    team_dir = os.path.join(vault, "10-BUSINESS", "TEAM")
    if os.path.exists(o70):
        for f in os.listdir(o70):
            safe_move(os.path.join(o70, f), os.path.join(team_dir, f))
        try:
            shutil.rmtree(o70)
            print("Removed 70-Odamlar folder.")
        except Exception:
            pass

    # 4. Move 70-Telegram -> 10-BUSINESS/OPERATIONS
    t70 = os.path.join(vault, "70-Telegram")
    ops_dir = os.path.join(vault, "10-BUSINESS", "OPERATIONS")
    if os.path.exists(t70):
        for f in os.listdir(t70):
            safe_move(os.path.join(t70, f), os.path.join(ops_dir, f))
        try:
            shutil.rmtree(t70)
            print("Removed 70-Telegram folder.")
        except Exception:
            pass

    # 5. Move 20-Areas files to appropriate OISHA OS destinations
    a20 = os.path.join(vault, "20-Areas")
    if os.path.exists(a20):
        areas_mapping = {
            "Savdo.md": ("10-BUSINESS", "SALES", "Savdo.md"),
            "JonBranding_2Year_Sales_Intelligence.md": ("10-BUSINESS", "SALES", "JonBranding_2Year_Sales_Intelligence.md"),
            "JonBranding CRM Follow-up Gate.md": ("10-BUSINESS", "SALES", "JonBranding CRM Follow-up Gate.md"),
            "JonBranding Operations.md": ("10-BUSINESS", "OPERATIONS", "JonBranding Operations.md"),
            "JonBranding Project Delivery Gate.md": ("10-BUSINESS", "OPERATIONS", "JonBranding Project Delivery Gate.md"),
            "JonBranding Naming Intake Gate.md": ("10-BUSINESS", "OPERATIONS", "JonBranding Naming Intake Gate.md"),
            "Jamoa va PM.md": ("10-BUSINESS", "TEAM", "Jamoa va PM.md"),
            "People.md": ("10-BUSINESS", "TEAM", "People.md"),
            "Yordamchi Vazifalari.md": ("10-BUSINESS", "TEAM", "Yordamchi Vazifalari.md"),
            "Marketing va Kontent.md": ("50-CONTENT", "Marketing va Kontent.md"),
            "Dizayn Sifati.md": ("40-KNOWLEDGE", "IDENTITY", "Dizayn Sifati.md"),
            "AI Stack.md": ("40-KNOWLEDGE", "AI", "AI Stack.md"),
            "AI Automation.md": ("40-KNOWLEDGE", "AI", "AI Automation.md"),
            "AI va Ikkinchi Miya.md": ("40-KNOWLEDGE", "AI", "AI va Ikkinchi Miya.md"),
            "Brain MCP.md": ("40-KNOWLEDGE", "AI", "Brain MCP.md"),
            "AI Owner Proxy Protocol.md": ("40-KNOWLEDGE", "AI", "AI Owner Proxy Protocol.md"),
            "Ikkinchi Miya Boshqaruv Ritmi.md": ("00-SYSTEM", "Ikkinchi Miya Boshqaruv Ritmi.md"),
            "Haftalik Review.md": ("00-SYSTEM", "Haftalik Review.md"),
            "Baxtiyorjon.md": ("00-SYSTEM", "Baxtiyorjon (Dosye).md"),
        }
        for fname, dest_parts in areas_mapping.items():
            src_f = os.path.join(a20, fname)
            if os.path.exists(src_f):
                dst_f = os.path.join(vault, *dest_parts)
                safe_move(src_f, dst_f)
        # Any remaining in 20-Areas
        for f in os.listdir(a20):
            safe_move(os.path.join(a20, f), os.path.join(vault, "10-BUSINESS", "OPERATIONS", f))
        try:
            shutil.rmtree(a20)
            print("Removed 20-Areas folder.")
        except Exception:
            pass

    # 6. Move 30-Resources
    r30 = os.path.join(vault, "30-Resources")
    if os.path.exists(r30):
        resources_mapping = {
            "Xizmatlar.md": ("10-BUSINESS", "PRODUCTS", "Xizmatlar.md"),
            "Portfolio.md": ("60-REFERENCE", "Portfolio.md"),
            "Contractors_and_Partners_Network.md": ("10-BUSINESS", "TEAM", "Contractors_and_Partners_Network.md"),
            "React Hooks.md": ("40-KNOWLEDGE", "React Hooks.md"),
            "VIP_Partners_and_Clients_Archive.md": ("90-ARCHIVE", "VIP_Partners_and_Clients_Archive.md"),
            "JonBranding Memory Pack.md": ("90-ARCHIVE", "JonBranding Memory Pack.md"),
            "jonbranding_ai_memory_pack": ("90-ARCHIVE", "jonbranding_ai_memory_pack"),
            "Codex Memory Snapshot 2026-07-22.md": ("90-ARCHIVE", "Codex Memory Snapshot 2026-07-22.md"),
            "AI Javob Qoidalari.md": ("90-ARCHIVE", "AI Javob Qoidalari.md"),
            "Mijozlar.md": ("90-ARCHIVE", "Mijozlar (Eski).md"),
        }
        for fname, dest_parts in resources_mapping.items():
            src_f = os.path.join(r30, fname)
            if os.path.exists(src_f):
                dst_f = os.path.join(vault, *dest_parts)
                safe_move(src_f, dst_f)
        for f in os.listdir(r30):
            safe_move(os.path.join(r30, f), os.path.join(vault, "90-ARCHIVE", f))
        try:
            shutil.rmtree(r30)
            print("Removed 30-Resources folder.")
        except Exception:
            pass

    # 7. Move 40-Archive -> 90-ARCHIVE
    a40 = os.path.join(vault, "40-Archive")
    a90 = os.path.join(vault, "90-ARCHIVE")
    if os.path.exists(a40):
        safe_copy_tree(a40, a90)

    # 8. Move 60-Wiki -> 90-ARCHIVE/60-Wiki
    w60 = os.path.join(vault, "60-Wiki")
    w_dest = os.path.join(vault, "90-ARCHIVE", "60-Wiki")
    if os.path.exists(w60):
        safe_copy_tree(w60, w_dest)

    # 9. Update Graph View Colors (.obsidian/graph.json)
    graph_json_path = os.path.join(vault, ".obsidian", "graph.json")
    if os.path.exists(graph_json_path):
        try:
            with open(graph_json_path, "r", encoding="utf-8") as gf:
                graph_cfg = json.load(gf)

            # Elegant Palette for OISHA OS v0.1:
            graph_cfg["colorGroups"] = [
                {"query": "path:00-SYSTEM", "color": {"a": 1, "rgb": 10182117}},     # Purple / Magenta (#9B5DE5)
                {"query": "path:10-BUSINESS", "color": {"a": 1, "rgb": 48121}},       # Vibrant Azure (#00BBF9)
                {"query": "path:20-CLIENTS", "color": {"a": 1, "rgb": 62932}},        # Emerald Mint (#00F5D4)
                {"query": "path:30-PROJECTS", "color": {"a": 1, "rgb": 16471559}},    # Coral Flame (#FB5607)
                {"query": "path:40-KNOWLEDGE", "color": {"a": 1, "rgb": 16704576}},   # Amber Gold (#FEE440)
                {"query": "path:50-CONTENT", "color": {"a": 1, "rgb": 16711790}},     # Ruby Crimson (#FF006E)
                {"query": "path:60-REFERENCE", "color": {"a": 1, "rgb": 3835647}},    # Electric Blue (#3A86FF)
                {"query": "path:50-Daily", "color": {"a": 1, "rgb": 8599788}},        # Lavender Purple (#8338EC)
                {"query": "path:90-ARCHIVE", "color": {"a": 1, "rgb": 7107965}},      # Muted Slate (#6C757D)
            ]
            graph_cfg["showArrow"] = True
            graph_cfg["nodeSizeMultiplier"] = 1.25
            graph_cfg["lineSizeMultiplier"] = 1.1
            graph_cfg["centerStrength"] = 0.45
            graph_cfg["repelStrength"] = 14
            graph_cfg["linkStrength"] = 0.85
            graph_cfg["linkDistance"] = 220

            with open(graph_json_path, "w", encoding="utf-8") as gf:
                json.dump(graph_cfg, gf, indent=2)
            print(f"Updated .obsidian/graph.json with OISHA OS neural galaxy palette!")
        except Exception as ge:
            print(f"Failed to update graph.json: {ge}")

    # 10. Update broken explicit folder wikilinks across markdown files
    link_replacements = {
        "[[10-Projects/": "[[30-PROJECTS/",
        "[[20-Areas/Savdo": "[[10-BUSINESS/SALES/Savdo",
        "[[20-Areas/JonBranding Operations": "[[10-BUSINESS/OPERATIONS/JonBranding Operations",
        "[[20-Areas/": "[[10-BUSINESS/",
        "[[70-Mijozlar/": "[[20-CLIENTS/",
        "[[70-Odamlar/": "[[10-BUSINESS/TEAM/",
        "[[30-Resources/": "[[60-REFERENCE/",
    }
    
    updated_files = 0
    for root, _, files in os.walk(vault):
        if ".git" in root or ".obsidian" in root:
            continue
        for f in files:
            if f.endswith(".md"):
                fp = os.path.join(root, f)
                try:
                    text = open(fp, "r", encoding="utf-8").read()
                    changed = False
                    for old_link, new_link in link_replacements.items():
                        if old_link in text:
                            text = text.replace(old_link, new_link)
                            changed = True
                    if changed:
                        with open(fp, "w", encoding="utf-8") as out:
                            out.write(text)
                        updated_files += 1
                except Exception:
                    pass
    print(f"Updated wikilinks in {updated_files} notes.")


if __name__ == "__main__":
    for v in VAULTS:
        consolidate_vault(v)
