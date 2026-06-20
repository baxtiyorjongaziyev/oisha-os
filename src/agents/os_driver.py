"""
Oisha OS Driver — PyAutoGUI + MSS asosida desktop avtomatizatsiyasi.

Oisha-OS tizimi uchun kompyuter ekranini ko'rish,
sichqonchani boshqarish va klaviaturada yozish imkoniyatini beradi.
"""
import pyautogui
import mss
import mss.tools
import time
import os
import logging
import subprocess
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# PyAutoGUI global sozlamalari
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


class OishaOSDriver:
    """PyAutoGUI va MSS asosidagi desktop avtomatizatsiya driveri."""

    def __init__(self):
        self.sct = mss.MSS()
        logger.info("[OSDriver] Initialized.")

    # ── Screen ─────────────────────────────────────────────

    def get_screen_size(self) -> Tuple[int, int]:
        """Ekran o'lchamlarini olish (width, height)."""
        return pyautogui.size()

    def take_screenshot(self, filename: str = "os_screenshot.png", region: Optional[Tuple] = None) -> str:
        """
        Ekran skrinshotini olish.
        region: (x, y, width, height) — ixtiyoriy, faqat shu qismni olish.
        """
        if region:
            monitor = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
            sct_img = self.sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=filename)
        else:
            self.sct.shot(mon=1, output=filename)
        logger.info(f"[OSDriver] Screenshot saved to {filename}")
        return filename

    def get_pixel_color(self, x: int, y: int) -> Tuple[int, int, int]:
        """Berilgan koordinatadagi piksel rangini olish (R, G, B)."""
        img = pyautogui.screenshot(region=(x, y, 1, 1))
        return img.getpixel((0, 0))[:3]

    # ── Mouse ──────────────────────────────────────────────

    def get_mouse_position(self) -> Tuple[int, int]:
        """Sichqonchaning hozirgi koordinatalarini olish."""
        return pyautogui.position()

    def move_to(self, x: int, y: int, duration: float = 0.3):
        """Sichqonchani berilgan koordinataga silliq ko'chirish."""
        logger.info(f"[OSDriver] Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=duration)

    def click(self, x: int, y: int, clicks: int = 1, button: str = "left"):
        """Berilgan koordinatada bosish."""
        logger.info(f"[OSDriver] Clicking at ({x}, {y}) button={button}")
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)

    def double_click(self, x: int, y: int):
        """Ikki marta bosish."""
        logger.info(f"[OSDriver] Double-clicking at ({x}, {y})")
        pyautogui.doubleClick(x=x, y=y)

    def right_click(self, x: int, y: int):
        """O'ng tugma bilan bosish."""
        logger.info(f"[OSDriver] Right-clicking at ({x}, {y})")
        pyautogui.rightClick(x=x, y=y)

    def drag_to(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        """Sichqonchani bir nuqtadan ikkinchisiga sudrab olib borish (drag)."""
        logger.info(f"[OSDriver] Dragging from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        pyautogui.moveTo(start_x, start_y, duration=0.2)
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)

    def scroll(self, amount: int = 3, x: Optional[int] = None, y: Optional[int] = None):
        """
        Sahifani aylantirish.
        amount > 0 — yuqoriga, amount < 0 — pastga.
        """
        logger.info(f"[OSDriver] Scrolling {amount} at ({x}, {y})")
        pyautogui.scroll(amount, x=x, y=y)

    # ── Keyboard ───────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.04, enter: bool = False):
        """
        Matn yozish (lotin harflari uchun).
        Kirill yoki maxsus belgilar uchun type_text_clipboard ni ishlating.
        """
        logger.info(f"[OSDriver] Typing: {text[:40]}...")
        pyautogui.write(text, interval=interval)
        if enter:
            pyautogui.press("enter")

    def type_text_clipboard(self, text: str, enter: bool = False):
        """
        Matn yozish (clipboard orqali — har qanday til uchun ishlaydi).
        Unicode/Kirill/O'zbek harflarini to'g'ri kiritish uchun.
        """
        import pyperclip
        logger.info(f"[OSDriver] Typing via clipboard: {text[:40]}...")
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        if enter:
            pyautogui.press("enter")

    def press_key(self, key: str):
        """Bitta tugmani bosish (enter, tab, escape, space, delete va h.k.)."""
        logger.info(f"[OSDriver] Pressing key: {key}")
        pyautogui.press(key)

    def hotkey(self, *keys):
        """
        Tugmalar kombinatsiyasini bosish.
        Masalan: hotkey('ctrl', 'c') — nusxalash.
        """
        logger.info(f"[OSDriver] Pressing hotkey: {'+'.join(keys)}")
        pyautogui.hotkey(*keys)

    def key_down(self, key: str):
        """Tugmani bosib turish (keydown)."""
        pyautogui.keyDown(key)

    def key_up(self, key: str):
        """Tugmani qo'yib yuborish (keyup)."""
        pyautogui.keyUp(key)

    # ── Applications ───────────────────────────────────────

    def open_application(self, app_path: str) -> subprocess.Popen:
        """
        Dasturni ochish (to'liq yo'l yoki ism).
        Masalan: open_application('notepad.exe')
        """
        logger.info(f"[OSDriver] Opening application: {app_path}")
        return subprocess.Popen(app_path, shell=True)

    def open_start_menu(self):
        """Windows Start menyusini ochish."""
        pyautogui.press("win")
        time.sleep(0.5)

    def open_run_dialog(self):
        """Windows Run dialogini ochish (Win+R)."""
        pyautogui.hotkey("win", "r")
        time.sleep(0.5)

    def search_and_open(self, query: str):
        """
        Windows qidiruvida dastur yoki faylni topib ochish.
        Start menyusini ochib, matn yozib, Enter bosadi.
        """
        logger.info(f"[OSDriver] Searching and opening: {query}")
        pyautogui.press("win")
        time.sleep(0.8)
        pyautogui.write(query, interval=0.05)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(1.5)

    # ── Window Management ──────────────────────────────────

    def minimize_window(self):
        """Hozirgi oynani kichraytirish."""
        pyautogui.hotkey("win", "down")

    def maximize_window(self):
        """Hozirgi oynani kattalshtirish."""
        pyautogui.hotkey("win", "up")

    def close_window(self):
        """Hozirgi oynani yopish (Alt+F4)."""
        pyautogui.hotkey("alt", "F4")

    def switch_window(self):
        """Boshqa oynaga o'tish (Alt+Tab)."""
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.5)

    def snap_window_left(self):
        """Oynani ekranning chap yarmiga qo'yish."""
        pyautogui.hotkey("win", "left")

    def snap_window_right(self):
        """Oynani ekranning o'ng yarmiga qo'yish."""
        pyautogui.hotkey("win", "right")

    # ── Clipboard ──────────────────────────────────────────

    def copy(self):
        """Tanlangan matnni nusxalash (Ctrl+C)."""
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.1)

    def paste(self):
        """Clipboard dan qo'yish (Ctrl+V)."""
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)

    def cut(self):
        """Tanlangan matnni kesish (Ctrl+X)."""
        pyautogui.hotkey("ctrl", "x")
        time.sleep(0.1)

    def select_all(self):
        """Barchasini tanlash (Ctrl+A)."""
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)

    def undo(self):
        """Orqaga qaytarish (Ctrl+Z)."""
        pyautogui.hotkey("ctrl", "z")

    def redo(self):
        """Qayta bajarish (Ctrl+Y)."""
        pyautogui.hotkey("ctrl", "y")

    # ── Image Recognition (Ekranda rasm qidirish) ─────────

    def find_on_screen(self, image_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """
        Ekranda rasm (icon, tugma) ni qidirish.
        Topilsa markaziy (x, y) koordinatalarini qaytaradi.
        confidence: 0.0 - 1.0 (aniqlik darajasi).
        """
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location:
                center = pyautogui.center(location)
                logger.info(f"[OSDriver] Found image at ({center.x}, {center.y})")
                return (center.x, center.y)
        except Exception as e:
            logger.warning(f"[OSDriver] Image not found or error: {e}")
        return None

    def click_on_image(self, image_path: str, confidence: float = 0.8) -> bool:
        """Ekranda rasmni topib, unga bosish."""
        pos = self.find_on_screen(image_path, confidence)
        if pos:
            self.click(pos[0], pos[1])
            return True
        return False

    def wait_for_image(self, image_path: str, timeout: int = 15, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """
        Rasm ekranda paydo bo'lguncha kutish.
        timeout soniyalarda beriladi.
        """
        start = time.time()
        while time.time() - start < timeout:
            pos = self.find_on_screen(image_path, confidence)
            if pos:
                return pos
            time.sleep(0.5)
        logger.warning(f"[OSDriver] Image not found within {timeout}s: {image_path}")
        return None

    # ── Utility ────────────────────────────────────────────

    def sleep(self, seconds: float):
        """Berilgan vaqt kutish."""
        time.sleep(seconds)

    def alert(self, text: str, title: str = "Oisha-OS"):
        """Foydalanuvchiga xabar ko'rsatish (popup)."""
        pyautogui.alert(text=text, title=title)

    def confirm(self, text: str, title: str = "Oisha-OS") -> str:
        """Ha/Yo'q dialog ko'rsatish. 'OK' yoki 'Cancel' qaytaradi."""
        return pyautogui.confirm(text=text, title=title)

    def prompt(self, text: str, title: str = "Oisha-OS", default: str = "") -> Optional[str]:
        """Foydalanuvchidan matn so'rash."""
        return pyautogui.prompt(text=text, title=title, default=default)


# Sinov uchun
if __name__ == "__main__":
    driver = OishaOSDriver()
    w, h = driver.get_screen_size()
    print(f"Screen size: {w}x{h}")
    print(f"Mouse position: {driver.get_mouse_position()}")
    driver.take_screenshot("os_test_screenshot.png")
    print("Test complete. Check os_test_screenshot.png.")
