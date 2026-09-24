from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
class NotificationChannel(str, Enum):
    IN_APP="in_app"; EMAIL="email"; SMS="sms"; TELEGRAM="telegram"
class NotificationKind(str, Enum):
    ANALYSIS="analysis"; PLAN="plan"; TEST="test"; SYSTEM="system"; ERROR="error"; INFO="info"
class NotificationPayload(BaseModel):
    user_id: Optional[str]=None; kind: NotificationKind; title: str; title_fa: str; body: str; body_fa: str
    channels: List[NotificationChannel]; metadata: Optional[Dict[str, Any]]=None; priority: str="medium"
class NotificationResult(BaseModel):
    channel: NotificationChannel; success: bool; message_id: Optional[str]=None; error: Optional[str]=None; at: str
