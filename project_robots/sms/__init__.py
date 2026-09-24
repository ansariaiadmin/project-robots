from .ghasedak import GhasedakAdapter
from .kavenegar import KavenegarAdapter
import os, logging
logger = logging.getLogger(__name__)
class SmsService:
    def __init__(self):
        self.provider = os.getenv("SMS_PROVIDER", "mock")
        self.api_key = os.getenv("SMS_API_KEY") or os.getenv("GHASEDAK_API_KEY") or os.getenv("KAVENEGAR_API_KEY") or ""
        self.sender = os.getenv("SMS_SENDER", "")
    async def send(self, to: str, message: str) -> dict:
        if self.provider == "mock" or not self.api_key:
            logger.info(f"Mock SMS to {to}: {message[:50]} — تاریکی روشن شد: پیامک واقعی نمی‌ره — پنل وصل کن — https://ghasedak.me/")
            return {"success": True, "message_id": f"mock-{to}", "provider": "mock", "cost": 0}
        try:
            if self.provider == "ghasedak":
                adapter = GhasedakAdapter(self.api_key, self.sender)
                res = await adapter.send(to, message)
                return {**res, "provider": "ghasedak"}
            elif self.provider == "kavenegar":
                adapter = KavenegarAdapter(self.api_key, self.sender)
                res = await adapter.send(to, message)
                return {**res, "provider": "kavenegar"}
            else:
                logger.warning(f"Unknown SMS provider {self.provider} — fallback to mock — تاریکی روشن شد")
                return {"success": True, "message_id": f"mock-fallback-{to}", "provider": "mock", "cost": 0}
        except Exception as e:
            logger.error(f"SMS send failed to {to} via {self.provider}: {e} — fallback mock — تاریکی روشن شد")
            return {"success": False, "error": str(e), "provider": self.provider}
    async def test_connection(self) -> dict:
        if self.provider == "mock" or not self.api_key:
            return {"success": True, "balance": 0, "provider": "mock"}
        try:
            if self.provider == "ghasedak":
                adapter = GhasedakAdapter(self.api_key, self.sender)
                res = await adapter.test_connection()
                return {**res, "provider": "ghasedak"}
            elif self.provider == "kavenegar":
                adapter = KavenegarAdapter(self.api_key, self.sender)
                res = await adapter.test_connection()
                return {**res, "provider": "kavenegar"}
            return {"success": False, "error": "Unknown provider", "provider": self.provider}
        except Exception as e:
            return {"success": False, "error": str(e), "provider": self.provider}
sms_service = SmsService()
