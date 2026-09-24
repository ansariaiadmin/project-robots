import os, logging
from datetime import datetime, timezone
from typing import List, Dict
import httpx
from .types import NotificationPayload, NotificationResult, NotificationChannel
logger = logging.getLogger(__name__)
inbox: Dict[str, List[NotificationPayload]] = {}
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
                    uid=payload.user_id or "system"; lst=inbox.get(uid,[]); lst.append(payload)
                    if len(lst)>50: lst=lst[-50:]; inbox[uid]=lst
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
notification_service = NotificationService()
