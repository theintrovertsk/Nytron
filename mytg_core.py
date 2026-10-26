# mytg_core.py — GUI-SAFE EDITION
# No input() calls — all login is callback-based
# Works in Kivy, terminal, and any GUI

import asyncio
import json
import sqlite3
import time
import random
import hashlib
import base64
import os
import re
import io
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field

from telethon import TelegramClient, events, functions, types, utils
from telethon.sessions import StringSession
from telethon.tl.functions.account import (
    UpdateStatusRequest, GetPasswordRequest, GetAuthorizationsRequest,
    ResetAuthorizationRequest, UpdateProfileRequest, SetPrivacyRequest,
    UpdateUsernameRequest, GetPrivacyRequest, DeleteAccountRequest,
    SetAccountTTLRequest, ChangePhoneRequest,
    SendChangePhoneCodeRequest, GetAccountTTLRequest,
    ReportPeerRequest
)
from telethon.tl.types import AccountDaysTTL
from telethon.tl.functions.messages import (
    SendReactionRequest, ImportChatInviteRequest, SetTypingRequest,
    ReadHistoryRequest, SaveDraftRequest, GetScheduledHistoryRequest,
    DeleteScheduledMessagesRequest, GetPollVotesRequest,
    SendVoteRequest, GetStickerSetRequest, GetAllStickersRequest,
    GetFavedStickersRequest, FaveSticker, UnpinAllMessagesRequest,
    UpdatePinnedMessageRequest, ForwardMessagesRequest,
    GetDialogFiltersRequest, UpdateDialogFiltersRequest,
    CreateChatRequest, SetChatAvailableReactionsRequest,
    GetMessageReactionsListRequest, TranslateTextRequest,
    GetEmojiKeywordsRequest, SearchGlobalRequest, GetOnlinesRequest
)
from telethon.tl.functions.channels import (
    JoinChannelRequest, LeaveChannelRequest, EditBannedRequest,
    GetFullChannelRequest, EditAdminRequest, GetParticipantsRequest,
    UpdateUsernameRequest as ChannelUpdateUsernameRequest,
    SetDiscussionGroupRequest, TogglePreHistoryHiddenRequest,
    ToggleSignaturesRequest, EditCreatorRequest,
    CreateChannelRequest, DeleteChannelRequest,
    GetAdminLogRequest, GetGroupParticipantsRequest
)
from telethon.tl.functions.contacts import (
    ResolveUsernameRequest, GetContactsRequest, DeleteContactsRequest,
    AddContactRequest, BlockRequest, UnblockRequest, GetBlockedRequest,
    ImportContactsRequest
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.photos import (
    GetUserPhotosRequest, UploadProfilePhotoRequest, DeletePhotosRequest
)
from telethon.tl.functions.auth import (
    ExportLoginTokenRequest, ImportLoginTokenRequest,
    CheckPasswordRequest, RequestPasswordRecoveryRequest
)
from telethon.tl.functions.stories import (
    GetAllStoriesRequest, GetPeerStoriesRequest,
    ReadStoriesRequest, GetStoriesByIDRequest
)
from telethon.tl.types import (
    ChatBannedRights, ChatAdminRights,
    InputPrivacyValueAllowAll, InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll, InputPrivacyValueAllowUsers,
    InputPrivacyValueDisallowUsers,
    InputKeyPrivacyRulesPhoneNumber, InputKeyPrivacyRulesLastSeen,
    InputKeyPrivacyRulesProfilePhoto, InputKeyPrivacyRulesForwards,
    InputKeyPrivacyRulesPhoneCall, InputKeyPrivacyRulesChatInvite,
    InputKeyPrivacyRulesAbout, InputKeyPrivacyRulesVoiceMessages,
    SendMessageTypingAction, SendMessageCancelAction,
    SendMessageGamePlayAction, SendMessageRecordAudioAction,
    SendMessageUploadDocumentAction, SendMessageChooseStickerAction,
    MessageMediaDocument, MessageMediaPhoto, ReactionEmoji,
    InputUser, InputPhoneContact, DocumentAttributeFilename,
    ChannelParticipantsRecent, ChannelParticipantsAdmins,
    ChannelParticipantsBanned, ChannelParticipantsSearch,
    InputReportReasonSpam, InputReportReasonViolence,
    InputReportReasonPornography, InputReportReasonOther,
    TypeInputPrivacyKey
)
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserAlreadyParticipantError,
    InviteHashExpiredError, ChannelPrivateError, ChatAdminRequiredError,
    UserNotParticipantError, MessageNotModifiedError, MessageIdInvalidError,
    PhoneNumberInvalidError, PhoneCodeInvalidError, PhoneCodeExpiredError,
    UsernameNotOccupiedError, PeerIdInvalidError, UserBlockedError,
    ChatWriteForbiddenError, SlowModeWaitError, MediaCaptionTooLongError,
    FilePartsInvalidError, AuthKeyError
)

# ==================== CREDENTIALS ====================
API_ID   = 38508708
API_HASH = "eed34e5b6ae89fa60ea734450347dc91"
# =====================================================

