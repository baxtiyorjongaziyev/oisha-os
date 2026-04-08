import zipfile
import os

def bundle_widget():
    widget_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(widget_dir, "oisha_widget_v1.zip")
    
    # Files and folders to include
    items = [
        "manifest.json",
        "script.js",
        "style.css",
        "i18n/ru.json",
        "i18n/en.json",
        "templates/index.twig",
        "images/logo.png",
        "images/logo_small.png"
    ]
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for item in items:
            full_path = os.path.join(widget_dir, item)
            if os.path.exists(full_path):
                zipf.write(full_path, item)
            else:
                print(f"Warning: {item} not found!")
                
    print(f"✅ Oisha Widget bundled at: {zip_path}")

if __name__ == "__main__":
    bundle_widget()
