# main.py — Nytron  (Soft B&W UI — Telegram-style login)
# Soft black-white + country-code login + feature toggles

import asyncio
import threading
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle

# ── Pure Black & White (no color accents) ───────────────────
BG          = (0.00, 0.00, 0.00, 1)       # pure black
CARD        = (0.10, 0.10, 0.10, 1)       # dark gray surface
ACCENT      = (1.00, 1.00, 1.00, 1)       # white
ACCENT2     = (0.75, 0.75, 0.75, 1)       # light gray
DANGER      = (0.90, 0.90, 0.90, 1)       # white (no red)
SUCCESS     = (1.00, 1.00, 1.00, 1)       # white
WARN        = (0.70, 0.70, 0.70, 1)       # gray
TEXT        = (1.00, 1.00, 1.00, 1)       # white
MUTED       = (0.50, 0.50, 0.50, 1)       # mid gray
INPUT_BG    = (0.14, 0.14, 0.14, 1)       # input gray

Window.clearcolor = BG

try:
    from mytg_core import MyTG
    import mytg_patch
    HAS_CORE = True
    CORE_ERROR = ""
except Exception as e:
    HAS_CORE = False
    CORE_ERROR = str(e)

_loop = None
_tg = None
_current_aid = None


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


def set_current(aid):
    global _current_aid
    _current_aid = aid


def get_current():
    global _current_aid
    if _current_aid and _tg and _current_aid in _tg.clients:
        return _current_aid
    if _tg and _tg.clients:
        _current_aid = list(_tg.clients.keys())[0]
        return _current_aid
    return None


# Common country codes (Pro / TG style)
COUNTRY_CODES = [
    ("India", "+91"), ("United States", "+1"), ("United Kingdom", "+44"),
    ("Russia", "+7"), ("UAE", "+971"), ("Saudi Arabia", "+966"),
    ("Pakistan", "+92"), ("Bangladesh", "+880"), ("Indonesia", "+62"),
    ("Turkey", "+90"), ("Germany", "+49"), ("France", "+33"),
    ("Brazil", "+55"), ("Ukraine", "+380"), ("Iran", "+98"),
    ("Egypt", "+20"), ("Nigeria", "+234"), ("South Africa", "+27"),
    ("Canada", "+1"), ("Australia", "+61"), ("Japan", "+81"),
    ("South Korea", "+82"), ("China", "+86"), ("Singapore", "+65"),
    ("Malaysia", "+60"), ("Thailand", "+66"), ("Vietnam", "+84"),
    ("Philippines", "+63"), ("Nepal", "+977"), ("Sri Lanka", "+94"),
]

FEATURE_FLAGS = {
    "anti_recall": True,
    "ghost_default": False,
    "local_premium": False,
    "auto_react": False,
    "streamer": False,
    "mass_tools": True,
    "vault": True,
}



# ── Custom neon button ──────────────────────────────────────
class NeonButton(Button):
    def __init__(self, text="", color=ACCENT, **kw):
        super().__init__(**kw)
        self.text = text
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = TEXT
        self.font_size = sp(14)
        self.bold = True
        self.size_hint_y = None
        self.height = dp(50)
        self._neon = color
        with self.canvas.before:
            Color(*color)
            self._border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 12), width=1.4)
            Color(color[0], color[1], color[2], 0.12)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._update, size=self._update)

    def _update(self, *a):
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, 12)
        self._bg.pos = self.pos
        self._bg.size = self.size


class SectionLabel(Label):
    def __init__(self, text="", **kw):
        super().__init__(**kw)
        self.text = text
        self.color = ACCENT
        self.font_size = sp(13)
        self.bold = True
        self.size_hint_y = None
        self.height = dp(28)
        self.halign = "left"
        self.text_size = (Window.width - dp(40), None)