DATA_DIR  = Path("mytg_data")
MEDIA_DIR = DATA_DIR / "media"
LOG_DIR   = DATA_DIR / "logs"
EXPORT_DIR = DATA_DIR / "exports"
for d in [DATA_DIR, MEDIA_DIR, LOG_DIR, EXPORT_DIR]:
    d.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "core.db"

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# ==================== DB ====================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, type TEXT, session TEXT,
        phone_or_token TEXT, is_active INTEGER DEFAULT 1,
        device_model TEXT, app_version TEXT,
        created REAL, last_used REAL
    );
    CREATE TABLE IF NOT EXISTS deleted_msgs (
        id INTEGER, chat_id INTEGER, account_id INTEGER,
        data TEXT, ts REAL, PRIMARY KEY (id, chat_id, account_id)
    );
    CREATE TABLE IF NOT EXISTS edit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id INTEGER, chat_id INTEGER, account_id INTEGER,
        text TEXT, date REAL
    );
    CREATE TABLE IF NOT EXISTS scheduled (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, chat_id INTEGER, text TEXT,
        media_path TEXT, run_at REAL, recurring TEXT,
        status TEXT DEFAULT 'pending', created REAL
    );
    CREATE TABLE IF NOT EXISTS vault (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, blob BLOB, created REAL
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, body TEXT, chat_id INTEGER, created REAL, updated REAL
    );
    CREATE TABLE IF NOT EXISTS notif_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, chat_id INTEGER, keyword TEXT,
        action TEXT, notify_acc INTEGER, enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS snippets (
        name TEXT PRIMARY KEY, content TEXT, created REAL
    );
    CREATE TABLE IF NOT EXISTS auto_forward (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, src_chat INTEGER, dst_chat INTEGER,
        keywords TEXT, strip_meta INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS shadow_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, action TEXT, target TEXT, detail TEXT, ts REAL
    );
    CREATE TABLE IF NOT EXISTS message_index (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, chat_id INTEGER, msg_id INTEGER,
        text TEXT, sender_id INTEGER, date REAL
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(
        text, content='message_index', content_rowid='rowid'
    );
    CREATE TABLE IF NOT EXISTS contact_book (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, user_id INTEGER, username TEXT,
        name TEXT, phone TEXT, note TEXT, tag TEXT, updated REAL
    );
    CREATE TABLE IF NOT EXISTS blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, user_id INTEGER, reason TEXT, added REAL
    );
    CREATE TABLE IF NOT EXISTS dm_drafts (
        account_id INTEGER, chat_id INTEGER,
        text TEXT, updated REAL,
        PRIMARY KEY (account_id, chat_id)
    );
    CREATE TABLE IF NOT EXISTS media_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, chat_id INTEGER, msg_id INTEGER,
        local_path TEXT, media_type TEXT, ts REAL
    );
    CREATE TABLE IF NOT EXISTS broadcast_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, name TEXT, chat_ids TEXT, created REAL
    );
    CREATE TABLE IF NOT EXISTS pin_codes (
        account_id INTEGER PRIMARY KEY,
        pin_hash TEXT, enabled INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS warmup_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, status TEXT DEFAULT 'idle',
        actions_done INTEGER DEFAULT 0, started REAL, updated REAL
    );
    CREATE TABLE IF NOT EXISTS user_track (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        watcher_acc INTEGER, target_user INTEGER,
        event_type TEXT, detail TEXT, ts REAL
    );
    CREATE TABLE IF NOT EXISTS group_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, chat_id INTEGER,
        member_count INTEGER, msg_count INTEGER, active_users INTEGER,
        ts REAL
    );
    CREATE TABLE IF NOT EXISTS story_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, target_id INTEGER,
        story_id INTEGER, viewed_at REAL
    );
    CREATE TABLE IF NOT EXISTS phone_lookup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, phone TEXT, user_id INTEGER,
        username TEXT, name TEXT, looked_up REAL
    );
    CREATE TABLE IF NOT EXISTS scheduled_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, action_type TEXT,
        params TEXT, run_at REAL, status TEXT DEFAULT 'pending'
    );
    """)
    db.commit()
    db.close()


init_db()


# ==================== VAULT ====================
class Vault:
    def __init__(self, password: str):
        if not HAS_CRYPTO:
            raise RuntimeError("pip install cryptography")
        salt = b"mytg_vault_v3_salt"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.fernet = Fernet(key)
    def lock(self, data: str) -> bytes:
        return self.fernet.encrypt(data.encode())
    def unlock(self, blob: bytes) -> str:
        return self.fernet.decrypt(blob).decode()


# ==================== DEVICE PROFILES ====================
DEVICE_PROFILES = {
    "android_samsung": {
        "device_model": "Samsung Galaxy S24 Ultra",
        "system_version": "Android 14",
        "app_version": "10.3.2",
        "lang_code": "en",
        "system_lang_code": "en-US"
    },
    "iphone_15": {
        "device_model": "iPhone 15 Pro Max",
        "system_version": "iOS 17.4",
        "app_version": "10.3.1",
        "lang_code": "en",
        "system_lang_code": "en-US"
    },
    "android_pixel": {
        "device_model": "Google Pixel 8 Pro",
        "system_version": "Android 14",
        "app_version": "10.2.9",
        "lang_code": "en",
        "system_lang_code": "en-US"
    },
    "windows_desktop": {
        "device_model": "Desktop",
        "system_version": "Windows 11",
        "app_version": "4.16.8",
        "lang_code": "en",
        "system_lang_code": "en-US"
    },
    "mac_desktop": {
        "device_model": "MacBook Pro M3",
        "system_version": "macOS 14.4",
        "app_version": "10.3.0",
        "lang_code": "en",
        "system_lang_code": "en-US"
    },
    "oneplus": {
        "device_model": "OnePlus 12",
        "system_version": "Android 14",
        "app_version": "10.3.0",
        "lang_code": "en",
        "system_lang_code": "en-US"
    }
}


def random_device() -> dict:
    return random.choice(list(DEVICE_PROFILES.values()))


@dataclass
class Account:
    id: int
    name: str
    type: str
    session: str
    phone_or_token: str
    device_profile: str = "android_samsung"


@dataclass
class StealthConfig:
    ghost: bool = False
    no_read: bool = False
    no_typing: bool = False
    fake_online: bool = False
    delay_min: float = 0.8
    delay_max: float = 3.5
    human_typing: bool = True
    anti_screenshot: bool = False


# ==================== CORE ====================
class MyTG:
    def __init__(self):
        self.clients: Dict[int, TelegramClient] = {}
        self.accounts: Dict[int, Account] = {}
        self.stealth: Dict[int, StealthConfig] = {}
        self.vault: Optional[Vault] = None
        self._tasks: List[asyncio.Task] = []
        self._scheduler_running = False
        self._online_spoofer_running = False
        self._load_accounts()

    def _load_accounts(self):
        db = get_db()
        for r in db.execute("SELECT * FROM accounts WHERE is_active=1").fetchall():
            self.accounts[r["id"]] = Account(
                r["id"], r["name"], r["type"],
                r["session"] or "", r["phone_or_token"] or "",
                r["device_model"] or "android_samsung"
            )
            self.stealth[r["id"]] = StealthConfig()
        db.close()

    def _log(self, acc_id: int, action: str, target: str = "", detail: str = ""):
        db = get_db()
        db.execute(
            "INSERT INTO shadow_log (account_id,action,target,detail,ts) VALUES (?,?,?,?,?)",
            (acc_id, action, str(target), detail, time.time())
        )
        db.commit()
        db.close()

    def _save_account(self, name, acc_type, session, phone_or_token, device_profile="android_samsung") -> int:
        db = get_db()
        dp = DEVICE_PROFILES.get(device_profile, DEVICE_PROFILES["android_samsung"])
        cur = db.execute(
            "INSERT INTO accounts (name,type,session,phone_or_token,device_model,app_version,created,last_used) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (name, acc_type, session, phone_or_token,
             dp["device_model"], dp["app_version"], time.time(), time.time())
        )
        acc_id = cur.lastrowid
        db.commit()
        db.close()
        return acc_id

    def _make_client(self, session_str: str = "", device: str = "android_samsung") -> TelegramClient:
        dp = DEVICE_PROFILES.get(device, DEVICE_PROFILES["android_samsung"])
        return TelegramClient(
            StringSession(session_str), API_ID, API_HASH,
            device_model=dp["device_model"],
            system_version=dp["system_version"],
            app_version=dp["app_version"],
            lang_code=dp["lang_code"],
            system_lang_code=dp["system_lang_code"]
        )

    # ==================== LOGIN (CALLBACK-BASED) ====================

    async def login_phone_start(self, name: str, phone: str,
                                 device: str = "android_samsung") -> dict:
        client = self._make_client(device=device)
        await client.connect()
        sent = await client.send_code_request(phone)
        return {
            "phone_code_hash": sent.phone_code_hash,
            "client": client,
            "name": name,
            "phone": phone,
            "device": device
        }

    async def login_phone_complete(self, session_data: dict, otp: str,
                                    password: str = None) -> Account:
        client = session_data["client"]
        phone = session_data["phone"]
        name = session_data["name"]
        phone_code_hash = session_data["phone_code_hash"]
        device = session_data["device"]

        try:
            await client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise ValueError("2FA_REQUIRED")
            await client.sign_in(password=password)
        except PhoneCodeInvalidError:
            raise ValueError("WRONG_OTP")
        except PhoneCodeExpiredError:
            raise ValueError("OTP_EXPIRED")

        me = await client.get_me()
        session = client.session.save()
        acc_id = self._save_account(name or me.first_name, "user", session, phone, device)
        self.clients[acc_id] = client
        self.accounts[acc_id] = Account(acc_id, name or me.first_name, "user", session, phone, device)
        self.stealth[acc_id] = StealthConfig()
        await self._attach_handlers(acc_id, client)
        self._log(acc_id, "login_phone", phone)
        return self.accounts[acc_id]

    async def login_bot(self, name: str, token: str,
                         device: str = "android_samsung") -> Account:
        client = self._make_client(device=device)
        await client.start(bot_token=token)
        me = await client.get_me()
        session = client.session.save()
        acc_id = self._save_account(name or f"@{me.username}", "bot", session, token, device)
        self.clients[acc_id] = client
        self.accounts[acc_id] = Account(acc_id, name or f"@{me.username}", "bot", session, token, device)
        self.stealth[acc_id] = StealthConfig()
        await self._attach_handlers(acc_id, client)
        self._log(acc_id, "login_bot", token[:20])
        return self.accounts[acc_id]

    async def login_session(self, name: str, session_str: str,
                             device: str = "iphone_15") -> Account:
        client = self._make_client(session_str=session_str, device=device)
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("session dead or invalid")
        me = await client.get_me()
        session = client.session.save()
        acc_id = self._save_account(name or (me.first_name or me.username), "user", session, "", device)
        self.clients[acc_id] = client
        self.accounts[acc_id] = Account(acc_id, name or (me.first_name or ""), "user", session, "", device)
        self.stealth[acc_id] = StealthConfig()
        await self._attach_handlers(acc_id, client)
        self._log(acc_id, "login_session", "imported")
        return self.accounts[acc_id]

    async def login_qr_start(self, name: str, device: str = "android_samsung") -> dict:
        client = self._make_client(device=device)
        await client.connect()
        r = await client(ExportLoginTokenRequest(
            api_id=API_ID, api_hash=API_HASH, except_ids=[]
        ))
        if not hasattr(r, 'token'):
            raise RuntimeError("QR not available — use phone/session login")

        token_b64 = base64.urlsafe_b64encode(r.token).decode()
        qr_url = f"tg://login?token={token_b64}"
        return {
            "token": r.token,
            "url": qr_url,
            "client": client,
            "name": name,
            "device": device
        }

    async def login_qr_complete(self, session_data: dict) -> Account:
        client = session_data["client"]
        r = await client(ImportLoginTokenRequest(session_data["token"]))
        me = await client.get_me()
        if not me:
            raise RuntimeError("QR scan not completed")
        session = client.session.save()
        name = session_data["name"]
        device = session_data["device"]
        acc_id = self._save_account(name or me.first_name, "user", session, "", device)
        self.clients[acc_id] = client
        self.accounts[acc_id] = Account(acc_id, name or me.first_name, "user", session, "", device)
        self.stealth[acc_id] = StealthConfig()
        await self._attach_handlers(acc_id, client)
        self._log(acc_id, "login_qr", "qr_scan")
        return self.accounts[acc_id]

    # Old aliases (terminal compat — these use input(), don't call from GUI)
    async def login_phone(self, name, phone, device="android_samsung"):
        sd = await self.login_phone_start(name, phone, device)
        otp = input(f"[OTP] Code for {phone}: ").strip()
        try:
            return await self.login_phone_complete(sd, otp)
        except ValueError as e:
            if str(e) == "2FA_REQUIRED":
                pw = input("[2FA] Password: ").strip()
                return await self.login_phone_complete(sd, otp, password=pw)
            raise

    async def login_qr(self, name, device="android_samsung"):
        sd = await self.login_qr_start(name, device)
        print(f"\n[QR] Open in Telegram: {sd['url']}")
        print("[QR] Waiting for scan... (press Enter after scanning)")
        input()
        return await self.login_qr_complete(sd)

    # ==================== START ALL ====================
    async def start_all(self):
        for acc_id, acc in list(self.accounts.items()):
            if acc_id in self.clients:
                continue
            client = self._make_client(session_str=acc.session, device=acc.device_profile)
            try:
                if acc.type == "bot":
                    await client.start(bot_token=acc.phone_or_token)
                else:
                    await client.connect()
                    if not await client.is_user_authorized():
                        print(f"[!] {acc.name}: session expired")
                        continue
                self.clients[acc_id] = client
                self.stealth[acc_id] = StealthConfig()
                await self._attach_handlers(acc_id, client)
                me = await client.get_me()
                db = get_db()
                db.execute("UPDATE accounts SET last_used=? WHERE id=?", (time.time(), acc_id))
                db.commit()
                db.close()
                print(f"[+] {acc.type.upper()} | {acc.name} | @{me.username}")
            except AuthKeyError:
                print(f"[!] {acc.name}: auth key invalid")
            except Exception as e:
                print(f"[!] {acc.name}: {e}")

    async def remove_account(self, acc_id: int, logout: bool = False):
        client = self.clients.pop(acc_id, None)
        if client:
            if logout:
                try:
                    await client.log_out()
                except Exception:
                    pass
            await client.disconnect()
        db = get_db()
        db.execute("UPDATE accounts SET is_active=0 WHERE id=?", (acc_id,))
        db.commit()
        db.close()
        self.accounts.pop(acc_id, None)
        self.stealth.pop(acc_id, None)

    async def export_session(self, acc_id: int) -> str:
        s = self.clients[acc_id].session.save()
        self._log(acc_id, "export_session", "self")
        return s

    # ==================== HANDLERS ====================
    async def _attach_handlers(self, acc_id: int, client: TelegramClient):
        @client.on(events.NewMessage)
        async def on_new(event):
            if event.raw_text:
                db = get_db()
                db.execute(
                    "INSERT INTO message_index (account_id,chat_id,msg_id,text,sender_id,date) "
                    "VALUES (?,?,?,?,?,?)",
                    (acc_id, event.chat_id, event.id, event.raw_text,
                     event.sender_id or 0, time.time())
                )
                db.execute(
                    "INSERT INTO message_fts(rowid,text) SELECT last_insert_rowid(),?",
                    (event.raw_text,)
                )
                db.commit()
                db.close()
            await self._check_blacklist_auto(acc_id, event)
            await self._check_auto_forward(acc_id, event)

        @client.on(events.MessageDeleted)
        async def on_del(event):
            for mid in event.deleted_ids:
                db = get_db()
                db.execute(
                    "INSERT OR IGNORE INTO deleted_msgs (id,chat_id,account_id,data,ts) VALUES (?,?,?,?,?)",
                    (mid, event.chat_id or 0, acc_id,
                     json.dumps({"id": mid, "chat": event.chat_id}), time.time())
                )
                db.commit()
                db.close()

        @client.on(events.MessageEdited)
        async def on_edit(event):
            db = get_db()
            db.execute(
                "INSERT INTO edit_history (msg_id,chat_id,account_id,text,date) VALUES (?,?,?,?,?)",
                (event.id, event.chat_id, acc_id, event.raw_text or "", time.time())
            )
            db.commit()
            db.close()

    async def _check_blacklist_auto(self, acc_id: int, event):
        if event.out or not event.sender_id:
            return
        db = get_db()
        row = db.execute(
            "SELECT id FROM blacklist WHERE account_id=? AND user_id=?",
            (acc_id, event.sender_id)
        ).fetchone()
        db.close()
        if row:
            try:
                await event.delete()
            except Exception:
                pass

    async def _check_auto_forward(self, acc_id: int, event):
        if event.out:
            return
        db = get_db()
        rules = db.execute(
            "SELECT * FROM auto_forward WHERE account_id=? AND src_chat=? AND enabled=1",
            (acc_id, event.chat_id)
        ).fetchall()
        db.close()
        client = self.clients.get(acc_id)
        if not client:
            return
        text = (event.raw_text or "").lower()
        for r in rules:
            kws = [k.strip().lower() for k in (r["keywords"] or "").split(",") if k.strip()]
            if not kws or any(k in text for k in kws):
                try:
                    if r["strip_meta"]:
                        if event.message.media:
                            await client.send_file(r["dst_chat"], event.message.media,
                                                   caption=event.raw_text or "")
                        else:
                            await client.send_message(r["dst_chat"], event.raw_text or "")
                    else:
                        await client.forward_messages(r["dst_chat"], event.message)
                except Exception:
                    pass

    # ==================== STEALTH ====================
    async def stealth_set(self, acc_id: int, **kwargs):
        cfg = self.stealth.setdefault(acc_id, StealthConfig())
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        client = self.clients.get(acc_id)
        if client and cfg.ghost:
            await client(UpdateStatusRequest(offline=True))

    async def typing_human(self, acc_id: int, chat_id: int, text: str):
        cfg = self.stealth.get(acc_id, StealthConfig())
        if cfg.ghost or cfg.no_typing:
            return
        client = self.clients[acc_id]
        duration = max(1.5, min(len(text) / 3.3, 8.0))
        entity = await client.get_entity(chat_id)
        await client(SetTypingRequest(entity, SendMessageTypingAction()))
        await asyncio.sleep(duration + random.uniform(-0.3, 0.5))
        await client(SetTypingRequest(entity, SendMessageCancelAction()))

    async def fake_action(self, acc_id: int, chat_id: int,
                           action: str = "typing", duration: float = 3.0):
        client = self.clients[acc_id]
        entity = await client.get_entity(chat_id)
        actions = {
            "typing":    SendMessageTypingAction(),
            "recording": SendMessageRecordAudioAction(),
            "uploading": SendMessageUploadDocumentAction(progress=0),
            "playing":   SendMessageGamePlayAction(),
            "sticker":   SendMessageChooseStickerAction(),
        }
        act = actions.get(action, SendMessageTypingAction())
        await client(SetTypingRequest(entity, act))
        await asyncio.sleep(duration)
        await client(SetTypingRequest(entity, SendMessageCancelAction()))

    # ==================== MESSAGE OPS ====================
    async def send_stealth(self, acc_id: int, chat_id: int, text: str,
                            reply_to: int = None, schedule_secs: int = 0):
        client = self.clients[acc_id]
        cfg = self.stealth.get(acc_id, StealthConfig())
        if cfg.human_typing:
            await self.typing_human(acc_id, chat_id, text)
        kwargs = {}
        if reply_to:
            kwargs["reply_to"] = reply_to
        if schedule_secs:
            from datetime import timezone
            kwargs["schedule"] = datetime.now(timezone.utc) + timedelta(seconds=schedule_secs)
        await client.send_message(chat_id, text, **kwargs)

    async def clone_chat(self, acc_id: int, src: int, dst: int,
                          limit: int = 500, delay: float = 1.0,
                          as_copy: bool = True, filter_keyword: str = None):
        client = self.clients[acc_id]
        msgs = list(reversed(await client.get_messages(src, limit=limit)))
        cloned = 0
        for msg in msgs:
            if filter_keyword and filter_keyword.lower() not in (msg.text or "").lower():
                continue
            try:
                if as_copy:
                    if msg.media:
                        await client.send_file(dst, msg.media, caption=msg.text or "")
                    elif msg.text:
                        await client.send_message(dst, msg.text)
                    else:
                        continue
                else:
                    await client.forward_messages(dst, msg.id, from_peer=src)
                cloned += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                print(f"[clone] {e}")
            await asyncio.sleep(delay + random.uniform(0.1, 0.5))
        self._log(acc_id, "clone_chat", f"{src}->{dst}", f"n={cloned}")
        return cloned

    async def message_bomb(self, acc_id: int, chat_id: int, text: str,
                            count: int = 10, delay: float = 0.5):
        client = self.clients[acc_id]
        sent = 0
        for i in range(count):
            try:
                await client.send_message(chat_id, text)
                sent += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
            except SlowModeWaitError as e:
                await asyncio.sleep(e.seconds + 1)
            except Exception:
                break
            await asyncio.sleep(delay + random.uniform(0, 0.3))
        self._log(acc_id, "msg_bomb", str(chat_id), f"n={sent}")
        return sent

    async def reaction_bomb(self, acc_id: int, chat_id: int,
                             msg_ids: List[int], emoji: str = "🔥"):
        client = self.clients[acc_id]
        done = 0
        for mid in msg_ids:
            try:
                await client(SendReactionRequest(
                    peer=await client.get_entity(chat_id),
                    msg_id=mid,
                    reaction=[ReactionEmoji(emoticon=emoji)]
                ))
                done += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception:
                pass
            await asyncio.sleep(random.uniform(0.3, 0.8))
        self._log(acc_id, "reaction_bomb", str(chat_id), f"n={done}")
        return done

    async def vote_poll(self, acc_id: int, chat_id: int, msg_id: int, option: int = 0):
        client = self.clients[acc_id]
        msg = await client.get_messages(chat_id, ids=msg_id)
        if not msg or not hasattr(msg.media, 'poll'):
            raise ValueError("not a poll message")
        answers = msg.media.poll.answers
        if option >= len(answers):
            raise IndexError(f"option {option} out of range")
        await client(SendVoteRequest(
            peer=await client.get_entity(chat_id),
            msg_id=msg_id,
            options=[answers[option].option]
        ))
        self._log(acc_id, "vote_poll", str(chat_id), f"msg={msg_id} opt={option}")

    async def bulk_delete_messages(self, acc_id: int, chat_id: int,
                                    limit: int = 0, keyword: str = None,
                                    older_than_days: int = 0):
        client = self.clients[acc_id]
        me = await client.get_me()
        deleted = 0
        cutoff = time.time() - older_than_days * 86400 if older_than_days else 0
        async for msg in client.iter_messages(chat_id, from_user=me.id, limit=limit or None):
            if keyword and keyword.lower() not in (msg.text or "").lower():
                continue
            if cutoff and msg.date.timestamp() > cutoff:
                continue
            try:
                await msg.delete()
                deleted += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)
        self._log(acc_id, "bulk_delete", str(chat_id), f"n={deleted}")
        return deleted

    async def send_scheduled(self, acc_id: int, chat_id: int, text: str,
                              when: datetime, media_path: str = None,
                              recurring: str = None):
        db = get_db()
        db.execute(
            "INSERT INTO scheduled (account_id,chat_id,text,media_path,run_at,recurring,created) "
            "VALUES (?,?,?,?,?,?,?)",
            (acc_id, chat_id, text, media_path, when.timestamp(), recurring, time.time())
        )
        db.commit()
        db.close()

    async def _scheduler_loop(self):
        while self._scheduler_running:
            now = time.time()
            db = get_db()
            rows = db.execute(
                "SELECT * FROM scheduled WHERE status='pending' AND run_at<=?", (now,)
            ).fetchall()
            db.close()
            for r in rows:
                client = self.clients.get(r["account_id"])
                if not client:
                    continue
                try:
                    if r["media_path"] and Path(r["media_path"]).exists():
                        await client.send_file(r["chat_id"], r["media_path"],
                                               caption=r["text"] or "")
                    elif r["text"]:
                        await client.send_message(r["chat_id"], r["text"])
                    db = get_db()
                    if r["recurring"] == "daily":
                        db.execute("UPDATE scheduled SET run_at=? WHERE id=?",
                                   (r["run_at"] + 86400, r["id"]))
                    elif r["recurring"] == "weekly":
                        db.execute("UPDATE scheduled SET run_at=? WHERE id=?",
                                   (r["run_at"] + 604800, r["id"]))
                    else:
                        db.execute("UPDATE scheduled SET status='done' WHERE id=?", (r["id"],))
                    db.commit()
                    db.close()
                except Exception as e:
                    db = get_db()
                    db.execute("UPDATE scheduled SET status='error' WHERE id=?", (r["id"],))
                    db.commit()
                    db.close()
                    print(f"[sched] err: {e}")
            await asyncio.sleep(10)

    def start_scheduler(self, acc_id=None):
        if not self._scheduler_running:
            self._scheduler_running = True
            self._tasks.append(asyncio.create_task(self._scheduler_loop()))

    # ==================== GROUP OPS ====================
    async def mass_join(self, acc_id: int, links: List[str],
                         delay: float = 5.0) -> List[Tuple[str, str]]:
        client = self.clients[acc_id]
        results = []
        for link in links:
            link = link.strip()
            try:
                if "joinchat/" in link or link.startswith("+"):
                    hash_ = link.split("/")[-1].lstrip("+")
                    await client(ImportChatInviteRequest(hash_))
                    results.append((link, "joined_private"))
                else:
                    username = link.split("/")[-1].replace("@", "")
                    entity = await client.get_entity(username)
                    await client(JoinChannelRequest(entity))
                    results.append((link, "joined_public"))
                self._log(acc_id, "join", link)
            except UserAlreadyParticipantError:
                results.append((link, "already_member"))
            except FloodWaitError as e:
                results.append((link, f"flood_{e.seconds}s"))
                await asyncio.sleep(e.seconds + 5)
                continue
            except InviteHashExpiredError:
                results.append((link, "invite_expired"))
            except ChannelPrivateError:
                results.append((link, "private_channel"))
            except Exception as e:
                results.append((link, str(e)[:50]))
            await asyncio.sleep(delay + random.uniform(1, 3))
        return results

    async def mass_leave(self, acc_id: int, chat_ids: List[int],
                          revoke: bool = False, delay: float = 2.0):
        client = self.clients[acc_id]
        results = []
        for cid in chat_ids:
            try:
                await client.delete_dialog(cid, revoke=revoke)
                results.append((cid, "left"))
            except Exception as e:
                results.append((cid, str(e)[:40]))
            await asyncio.sleep(delay + random.uniform(0, 1))
        return results

    async def members_dump(self, acc_id: int, chat, limit: int = 0,
                            aggressive: bool = False) -> List[dict]:
        client = self.clients[acc_id]
        members = []
        seen = set()

        async def _collect(search: str = ""):
            try:
                async for user in client.iter_participants(
                    chat, aggressive=aggressive,
                    search=search, limit=limit or None
                ):
                    if user.id not in seen:
                        seen.add(user.id)
                        members.append({
                            "id": user.id,
                            "username": user.username,
                            "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                            "phone": getattr(user, "phone", None),
                            "bot": user.bot,
                            "premium": getattr(user, "premium", False),
                            "scam": getattr(user, "scam", False),
                            "fake": getattr(user, "fake", False),
                        })
            except (ChatAdminRequiredError, ChannelPrivateError):
                pass
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)

        if aggressive:
            for ch in "abcdefghijklmnopqrstuvwxyz0123456789":
                await _collect(ch)
                await asyncio.sleep(random.uniform(0.3, 0.8))
        else:
            await _collect()

        self._log(acc_id, "members_dump", str(chat), f"n={len(members)}")
        return members

    async def ban_user(self, acc_id: int, chat, user_id: int,
                        until: int = 0, reason: str = ""):
        client = self.clients[acc_id]
        rights = ChatBannedRights(
            until_date=datetime.utcfromtimestamp(time.time() + until) if until else None,
            view_messages=True, send_messages=True, send_media=True,
            send_stickers=True, send_gifs=True, send_games=True,
            send_inline=True, embed_links=True
        )
        entity = await client.get_entity(chat)
        user_entity = await client.get_entity(user_id)
        await client(EditBannedRequest(entity, user_entity, rights))
        self._log(acc_id, "ban", str(user_id), reason)

    async def unban_user(self, acc_id: int, chat, user_id: int):
        client = self.clients[acc_id]
        rights = ChatBannedRights(until_date=None)
        entity = await client.get_entity(chat)
        user_entity = await client.get_entity(user_id)
        await client(EditBannedRequest(entity, user_entity, rights))

    async def promote_admin(self, acc_id: int, chat, user_id: int,
                             title: str = "", full_rights: bool = False):
        client = self.clients[acc_id]
        rights = ChatAdminRights(
            change_info=full_rights, post_messages=full_rights,
            edit_messages=full_rights, delete_messages=True,
            ban_users=full_rights, invite_users=True,
            pin_messages=full_rights, add_admins=False,
            manage_call=full_rights, anonymous=False,
            manage_topics=full_rights
        )
        entity = await client.get_entity(chat)
        user_entity = await client.get_entity(user_id)
        await client(EditAdminRequest(entity, user_entity, rights, title))

    async def get_invite_link(self, acc_id: int, chat_id: int,
                               expire_hours: int = 0, usage_limit: int = 0) -> str:
        client = self.clients[acc_id]
        entity = await client.get_entity(chat_id)
        r = await client(functions.messages.ExportChatInviteRequest(
            peer=entity,
            expire_date=int(time.time() + expire_hours * 3600) if expire_hours else None,
            usage_limit=usage_limit or 0,
            request_needed=False
        ))
        return r.link

    # ==================== USER OPS ====================
    async def user_deep_info(self, acc_id: int, user) -> dict:
        client = self.clients[acc_id]
        if isinstance(user, str):
            r = await client(ResolveUsernameRequest(user.replace("@", "")))
            entity = r.peer
        else:
            entity = user
        full = await client(GetFullUserRequest(entity))
        u = full.users[0] if full.users else None
        photos_r = await client(GetUserPhotosRequest(entity, 0, 0, 0))
        common = await client(functions.messages.GetCommonChatsRequest(
            user_id=await client.get_entity(entity), max_id=0, limit=100
        ))
        return {
            "id": u.id if u else None,
            "username": u.username if u else None,
            "first": u.first_name if u else None,
            "last": u.last_name if u else None,
            "bio": full.full_user.about,
            "common_chats": full.full_user.common_chats_count,
            "common_chat_titles": [c.title for c in common.chats[:5]],
            "blocked": full.full_user.blocked,
            "phone": getattr(u, "phone", None),
            "photo_count": photos_r.count,
            "premium": getattr(u, "premium", False),
            "scam": getattr(u, "scam", False),
            "fake": getattr(u, "fake", False),
            "verified": getattr(u, "verified", False),
            "bot": getattr(u, "bot", False),
            "restricted": getattr(u, "restricted", False),
        }

    async def phone_to_user(self, acc_id: int, phones: List[str]) -> List[dict]:
        client = self.clients[acc_id]
        contacts = []
        for i, ph in enumerate(phones):
            contacts.append(InputPhoneContact(
                client_id=i, phone=ph, first_name=f"lookup{i}", last_name=""
            ))
        r = await client(ImportContactsRequest(contacts))
        results = []
        for u in r.users:
            db = get_db()
            db.execute(
                "INSERT INTO phone_lookup (account_id,phone,user_id,username,name,looked_up) "
                "VALUES (?,?,?,?,?,?)",
                (acc_id, getattr(u, "phone", ""), u.id, u.username or "",
                 f"{u.first_name or ''} {u.last_name or ''}".strip(), time.time())
            )
            db.commit()
            db.close()
            results.append({
                "phone": getattr(u, "phone", ""),
                "id": u.id,
                "username": u.username,
                "name": f"{u.first_name or ''} {u.last_name or ''}".strip()
            })
        try:
            imported = [InputUser(u.id, u.access_hash) for u in r.users]
            if imported:
                await client(DeleteContactsRequest(imported))
        except Exception:
            pass
        self._log(acc_id, "phone_lookup", "", f"n={len(results)}")
        return results

    async def get_online_status(self, acc_id: int, user_id: int) -> dict:
        client = self.clients[acc_id]
        entity = await client.get_entity(user_id)
        status = getattr(entity, "status", None)
        if status is None:
            return {"online": False, "last_seen": "hidden"}
        t = type(status).__name__
        if t == "UserStatusOnline":
            return {"online": True, "last_seen": "now"}
        if t == "UserStatusOffline":
            return {"online": False, "last_seen": str(getattr(status, "was_online", "?"))}
        if t == "UserStatusRecently":
            return {"online": False, "last_seen": "recently"}
        return {"online": False, "last_seen": t.replace("UserStatus", "").lower()}

    async def block_user(self, acc_id: int, user_id: int, reason: str = ""):
        client = self.clients[acc_id]
        entity = await client.get_entity(user_id)
        await client(BlockRequest(entity))
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO blacklist (account_id,user_id,reason,added) VALUES (?,?,?,?)",
            (acc_id, user_id, reason, time.time())
        )
        db.commit()
        db.close()

    async def unblock_user(self, acc_id: int, user_id: int):
        client = self.clients[acc_id]
        entity = await client.get_entity(user_id)
        await client(UnblockRequest(entity))
        db = get_db()
        db.execute("DELETE FROM blacklist WHERE account_id=? AND user_id=?", (acc_id, user_id))
        db.commit()
        db.close()

    async def get_blocked_list(self, acc_id: int) -> List[dict]:
        client = self.clients[acc_id]
        r = await client(GetBlockedRequest(offset=0, limit=100))
        return [{"id": u.id, "username": u.username,
                  "name": f"{u.first_name or ''} {u.last_name or ''}".strip()}
                for u in r.users]

    # ==================== STORIES ====================
    async def view_stories(self, acc_id: int, peer, silent: bool = True) -> int:
        client = self.clients[acc_id]
        try:
            entity = await client.get_entity(peer)
            r = await client(GetPeerStoriesRequest(peer=entity))
            story_ids = [s.id for s in r.stories.stories]
            if story_ids:
                await client(ReadStoriesRequest(peer=entity, max_id=max(story_ids)))
                for sid in story_ids:
                    db = get_db()
                    db.execute(
                        "INSERT INTO story_log (account_id,target_id,story_id,viewed_at) VALUES (?,?,?,?)",
                        (acc_id, entity.id, sid, time.time())
                    )
                    db.commit()
                    db.close()
            self._log(acc_id, "view_stories", str(entity.id), f"n={len(story_ids)}")
            return len(story_ids)
        except Exception as e:
            print(f"[story] {e}")
            return 0

    async def mass_story_view(self, acc_id: int, peers: List, delay: float = 1.0):
        results = []
        for peer in peers:
            n = await self.view_stories(acc_id, peer)
            results.append((peer, n))
            await asyncio.sleep(delay + random.uniform(0, 0.5))
        return results

    # ==================== PRIVACY ====================
    async def set_privacy_all(self, acc_id: int, setting: str = "everybody"):
        client = self.clients[acc_id]
        val = {
            "everybody": InputPrivacyValueAllowAll(),
            "contacts": InputPrivacyValueAllowContacts(),
            "nobody": InputPrivacyValueDisallowAll()
        }.get(setting, InputPrivacyValueAllowAll())
        keys = [
            InputKeyPrivacyRulesLastSeen(),
            InputKeyPrivacyRulesProfilePhoto(),
            InputKeyPrivacyRulesForwards(),
            InputKeyPrivacyRulesChatInvite(),
            InputKeyPrivacyRulesAbout(),
            InputKeyPrivacyRulesVoiceMessages(),
        ]
        for key in keys:
            try:
                await client(SetPrivacyRequest(key=key, rules=[val]))
                await asyncio.sleep(0.4)
            except Exception:
                pass

    async def update_profile(self, acc_id: int, first: str = None,
                              last: str = None, bio: str = None, username: str = None):
        client = self.clients[acc_id]
        kwargs = {}
        if first is not None:
            kwargs["first_name"] = first
        if last is not None:
            kwargs["last_name"] = last
        if bio is not None:
            kwargs["about"] = bio
        if kwargs:
            await client(UpdateProfileRequest(**kwargs))
        if username is not None:
            await client(UpdateUsernameRequest(username))

    async def set_profile_photo(self, acc_id: int, path: str):
        client = self.clients[acc_id]
        await client(UploadProfilePhotoRequest(file=await client.upload_file(path)))

    async def clear_old_photos(self, acc_id: int):
        client = self.clients[acc_id]
        me = await client.get_me()
        r = await client(GetUserPhotosRequest(me.id, 0, 0, 0))
        if len(r.photos) > 1:
            await client(DeletePhotosRequest(r.photos[1:]))

    async def get_profile_photos(self, acc_id: int, user, limit: int = 10) -> List[str]:
        client = self.clients[acc_id]
        paths = []
        async for photo in client.iter_profile_photos(user, limit=limit):
            p = await client.download_profile_photo(
                user, file=str(MEDIA_DIR / f"pfp_{acc_id}_{photo.id}.jpg")
            )
            if p:
                paths.append(p)
        return paths

    async def set_account_ttl(self, acc_id: int, days: int = 180):
        client = self.clients[acc_id]
        try:
            from telethon.tl.types import AccountDaysTTL as _TTL
        except ImportError:
            try:
                from telethon.tl.types import AccountTTL as _TTL
            except ImportError:
                return False
        await client(SetAccountTTLRequest(ttl=_TTL(days=days)))
        return True

    # ==================== SEARCH ====================
    async def search_local(self, acc_id: int, query: str,
                            chat_id: int = None, limit: int = 50) -> List[dict]:
        db = get_db()
        if chat_id:
            rows = db.execute(
                "SELECT mi.* FROM message_fts mf "
                "JOIN message_index mi ON mi.rowid=mf.rowid "
                "WHERE mf.text MATCH ? AND mi.account_id=? AND mi.chat_id=? "
                "ORDER BY mi.date DESC LIMIT ?",
                (query, acc_id, chat_id, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT mi.* FROM message_fts mf "
                "JOIN message_index mi ON mi.rowid=mf.rowid "
                "WHERE mf.text MATCH ? AND mi.account_id=? "
                "ORDER BY mi.date DESC LIMIT ?",
                (query, acc_id, limit)
            ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    async def search_global(self, acc_id: int, query: str, limit: int = 50) -> List[dict]:
        client = self.clients[acc_id]
        results = []
        async for msg in client.iter_messages(None, search=query, limit=limit):
            results.append({
                "id": msg.id, "chat": msg.chat_id,
                "text": msg.text, "date": str(msg.date)
            })
        return results

    # ==================== DIALOGS ====================
    async def get_dialogs(self, acc_id: int, limit: int = 100) -> List[dict]:
        client = self.clients[acc_id]
        out = []
        async for d in client.iter_dialogs(limit=limit):
            out.append({
                "id": d.id, "name": d.name, "unread": d.unread_count,
                "pinned": d.pinned, "archived": d.archived,
                "is_group": d.is_group, "is_channel": d.is_channel,
                "is_user": d.is_user, "draft": d.draft.text if d.draft else None
            })
        return out

    async def archive_chat(self, acc_id: int, chat_id: int):
        client = self.clients[acc_id]
        await client.edit_folder(chat_id, folder=1)

    async def unarchive_chat(self, acc_id: int, chat_id: int):
        client = self.clients[acc_id]
        await client.edit_folder(chat_id, folder=0)

    # ==================== ANALYTICS ====================
    async def chat_analytics(self, acc_id: int, chat_id: int,
                              msg_limit: int = 500) -> dict:
        client = self.clients[acc_id]
        sender_count: Dict[int, int] = {}
        hour_count: Dict[int, int] = {}
        word_count: Dict[str, int] = {}
        total = 0
        media_count = 0
        async for msg in client.iter_messages(chat_id, limit=msg_limit):
            total += 1
            if msg.sender_id:
                sender_count[msg.sender_id] = sender_count.get(msg.sender_id, 0) + 1
            if msg.date:
                h = msg.date.hour
                hour_count[h] = hour_count.get(h, 0) + 1
            if msg.media:
                media_count += 1
            for word in (msg.text or "").lower().split():
                if len(word) > 3:
                    word_count[word] = word_count.get(word, 0) + 1
        top_senders = sorted(sender_count.items(), key=lambda x: -x[1])[:10]
        peak_hour = max(hour_count, key=hour_count.get) if hour_count else 0
        top_words = sorted(word_count.items(), key=lambda x: -x[1])[:20]
        result = {
            "total_messages": total,
            "media_messages": media_count,
            "text_messages": total - media_count,
            "unique_senders": len(sender_count),
            "top_senders": top_senders,
            "peak_hour": peak_hour,
            "hour_distribution": hour_count,
            "top_words": top_words
        }
        db = get_db()
        db.execute(
            "INSERT INTO group_analytics (account_id,chat_id,member_count,msg_count,active_users,ts) "
            "VALUES (?,?,?,?,?,?)",
            (acc_id, chat_id, 0, total, len(sender_count), time.time())
        )
        db.commit()
        db.close()
        return result

    # ==================== MEDIA ====================
    async def download_media_range(self, acc_id: int, chat_id: int,
                                    limit: int = 100, media_type: str = "all") -> List[str]:
        client = self.clients[acc_id]
        paths = []
        async for msg in client.iter_messages(chat_id, limit=limit):
            if not msg.media:
                continue
            if media_type == "photo" and not isinstance(msg.media, MessageMediaPhoto):
                continue
            if media_type == "doc" and not isinstance(msg.media, MessageMediaDocument):
                continue
            try:
                p = await client.download_media(
                    msg, file=str(MEDIA_DIR / f"{acc_id}_{chat_id}_{msg.id}")
                )
                if p:
                    paths.append(p)
                    await asyncio.sleep(0.2)
            except Exception as e:
                print(f"[dl] {e}")
        return paths

    # ==================== VAULT ====================
    def vault_open(self, password: str):
        self.vault = Vault(password)

    def vault_save(self, title: str, data: str):
        if not self.vault:
            raise RuntimeError("vault locked")
        blob = self.vault.lock(data)
        db = get_db()
        db.execute("INSERT INTO vault (title,blob,created) VALUES (?,?,?)",
                   (title, blob, time.time()))
        db.commit()
        db.close()

    def vault_read(self, title: str) -> str:
        if not self.vault:
            raise RuntimeError("vault locked")
        db = get_db()
        row = db.execute("SELECT blob FROM vault WHERE title=?", (title,)).fetchone()
        db.close()
        if not row:
            raise KeyError(title)
        return self.vault.unlock(row["blob"])

    def vault_list(self) -> List[dict]:
        db = get_db()
        rows = db.execute("SELECT id,title,created FROM vault ORDER BY created DESC").fetchall()
        db.close()
        return [dict(r) for r in rows]

    def vault_delete(self, title: str):
        db = get_db()
        db.execute("DELETE FROM vault WHERE title=?", (title,))
        db.commit()
        db.close()

    # ==================== SNIPPETS ====================
    def snippet_save(self, name: str, content: str):
        db = get_db()
        db.execute("INSERT OR REPLACE INTO snippets (name,content,created) VALUES (?,?,?)",
                   (name, content, time.time()))
        db.commit()
        db.close()

    def snippet_get(self, name: str) -> str:
        db = get_db()
        row = db.execute("SELECT content FROM snippets WHERE name=?", (name,)).fetchone()
        db.close()
        if not row:
            raise KeyError(name)
        return row["content"]

    def snippet_list(self) -> List[dict]:
        db = get_db()
        rows = db.execute("SELECT name,created FROM snippets ORDER BY name").fetchall()
        db.close()
        return [dict(r) for r in rows]

    def snippet_delete(self, name: str):
        db = get_db()
        db.execute("DELETE FROM snippets WHERE name=?", (name,))
        db.commit()
        db.close()

    # ==================== LOG ====================
    def get_deleted_msgs(self, acc_id: int, chat_id: int = None) -> List[dict]:
        db = get_db()
        if chat_id:
            rows = db.execute(
                "SELECT * FROM deleted_msgs WHERE account_id=? AND chat_id=? ORDER BY ts DESC LIMIT 200",
                (acc_id, chat_id)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM deleted_msgs WHERE account_id=? ORDER BY ts DESC LIMIT 200",
                (acc_id,)
            ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def get_edit_history(self, acc_id: int, chat_id: int = None) -> List[dict]:
        db = get_db()
        if chat_id:
            rows = db.execute(
                "SELECT * FROM edit_history WHERE account_id=? AND chat_id=? ORDER BY date DESC LIMIT 200",
                (acc_id, chat_id)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM edit_history WHERE account_id=? ORDER BY date DESC LIMIT 200",
                (acc_id,)
            ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def get_shadow_log(self, acc_id: int = None, limit: int = 100) -> List[dict]:
        db = get_db()
        if acc_id:
            rows = db.execute(
                "SELECT * FROM shadow_log WHERE account_id=? ORDER BY ts DESC LIMIT ?",
                (acc_id, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM shadow_log ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    # ==================== MISC ====================
    async def resolve_entity(self, acc_id: int, username: str) -> dict:
        client = self.clients[acc_id]
        r = await client(ResolveUsernameRequest(username.replace("@", "")))
        if r.users:
            u = r.users[0]
            return {"type": "user", "id": u.id, "username": u.username}
        if r.chats:
            c = r.chats[0]
            return {"type": "chat", "id": c.id, "title": c.title}
        return {}

    async def check_username(self, acc_id: int, username: str) -> bool:
        client = self.clients[acc_id]
        try:
            await client(ResolveUsernameRequest(username))
            return False
        except UsernameNotOccupiedError:
            return True
        except Exception:
            return False

    async def get_sessions(self, acc_id: int) -> List[dict]:
        client = self.clients[acc_id]
        r = await client(GetAuthorizationsRequest())
        return [{
            "hash": a.hash, "device": a.device_model, "app": a.app_name,
            "country": a.country, "ip": a.ip, "current": a.current,
            "active": str(a.date_active)
        } for a in r.authorizations]

    async def kill_sessions(self, acc_id: int, keep_current: bool = True) -> int:
        client = self.clients[acc_id]
        r = await client(GetAuthorizationsRequest())
        killed = 0
        for a in r.authorizations:
            if keep_current and a.current:
                continue
            try:
                await client(ResetAuthorizationRequest(hash=a.hash))
                killed += 1
                await asyncio.sleep(0.3)
            except Exception:
                pass
        return killed

    async def mark_read(self, acc_id: int, chat_id: int = None):
        client = self.clients[acc_id]
        if chat_id:
            await client.send_read_acknowledge(chat_id)
        else:
            async for d in client.iter_dialogs():
                try:
                    await client.send_read_acknowledge(d.entity)
                    await asyncio.sleep(0.1)
                except Exception:
                    pass

    async def pin_chat(self, acc_id: int, chat_id: int, pin: bool = True):
        client = self.clients[acc_id]
        await client(functions.messages.ToggleDialogPinRequest(
            peer=await client.get_entity(chat_id), pinned=pin
        ))

    async def save_draft(self, acc_id: int, chat_id: int, text: str):
        client = self.clients[acc_id]
        entity = await client.get_entity(chat_id)
        await client(SaveDraftRequest(peer=entity, message=text))

    async def auto_forward_add(self, acc_id: int, src: int, dst: int,
                                keywords: str = "", strip_meta: bool = False):
        db = get_db()
        db.execute(
            "INSERT INTO auto_forward (account_id,src_chat,dst_chat,keywords,strip_meta) VALUES (?,?,?,?,?)",
            (acc_id, src, dst, keywords, int(strip_meta))
        )
        db.commit()
        db.close()

    async def shutdown(self):
        self._scheduler_running = False
        for t in self._tasks:
            t.cancel()
        for c in self.clients.values():
            await c.disconnect()