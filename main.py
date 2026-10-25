# main.py — Nytron Kivy App (White & Black Theme + Pro Login)
import asyncio
import threading
import json
import os
import time
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle

try:
    from mytg_core import MyTG
    import mytg_patch
    HAS_CORE = True
    CORE_ERROR = ""
except Exception as e:
    HAS_CORE = False
    CORE_ERROR = str(e)

# Force Dark Theme Window Background
Window.clearcolor = (0.05, 0.05, 0.05, 1)

_loop = None
_tg = None

def get_loop():
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()
        t = threading.Thread(target=_loop.run_forever, daemon=True)
        t.start()
    return _loop

def run_async_wait(coro, timeout=90):
    loop = get_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return fut.result(timeout=timeout)
    except Exception as e:
        return e

# ==================== BASE UI ====================
class BaseScreen(Screen):
    title = StringProperty("Nytron")

    def __init__(self, **kw):
        super().__init__(**kw)
        # Main Layout with Dark Background
        self.layout = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        
        with self.layout.canvas.before:
            Color(0.08, 0.08, 0.08, 1) # Very dark grey/black
            self.rect = Rectangle(size=self.layout.size, pos=self.layout.pos)
        self.layout.bind(size=self._update_rect, pos=self._update_rect)

        # Top Bar
        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        back_btn = Button(text="<", size_hint_x=None, width=dp(50),
                          background_color=(0.15, 0.15, 0.15, 1),
                          color=(1, 1, 1, 1), font_size=sp(20), bold=True)
        back_btn.bind(on_press=self.go_back)
        
        title_lbl = Label(text=self.title, font_size=sp(18), bold=True, color=(1, 1, 1, 1))
        top.add_widget(back_btn)
        top.add_widget(title_lbl)
        self.layout.add_widget(top)

        # Content Area
        self.scroll = ScrollView()
        self.content = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(12), padding=dp(10))
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.layout.add_widget(self.scroll)
        self.add_widget(self.layout)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def go_back(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "menu"

    def add_button(self, text, cb, color=(0.2, 0.2, 0.2, 1)):
        btn = Button(text=text, size_hint_y=None, height=dp(50),
                     background_color=color, color=(1, 1, 1, 1), 
                     font_size=sp(15), bold=True)
        btn.bind(on_press=cb)
        self.content.add_widget(btn)
        return btn

    def add_label(self, text, color=(0.8, 0.8, 0.8, 1), size=sp(14)):
        lbl = Label(text=text, size_hint_y=None, height=dp(30),
                    color=color, font_size=size,
                    text_size=(Window.width - dp(40), None),
                    halign="center", valign="middle")
        self.content.add_widget(lbl)
        return lbl

    def add_input(self, hint, password=False):
        inp = TextInput(hint_text=hint, multiline=False,
                        size_hint_y=None, height=dp(50),
                        password=password, font_size=sp(15),
                        background_color=(0.15, 0.15, 0.15, 1),
                        foreground_color=(1, 1, 1, 1),
                        cursor_color=(1, 1, 1, 1),
                        hint_text_color=(0.5, 0.5, 0.5, 1))
        self.content.add_widget(inp)
        return inp

    def popup(self, title, msg, size=(0.88, 0.45)):
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        lbl = Label(text=str(msg), text_size=(Window.width - dp(80), None),
                    valign="top", halign="left", size_hint_y=0.8, color=(1,1,1,1))
        lbl.bind(size=lambda *a: setattr(lbl, "text_size", (lbl.width, None)))
        content.add_widget(lbl)
        btn = Button(text="Close", size_hint_y=None, height=dp(45),
                     background_color=(0.3, 0.3, 0.3, 1), color=(1,1,1,1))
        content.add_widget(btn)
        p = Popup(title=title, content=content, size_hint=size,
                  background_color=(0.1, 0.1, 0.1, 1), title_color=(1,1,1,1))
        btn.bind(on_press=p.dismiss)
        p.open()
        return p

    def prompt_multi(self, title, fields, on_submit, size=(0.9, 0.8)):
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        inputs = {}
        inner = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        inner.bind(minimum_height=inner.setter("height"))
        for f in fields:
            key, hint = f[0], f[1]
            password = f[2] if len(f) > 2 else False
            inner.add_widget(Label(text=hint, size_hint_y=None, height=dp(25),
                                    size=sp(13), color=(0.7, 0.7, 0.7, 1)))
            inp = TextInput(hint_text=hint, multiline=False,
                            password=password, size_hint_y=None, height=dp(45),
                            font_size=sp(14), background_color=(0.15, 0.15, 0.15, 1),
                            foreground_color=(1, 1, 1, 1), cursor_color=(1, 1, 1, 1))
            inner.add_widget(inp)
            inputs[key] = inp
        scroll = ScrollView(size_hint_y=0.85)
        scroll.add_widget(inner)
        content.add_widget(scroll)
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        ok_btn = Button(text="OK", background_color=(0.9, 0.9, 0.9, 1), color=(0,0,0,1), bold=True)
        cancel_btn = Button(text="Cancel", background_color=(0.3, 0.3, 0.3, 1), color=(1,1,1,1))
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)
        popup = Popup(title=title, content=content, size_hint=size,
                      background_color=(0.1, 0.1, 0.1, 1), title_color=(1,1,1,1))

        def do_ok(*a):
            popup.dismiss()
            vals = {k: v.text for k, v in inputs.items()}
            on_submit(vals)

        ok_btn.bind(on_press=do_ok)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()
        return popup


