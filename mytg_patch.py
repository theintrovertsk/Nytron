# mytg_patch.py — Adds ALL extra methods to MyTG
# Import once: import mytg_patch
# All 80+ methods added: Pro client features, non-forwardable, bot token, extras

import asyncio
import json
import time
import random
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

from telethon import functions, types, events
from telethon.tl.functions.messages import (
    SendReactionRequest, SetTypingRequest, GetScheduledHistoryRequest,
    DeleteScheduledMessagesRequest, TranslateTextRequest,
    GetDialogFiltersRequest, UpdateDialogFiltersRequest,
    GetCommonChatsRequest, GetExportedChatInvitesRequest,
    DeleteExportedChatInviteRequest, MarkDialogUnreadRequest,
    InputDialogPeer, GetPeerDialogsRequest, ToggleDialogPinRequest,
)
from telethon.tl.functions.channels import (
    GetFullChannelRequest, ToggleSlowModeRequest,
    GetAdminLogRequest,
)
from telethon.tl.functions.contacts import (
    GetContactsRequest, DeleteContactsRequest, ImportContactsRequest,
    GetBlockedRequest,
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import (
    UpdateStatusRequest, GetAuthorizationsRequest,
    ResetAuthorizationRequest, GetPasswordRequest,
)
from telethon.tl.types import (
    InputPhoneContact, InputUser, ReactionEmoji,
    SendMessageTypingAction, SendMessageCancelAction,
    MessageMediaPhoto, MessageMediaDocument,
    InputStickerSetShortName, InputThemeSlug, InputChatThemeEmpty,
    InputWallPaperSlug, InputMediaPoll, Poll, PollAnswer,
    InputDialogPeer, DialogFilter, InputDialogPeer,
)
from telethon.errors import FloodWaitError, SlowModeWaitError


def apply_patch():
    from mytg_core import MyTG, get_db, MEDIA_DIR, EXPORT_DIR, StealthConfig

    # ─── Aliases ───
    async def clone_chat_messages(self, acc_id, src, dst, limit=500,
                                   delay=1.0, as_copy=True, keyword=None):
        return await self.clone_chat(acc_id, src, dst, limit=limit,
                                      delay=delay, as_copy=as_copy,
                                      filter_keyword=keyword)

    async def flood_protect_send(self, acc_id, chat_id, texts, delay=3.0):
        client = self.clients[acc_id]
        sent = 0
        for text in texts:
            try:
                await client.send_message(chat_id, text)
                sent += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)
            except Exception:
                pass
            await asyncio.sleep(delay + random.uniform(0.2, 0.8))
        return sent

    async def broadcast(self, acc_id, chat_ids, text, delay=3.0,
                         media_path=None, caption=None):
        client = self.clients[acc_id]
        if chat_ids == "_inline_":
            return 0
        sent = 0
        for cid in chat_ids:
            try:
                if media_path and Path(media_path).exists():
                    await client.send_file(cid, media_path, caption=caption or text)
                else:
                    await client.send_message(cid, text)
                sent += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)
            except Exception:
                pass
            await asyncio.sleep(delay + random.uniform(0.2, 1.0))
        return sent

    async def auto_react(self, acc_id, chat_id, emoji="❤️", watch=True):
        client = self.clients[acc_id]

        @client.on(events.NewMessage(chats=chat_id))
        async def handler(event):
            try:
                await client(SendReactionRequest(
                    peer=event.chat_id, msg_id=event.id,
                    reaction=[ReactionEmoji(emoticon=emoji)]
                ))
            except Exception:
                pass
        return True

    async def set_typing(self, acc_id, chat_id, seconds=5.0):
        client = self.clients[acc_id]
        entity = await client.get_entity(chat_id)
        await client(SetTypingRequest(entity, SendMessageTypingAction()))
        await asyncio.sleep(seconds)
        await client(SetTypingRequest(entity, SendMessageCancelAction()))

    async def get_chat_full_info(self, acc_id, chat) -> dict:
        client = self.clients[acc_id]
        entity = await client.get_entity(chat)
        info = {"id": entity.id, "title": getattr(entity, "title", None),
                "username": getattr(entity, "username", None),
                "type": type(entity).__name__}
        try:
            full = await client(GetFullChannelRequest(entity))
            info["about"] = full.full_chat.about
            info["participants_count"] = full.full_chat.participants_count
            info["online_count"] = full.full_chat.online_count
            info["pinned_msg_id"] = full.full_chat.pinned_msg_id
            info["slowmode_seconds"] = full.full_chat.slowmode_seconds
        except Exception:
            pass
        return info

    async def revoke_invite_link(self, acc_id, chat_id, link):
        client = self.clients[acc_id]
        entity = await client.get_entity(chat_id)
        try:
            r = await client(GetExportedChatInvitesRequest(
                peer=entity, admin_id=(await client.get_me()).id, limit=100
            ))
            for inv in r.invites:
                if inv.link == link:
                    await client(DeleteExportedChatInviteRequest(
                        peer=entity, link=link
                    ))
                    return True
        except Exception:
            pass
        return False

    async def set_slow_mode(self, acc_id, chat_id, seconds=0):
        client = self.clients[acc_id]
        entity = await client.get_entity(chat_id)
        await client(ToggleSlowModeRequest(channel=entity, seconds=seconds))

    async def delete_history_silent(self, acc_id, chat_id, revoke=True):
        client = self.clients[acc_id]
        await client.delete_dialog(chat_id, revoke=revoke)

    async def bulk_delete_my_messages(self, acc_id, chat_id, limit=0, keyword=None):
        return await self.bulk_delete_messages(acc_id, chat_id,
                                                 limit=limit, keyword=keyword)

    async def mark_all_read(self, acc_id, chat_id=None):
        return await self.mark_read(acc_id, chat_id)

    async def get_common_chats(self, acc_id, user_id) -> List[dict]:
        client = self.clients[acc_id]
        r = await client(GetCommonChatsRequest(
            user_id=await client.get_entity(user_id), max_id=0, limit=100
        ))
        return [{"id": c.id, "title": getattr(c, "title", None),
                 "username": getattr(c, "username", None)} for c in r.chats]

    async def search_messages(self, acc_id, query, chat_id=None, limit=50):
        return await self.search_local(acc_id, query, chat_id=chat_id, limit=limit)

    async def search_telegram(self, acc_id, query, chat=None, limit=50):
        if chat:
            client = self.clients[acc_id]
            results = []
            async for msg in client.iter_messages(chat, search=query, limit=limit):
                results.append({"id": msg.id, "chat": msg.chat_id,
                                "text": msg.text, "date": str(msg.date)})
            return results
        return await self.search_global(acc_id, query, limit=limit)

    async def resolve_username(self, acc_id, username) -> dict:
        return await self.resolve_entity(acc_id, username)

    async def check_username_available(self, acc_id, username) -> bool:
        return await self.check_username(acc_id, username)

    async def export_contacts(self, acc_id):
        client = self.clients[acc_id]
        r = await client(GetContactsRequest(hash=0))
        return [{"id": u.id, "username": u.username,
                 "first": u.first_name, "last": u.last_name,
                 "phone": getattr(u, "phone", None)} for u in r.users]

    async def import_contacts(self, acc_id, contacts):
        client = self.clients[acc_id]
        inputs = []
        for i, c in enumerate(contacts):
            inputs.append(InputPhoneContact(
                client_id=i, phone=c.get("phone", ""),
                first_name=c.get("first", ""), last_name=c.get("last", "")
            ))
        await client(ImportContactsRequest(inputs))

    async def delete_all_contacts(self, acc_id):
        client = self.clients[acc_id]
        r = await client(GetContactsRequest(hash=0))
        if r.users:
            await client(DeleteContactsRequest(
                [InputUser(u.id, u.access_hash) for u in r.users]
            ))

    async def list_active_sessions(self, acc_id):
        return await self.get_sessions(acc_id)

    async def session_export(self, acc_id):
        return await self.export_session(acc_id)

    async def save_broadcast_list(self, acc_id, name, chat_ids):
        db = get_db()
        db.execute(
            "INSERT INTO broadcast_lists (account_id,name,chat_ids,created) VALUES (?,?,?,?)",
            (acc_id, name, json.dumps(chat_ids), time.time())
        )
        db.commit()
        db.close()

    # ─── Bot token ───
    async def add_bot_account(self, name, token):
        return await self.login_bot(name, token)

    async def add_user_account(self, name, phone):
        return await self.login_phone(name, phone)

    async def import_session(self, name, sess):
        return await self.login_session(name, sess)

    async def quick_bot_login(self, token, name=None):
        name = name or f"bot_{int(time.time())}"
        return await self.login_bot(name, token)

    # ─── Pro: Anti-recall ───
    async def anti_recall_enable(self, acc_id):
        client = self.clients[acc_id]

        @client.on(events.MessageDeleted)
        async def on_delete(event):
            for mid in event.deleted_ids:
                try:
                    msg = None
                    try:
                        msg = await client.get_messages(event.chat_id, ids=mid)
                    except Exception:
                        pass
                    data = {"id": mid, "chat": event.chat_id}
                    if msg:
                        data.update({"text": msg.text or "",
                                     "sender": msg.sender_id,
                                     "date": str(msg.date),
                                     "media": bool(msg.media)})
                        if msg.media:
                            try:
                                p = await client.download_media(
                                    msg, file=str(MEDIA_DIR / f"recall_{acc_id}_{mid}"))
                                if p:
                                    data["local_media"] = p
                            except Exception:
                                pass
                    db = get_db()
                    db.execute(
                        "INSERT OR REPLACE INTO deleted_msgs "
                        "(id,chat_id,account_id,data,ts) VALUES (?,?,?,?,?)",
                        (mid, event.chat_id or 0, acc_id, json.dumps(data), time.time())
                    )
                    db.commit()
                    db.close()
                except Exception:
                    pass
        return True

    async def recall_history(self, acc_id, chat_id=None, limit=100):
        db = get_db()
        if chat_id:
            rows = db.execute(
                "SELECT * FROM deleted_msgs WHERE account_id=? AND chat_id=? "
                "ORDER BY ts DESC LIMIT ?", (acc_id, chat_id, limit)).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM deleted_msgs WHERE account_id=? "
                "ORDER BY ts DESC LIMIT ?", (acc_id, limit)).fetchall()
        db.close()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["data"] = json.loads(d["data"])
            except Exception:
                pass
            out.append(d)
        return out

    # ─── Ghost ───
    async def ghost_mode(self, acc_id, enable: bool):
        self.stealth[acc_id].ghost = enable
        self.stealth[acc_id].no_read = enable
        self.stealth[acc_id].no_typing = enable
        client = self.clients[acc_id]
        await client(UpdateStatusRequest(offline=enable))

    async def ghost_granular(self, acc_id, online=None, read=None, typing=None):
        cfg = self.stealth[acc_id]
        if online is not None:
            cfg.ghost = not online
            await self.clients[acc_id](UpdateStatusRequest(offline=not online))
        if read is not None:
            cfg.no_read = not read
        if typing is not None:
            cfg.no_typing = not typing

    # ─── History ───
    async def message_history_search(self, acc_id, query, chat_id=None, limit=100):
        db = get_db()
        if chat_id:
            rows = db.execute(
                "SELECT * FROM message_index WHERE account_id=? AND chat_id=? "
                "AND text LIKE ? ORDER BY date DESC LIMIT ?",
                (acc_id, chat_id, f"%{query}%", limit)).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM message_index WHERE account_id=? "
                "AND text LIKE ? ORDER BY date DESC LIMIT ?",
                (acc_id, f"%{query}%", limit)).fetchall()
        db.close()
        return [dict(r) for r in rows]

    async def history_export(self, acc_id, chat_id, limit=1000):
        client = self.clients[acc_id]
        msgs = []
        async for msg in client.iter_messages(chat_id, limit=limit):
            msgs.append({"id": msg.id, "date": str(msg.date),
                         "sender": msg.sender_id, "text": msg.text,
                         "media": type(msg.media).__name__ if msg.media else None})
        fname = str(EXPORT_DIR / f"history_{acc_id}_{chat_id}_{int(time.time())}.json")
        with open(fname, "w") as f:
            json.dump(msgs, f, indent=2)
        return fname, len(msgs)

    # ─── Local premium ───
    async def local_premium_enable(self, acc_id, enable: bool = True):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"premium_{acc_id}", "1" if enable else "0", time.time()))
        db.commit()
        db.close()

    def local_premium_status(self, acc_id) -> bool:
        db = get_db()
        row = db.execute(
            "SELECT content FROM snippets WHERE name=?", (f"premium_{acc_id}",)).fetchone()
        db.close()
        return row is not None and row["content"] == "1"

    async def local_premium_emoji_status(self, acc_id, emoji):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"emoji_status_{acc_id}", emoji, time.time()))
        db.commit()
        db.close()

    async def local_premium_reaction(self, acc_id, chat_id, msg_id,
                                      emoji="⭐", premium_only=False):
        client = self.clients[acc_id]
        try:
            await client(SendReactionRequest(
                peer=await client.get_entity(chat_id), msg_id=msg_id,
                reaction=[ReactionEmoji(emoticon=emoji)], big=premium_only))
            return True
        except Exception:
            return False

    # ─── Streamer ───
    async def streamer_mode(self, acc_id, enable: bool):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"streamer_{acc_id}", "1" if enable else "0", time.time()))
        db.commit()
        db.close()

    def streamer_status(self, acc_id) -> bool:
        db = get_db()
        row = db.execute(
            "SELECT content FROM snippets WHERE name=?", (f"streamer_{acc_id}",)).fetchone()
        db.close()
        return row is not None and row["content"] == "1"

    # ─── Translator ───
    async def translator(self, acc_id, chat_id, msg_id, to_lang="en"):
        client = self.clients[acc_id]
        try:
            result = await client(TranslateTextRequest(
                peer=await client.get_entity(chat_id),
                id=[msg_id], to_lang=to_lang))
            if result.result:
                return result.result[0].text
        except Exception:
            pass
        return None

    # ─── Filters ───
    async def message_filter_add(self, acc_id, chat_id, keyword, action="hide"):
        db = get_db()
        db.execute(
            "INSERT INTO notif_rules (account_id, chat_id, keyword, action, enabled) "
            "VALUES (?,?,?,?,1)", (acc_id, chat_id, keyword, action))
        db.commit()
        db.close()

    def message_filter_list(self, acc_id) -> List[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM notif_rules WHERE account_id=? AND enabled=1",
            (acc_id,)).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def message_filter_delete(self, acc_id, filter_id: int):
        db = get_db()
        db.execute("DELETE FROM notif_rules WHERE id=? AND account_id=?",
                   (filter_id, acc_id))
        db.commit()
        db.close()

    # ─── Disable similar channels ───
    async def disable_similar_channels(self, acc_id, enable: bool = True):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"no_similar_{acc_id}", "1" if enable else "0", time.time()))
        db.commit()
        db.close()

    # ─── Hide notification counters ───
    async def hide_notification_counters(self, acc_id, enable: bool = True):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"hide_notif_{acc_id}", "1" if enable else "0", time.time()))
        db.commit()
        db.close()

    # ─── Message Shot ───
    async def message_shot(self, acc_id, chat_id, msg_id, out_path=None):
        client = self.clients[acc_id]
        msg = await client.get_messages(chat_id, ids=msg_id)
        if not msg:
            return None
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (600, 200), "#1a1a1a")
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except Exception:
                font = ImageFont.load_default()
            sender = await client.get_entity(msg.sender_id) if msg.sender_id else None
            sender_name = sender.first_name if sender else "Unknown"
            draw.text((20, 20), sender_name, fill="#ffffff", font=font)
            draw.text((20, 50), msg.text or "[media]", fill="#dddddd", font=font)
            out_path = out_path or str(MEDIA_DIR / f"shot_{acc_id}_{chat_id}_{msg_id}.png")
            img.save(out_path)
            return out_path
        except ImportError:
            out_path = out_path or str(MEDIA_DIR / f"shot_{acc_id}_{chat_id}_{msg_id}.txt")
            with open(out_path, "w") as f:
                f.write(f"Sender: {msg.sender_id}\nDate: {msg.date}\n\n{msg.text or '[media]'}")
            return out_path

    # ─── Voice transcription ───
    async def transcribe_voice(self, acc_id, chat_id, msg_id):
        client = self.clients[acc_id]
        try:
            msg = await client.get_messages(chat_id, ids=msg_id)
            if not msg or not msg.voice:
                return None
            path = await client.download_media(
                msg, file=str(MEDIA_DIR / f"voice_{msg_id}.ogg"))
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.AudioFile(path) as source:
                    audio = r.record(source)
                return r.recognize_google(audio)
            except ImportError:
                return f"[voice saved: {path}]"
            except Exception as e:
                return f"[failed: {e}]"
        except Exception:
            return None

    # ─── Sticker management ───
    async def sticker_set_info(self, acc_id, short_name):
        client = self.clients[acc_id]
        try:
            from telethon.tl.functions.messages import GetStickerSetRequest
            return await client(GetStickerSetRequest(
                stickerset=InputStickerSetShortName(short_name=short_name), hash=0))
        except Exception:
            return None

    # ─── Confirmations ───
    async def confirm_before_delete(self, acc_id, enable: bool = True):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"confirm_{acc_id}", "1" if enable else "0", time.time()))
        db.commit()
        db.close()

    def should_confirm(self, acc_id) -> bool:
        db = get_db()
        row = db.execute(
            "SELECT content FROM snippets WHERE name=?", (f"confirm_{acc_id}",)).fetchone()
        db.close()
        return row is None or row["content"] == "1"

    # ─── Auto-download ───
    async def set_auto_download(self, acc_id, enable: bool, media_types=None):
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO snippets (name, content, created) VALUES (?,?,?)",
            (f"autodl_{acc_id}", json.dumps({
                "enabled": enable,
                "types": media_types or ["photo", "video", "document"]
            }), time.time()))
        db.commit()
        db.close()

    # ─── NON-FORWARDABLE FORWARDING ───
    async def forward_non_forwardable(self, acc_id, src_chat, dst_chat,
                                       msg_ids: List[int] = None,
                                       limit: int = 100, delay: float = 1.5):
        client = self.clients[acc_id]
        forwarded = 0
        errors = 0

        if msg_ids:
            msgs = await client.get_messages(src_chat, ids=msg_ids)
        else:
            msgs = await client.get_messages(src_chat, limit=limit)

        for msg in (msgs if isinstance(msgs, list) else [msgs]):
            if not msg:
                continue
            try:
                if msg.media:
                    temp_path = await client.download_media(
                        msg, file=str(MEDIA_DIR / f"nfwd_{acc_id}_{msg.id}"))
                    if temp_path:
                        caption = msg.text or ""
                        await client.send_file(dst_chat, temp_path,
                                                caption=caption, force_document=False)
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                        forwarded += 1
                elif msg.text:
                    await client.send_message(dst_chat, msg.text)
                    forwarded += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)
                errors += 1
            except Exception as e:
                print(f"[nfwd] msg {msg.id}: {e}")
                errors += 1
            await asyncio.sleep(delay + random.uniform(0.2, 0.8))

        self._log(acc_id, "non_forwardable", f"{src_chat}->{dst_chat}",
                  f"fwd={forwarded} err={errors}")
        return {"forwarded": forwarded, "errors": errors}

    async def clone_non_forwardable_chat(self, acc_id, src_chat, dst_chat,
                                          limit: int = 500, delay: float = 2.0):
        return await self.forward_non_forwardable(
            acc_id, src_chat, dst_chat, msg_ids=None, limit=limit, delay=delay)

    # ─── Poll ───
    async def poll_create(self, acc_id, chat_id, question, options: List[str],
                           anonymous=True, multiple_choice=False, quiz=False,
                           correct_option: int = None):
        client = self.clients[acc_id]
        answers = [PollAnswer(text=opt, option=bytes([i]))
                   for i, opt in enumerate(options)]
        poll = Poll(
            id=random.randint(1, 2**31), question=question,
            answers=answers, public_voters=not anonymous,
            multiple_choice=multiple_choice, quiz=quiz,
            close_period=None, close_date=None)
        if quiz and correct_option is not None:
            poll.quiz = True
            poll.correct_answers = [answers[correct_option].option]
        from telethon.tl.functions.messages import SendMediaRequest
        await client(SendMediaRequest(
            peer=await client.get_entity(chat_id),
            media=InputMediaPoll(poll=poll),
            random_id=random.randint(1, 2**63)))
        return True

    # ─── Stories ───
    async def story_download(self, acc_id, user_id, limit: int = 5) -> List[str]:
        client = self.clients[acc_id]
        paths = []
        try:
            from telethon.tl.functions.stories import GetPeerStoriesRequest
            r = await client(GetPeerStoriesRequest(
                peer=await client.get_entity(user_id)))
            for story in r.stories.stories[:limit]:
                if hasattr(story, "media"):
                    try:
                        p = await client.download_media(
                            story.media,
                            file=str(MEDIA_DIR / f"story_{acc_id}_{user_id}_{story.id}"))
                        if p:
                            paths.append(p)
                    except Exception:
                        pass
        except Exception:
            pass
        return paths

    # ─── Auto-reply ───
    async def auto_reply_setup(self, acc_id, keyword, reply_text, chat_id=None):
        client = self.clients[acc_id]

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if chat_id and event.chat_id != chat_id:
                return
            if keyword.lower() in (event.raw_text or "").lower():
                try:
                    await event.reply(reply_text)
                except Exception:
                    pass
        return True

    # ─── Bulk download ───
    async def bulk_download_media(self, acc_id, chat_id, media_type="all",
                                   limit=100, out_dir=None) -> List[str]:
        client = self.clients[acc_id]
        if out_dir is None:
            out_dir = MEDIA_DIR / f"bulk_{acc_id}_{chat_id}"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
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
                    msg, file=str(Path(out_dir) / f"{msg.id}"))
                if p:
                    paths.append(p)
                    await asyncio.sleep(0.3)
            except Exception:
                pass
        return paths

    # ─── Extras ───
    async def auto_join_by_keyword(self, acc_id, keyword, limit=10):
        from telethon.tl.functions.contacts import SearchRequest
        from telethon.tl.functions.channels import JoinChannelRequest
        client = self.clients[acc_id]
        joined = 0
        try:
            results = await client(SearchRequest(q=keyword, limit=limit))
            for chat in results.chats:
                try:
                    await client(JoinChannelRequest(chat))
                    joined += 1
                    await asyncio.sleep(random.uniform(3, 7))
                except Exception:
                    pass
        except Exception:
            pass
        return joined

    async def mass_unread(self, acc_id, limit=50):
        client = self.clients[acc_id]
        count = 0
        async for d in client.iter_dialogs(limit=limit):
            try:
                await client(MarkDialogUnreadRequest(
                    peer=InputDialogPeer(peer=d.entity), unread=True))
                count += 1
            except Exception:
                pass
        return count

    async def send_silent(self, acc_id, chat_id, text, schedule_secs=0):
        client = self.clients[acc_id]
        kwargs = {"silent": True}
        if schedule_secs:
            kwargs["schedule"] = datetime.now(timezone.utc) + timedelta(seconds=schedule_secs)
        await client.send_message(chat_id, text, **kwargs)

    async def chat_folder_create(self, acc_id, name, chat_ids, emoticon=None):
        client = self.clients[acc_id]
        try:
            r = await client(GetDialogFiltersRequest())
            folders = list(r.filters) if r.filters else []
            new_filter = DialogFilter(
                id=len(folders) + 2, title=name,
                pinned_peers=[InputDialogPeer(peer=await client.get_entity(cid))
                              for cid in chat_ids],
                include_peers=[], exclude_peers=[], emoticon=emoticon)
            folders.append(new_filter)
            await client(UpdateDialogFiltersRequest(filters=folders))
            return True
        except Exception as e:
            print(f"[folder] {e}")
            return False

    async def scheduled_cleanup(self, acc_id):
        client = self.clients[acc_id]
        try:
            r = await client(GetScheduledHistoryRequest(
                peer=await client.get_entity("me"), hash=0))
            ids = [m.id for m in r.messages]
            if ids:
                await client(DeleteScheduledMessagesRequest(
                    peer=await client.get_entity("me"), id=ids))
                return len(ids)
        except Exception:
            pass
        return 0

    async def emergency_logout_all(self, acc_id):
        client = self.clients[acc_id]
        r = await client(GetAuthorizationsRequest())
        killed = 0
        for a in r.authorizations:
            if not a.current:
                try:
                    await client(ResetAuthorizationRequest(hash=a.hash))
                    killed += 1
                except Exception:
                    pass
        return killed

    async def account_health_check(self, acc_id):
        client = self.clients[acc_id]
        health = {"account_id": acc_id, "valid": False}
        try:
            me = await client.get_me()
            health["valid"] = True
            health["username"] = me.username
            health["name"] = me.first_name
            health["premium"] = getattr(me, "premium", False)
        except Exception as e:
            health["error"] = str(e)
        return health

    async def account_stats(self, acc_id):
        client = self.clients[acc_id]
        stats = {}
        try:
            me = await client.get_me()
            stats["username"] = me.username
            stats["id"] = me.id
            stats["premium"] = getattr(me, "premium", False)
            dialogs = []
            async for d in client.iter_dialogs():
                dialogs.append(d)
            stats["total_dialogs"] = len(dialogs)
            stats["unread_dialogs"] = sum(1 for d in dialogs if d.unread_count > 0)
            stats["groups"] = sum(1 for d in dialogs if d.is_group)
            stats["channels"] = sum(1 for d in dialogs if d.is_channel)
            stats["users"] = sum(1 for d in dialogs if d.is_user)
        except Exception:
            pass
        return stats

    async def edit_message(self, acc_id, chat_id, msg_id, new_text):
        client = self.clients[acc_id]
        try:
            await client.edit_message(chat_id, msg_id, new_text)
            return True
        except Exception:
            return False

    async def forward_message(self, acc_id, src_chat, msg_ids, dst_chat):
        client = self.clients[acc_id]
        try:
            await client.forward_messages(dst_chat, msg_ids, from_peer=src_chat)
            return True
        except Exception:
            return False

    async def pin_message(self, acc_id, chat_id, msg_id, notify=False):
        client = self.clients[acc_id]
        try:
            await client.pin_message(chat_id, msg_id, notify=notify)
            return True
        except Exception:
            return False

    async def unpin_all_messages(self, acc_id, chat_id):
        from telethon.tl.functions.messages import UnpinAllMessagesRequest
        client = self.clients[acc_id]
        try:
            await client(UnpinAllMessagesRequest(
                peer=await client.get_entity(chat_id)))
            return True
        except Exception:
            return False

    async def delete_message(self, acc_id, chat_id, msg_ids, revoke=True):
        client = self.clients[acc_id]
        try:
            await client.delete_messages(chat_id, msg_ids, revoke=revoke)
            return True
        except Exception:
            return False

    async def message_reactions_list(self, acc_id, chat_id, msg_id):
        from telethon.tl.functions.messages import GetMessageReactionsListRequest
        client = self.clients[acc_id]
        try:
            r = await client(GetMessageReactionsListRequest(
                peer=await client.get_entity(chat_id), id=msg_id, limit=100))
            out = []
            for rxn in r.reactions:
                out.append({
                    "user": rxn.peer_id,
                    "reaction": getattr(rxn.reaction, "emoticon", "?"),
                    "date": str(rxn.date)})
            return out
        except Exception:
            return []

    async def group_members_filtered(self, acc_id, chat_id, filter_type="all",
                                      limit=200):
        from telethon.tl.types import (
            ChannelParticipantsRecent, ChannelParticipantsAdmins,
            ChannelParticipantsBanned)
        client = self.clients[acc_id]
        filter_map = {
            "all": ChannelParticipantsRecent(),
            "admins": ChannelParticipantsAdmins(),
            "banned": ChannelParticipantsBanned(q=""),
            "recent": ChannelParticipantsRecent(),
        }
        filt = filter_map.get(filter_type, ChannelParticipantsRecent())
        members = []
        try:
            async for u in client.iter_participants(chat_id, filter=filt, limit=limit):
                members.append({
                    "id": u.id, "username": u.username,
                    "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                    "bot": u.bot,
                    "premium": getattr(u, "premium", False)})
        except Exception:
            pass
        return members

    async def group_admin_log(self, acc_id, chat_id, limit=100):
        client = self.clients[acc_id]
        try:
            entity = await client.get_entity(chat_id)
            r = await client(GetAdminLogRequest(
                channel=entity, q="", min_id=0, max_id=0,
                limit=limit, events_filter=None, admins=None))
            out = []
            for e in r.events:
                out.append({
                    "id": e.id, "date": str(datetime.fromtimestamp(e.date)),
                    "user_id": e.user_id,
                    "action": type(e.action).__name__})
            return out
        except Exception:
            return []

    async def check_2fa_enabled(self, acc_id):
        client = self.clients[acc_id]
        try:
            r = await client(GetPasswordRequest())
            return {"has_password": r.has_password, "hint": r.hint}
        except Exception:
            return {}

    async def story_view_stealth(self, acc_id, user_id):
        from telethon.tl.functions.stories import ActivateStealthModeRequest
        client = self.clients[acc_id]
        try:
            await client(ActivateStealthModeRequest())
            return await self.view_stories(acc_id, user_id)
        except Exception:
            return 0

    # ─── Apply all ───
    methods = [
        clone_chat_messages, flood_protect_send, broadcast, auto_react,
        set_typing, get_chat_full_info, revoke_invite_link, set_slow_mode,
        delete_history_silent, bulk_delete_my_messages, mark_all_read,
        get_common_chats, search_messages, search_telegram,
        resolve_username, check_username_available,
        export_contacts, import_contacts, delete_all_contacts,
        list_active_sessions, session_export, save_broadcast_list,
        add_bot_account, add_user_account, import_session, quick_bot_login,
        anti_recall_enable, recall_history,
        ghost_mode, ghost_granular,
        message_history_search, history_export,
        local_premium_enable, local_premium_status,
        local_premium_emoji_status, local_premium_reaction,
        streamer_mode, streamer_status,
        translator,
        message_filter_add, message_filter_list, message_filter_delete,
        disable_similar_channels, hide_notification_counters,
        message_shot, transcribe_voice, sticker_set_info,
        confirm_before_delete, should_confirm, set_auto_download,
        forward_non_forwardable, clone_non_forwardable_chat,
        poll_create, story_download, auto_reply_setup, bulk_download_media,
        auto_join_by_keyword, mass_unread, send_silent,
        chat_folder_create, scheduled_cleanup, emergency_logout_all,
        account_health_check, account_stats,
        edit_message, forward_message, pin_message,
        unpin_all_messages, delete_message, message_reactions_list,
        group_members_filtered, group_admin_log, check_2fa_enabled,
        story_view_stealth,
    ]

    for m in methods:
        setattr(MyTG, m.__name__, m)

    print(f"[+] Patched MyTG with {len(methods)} methods")
    return True


if __name__ != "__main__":
    try:
        apply_patch()
    except Exception as e:
        print(f"[!] Patch failed: {e}")

    async def privacy_preset(self, acc_id, preset="ghost"):
        if preset == "ghost":
            await self.ghost_mode(acc_id, True)
            return "ghost on"
        await self.ghost_mode(acc_id, False)
        return "ghost off"

    async def set_ghost_mode(self, acc_id, enable=True):
        return await self.ghost_mode(acc_id, enable)

    MyTG.privacy_preset = privacy_preset
    MyTG.set_ghost_mode = set_ghost_mode
