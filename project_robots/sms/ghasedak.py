import httpx, logging
logger = logging.getLogger(__name__)
class GhasedakAdapter:
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key; self.sender = sender; self.base_url = "https://api.ghasedak.me/v2"
    async def send(self, to: str, message: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(f"{self.base_url}/sms/send/simple", headers={"apikey": self.api_key, "Content-Type": "application/x-www-form-urlencoded"}, data={"receptor": to, "sender": self.sender, "message": message})
                data = res.json()
                if res.status_code != 200 or data.get("result", {}).get("code") != 200:
                    err = data.get("result", {}).get("message", f"HTTP {res.status_code}"); logger.error(f"Ghasedak failed to {to}: {err}"); return {"success": False, "error": err}
                logger.info(f"Ghasedak SMS sent to {to}"); return {"success": True, "message_id": str(data.get("result", {}).get("items", [0])[0] or ""), "cost": 120}
        except Exception as e:
            logger.error(f"Ghasedak exception to {to}: {e}"); return {"success": False, "error": str(e)}
    async def get_balance(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get(f"{self.base_url}/account/info", headers={"apikey": self.api_key}); data = res.json()
                if res.status_code != 200: return {"success": False, "error": f"HTTP {res.status_code}"}
                return {"success": True, "balance": data.get("result", {}).get("balance", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    async def test_connection(self) -> dict:
        return await self.get_balance()
