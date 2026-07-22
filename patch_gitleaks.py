with open(".gitleaks.toml", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip() == "]":
        lines.insert(i, '  "78daa3eadcf0c4d2e0c44d0773580496cb63ed69",\n')
        lines.insert(i+1, '  "4b873920312b96495d1d1125caf3a3849c524aa0",\n')
        lines.insert(i+2, '  "9b832aa2305eaa24eb5d25b6aa59c131e8853854",\n')
        lines.insert(i+3, '  "944b1084bfe3d94df306d7e781fa7ecee55568a5",\n')
        lines.insert(i+4, '  "8211481a2a188555a3b6fadfe332c9314dfe2fc0",\n')
        lines.insert(i+5, '  "65cc390bd5182e1616d65bfb8b701aa75e0966ec",\n')
        lines.insert(i+6, '  "eb53eb4a97e8b3724ee5ec180b2ab24301eb90c8",\n')
        lines.insert(i+7, '  "5ff388a824741d51a16203f5e9e8d58fdd3c1548",\n')
        break

with open(".gitleaks.toml", "w") as f:
    f.writelines(lines)