# ── Base Screen ─────────────────────────────────────────────
class BaseScreen(Screen):
    title = StringProperty("Nytron")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        # header bar
        header = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        back = NeonButton(text="◀", color=MUTED)
        back.size_hint_x = None
        back.width = dp(48)
        back.bind(on_press=self.go_back)
        self.title_lbl = Label(text=self.title, color=TEXT, font_size=sp(18), bold=True,
                               halign="left", valign="middle")
        self.title_lbl.bind(size=lambda *a: setattr(self.title_lbl, "text_size", self.title_lbl.size))
        self.acc_lbl = Label(text="", color=ACCENT, font_size=sp(11), size_hint_x=None, width=dp(110),
                             halign="right", valign="middle")
        self.acc_lbl.bind(size=lambda *a: setattr(self.acc_lbl, "text_size", self.acc_lbl.size))
        header.add_widget(back)
        header.add_widget(self.title_lbl)
        header.add_widget(self.acc_lbl)
        self.layout.add_widget(header)

        # thin neon line
        line = Widget(size_hint_y=None, height=dp(2))
        with line.canvas:
            Color(*ACCENT)
            self._hline = Rectangle(pos=line.pos, size=(Window.width, dp(2)))
        line.bind(pos=lambda *a: setattr(self._hline, "pos", line.pos),
                  size=lambda *a: setattr(self._hline, "size", (line.width, dp(2))))
        self.layout.add_widget(line)

        self.scroll = ScrollView(do_scroll_x=False)
        self.content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=[0, dp(6)])
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.layout.add_widget(self.scroll)
        self.add_widget(self.layout)

    def on_pre_enter(self, *a):
        self._refresh_acc_label()

    def _refresh_acc_label(self):
        aid = get_current()
        if aid and _tg and aid in _tg.accounts:
            acc = _tg.accounts[aid]
            self.acc_lbl.text = f"#{aid} {acc.name[:10]}"
        else:
            self.acc_lbl.text = "no session"

    def go_back(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "menu"

    def add_neon(self, text, cb, color=ACCENT):
        btn = NeonButton(text=text, color=color)
        btn.bind(on_press=cb)
        self.content.add_widget(btn)
        return btn

    def add_section(self, text):
        self.content.add_widget(SectionLabel(text=text))

    def add_label(self, text, color=MUTED, size=sp(13)):
        lbl = Label(text=text, color=color, font_size=size, size_hint_y=None, height=dp(26),
                    halign="left", valign="middle")
        lbl.bind(size=lambda *a: setattr(lbl, "text_size", (lbl.width, None)))
        self.content.add_widget(lbl)
        return lbl

    def add_input(self, hint, password=False):
        inp = TextInput(hint_text=hint, multiline=False, password=password,
                        size_hint_y=None, height=dp(46), font_size=sp(14),
                        background_color=INPUT_BG, foreground_color=TEXT,
                        cursor_color=ACCENT, hint_text_color=MUTED,
                        padding=[dp(12), dp(12)])
        self.content.add_widget(inp)
        return inp

    def add_spacer(self, h=10):
        self.content.add_widget(Widget(size_hint_y=None, height=dp(h)))

    def popup(self, title, msg, size=(0.9, 0.5)):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        lbl = Label(text=str(msg), color=TEXT, text_size=(Window.width - dp(80), None),
                    valign="top", halign="left", size_hint_y=0.85)
        lbl.bind(size=lambda *a: setattr(lbl, "text_size", (lbl.width, None)))
        box.add_widget(lbl)
        close = NeonButton(text="CLOSE", color=ACCENT)
        box.add_widget(close)
        p = Popup(title=title, title_color=ACCENT, title_size=sp(16),
                  content=box, size_hint=size,
                  background="", separator_color=ACCENT,
                  background_color=CARD)
        close.bind(on_press=p.dismiss)
        p.open()
        return p

    def prompt_multi(self, title, fields, on_submit, size=(0.92, 0.78)):
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        inputs = {}
        inner = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        inner.bind(minimum_height=inner.setter("height"))
        for f in fields:
            key, hint = f[0], f[1]
            password = f[2] if len(f) > 2 else False
            inner.add_widget(Label(text=hint, color=MUTED, size_hint_y=None, height=dp(20),
                                   font_size=sp(12), halign="left"))
            inp = TextInput(hint_text=hint, multiline=False, password=password,
                            size_hint_y=None, height=dp(42), font_size=sp(13),
                            background_color=INPUT_BG, foreground_color=TEXT,
                            cursor_color=ACCENT, hint_text_color=MUTED,
                            padding=[dp(10), dp(10)])
            inner.add_widget(inp)
            inputs[key] = inp
        sc = ScrollView(size_hint_y=0.82)
        sc.add_widget(inner)
        box.add_widget(sc)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        ok = NeonButton(text="EXECUTE", color=SUCCESS)
        cancel = NeonButton(text="CANCEL", color=DANGER)
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        popup = Popup(title=title, title_color=ACCENT, content=box, size_hint=size,
                      background="", separator_color=ACCENT, background_color=CARD)

        def do_ok(*a):
            popup.dismiss()
            on_submit({k: v.text for k, v in inputs.items()})
        ok.bind(on_press=do_ok)
        cancel.bind(on_press=popup.dismiss)
        popup.open()
        return popup

    def pick_account(self, on_chosen, title="SELECT SESSION"):
        if not _tg or not _tg.clients:
            self.popup("Error", "No live sessions")
            return
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        for aid, acc in _tg.accounts.items():
            if aid not in _tg.clients:
                continue
            mark = "◆" if aid == get_current() else "◇"
            btn = NeonButton(text=f"{mark}  #{aid}  {acc.name}  [{acc.type}]",
                             color=ACCENT if aid == get_current() else ACCENT2)
            def make(a=aid):
                def cb(*x):
                    popup.dismiss()
                    set_current(a)
                    self._refresh_acc_label()
                    on_chosen(a)
                return cb
            btn.bind(on_press=make())
            box.add_widget(btn)
        sc = ScrollView()
        sc.add_widget(box)
        popup = Popup(title=title, title_color=ACCENT, content=sc, size_hint=(0.92, 0.65),
                      background="", separator_color=ACCENT, background_color=CARD)
        popup.open()

    def require_account(self, on_ready):
        if not _tg or not _tg.clients:
            self.popup("Sign in required", "Login first, then open Settings.")
            return
        if len(_tg.clients) == 1:
            aid = list(_tg.clients.keys())[0]
            set_current(aid)
            self._refresh_acc_label()
            on_ready(aid)
        else:
            self.pick_account(on_ready)


# ── Login ───────────────────────────────────────────────────
class LoginScreen(BaseScreen):
    title = "Nytron"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_label("Your phone number", color=TEXT, size=sp(20))
        self.add_label("Country code + number (Telegram style)", color=MUTED, size=sp(12))
        self.add_spacer(8)

        self.add_section("PHONE LOGIN")
        self.phone_name = self.add_input("Account label (optional)")
        # country row
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.cc_btn = NeonButton(text="+91 India", color=ACCENT2)
        self.cc_btn.size_hint_x = 0.42
        self.cc_btn.bind(on_press=self.pick_country)
        self._cc = "+91"
        self.phone_num = TextInput(hint_text="Phone number", multiline=False,
                                   size_hint_y=None, height=dp(46), font_size=sp(15),
                                   background_color=INPUT_BG, foreground_color=TEXT,
                                   cursor_color=ACCENT, hint_text_color=MUTED,
                                   padding=[dp(12), dp(12)], input_filter="int")
        row.add_widget(self.cc_btn)
        row.add_widget(self.phone_num)
        self.content.add_widget(row)
        self.add_neon("Next", self.login_phone_start, SUCCESS)

        self.add_spacer(10)
        self.add_section("Other sign-in options")
        self.add_neon("Log in by QR code", self.login_qr_start, ACCENT)
        self.qr_name = self.add_input("QR account label")
        self.add_neon("Bot token", self._show_bot, ACCENT2)
        self.add_neon("Session string", self._show_sess, MUTED)

        self.add_spacer(8)
        self.add_neon("Skip", self.go_menu, MUTED)
        self.status = self.add_label("", color=WARN)
        self.bot_name = self.bot_token = self.sess_name = self.sess_str = None

    def pick_country(self, *a):
        box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        for name, code in COUNTRY_CODES:
            b = NeonButton(text=f"{code}  {name}", color=ACCENT)
            def make(n=name, c=code):
                def cb(*x):
                    self._cc = c
                    self.cc_btn.text = f"{c} {n}"
                    popup.dismiss()
                return cb
            b.bind(on_press=make())
            box.add_widget(b)
        sc = ScrollView()
        sc.add_widget(box)
        popup = Popup(title="Country", title_color=ACCENT, content=sc,
                      size_hint=(0.92, 0.75), background="", separator_color=ACCENT,
                      background_color=CARD)
        popup.open()

    def _show_bot(self, *a):
        def submit(v):
            self.bot_name = type("X", (), {"text": v.get("name") or "bot"})()
            self.bot_token = type("X", (), {"text": v.get("token") or ""})()
            self.login_bot()
        self.prompt_multi("Bot login", [("name", "label"), ("token", "bot token", True)], submit)

    def _show_sess(self, *a):
        def submit(v):
            self.sess_name = type("X", (), {"text": v.get("name") or "imported"})()
            self.sess_str = type("X", (), {"text": v.get("sess") or ""})()
            self.import_session()
        self.prompt_multi("Session", [("name", "label"), ("sess", "session string", True)], submit)

    def set_status(self, txt, color=WARN):
        Clock.schedule_once(lambda dt: setattr(self.status, "text", txt), 0)
        Clock.schedule_once(lambda dt: setattr(self.status, "color", color), 0)

    def login_bot(self, *a):
        if not HAS_CORE:
            self.popup("Core Error", CORE_ERROR)
            return
        name = self.bot_name.text.strip() or "bot"
        token = self.bot_token.text.strip()
        if not token:
            self.popup("Error", "Token required")
            return
        self.set_status("authenticating...")
        def _w():
            try:
                acc = run_async_wait(_tg.login_bot(name, token))
                if isinstance(acc, Exception):
                    self.set_status(f"✗ {acc}", DANGER)
                else:
                    set_current(acc.id)
                    self.set_status(f"✓ {acc.name}", SUCCESS)
                    Clock.schedule_once(lambda dt: self.go_menu(), 0.8)
            except Exception as e:
                self.set_status(f"✗ {e}", DANGER)
        threading.Thread(target=_w, daemon=True).start()

    def login_phone_start(self, *a):
        if not HAS_CORE:
            self.popup("Core Error", CORE_ERROR)
            return
        name = (self.phone_name.text.strip() if self.phone_name else "") or "user"
        raw = self.phone_num.text.strip() if self.phone_num else ""
        if not raw:
            self.popup("Error", "Phone required")
            return
        cc = getattr(self, "_cc", "+91")
        phone = raw if raw.startswith("+") else (cc + raw.lstrip("0"))
        self.set_status("sending otp...")
        def _w():
            try:
                sd = run_async_wait(_tg.login_phone_start(name, phone))
                if isinstance(sd, Exception):
                    self.set_status(f"✗ {sd}", DANGER)
                    return
                self.set_status("otp sent", SUCCESS)
                Clock.schedule_once(lambda dt: self._otp_popup(sd), 0)
            except Exception as e:
                self.set_status(f"✗ {e}", DANGER)
        threading.Thread(target=_w, daemon=True).start()

    def _otp_popup(self, session_data):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        otp = TextInput(hint_text="OTP code", multiline=False, size_hint_y=None, height=dp(48),
                        font_size=sp(18), background_color=INPUT_BG, foreground_color=TEXT,
                        cursor_color=ACCENT, padding=[dp(12), dp(12)])
        box.add_widget(otp)
        btn = NeonButton(text="VERIFY", color=SUCCESS)
        box.add_widget(btn)
        popup = Popup(title="OTP", title_color=ACCENT, content=box, size_hint=(0.9, 0.35),
                      auto_dismiss=False, background="", separator_color=ACCENT, background_color=CARD)
        def do(*a):
            code = otp.text.strip()
            if not code:
                return
            popup.dismiss()
            self.set_status("verifying...")
            def _w():
                try:
                    acc = run_async_wait(_tg.login_phone_complete(session_data, code))
                    if isinstance(acc, Exception):
                        if "2FA_REQUIRED" in str(acc):
                            self.set_status("2FA required", WARN)
                            Clock.schedule_once(lambda dt: self._2fa_popup(session_data, code), 0)
                        else:
                            self.set_status(f"✗ {acc}", DANGER)
                    else:
                        set_current(acc.id)
                        self.set_status(f"✓ {acc.name}", SUCCESS)
                        Clock.schedule_once(lambda dt: self.go_menu(), 0.8)
                except Exception as e:
                    self.set_status(f"✗ {e}", DANGER)
            threading.Thread(target=_w, daemon=True).start()
        btn.bind(on_press=do)
        popup.open()

    def _2fa_popup(self, session_data, otp):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        pw = TextInput(hint_text="2FA password", multiline=False, password=True,
                       size_hint_y=None, height=dp(48), background_color=INPUT_BG,
                       foreground_color=TEXT, cursor_color=ACCENT, padding=[dp(12), dp(12)])
        box.add_widget(pw)
        btn = NeonButton(text="VERIFY 2FA", color=SUCCESS)
        box.add_widget(btn)
        popup = Popup(title="2FA", title_color=ACCENT, content=box, size_hint=(0.9, 0.35),
                      auto_dismiss=False, background="", separator_color=ACCENT, background_color=CARD)
        def do(*a):
            if not pw.text:
                return
            popup.dismiss()
            self.set_status("2FA check...")
            def _w():
                try:
                    acc = run_async_wait(_tg.login_phone_complete(session_data, otp, password=pw.text))
                    if isinstance(acc, Exception):
                        self.set_status(f"✗ {acc}", DANGER)
                    else:
                        set_current(acc.id)
                        self.set_status(f"✓ {acc.name}", SUCCESS)
                        Clock.schedule_once(lambda dt: self.go_menu(), 0.8)
                except Exception as e:
                    self.set_status(f"✗ {e}", DANGER)
            threading.Thread(target=_w, daemon=True).start()
        btn.bind(on_press=do)
        popup.open()

    def login_qr_start(self, *a):
        if not HAS_CORE:
            self.popup("Core Error", CORE_ERROR)
            return
        name = ((self.qr_name.text.strip() if self.qr_name else "") or "qr_user")
        self.set_status("generating qr...")
        def _w():
            try:
                sd = run_async_wait(_tg.login_qr_start(name))
                if isinstance(sd, Exception):
                    self.set_status(f"✗ {sd}", DANGER)
                    return
                self.set_status("scan in telegram", SUCCESS)
                Clock.schedule_once(lambda dt: self._qr_popup(sd), 0)
            except Exception as e:
                self.set_status(f"✗ {e}", DANGER)
        threading.Thread(target=_w, daemon=True).start()

    def _qr_popup(self, session_data):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        url = session_data.get("url", "")
        box.add_widget(Label(text=f"Open in Telegram:\n\n{url}\n\nThen press Complete",
                             color=TEXT, text_size=(Window.width - dp(70), None),
                             halign="left", size_hint_y=0.7))
        btn = NeonButton(text="COMPLETE QR LOGIN", color=SUCCESS)
        box.add_widget(btn)
        popup = Popup(title="QR GATE", title_color=ACCENT, content=box, size_hint=(0.92, 0.55),
                      auto_dismiss=False, background="", separator_color=ACCENT, background_color=CARD)
        def do(*a):
            popup.dismiss()
            self.set_status("finishing...")
            def _w():
                try:
                    acc = run_async_wait(_tg.login_qr_complete(session_data))
                    if isinstance(acc, Exception):
                        self.set_status(f"✗ {acc}", DANGER)
                    else:
                        set_current(acc.id)
                        self.set_status(f"✓ {acc.name}", SUCCESS)
                        Clock.schedule_once(lambda dt: self.go_menu(), 0.8)
                except Exception as e:
                    self.set_status(f"✗ {e}", DANGER)
            threading.Thread(target=_w, daemon=True).start()
        btn.bind(on_press=do)
        popup.open()

    def import_session(self, *a):
        if not HAS_CORE:
            self.popup("Core Error", CORE_ERROR)
            return
        name = self.sess_name.text.strip() or "imported"
        sess = self.sess_str.text.strip()
        if not sess:
            self.popup("Error", "Session required")
            return
        self.set_status("importing...")
        def _w():
            try:
                acc = run_async_wait(_tg.login_session(name, sess))
                if isinstance(acc, Exception):
                    self.set_status(f"✗ {acc}", DANGER)
                else:
                    set_current(acc.id)
                    self.set_status(f"✓ {acc.name}", SUCCESS)
                    Clock.schedule_once(lambda dt: self.go_menu(), 0.8)
            except Exception as e:
                self.set_status(f"✗ {e}", DANGER)
        threading.Thread(target=_w, daemon=True).start()

    def go_menu(self, *a):
        def _w():
            try:
                run_async_wait(_tg.start_all(), timeout=120)
            except Exception:
                pass
        threading.Thread(target=_w, daemon=True).start()
        self.manager.transition = FadeTransition(duration=0.25)
        self.manager.current = "menu"


# ── Menu ────────────────────────────────────────────────────
class MenuScreen(BaseScreen):
    title = "Nytron"

    def on_enter(self):
        self.content.clear_widgets()
        cur = get_current()
        if cur:
            self.add_label(f"Signed in · {cur}", color=TEXT, size=sp(14))
            self.add_label("All tools are in Settings", color=MUTED, size=sp(12))
        else:
            self.add_label("Not signed in", color=MUTED, size=sp(14))
            self.add_neon("Sign in", lambda *a: self.goto("login"), ACCENT)
        self.add_spacer(8)

        self.add_section("MAIN")
        self.add_neon("Settings", lambda *a: self.goto("settings"), ACCENT)
        self.add_neon("Accounts", lambda *a: self.goto("accounts"), ACCENT2)
        self.add_spacer(6)

        self.add_section("QUICK")
        for label, screen in [
            ("Chats tools", "messages"),
            ("Groups", "groups"),
            ("Contacts", "users"),
            ("Privacy", "privacy"),
            ("Tools", "protools"),
            ("Search", "search"),
            ("Dialogs", "dialogs"),
            ("Stories", "stories"),
            ("Vault", "vault"),
            ("Media", "media"),
            ("More", "extras"),
        ]:
            self.add_neon(label, lambda *a, s=screen: self.goto(s), ACCENT)
        self.add_spacer(8)
        self.add_neon("Sign out screen", lambda *a: self.goto("login"), MUTED)


class AccountsScreen(BaseScreen):
    title = "SESSIONS"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("LIST SESSIONS", self.list_acc, ACCENT)
        self.add_neon("SWITCH ACTIVE", self.switch_acc, ACCENT2)
        self.add_neon("EXPORT SESSION", self.exp_sess, WARN)
        self.add_neon("ACTIVE DEVICES", self.active_sess, ACCENT)
        self.add_neon("KILL OTHER DEVICES", self.kill_sess, DANGER)
        self.add_neon("HEALTH CHECK", self.health, SUCCESS)
        self.add_neon("STATS", self.stats, MUTED)
        self.add_neon("EMERGENCY LOGOUT ALL", self.emergency, DANGER)

    def switch_acc(self, *a):
        self.pick_account(lambda aid: self.popup("Locked", f"#{aid}"))

    def list_acc(self, *a):
        if not _tg or not _tg.accounts:
            self.popup("Empty", "No sessions")
            return
        txt = ""
        for aid, acc in _tg.accounts.items():
            live = "●" if aid in _tg.clients else "○"
            cur = " ◆" if aid == get_current() else ""
            txt += f"{live} #{aid} {acc.name} ({acc.type}){cur}\n"
        self.popup("SESSIONS", txt)

    def exp_sess(self, *a):
        def go(aid):
            s = run_async_wait(_tg.export_session(aid))
            self.popup("Session string", str(s), size=(0.92, 0.6))
        self.require_account(go)

    def active_sess(self, *a):
        def go(aid):
            sessions = run_async_wait(_tg.get_sessions(aid))
            if isinstance(sessions, Exception):
                self.popup("Error", str(sessions))
                return
            txt = ""
            for s in sessions:
                cur = "✓ " if s.get("current") else "  "
                txt += f"{cur}{s.get('device')} | {s.get('country')}\n  {s.get('ip')}\n\n"
            self.popup("DEVICES", txt or "none", size=(0.92, 0.7))
        self.require_account(go)

    def kill_sess(self, *a):
        def go(aid):
            n = run_async_wait(_tg.kill_sessions(aid))
            self.popup("Done", f"Killed {n} devices")
        self.require_account(go)

    def health(self, *a):
        def go(aid):
            h = run_async_wait(_tg.account_health_check(aid))
            self.popup("HEALTH", "\n".join(f"{k}: {v}" for k, v in h.items()))
        self.require_account(go)

    def stats(self, *a):
        def go(aid):
            h = run_async_wait(_tg.account_stats(aid))
            self.popup("STATS", "\n".join(f"{k}: {v}" for k, v in h.items()))
        self.require_account(go)

    def emergency(self, *a):
        def go(aid):
            n = run_async_wait(_tg.emergency_logout_all(aid))
            self.popup("LOGOUT", f"Terminated {n} sessions")
        self.require_account(go)


# ── Messages ────────────────────────────────────────────────
class MessagesScreen(BaseScreen):
    title = "SIGNAL"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_section("▸ CORE")
        self.add_neon("SEND", self.send_msg, ACCENT)
        self.add_neon("BROADCAST", self.broadcast, WARN)
        self.add_neon("CLONE CHAT", self.clone, ACCENT2)
        self.add_neon("NON-FORWARDABLE", self.non_fwd, DANGER)
        self.add_section("▸ MASS")
        self.add_neon("MESSAGE BOMB", self.bomb, DANGER)
        self.add_neon("BULK DELETE MINE", self.bulk_del, DANGER)
        self.add_neon("AUTO-REACT", self.auto_react, SUCCESS)
        self.add_neon("REACTION BOMB", self.react_bomb, WARN)
        self.add_section("▸ CONTROL")
        self.add_neon("EDIT", self.edit_msg, ACCENT)
        self.add_neon("PIN", self.pin_msg, ACCENT2)
        self.add_neon("SCHEDULE", self.schedule_msg, MUTED)
        self.add_neon("AUTO-FORWARD RULE", self.auto_fwd, SUCCESS)
        self.add_neon("MASS UNREAD", self.mass_unread, WARN)

    def send_msg(self, *a):
        def after(aid):
            def submit(v):
                try:
                    cid = int(v["chat"]) if v["chat"].lstrip("-").isdigit() else v["chat"]
                    run_async_wait(_tg.clients[aid].send_message(cid, v["text"]))
                    self.popup("Sent", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("SEND", [("chat", "chat id / @user"), ("text", "text")], submit)
        self.require_account(after)

    def broadcast(self, *a):
        def after(aid):
            def submit(v):
                try:
                    ids = [int(x.strip()) for x in v["ids"].split(",") if x.strip()]
                    n = run_async_wait(_tg.broadcast(aid, ids, v["text"]), timeout=180)
                    self.popup("Broadcast", f"{n}/{len(ids)}")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("BROADCAST", [("ids", "ids comma"), ("text", "text")], submit)
        self.require_account(after)

    def clone(self, *a):
        def after(aid):
            def submit(v):
                try:
                    n = run_async_wait(_tg.clone_chat_messages(
                        aid, int(v["src"]), int(v["dst"]), limit=int(v.get("lim") or 100)), timeout=300)
                    self.popup("Clone", f"{n} msgs")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("CLONE", [("src", "source"), ("dst", "dest"), ("lim", "limit 100")], submit)
        self.require_account(after)

    def non_fwd(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.forward_non_forwardable(
                        aid, int(v["src"]), int(v["dst"]), limit=int(v.get("lim") or 50)), timeout=600)
                    self.popup("NFWD", f"ok {r['forwarded']}  err {r['errors']}")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("NON-FWD", [("src", "source"), ("dst", "dest"), ("lim", "50")], submit)
        self.require_account(after)

    def bomb(self, *a):
        def after(aid):
            def submit(v):
                try:
                    n = int(v.get("n") or 10)
                    r = run_async_wait(_tg.message_bomb(aid, int(v["chat"]), v["text"], count=n), timeout=300)
                    self.popup("Bomb", f"{r}/{n}")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("BOMB", [("chat", "chat"), ("text", "text"), ("n", "count 10")], submit)
        self.require_account(after)

    def bulk_del(self, *a):
        def after(aid):
            def submit(v):
                try:
                    n = run_async_wait(_tg.bulk_delete_my_messages(aid, int(v["chat"])), timeout=600)
                    self.popup("Deleted", str(n))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("BULK DEL", [("chat", "chat id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def auto_react(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.auto_react(aid, int(v["chat"]), v.get("emoji") or "❤️"))
                    self.popup("Armed", "auto-react live")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("AUTO-REACT", [("chat", "chat"), ("emoji", "❤️")], submit)
        self.require_account(after)

    def react_bomb(self, *a):
        def after(aid):
            def submit(v):
                try:
                    ids = [int(x.strip()) for x in v["mids"].split(",") if x.strip()]
                    n = run_async_wait(_tg.reaction_bomb(aid, int(v["chat"]), ids, v.get("emoji") or "🔥"))
                    self.popup("React Bomb", f"{n} reactions")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("REACT BOMB",
                              [("chat", "chat"), ("mids", "msg ids comma"), ("emoji", "🔥")], submit)
        self.require_account(after)

    def edit_msg(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.edit_message(aid, int(v["chat"]), int(v["mid"]), v["text"]))
                    self.popup("Edit", "OK" if r else "Fail")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("EDIT", [("chat", "chat"), ("mid", "msg id"), ("text", "new")], submit)
        self.require_account(after)

    def pin_msg(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.pin_message(aid, int(v["chat"]), int(v["mid"])))
                    self.popup("Pinned", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("PIN", [("chat", "chat"), ("mid", "msg id")], submit)
        self.require_account(after)

    def schedule_msg(self, *a):
        def after(aid):
            def submit(v):
                try:
                    secs = int(v.get("secs") or 60)
                    when = datetime.now() + timedelta(seconds=secs)
                    run_async_wait(_tg.send_scheduled(aid, int(v["chat"]), v["text"], when))
                    self.popup("Scheduled", f"+{secs}s")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("SCHEDULE", [("chat", "chat"), ("text", "text"), ("secs", "60")], submit)
        self.require_account(after)

    def auto_fwd(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.auto_forward_add(
                        aid, int(v["src"]), int(v["dst"]),
                        keywords=v.get("kw") or "",
                        strip_meta=v.get("strip", "").lower() in ("1", "true", "yes")))
                    self.popup("Rule", "added")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("AUTO-FWD",
                              [("src", "src"), ("dst", "dst"), ("kw", "keywords"), ("strip", "0/1")], submit)
        self.require_account(after)

    def mass_unread(self, *a):
        def go(aid):
            n = run_async_wait(_tg.mass_unread(aid))
            self.popup("Unread", f"{n} dialogs marked")
        self.require_account(go)


# ── Groups ──────────────────────────────────────────────────
class GroupsScreen(BaseScreen):
    title = "NODES"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("MASS JOIN", self.join, SUCCESS)
        self.add_neon("MASS LEAVE", self.leave, DANGER)
        self.add_neon("DUMP MEMBERS", self.dump, ACCENT)
        self.add_neon("CHAT INFO", self.info, MUTED)
        self.add_neon("BAN USER", self.ban, DANGER)
        self.add_neon("PROMOTE ADMIN", self.promote, WARN)
        self.add_neon("ANALYTICS", self.analytics, ACCENT2)
        self.add_neon("CREATE INVITE", self.invite, SUCCESS)
        self.add_neon("AUTO JOIN BY KEYWORD", self.auto_join, ACCENT)

    def join(self, *a):
        def after(aid):
            def submit(v):
                links = [l.strip() for l in v["links"].split("\n") if l.strip()]
                r = run_async_wait(_tg.mass_join(aid, links), timeout=600)
                self.popup("Join", "\n".join(f"{l[:35]}: {s}" for l, s in r), size=(0.92, 0.7))
            self.prompt_multi("MASS JOIN", [("links", "one link per line")], submit)
        self.require_account(after)

    def leave(self, *a):
        def after(aid):
            def submit(v):
                ids = [int(x.strip()) for x in v["ids"].split(",") if x.strip()]
                r = run_async_wait(_tg.mass_leave(aid, ids))
                self.popup("Leave", "\n".join(f"{c}: {s}" for c, s in r))
            self.prompt_multi("LEAVE", [("ids", "chat ids")], submit)
        self.require_account(after)

    def dump(self, *a):
        def after(aid):
            def submit(v):
                try:
                    m = run_async_wait(_tg.members_dump(aid, int(v["chat"])), timeout=600)
                    txt = f"Total {len(m)}\n\n"
                    for x in m[:35]:
                        txt += f"[{x['id']}] @{x.get('username') or '-'} {x['name']}\n"
                    self.popup("MEMBERS", txt, size=(0.92, 0.8))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("DUMP", [("chat", "chat id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def info(self, *a):
        def after(aid):
            def submit(v):
                try:
                    d = run_async_wait(_tg.get_chat_full_info(aid, int(v["chat"])))
                    self.popup("INFO", "\n".join(f"{k}: {v2}" for k, v2 in d.items()))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("INFO", [("chat", "chat id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def ban(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.ban_user(aid, int(v["chat"]), int(v["user"])))
                    self.popup("Banned", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("BAN", [("chat", "chat"), ("user", "user id")], submit)
        self.require_account(after)

    def promote(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.promote_admin(aid, int(v["chat"]), int(v["user"]), full_rights=True))
                    self.popup("Promoted", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("PROMOTE", [("chat", "chat"), ("user", "user id")], submit)
        self.require_account(after)

    def analytics(self, *a):
        def after(aid):
            def submit(v):
                try:
                    d = run_async_wait(_tg.chat_analytics(aid, int(v["chat"]),
                                                          msg_limit=int(v.get("lim") or 500)), timeout=180)
                    txt = (f"Total: {d['total_messages']}\nMedia: {d['media_messages']}\n"
                           f"Text: {d['text_messages']}\nSenders: {d['unique_senders']}\n"
                           f"Peak hour: {d['peak_hour']}:00")
                    self.popup("ANALYTICS", txt)
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("ANALYTICS", [("chat", "chat"), ("lim", "500")], submit)
        self.require_account(after)

    def invite(self, *a):
        def after(aid):
            def submit(v):
                try:
                    link = run_async_wait(_tg.get_invite_link(
                        aid, int(v["chat"]),
                        expire_hours=int(v.get("exp") or 0),
                        usage_limit=int(v.get("use") or 0)))
                    self.popup("INVITE", link)
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("INVITE", [("chat", "chat"), ("exp", "hours 0"), ("use", "limit 0")], submit)
        self.require_account(after)

    def auto_join(self, *a):
        def after(aid):
            def submit(v):
                try:
                    n = run_async_wait(_tg.auto_join_by_keyword(aid, v["kw"], limit=int(v.get("lim") or 8)))
                    self.popup("Joined", f"{n} channels")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("AUTO-JOIN", [("kw", "keyword"), ("lim", "8")], submit)
        self.require_account(after)


# ── Users ───────────────────────────────────────────────────
class UserToolsScreen(BaseScreen):
    title = "PROBES"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("DEEP USER INFO", self.info, ACCENT)
        self.add_neon("PHONE LOOKUP", self.phone, SUCCESS)
        self.add_neon("ONLINE STATUS", self.online, ACCENT2)
        self.add_neon("BLOCK", self.block, DANGER)
        self.add_neon("UNBLOCK", self.unblock, SUCCESS)
        self.add_neon("BLOCKED LIST", self.blocked, MUTED)
        self.add_neon("USERNAME CHECK", self.user_check, WARN)
        self.add_neon("COMMON CHATS", self.common, ACCENT)

    def info(self, *a):
        def after(aid):
            def submit(v):
                try:
                    uid = v["uid"].strip()
                    uid = uid if uid.startswith("@") else int(uid)
                    d = run_async_wait(_tg.user_deep_info(aid, uid))
                    self.popup("USER", "\n".join(f"{k}: {v2}" for k, v2 in d.items()), size=(0.92, 0.75))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("USER", [("uid", "id / @user")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def phone(self, *a):
        def after(aid):
            def submit(v):
                phones = [p.strip() for p in v["phones"].split(",") if p.strip()]
                try:
                    r = run_async_wait(_tg.phone_to_user(aid, phones), timeout=120)
                    txt = "\n".join(f"{x['phone']} → {x['id']} @{x.get('username') or '-'}" for x in r)
                    self.popup("LOOKUP", txt or "none")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("PHONE", [("phones", "comma phones")], submit)
        self.require_account(after)

    def online(self, *a):
        def after(aid):
            def submit(v):
                try:
                    s = run_async_wait(_tg.get_online_status(aid, int(v["uid"])))
                    self.popup("STATUS", f"Online: {s['online']}\nLast: {s['last_seen']}")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("ONLINE", [("uid", "user id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def block(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.block_user(aid, int(v["uid"])))
                    self.popup("Blocked", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("BLOCK", [("uid", "user id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def unblock(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.unblock_user(aid, int(v["uid"])))
                    self.popup("Unblocked", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("UNBLOCK", [("uid", "user id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def blocked(self, *a):
        def after(aid):
            try:
                lst = run_async_wait(_tg.get_blocked_list(aid))
                txt = "\n".join(f"[{u['id']}] @{u.get('username') or '-'} {u['name']}" for u in lst)
                self.popup("BLOCKED", txt or "none")
            except Exception as e:
                self.popup("Error", str(e))
        self.require_account(after)

    def user_check(self, *a):
        def after(aid):
            def submit(v):
                try:
                    free = run_async_wait(_tg.check_username(aid, v["u"]))
                    self.popup("USERNAME", "AVAILABLE" if free else "TAKEN")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("CHECK", [("u", "username without @")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def common(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.get_common_chats(aid, int(v["uid"])))
                    txt = "\n".join(f"[{c['id']}] {c.get('title')}" for c in r)
                    self.popup("COMMON", txt or "none")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("COMMON", [("uid", "user id")], submit, size=(0.9, 0.4))
        self.require_account(after)


# ── Privacy ─────────────────────────────────────────────────
class PrivacyScreen(BaseScreen):
    title = "SHIELD"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("GHOST ON", self.ghost_on, ACCENT2)
        self.add_neon("GHOST OFF", self.ghost_off, MUTED)
        self.add_neon("PRIVACY → EVERYBODY", self.priv_all, SUCCESS)
        self.add_neon("PRIVACY → CONTACTS", self.priv_cont, WARN)
        self.add_neon("PRIVACY → NOBODY", self.priv_none, DANGER)
        self.add_neon("ANTI-RECALL ON", self.anti_recall, ACCENT)
        self.add_neon("STREAMER MODE", self.streamer, ACCENT2)
        self.add_neon("UPDATE PROFILE", self.upd_profile, ACCENT)

    def ghost_on(self, *a):
        def go(aid):
            run_async_wait(_tg.ghost_mode(aid, True))
            self.popup("Ghost", "ON")
        self.require_account(go)

    def ghost_off(self, *a):
        def go(aid):
            run_async_wait(_tg.ghost_mode(aid, False))
            self.popup("Ghost", "OFF")
        self.require_account(go)

    def priv_all(self, *a):
        def go(aid):
            run_async_wait(_tg.set_privacy_all(aid, "everybody"))
            self.popup("Privacy", "everybody")
        self.require_account(go)

    def priv_cont(self, *a):
        def go(aid):
            run_async_wait(_tg.set_privacy_all(aid, "contacts"))
            self.popup("Privacy", "contacts")
        self.require_account(go)

    def priv_none(self, *a):
        def go(aid):
            run_async_wait(_tg.set_privacy_all(aid, "nobody"))
            self.popup("Privacy", "nobody")
        self.require_account(go)

    def anti_recall(self, *a):
        def go(aid):
            run_async_wait(_tg.anti_recall_enable(aid))
            self.popup("Anti-recall", "ARMED")
        self.require_account(go)

    def streamer(self, *a):
        def go(aid):
            run_async_wait(_tg.streamer_mode(aid, True))
            self.popup("Streamer", "ON")
        self.require_account(go)

    def upd_profile(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.update_profile(
                        aid, first=v.get("first") or None, last=v.get("last") or None,
                        bio=v.get("bio") or None, username=v.get("username") or None))
                    self.popup("Profile", "updated")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("PROFILE",
                              [("first", "first"), ("last", "last"), ("bio", "bio"), ("username", "user")], submit)
        self.require_account(after)


# ── Pro+ ────────────────────────────────────────────────
class ProScreen(BaseScreen):
    title = "PRO TOOLS"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("HISTORY SEARCH", self.history, ACCENT)
        self.add_neon("TRANSLATOR", self.trans, SUCCESS)
        self.add_neon("LOCAL PREMIUM ON", self.prem_on, WARN)
        self.add_neon("LOCAL PREMIUM OFF", self.prem_off, MUTED)
        self.add_neon("ADD FILTER", self.filt, ACCENT2)
        self.add_neon("RECALL HISTORY", self.recall, DANGER)
        self.add_neon("EMOJI STATUS", self.emoji_status, ACCENT)
        self.add_neon("MESSAGE SHOT", self.shot, WARN)

    def history(self, *a):
        def after(aid):
            def submit(v):
                r = run_async_wait(_tg.message_history_search(aid, v["q"]))
                txt = "\n".join(f"[{x['chat_id']}] {(x['text'] or '')[:55]}" for x in r[:25])
                self.popup(f"HITS {len(r)}", txt or "none", size=(0.92, 0.75))
            self.prompt_multi("SEARCH", [("q", "query")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def trans(self, *a):
        def after(aid):
            def submit(v):
                try:
                    t = run_async_wait(_tg.translator(aid, int(v["chat"]), int(v["mid"]), v.get("lang") or "en"))
                    self.popup("TRANSLATE", t or "fail")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("TRANSLATE", [("chat", "chat"), ("mid", "msg"), ("lang", "en")], submit)
        self.require_account(after)

    def prem_on(self, *a):
        def go(aid):
            run_async_wait(_tg.local_premium_enable(aid, True))
            self.popup("Premium", "ON")
        self.require_account(go)

    def prem_off(self, *a):
        def go(aid):
            run_async_wait(_tg.local_premium_enable(aid, False))
            self.popup("Premium", "OFF")
        self.require_account(go)

    def filt(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.message_filter_add(aid, int(v["chat"]), v["kw"]))
                    self.popup("Filter", "added")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("FILTER", [("chat", "chat"), ("kw", "keyword")], submit)
        self.require_account(after)

    def recall(self, *a):
        def go(aid):
            r = run_async_wait(_tg.recall_history(aid))
            txt = "\n".join(
                f"[{x['chat_id']}] {x['id']} — {datetime.fromtimestamp(x['ts']).strftime('%m-%d %H:%M')}"
                for x in r[:25])
            self.popup(f"RECALL {len(r)}", txt or "none", size=(0.92, 0.75))
        self.require_account(go)

    def emoji_status(self, *a):
        def after(aid):
            def submit(v):
                run_async_wait(_tg.local_premium_emoji_status(aid, v["emoji"]))
                self.popup("Status", v["emoji"])
            self.prompt_multi("EMOJI", [("emoji", "emoji")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def shot(self, *a):
        def after(aid):
            def submit(v):
                try:
                    p = run_async_wait(_tg.message_shot(aid, int(v["chat"]), int(v["mid"])))
                    self.popup("SHOT", str(p))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("SHOT", [("chat", "chat"), ("mid", "msg id")], submit)
        self.require_account(after)


# ── Search ──────────────────────────────────────────────────
class SearchScreen(BaseScreen):
    title = "SEARCH"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("FTS SEARCH", self.fts, ACCENT)
        self.add_neon("DELETED MSGS", self.deleted, DANGER)
        self.add_neon("EDIT HISTORY", self.edits, WARN)

    def fts(self, *a):
        def after(aid):
            def submit(v):
                r = run_async_wait(_tg.search_messages(aid, v["q"]))
                txt = "\n".join(f"[{x['chat_id']}] {(x['text'] or '')[:55]}" for x in r[:25])
                self.popup(f"RESULTS {len(r)}", txt or "none", size=(0.92, 0.75))
            self.prompt_multi("FTS", [("q", "query")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def deleted(self, *a):
        def go(aid):
            r = _tg.get_deleted_msgs(aid)
            txt = "\n".join(
                f"[{x['chat_id']}] {x['id']} — {datetime.fromtimestamp(x['ts']).strftime('%m-%d %H:%M')}"
                for x in r[:30])
            self.popup(f"DELETED {len(r)}", txt or "none", size=(0.92, 0.75))
        self.require_account(go)

    def edits(self, *a):
        def go(aid):
            r = _tg.get_edit_history(aid)
            txt = "\n".join(f"[{x['chat_id']}] {x['msg_id']}: {(x['text'] or '')[:40]}" for x in r[:25])
            self.popup(f"EDITS {len(r)}", txt or "none", size=(0.92, 0.75))
        self.require_account(go)


# ── Dialogs ─────────────────────────────────────────────────
class DialogsScreen(BaseScreen):
    title = "CHANNELS"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("LIST DIALOGS", self.list_dlgs, ACCENT)

    def list_dlgs(self, *a):
        def go(aid):
            d = run_async_wait(_tg.get_dialogs(aid, limit=40))
            txt = "\n".join(f"[{x['id']}] {x['name']} ({x['unread']})" for x in d)
            self.popup("DIALOGS", txt or "none", size=(0.92, 0.8))
        self.require_account(go)


# ── Stories ─────────────────────────────────────────────────
class StoriesScreen(BaseScreen):
    title = "STORIES"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("DOWNLOAD STORIES", self.dl, ACCENT)
        self.add_neon("VIEW STEALTH", self.view, ACCENT2)

    def dl(self, *a):
        def after(aid):
            def submit(v):
                try:
                    p = run_async_wait(_tg.story_download(aid, int(v["uid"])), timeout=180)
                    self.popup("Downloaded", f"{len(p)} files")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("DOWNLOAD", [("uid", "user id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def view(self, *a):
        def after(aid):
            def submit(v):
                try:
                    n = run_async_wait(_tg.story_view_stealth(aid, int(v["uid"])))
                    self.popup("Viewed", f"{n} stories")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("STEALTH", [("uid", "user id")], submit, size=(0.9, 0.4))
        self.require_account(after)


# ── Vault ───────────────────────────────────────────────────
class VaultScreen(BaseScreen):
    title = "VAULT"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("UNLOCK", self.unlock, SUCCESS)
        self.add_neon("SAVE SECRET", self.save, ACCENT)
        self.add_neon("READ SECRET", self.read, WARN)

    def unlock(self, *a):
        if not _tg:
            return
        def submit(v):
            try:
                _tg.vault_open(v["pw"])
                self.popup("Vault", "unlocked")
            except Exception as e:
                self.popup("Error", str(e))
        self.prompt_multi("UNLOCK", [("pw", "password", True)], submit, size=(0.9, 0.4))

    def save(self, *a):
        if not _tg or not _tg.vault:
            self.popup("Error", "Unlock first")
            return
        def submit(v):
            _tg.vault_save(v["title"], v["data"])
            self.popup("Saved", "OK")
        self.prompt_multi("SAVE", [("title", "title"), ("data", "data")], submit)

    def read(self, *a):
        if not _tg or not _tg.vault:
            self.popup("Error", "Unlock first")
            return
        def submit(v):
            try:
                d = _tg.vault_read(v["title"])
                self.popup("SECRET", d)
            except Exception as e:
                self.popup("Error", str(e))
        self.prompt_multi("READ", [("title", "title")], submit, size=(0.9, 0.4))


# ── Media ───────────────────────────────────────────────────
class MediaScreen(BaseScreen):
    title = "MEDIA"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_neon("BULK DOWNLOAD", self.dl, ACCENT)
        self.add_neon("ACCOUNT STATS", self.stats, MUTED)

    def dl(self, *a):
        def after(aid):
            def submit(v):
                try:
                    p = run_async_wait(_tg.bulk_download_media(
                        aid, int(v["chat"]), limit=int(v.get("lim") or 100)), timeout=600)
                    self.popup("Downloaded", f"{len(p)} files")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("DOWNLOAD", [("chat", "chat"), ("lim", "100")], submit)
        self.require_account(after)

    def stats(self, *a):
        def go(aid):
            h = run_async_wait(_tg.account_stats(aid))
            self.popup("STATS", "\n".join(f"{k}: {v}" for k, v in h.items()))
        self.require_account(go)


# ── Settings ────────────────────────────────────────────────
class SettingsScreen(BaseScreen):
    title = "Settings"

    def on_enter(self):
        self.content.clear_widgets()
        cur = get_current()
        self.add_label(
            f"Account: {cur}" if cur else "No account — sign in first",
            color=TEXT if cur else MUTED, size=sp(13)
        )
        self.add_spacer(6)

        # ── Accounts (top section) ──
        self.add_section("ACCOUNTS")
        self.add_neon("Switch account", self.switch, ACCENT)
        self.add_neon("List sessions", self.list_all, MUTED)
        self.add_neon("Add account (login)", lambda *a: self.goto("login"), ACCENT2)

        # ── Privacy ──
        self.add_section("PRIVACY AND SECURITY")
        self.add_neon("Ghost mode (active account)", self.toggle_ghost, ACCENT)
        self.add_neon("Privacy presets", lambda *a: self.goto("privacy"), ACCENT)
        self.add_neon("Streamer mode / anti-recall", lambda *a: self.goto("privacy"), ACCENT2)

        # ── Feature master toggles ──
        self.add_section("FEATURE SWITCHES")
        for key, label in [
            ("anti_recall", "Save deleted messages"),
            ("ghost_default", "Ghost mode by default"),
            ("local_premium", "Local premium effects"),
            ("auto_react", "Auto-react"),
            ("streamer", "Streamer mode"),
            ("mass_tools", "Mass tools"),
            ("vault", "Encrypted vault"),
        ]:
            state = "On" if FEATURE_FLAGS.get(key) else "Off"
            self.add_neon(
                f"{label}  ·  {state}",
                lambda *a, k=key: self._toggle_flag(k),
                ACCENT2,
            )

        # ── All tools (hub) ──
        self.add_section("ALL TOOLS")
        tools = [
            ("Messages & send tools", "messages"),
            ("Groups & channels", "groups"),
            ("Contacts & users", "users"),
            ("Pro tools (history, filters…)", "protools"),
            ("Search", "search"),
            ("Dialogs", "dialogs"),
            ("Stories", "stories"),
            ("Vault", "vault"),
            ("Media download", "media"),
            ("More tools", "extras"),
        ]
        for label, screen in tools:
            self.add_neon(label, lambda *a, s=screen: self.goto(s), ACCENT)

        # ── Proxy / system ──
        self.add_section("CONNECTION")
        self.proxy_inp = self.add_input("socks5://user:pass@host:port")
        self.add_neon("Save proxy note", self.save_proxy, ACCENT)
        self.add_neon("Start scheduler", self.start_sched, MUTED)
        self.add_spacer(8)
        self.add_neon("Back to home", lambda *a: self.goto("menu"), MUTED)

    def _toggle_flag(self, key):
        FEATURE_FLAGS[key] = not FEATURE_FLAGS.get(key, False)
        self.popup("Feature", f"{key.replace('_', ' ')} → {'On' if FEATURE_FLAGS[key] else 'Off'}")
        self.on_enter()

    def switch(self, *a):
        def submit(v):
            name = v.get("name", "").strip()
            if name:
                ok = _tg.set_current(name)
                self.popup("Account", "switched" if ok else "not found")
                self.on_enter()
        self.prompt_multi("Switch account", [("name", "account name")], submit, size=(0.9, 0.4))

    def toggle_ghost(self, *a):
        def go(aid):
            def work():
                try:
                    r = run_async_wait(_tg.ghost_mode(aid, True))
                    self.popup("Ghost", str(r)[:200] if r is not None else "enabled")
                except Exception as e:
                    self.popup("Ghost", str(e)[:250])
            threading.Thread(target=work, daemon=True).start()
        self.require_account(go)

    def list_all(self, *a):
        if not _tg or not getattr(_tg, "clients", None):
            self.popup("Sessions", "none — sign in first")
            return
        lines = []
        for aid, client in _tg.clients.items():
            mark = "◆" if aid == get_current() else "◇"
            name = getattr(getattr(_tg, "accounts", {}).get(aid), "name", str(aid))
            lines.append(f"{mark} #{aid} {name}")
        self.popup("Sessions", "\n".join(lines) if lines else "none")

    def save_proxy(self, *a):
        val = (self.proxy_inp.text or "").strip()
        self.popup("Proxy", "saved (note)" if val else "empty")

    def start_sched(self, *a):
        def go(aid):
            def work():
                try:
                    _tg.start_scheduler(aid)
                    self.popup("Scheduler", "started")
                except Exception as e:
                    self.popup("Scheduler", str(e)[:250])
            threading.Thread(target=work, daemon=True).start()
        self.require_account(go)


class NytronApp(App):
    def build(self):
        global _tg
        if HAS_CORE:
            try:
                _tg = MyTG()
            except Exception as e:
                print(f"Core init failed: {e}")
                _tg = None
        else:
            _tg = None
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(MenuScreen(name="menu"))
        sm.current = "login"
        return sm


if __name__ == "__main__":
    NytronApp().run()


# ═══════════════════════════════════════════════════════════
# EXTRA FEATURES LAYER (appended)
# ═══════════════════════════════════════════════════════════

class ExtrasScreen(BaseScreen):
    title = "EXTRAS+"

    def on_enter(self):
        self.content.clear_widgets()
        self.add_section("▸ MESSAGE")
        self.add_neon("SILENT SEND", self.silent, ACCENT)
        self.add_neon("FAKE TYPING", self.typing, ACCENT2)
        self.add_neon("POLL CREATE", self.poll, WARN)
        self.add_neon("FLOOD PROTECT SEND", self.flood, SUCCESS)
        self.add_neon("HISTORY EXPORT JSON", self.hist_exp, MUTED)
        self.add_section("▸ DIALOG")
        self.add_neon("ARCHIVE CHAT", self.archive, ACCENT)
        self.add_neon("UNARCHIVE CHAT", self.unarchive, MUTED)
        self.add_neon("PIN DIALOG", self.pin_dlg, ACCENT2)
        self.add_neon("SAVE DRAFT", self.draft, WARN)
        self.add_neon("MARK READ", self.mark_read, SUCCESS)
        self.add_section("▸ CONTACTS")
        self.add_neon("EXPORT CONTACTS", self.exp_contacts, ACCENT)
        self.add_neon("WIPE ALL CONTACTS", self.wipe_contacts, DANGER)
        self.add_section("▸ GROUP ADV")
        self.add_neon("SLOW MODE", self.slow, WARN)
        self.add_neon("ADMIN LOG", self.admin_log, ACCENT2)
        self.add_neon("FILTERED MEMBERS", self.filt_mem, ACCENT)
        self.add_neon("DELETE HISTORY SILENT", self.del_hist, DANGER)
        self.add_section("▸ ACCOUNT")
        self.add_neon("2FA STATUS", self.twofa, WARN)
        self.add_neon("SET ACCOUNT TTL", self.ttl, DANGER)
        self.add_neon("CLEAR OLD PHOTOS", self.clear_photos, MUTED)
        self.add_neon("SCHEDULED CLEANUP", self.sched_clean, ACCENT)
        self.add_section("▸ OTHER")
        self.add_neon("STICKER SET INFO", self.sticker, ACCENT2)
        self.add_neon("REACTIONS LIST", self.react_list, SUCCESS)
        self.add_neon("AUTO-REPLY SETUP", self.auto_reply, WARN)
        self.add_neon("MASS STORY VIEW", self.mass_story, ACCENT)

    def silent(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.send_silent(aid, int(v["chat"]), v["text"],
                                                   schedule_secs=int(v.get("secs") or 0)))
                    self.popup("Silent", "sent")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("SILENT", [("chat", "chat"), ("text", "text"), ("secs", "0")], submit)
        self.require_account(after)

    def typing(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.set_typing(aid, int(v["chat"]), float(v.get("sec") or 5)))
                    self.popup("Typing", "done")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("TYPING", [("chat", "chat"), ("sec", "5")], submit, size=(0.9, 0.45))
        self.require_account(after)

    def poll(self, *a):
        def after(aid):
            def submit(v):
                try:
                    opts = [o.strip() for o in v["opts"].split(",") if o.strip()]
                    run_async_wait(_tg.poll_create(aid, int(v["chat"]), v["q"], opts))
                    self.popup("Poll", "created")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("POLL", [("chat", "chat"), ("q", "question"), ("opts", "opt1,opt2,opt3")], submit)
        self.require_account(after)

    def flood(self, *a):
        def after(aid):
            def submit(v):
                try:
                    texts = [t.strip() for t in v["texts"].split("\n") if t.strip()]
                    n = run_async_wait(_tg.flood_protect_send(aid, int(v["chat"]), texts,
                                                              delay=float(v.get("d") or 3)))
                    self.popup("Flood", f"sent {n}")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("FLOOD", [("chat", "chat"), ("texts", "one per line"), ("d", "3")], submit)
        self.require_account(after)

    def hist_exp(self, *a):
        def after(aid):
            def submit(v):
                try:
                    path, n = run_async_wait(_tg.history_export(aid, int(v["chat"]),
                                                                limit=int(v.get("lim") or 500)), timeout=300)
                    self.popup("Export", f"{n} msgs → {path}")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("EXPORT", [("chat", "chat"), ("lim", "500")], submit)
        self.require_account(after)

    def archive(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.archive_chat(aid, int(v["chat"])))
                    self.popup("Archived", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("ARCHIVE", [("chat", "chat id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def unarchive(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.unarchive_chat(aid, int(v["chat"])))
                    self.popup("Unarchived", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("UNARCHIVE", [("chat", "chat id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def pin_dlg(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.pin_chat(aid, int(v["chat"]), pin=True))
                    self.popup("Pinned", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("PIN DLG", [("chat", "chat id")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def draft(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.save_draft(aid, int(v["chat"]), v["text"]))
                    self.popup("Draft", "saved")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("DRAFT", [("chat", "chat"), ("text", "text")], submit)
        self.require_account(after)

    def mark_read(self, *a):
        def after(aid):
            def submit(v):
                try:
                    cid = int(v["chat"]) if v.get("chat") else None
                    run_async_wait(_tg.mark_read(aid, cid))
                    self.popup("Read", "OK")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("MARK READ", [("chat", "chat id (empty=all)")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def exp_contacts(self, *a):
        def go(aid):
            try:
                r = run_async_wait(_tg.export_contacts(aid))
                txt = "\n".join(f"{c.get('phone')} {c.get('first')} @{c.get('username') or '-'}" for c in r[:40])
                self.popup(f"CONTACTS {len(r)}", txt or "none", size=(0.92, 0.75))
            except Exception as e:
                self.popup("Error", str(e))
        self.require_account(go)

    def wipe_contacts(self, *a):
        def go(aid):
            try:
                run_async_wait(_tg.delete_all_contacts(aid))
                self.popup("Wiped", "all contacts deleted")
            except Exception as e:
                self.popup("Error", str(e))
        self.require_account(go)

    def slow(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.set_slow_mode(aid, int(v["chat"]), int(v.get("sec") or 0)))
                    self.popup("Slow", "set")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("SLOW", [("chat", "chat"), ("sec", "0=off")], submit, size=(0.9, 0.45))
        self.require_account(after)

    def admin_log(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.group_admin_log(aid, int(v["chat"]), limit=int(v.get("lim") or 50)))
                    txt = "\n".join(f"{x.get('date')} {x.get('action')} uid={x.get('user_id')}" for x in r[:30])
                    self.popup("ADMIN LOG", txt or "none", size=(0.92, 0.75))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("ADMIN LOG", [("chat", "chat"), ("lim", "50")], submit)
        self.require_account(after)

    def filt_mem(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.group_members_filtered(
                        aid, int(v["chat"]), filter_type=v.get("t") or "all",
                        limit=int(v.get("lim") or 100)))
                    txt = "\n".join(f"[{m['id']}] @{m.get('username') or '-'} {m['name']}" for m in r[:30])
                    self.popup(f"MEMBERS {len(r)}", txt or "none", size=(0.92, 0.75))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("FILTERED", [("chat", "chat"), ("t", "all/admins/banned/recent"), ("lim", "100")], submit)
        self.require_account(after)

    def del_hist(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.delete_history_silent(aid, int(v["chat"]),
                                                            revoke=v.get("rev", "1") in ("1", "true", "yes")))
                    self.popup("Deleted", "history wiped")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("DEL HIST", [("chat", "chat"), ("rev", "1")], submit, size=(0.9, 0.45))
        self.require_account(after)

    def twofa(self, *a):
        def go(aid):
            try:
                r = run_async_wait(_tg.check_2fa_enabled(aid))
                self.popup("2FA", "\n".join(f"{k}: {v}" for k, v in r.items()) or str(r))
            except Exception as e:
                self.popup("Error", str(e))
        self.require_account(go)

    def ttl(self, *a):
        def after(aid):
            def submit(v):
                try:
                    run_async_wait(_tg.set_account_ttl(aid, int(v.get("days") or 180)))
                    self.popup("TTL", "set")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("TTL", [("days", "180")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def clear_photos(self, *a):
        def go(aid):
            try:
                run_async_wait(_tg.clear_old_photos(aid))
                self.popup("Photos", "old cleared")
            except Exception as e:
                self.popup("Error", str(e))
        self.require_account(go)

    def sched_clean(self, *a):
        def go(aid):
            try:
                n = run_async_wait(_tg.scheduled_cleanup(aid))
                self.popup("Cleanup", f"removed {n}")
            except Exception as e:
                self.popup("Error", str(e))
        self.require_account(go)

    def sticker(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.sticker_set_info(aid, v["name"]))
                    self.popup("STICKER", str(r)[:500] if r else "none")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("STICKER", [("name", "short_name")], submit, size=(0.9, 0.4))
        self.require_account(after)

    def react_list(self, *a):
        def after(aid):
            def submit(v):
                try:
                    r = run_async_wait(_tg.message_reactions_list(aid, int(v["chat"]), int(v["mid"])))
                    txt = "\n".join(f"{x.get('user')} {x.get('reaction')}" for x in r[:30])
                    self.popup("REACTIONS", txt or "none")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("REACTS", [("chat", "chat"), ("mid", "msg id")], submit)
        self.require_account(after)

    def auto_reply(self, *a):
        def after(aid):
            def submit(v):
                try:
                    cid = int(v["chat"]) if v.get("chat") else None
                    run_async_wait(_tg.auto_reply_setup(aid, v["kw"], v["reply"], chat_id=cid))
                    self.popup("Auto-reply", "armed")
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("AUTO-REPLY",
                              [("kw", "keyword"), ("reply", "reply text"), ("chat", "chat (empty=all)")], submit)
        self.require_account(after)

    def mass_story(self, *a):
        def after(aid):
            def submit(v):
                try:
                    peers = [int(x.strip()) for x in v["uids"].split(",") if x.strip()]
                    r = run_async_wait(_tg.mass_story_view(aid, peers))
                    self.popup("Stories", str(r))
                except Exception as e:
                    self.popup("Error", str(e))
            self.prompt_multi("MASS STORY", [("uids", "user ids comma")], submit)
        self.require_account(after)


# register extras in map + menu
SCREEN_MAP["extras"] = ExtrasScreen

# patch MenuScreen to include EXTRAS button
_old_menu_enter = MenuScreen.on_enter
def _new_menu_enter(self):
    _old_menu_enter(self)
    self.add_neon("More tools", lambda *a: self.goto("extras"), WARN)
MenuScreen.on_enter = _new_menu_enter