# ==================== LOGIN SCREEN (PRO) ====================
class LoginScreen(BaseScreen):
    title = "Nytron Login"

    def on_enter(self):
        self.content.clear_widgets()
        # Logo text
        self.add_label("[b]NYTRON[/b]", color=(1, 1, 1, 1), size=sp(36))
        self.add_label("Advanced Telegram Manager", color=(0.5, 0.5, 0.5, 1), size=sp(14))
        self.content.add_widget(Label(size_hint_y=None, height=dp(20)))
        
        # Tab-like buttons
        self.add_label("Bot Token Login", color=(1, 1, 1, 1), size=sp(16))
        self.bot_token = self.add_input("Paste bot token (12345:ABC...)", password=True)
        self.add_button("Login as Bot", self.login_bot, color=(0.9, 0.9, 0.9, 1)) # White button
        
        self.content.add_widget(Label(size_hint_y=None, height=dp(10)))
        self.add_label("Phone Login", color=(1, 1, 1, 1), size=sp(16))
        self.phone_num = self.add_input("Phone number (+91...)")
        self.phone_name = self.add_input("Account Label (e.g. Main)")
        self.add_button("Send OTP", self.login_phone_start, color=(0.2, 0.2, 0.2, 1))
        
        self.content.add_widget(Label(size_hint_y=None, height=dp(20)))
        self.add_label("Import Session String", color=(1, 1, 1, 1), size=sp(16))
        self.sess_str = self.add_input("Session string", password=True)
        self.add_button("Import Session", self.import_session, color=(0.2, 0.2, 0.2, 1))

        self.status = self.add_label("", color=(0.8, 0.8, 0.8, 1), size=sp(13))

    def set_status(self, txt, color=(1, 1, 1, 1)):
        Clock.schedule_once(lambda dt: setattr(self.status, "text", txt), 0)
        Clock.schedule_once(lambda dt: setattr(self.status, "color", color), 0)

    def login_bot(self, *a):
        if not HAS_CORE:
            self.popup("Error", f"Core: {CORE_ERROR}")
            return
        token = self.bot_token.text.strip()
        if not token:
            self.popup("Error", "Enter bot token")
            return
        self.set_status("Logging in...")

        def _w():
            try:
                acc = run_async_wait(_tg.login_bot("bot", token))
                if isinstance(acc, Exception):
                    self.set_status(f"Error: {acc}", (1, 0.3, 0.3, 1))
                else:
                    self.set_status(f"Logged in: @{acc.name}", (0.3, 1, 0.3, 1))
                    Clock.schedule_once(lambda dt: self.go_menu(), 1)
            except Exception as e:
                self.set_status(f"Error: {e}", (1, 0.3, 0.3, 1))
        threading.Thread(target=_w, daemon=True).start()

    def login_phone_start(self, *a):
        if not HAS_CORE:
            self.popup("Error", f"Core: {CORE_ERROR}")
            return
        phone = self.phone_num.text.strip()
        name = self.phone_name.text.strip() or "user"
        if not phone:
            self.popup("Error", "Enter phone number")
            return
        self.set_status("Sending OTP...")

        def _w():
            try:
                sd = run_async_wait(_tg.login_phone_start(name, phone))
                if isinstance(sd, Exception):
                    self.set_status(f"Error: {sd}", (1, 0.3, 0.3, 1))
                    return
                self.set_status("OTP sent!", (0.3, 1, 0.3, 1))
                Clock.schedule_once(lambda dt: self._otp_popup(sd), 0)
            except Exception as e:
                self.set_status(f"Error: {e}", (1, 0.3, 0.3, 1))
        threading.Thread(target=_w, daemon=True).start()

    def _otp_popup(self, session_data):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(15))
        content.add_widget(Label(text="Enter Telegram OTP Code", color=(1,1,1,1)))
        otp_inp = TextInput(hint_text="12345", multiline=False,
                            size_hint_y=None, height=dp(50), font_size=sp(20),
                            halign="center", background_color=(0.15,0.15,0.15,1),
                            foreground_color=(1,1,1,1))
        content.add_widget(otp_inp)
        popup = Popup(title="OTP Verification", content=content,
                      size_hint=(0.9, 0.35), auto_dismiss=False,
                      background_color=(0.1,0.1,0.1,1), title_color=(1,1,1,1))

        def do_verify(*a):
            otp = otp_inp.text.strip()
            if not otp: return
            popup.dismiss()
            self.set_status("Verifying OTP...")

            def _w():
                try:
                    acc = run_async_wait(_tg.login_phone_complete(session_data, otp))
                    if isinstance(acc, Exception):
                        if "2FA_REQUIRED" in str(acc):
                            self.set_status("2FA Password needed", (1, 0.7, 0.3, 1))
                            Clock.schedule_once(lambda dt: self._2fa_popup(session_data, otp), 0)
                        else:
                            self.set_status(f"Error: {acc}", (1, 0.3, 0.3, 1))
                    else:
                        self.set_status(f"Logged in: {acc.name}", (0.3, 1, 0.3, 1))
                        Clock.schedule_once(lambda dt: self.go_menu(), 1)
                except Exception as e:
                    self.set_status(f"Error: {e}", (1, 0.3, 0.3, 1))
            threading.Thread(target=_w, daemon=True).start()

        btn = Button(text="Verify", size_hint_y=None, height=dp(45),
                     background_color=(0.9, 0.9, 0.9, 1), color=(0,0,0,1), bold=True)
        btn.bind(on_press=do_verify)
        content.add_widget(btn)
        popup.open()

    def _2fa_popup(self, session_data, otp):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(15))
        content.add_widget(Label(text="Enter 2FA Password", color=(1,1,1,1)))
        pw_inp = TextInput(hint_text="Password", multiline=False, password=True,
                           size_hint_y=None, height=dp(50),
                           background_color=(0.15,0.15,0.15,1), foreground_color=(1,1,1,1))
        content.add_widget(pw_inp)
        popup = Popup(title="2FA Verification", content=content,
                      size_hint=(0.9, 0.35), auto_dismiss=False,
                      background_color=(0.1,0.1,0.1,1), title_color=(1,1,1,1))

        def do_verify(*a):
            pw = pw_inp.text
            if not pw: return
            popup.dismiss()
            self.set_status("Verifying 2FA...")

            def _w():
                try:
                    acc = run_async_wait(_tg.login_phone_complete(session_data, otp, password=pw))
                    if isinstance(acc, Exception):
                        self.set_status(f"Error: {acc}", (1, 0.3, 0.3, 1))
                    else:
                        self.set_status(f"Logged in: {acc.name}", (0.3, 1, 0.3, 1))
                        Clock.schedule_once(lambda dt: self.go_menu(), 1)
                except Exception as e:
                    self.set_status(f"Error: {e}", (1, 0.3, 0.3, 1))
            threading.Thread(target=_w, daemon=True).start()

        btn = Button(text="Verify", size_hint_y=None, height=dp(45),
                     background_color=(0.9, 0.9, 0.9, 1), color=(0,0,0,1), bold=True)
        btn.bind(on_press=do_verify)
        content.add_widget(btn)
        popup.open()

    def import_session(self, *a):
        if not HAS_CORE: return
        sess = self.sess_str.text.strip()
        if not sess:
            self.popup("Error", "Enter session string")
            return
        self.set_status("Importing...")
        def _w():
            try:
                acc = run_async_wait(_tg.login_session("imported", sess))
                if isinstance(acc, Exception):
                    self.set_status(f"Error: {acc}", (1, 0.3, 0.3, 1))
                else:
                    self.set_status(f"Imported: {acc.name}", (0.3, 1, 0.3, 1))
                    Clock.schedule_once(lambda dt: self.go_menu(), 1)
            except Exception as e:
                self.set_status(f"Error: {e}", (1, 0.3, 0.3, 1))
        threading.Thread(target=_w, daemon=True).start()

    def go_menu(self, *a):
        def _w():
            try: run_async_wait(_tg.start_all(), timeout=120)
            except Exception: pass
        threading.Thread(target=_w, daemon=True).start()
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "menu"

