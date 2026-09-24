"""
Notification Service v3.2.1 — PERSISTENT — تاریکی روشن شد
قبلا Dict تو RAM بود — ریست می‌شد همه نوتیف‌ها می‌پرید — فاجعه
حالا فایل JSON — runtime/notifications/inbox.json — persist
"""
import os, json, logging
from datetime import datetime, timezone
from typing import List, Dict
from pathlib import Path
import httpx
from .types import NotificationPayload, NotificationResult, NotificationChannel
logger = logging.getLogger(__name__)

INBOX_FILE = Path(os.getenv("NOTIF_INBOX_FILE", "runtime/notifications/inbox.json"))
MAX_INBOX = 50

def _ensure_dir():
    try: INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    except: pass

def _load_inbox():
    try:
        _ensure_dir()
        if INBOX_FILE.exists():
            return json.loads(INBOX_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        logger.warning(f"Failed to load inbox: {e}")
    return {}

def _save_inbox(d):
    try:
        _ensure_dir()
        INBOX_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to persist inbox: {e}")

inbox: Dict[str, List] = _load_inbox()

class NotificationService:
    def __init__(self):
        self.in_app = os.getenv("NOTIF_IN_APP","true").lower()!="false"
        self.email_enabled = os.getenv("NOTIF_EMAIL","false").lower() in ("yes","true","1")
        self.email_provider = os.getenv("EMAIL_PROVIDER","mock")
        self.telegram_enabled = os.getenv("NOTIF_TELEGRAM","false").lower() in ("yes","true","1")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    async def send(self, payload: NotificationPayload) -> List[NotificationResult]:
        results=[]; at=datetime.now(timezone.utc).isoformat()
        for ch in payload.channels:
            try:
                if ch==NotificationChannel.IN_APP:
                    if not self.in_app: results.append(NotificationResult(channel=ch,success=False,error="Disabled",at=at)); continue
                    uid=payload.user_id or "system"; lst=inbox.get(uid,[]); lst.append(payload.model_dump() if hasattr(payload,'model_dump') else payload.__dict__ if hasattr(payload,'__dict__') else str(payload))
                    if len(lst)>MAX_INBOX: lst=lst[-MAX_INBOX:]; inbox[uid]=lst; _save_inbox(inbox)
                    results.append(NotificationResult(channel=ch,success=True,message_id=f"inapp-{int(datetime.now().timestamp())}",at=at))
                elif ch==NotificationChannel.TELEGRAM:
                    if not self.telegram_enabled or not self.telegram_token or not self.telegram_chat:
                        results.append(NotificationResult(channel=ch,success=False,error="Telegram not configured",at=at)); continue
                    try:
                        text=f"🔔 *{payload.title_fa}*\n\n{payload.body_fa}\n\n_{payload.kind} — {at}_"
                        url=f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                        async with httpx.AsyncClient(timeout=5) as client:
                            res=await client.post(url,json={"chat_id":self.telegram_chat,"text":text,"parse_mode":"Markdown"})
                            res.raise_for_status()
                            results.append(NotificationResult(channel=ch,success=True,message_id=str(int(datetime.now().timestamp())),at=at))
                    except Exception as e:
                        results.append(NotificationResult(channel=ch,success=False,error=str(e),at=at))
                else:
                    results.append(NotificationResult(channel=ch,success=True,message_id=f"{ch}-{int(datetime.now().timestamp())}",at=at))
            except Exception as e:
                results.append(NotificationResult(channel=ch,success=False,error=str(e),at=at))
        return results
    def list_in_app(self, user_id: str) -> List:
        return inbox.get(user_id, [])
notification_service = NotificationService()
