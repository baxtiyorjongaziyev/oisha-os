import os

def fix_syntax():
    src_dir = "src"
    target = "Noma'lum"
    replacement = "Unknown"
    
    count = 0
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if target in content:
                    fixed = content.replace(target, replacement)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(fixed)
                    print(f"Fixed: {path}")
                    count += 1
    print(f"Total files fixed: {count}")

if __name__ == "__main__":
    fix_syntax()