# ==================== MENU & OTHER SCREENS ====================
# (Note: Menus aur baaki screens same rahenge jaise pichle code me the,
# sirf color black & white kar diya gaya hai base class me)
class MenuScreen(BaseScreen):
    title = "Nytron — Main Menu"
    def on_enter(self):
        self.content.clear_widgets()
        items = [
            ("Accounts", "accounts"),
            ("Messages", "messages"),
            ("Groups & Channels", "groups"),
            ("User Tools", "users"),
            ("Privacy & Profile", "privacy"),
            ("AyuGram Extras", "ayugram"),
            ("Search", "search"),
            ("Dialogs", "dialogs"),
            ("Stories", "stories"),
            ("Vault", "vault"),
            ("Media & Export", "media"),
        ]
        for label, scr in items:
            self.add_button(label, lambda *a, s=scr: self.goto(s))

    def goto(self, name):
        if not self.manager.has_screen(name):
            self.manager.add_widget(SCREEN_MAP[name]())
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = name

# Baaki screens (AccountsScreen, MessagesScreen, etc.) waisi hi rahengi
# Unhe tu pichle message se copy kar sakta hai, unka logic same hai.
# Main file size chota rakhne ke liye unhe yahan include nahi kar raha.
# Bas unke saare color parameters default Black & White le lenge.

# TEMPORARY: Placeholder maps to prevent crash if other screens not added
class PlaceholderScreen(BaseScreen):
    pass

SCREEN_MAP = {
    "accounts": PlaceholderScreen, "messages": PlaceholderScreen,
    "groups": PlaceholderScreen, "users": PlaceholderScreen,
    "privacy": PlaceholderScreen, "ayugram": PlaceholderScreen,
    "search": PlaceholderScreen, "dialogs": PlaceholderScreen,
    "stories": PlaceholderScreen, "vault": PlaceholderScreen,
    "media": PlaceholderScreen,
}

class NytronApp(App):
    def build(self):
        global _tg
        if HAS_CORE:
            try: _tg = MyTG()
            except: _tg = None
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(MenuScreen(name="menu"))
        sm.current = "login"
        return sm

if __name__ == "__main__":
    NytronApp().run()
