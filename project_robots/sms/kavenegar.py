import httpx, logging
logger = logging.getLogger(__name__)
class KavenegarAdapter:
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key; self.sender = sender
    async def send(self, to: str, message: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(f"https://api.kavenegar.com/v1/{self.api_key}/sms/send.json", data={"receptor": to, "sender": self.sender, "message": message})
                data = res.json()
                if res.status_code != 200 or data.get("return", {}).get("status") != 200:
                    err = data.get("return", {}).get("message", f"HTTP {res.status_code}"); logger.error(f"Kavenegar failed to {to}: {err}"); return {"success": False, "error": err}
                logger.info(f"Kavenegar SMS sent to {to}"); return {"success": True, "message_id": str(data.get("entries", [{}])[0].get("messageid", "")), "cost": 110}
        except Exception as e:
            logger.error(f"Kavenegar exception to {to}: {e}"); return {"success": False, "error": str(e)}
    async def get_balance(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get(f"https://api.kavenegar.com/v1/{self.api_key}/account/info.json"); data = res.json()
                if res.status_code != 200: return {"success": False, "error": f"HTTP {res.status_code}"}
                return {"success": True, "balance": data.get("entries", {}).get("remaincredit", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    async def test_connection(self) -> dict:
        return await self.get_balance()
