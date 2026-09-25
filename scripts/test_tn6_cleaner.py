#!/usr/bin/env python3
"""Test TN6 contact extraction and cleaning logic."""
import csv
import re
from pathlib import Path

import sys
sys.stdout.reconfigure(encoding="utf-8")

def extract_phones(p: str) -> list[str]:
    if not p:
        return []
    # Find all international 998 numbers or 9-digit local numbers
    matches = re.findall(r"(?:\+?998\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}|\b\d{9}\b)", p)
    result = []
    seen = set()
    for m in matches:
        clean = re.sub(r"\D", "", m)
        if len(clean) == 9:
            clean = "998" + clean
        if len(clean) == 12 and clean.startswith("998"):
            norm = "+" + clean
            if norm not in seen:
                seen.add(norm)
                result.append(norm)
    return result

def extract_telegrams(text: str) -> list[str]:
    if not text:
        return []
    # Find all @usernames
    found = re.findall(r"@[a-zA-Z0-9_]{4,}", text)
    # Also check if text has "Username: something"
    m_uname = re.findall(r"(?:Username|username|TG Username):\s*@?([a-zA-Z0-9_]{4,})", text)
    for u in m_uname:
        found.append(f"@{u}")
    res = []
    seen = set()
    for u in found:
        low = u.lower()
        if low not in seen:
            seen.add(low)
            res.append(u)
    return res

def clean_contact_name(orig: str) -> str:
    s = orig or ""
    # Strip TN suffixes repeatedly
    pattern_tn = re.compile(
        r"(?:\s*TN\d*\s*(?:Gr|gr)?|\s*TN\s*(?:Gr|gr)?|\s*Tez\s*Natija\s*\d*|\s*TN\d*)+\s*$",
        re.IGNORECASE
    )
    s = pattern_tn.sub("", s).strip()
    
    # Strip leading/trailing punctuation and symbols
    s = re.sub(r"^[\s.,;:_()\-+*!?\"'`~#@^%&=/\\|<>\[\]{}]+", "", s)
    s = re.sub(r"[\s.,;:_()\-+*!?\"'`~#@^%&=/\\|<>\[\]{}]+$", "", s)
    s = s.strip()
    
    # If no letters remain, check if it's a phone number or just symbols
    if not re.search(r"[a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ]", s):
        m_dig = re.search(r"\d{7,}", s)
        if m_dig:
            return m_dig.group(0)
        return ""
    return s

def test_extraction():
    c7_path = Path(r"C:\Users\baxti\Downloads\contacts (7).csv")
    c6_path = Path(r"C:\Users\baxti\Downloads\contacts (6).csv")
    
    assert c7_path.exists()
    assert c6_path.exists()
    
    with open(c7_path, "r", encoding="utf-8") as f:
        tn6_rows = list(csv.DictReader(f))
        for r in tn6_rows:
            r["_source_file"] = "contacts (7).csv"
            
    with open(c6_path, "r", encoding="utf-8") as f:
        c6_rows = list(csv.DictReader(f))
        
    def k7(r):
        return (r.get("First Name", "").strip(), r.get("Last Name", "").strip())
        
    seen_k = {k7(r) for r in tn6_rows}
    extra_tn6 = []
    for r in c6_rows:
        fn = r.get("First Name", "")
        ln = r.get("Last Name", "")
        if ("TN6" in fn or "TN6" in ln) and k7(r) not in seen_k:
            r["_source_file"] = "contacts (6).csv"
            extra_tn6.append(r)
            seen_k.add(k7(r))
            
    all_contacts = tn6_rows + extra_tn6
    print(f"Total extracted TN6: {len(all_contacts)} (324 from c7 + {len(extra_tn6)} from c6)")
    
    sample_clean = []
    for r in all_contacts[:10]:
        fn = r.get("First Name", "")
        ln = r.get("Last Name", "")
        full = (fn + " " + ln).strip()
        cl = clean_contact_name(full)
        p1 = extract_phones(r.get("Phone 1 - Value", "") + " " + r.get("Phone 2 - Value", ""))
        tgs = extract_telegrams(r.get("Notes", "") + " " + full)
        sample_clean.append((full, cl, p1, tgs))
        
    for orig, cl, p1, tgs in sample_clean:
        print(f"Orig: {orig!r} -> Clean: {cl!r} | Phone: {p1!r} | TG: {tgs}")

if __name__ == "__main__":
    test_extraction()
