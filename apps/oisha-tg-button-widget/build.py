"""Vidjet arxivini yigʻadi: python apps/oisha-tg-button-widget/build.py"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["manifest.json", "script.js", "i18n/ru.json", "i18n/en.json"] + [
    "images/" + n for n in ("logo_main.png", "logo.png", "logo_small.png", "logo_min.png", "logo_medium.png")
]

if __name__ == "__main__":
    out = os.path.join(HERE, "widget.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(os.path.join(HERE, f), f)
    print(out)
