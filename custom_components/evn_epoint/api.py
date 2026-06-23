"""Client API EVN ePoint (bất đồng bộ, dùng aiohttp).

Reverse từ app chính chủ com.icom.epoint v1.18.12:
  - API thuần REST + Bearer token, KHÔNG ký HMAC.
  - password = sha256(plaintext)
  - key(login) = sha256(username + "+_=" + deviceKey + "/*" + workspaceCode)
  - public_key(sendOtp) = md5(owner_id + "|" + channel + "|" + time + "|" + OTP_MD5_PUBLIC_KEY)
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid

import aiohttp

from .const import (
    ACTION_LOGIN,
    APP_VERSION,
    BASE_URL,
    EP_BILLS,
    EP_BY_DATE,
    EP_BY_MONTH,
    EP_CHANNEL,
    EP_COMPARE_MONTH,
    EP_CONSUMPTION_INFO,
    EP_CONTRACTS,
    EP_LOGIN,
    EP_REFRESH,
    EP_SEND_OTP,
    EP_VERIFY_OTP,
    OS_MODEL,
    OTP_MD5_PUBLIC_KEY,
    WORKSPACE,
)

_LOGGER = logging.getLogger(__name__)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def new_device_key() -> str:
    """Sinh device_key cố định cho 'thiết bị' này."""
    return str(uuid.uuid4())


class EpointError(Exception):
    """Lỗi chung từ API ePoint."""


class EpointAuthError(EpointError):
    """Token hết hạn / cần đăng nhập lại."""


class EpointApi:
    """Bao bọc các lời gọi API ePoint."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        device_key: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._session = session
        self.username = username
        self.device_key = device_key
        self.access_token = access_token
        self.refresh_token = refresh_token

    # ---- low level -------------------------------------------------------

    def _headers(self, auth: bool = True) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "version": APP_VERSION,
            "operating-system": "Android",
            "model": OS_MODEL,
            "User-Agent": "okhttp/4.x",
        }
        if auth and self.access_token:
            h["Authorization"] = "Bearer " + self.access_token
        return h

    async def _request(
        self, method: str, path: str, *, auth: bool = True, json_body=None, params=None
    ):
        url = BASE_URL + path
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers(auth),
                json=json_body,
                params=params,
                timeout=aiohttp.ClientTimeout(total=40),
            ) as resp:
                status = resp.status
                try:
                    data = await resp.json(content_type=None)
                except Exception:  # noqa: BLE001
                    data = None
        except aiohttp.ClientError as err:
            raise EpointError(f"Lỗi mạng khi gọi {path}: {err}") from err

        if status in (401, 403):
            raise EpointAuthError(f"Phiên hết hạn ({status}) tại {path}")
        return status, data

    async def _get(self, path: str, params=None):
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json_body, *, auth: bool = True):
        return await self._request("POST", path, auth=auth, json_body=json_body)

    # ---- auth flow -------------------------------------------------------

    async def login_request(self, password: str, channel: str) -> dict:
        """Bước 1: gửi username + password (sha256). Thiết bị mới -> 202."""
        body = {
            "username": self.username,
            "password": _sha256(password),
            "deviceKey": self.device_key,
            "workspaceCode": WORKSPACE,
            "key": _sha256(f"{self.username}+_={self.device_key}/*{WORKSPACE}"),
            "model": OS_MODEL,
            "platform": "Android",
            "channelOTP": channel,
        }
        status, data = await self._post(EP_LOGIN, body, auth=False)
        return {"status": status, "data": data}

    async def channel_available(self) -> dict | None:
        _, data = await self._post(
            EP_CHANNEL, {"phone": self.username, "action": ACTION_LOGIN}, auth=False
        )
        return data

    async def send_otp(self, channel: str) -> dict:
        """Bước 2: gửi OTP qua kênh (SMS/ZALO)."""
        t = int(time.time())
        public_key = _md5(f"{self.username}|{channel}|{t}|{OTP_MD5_PUBLIC_KEY}")
        body = {
            "owner_id": self.username,
            "region_id": None,
            "action": ACTION_LOGIN,
            "public_key": public_key,
            "channel": channel,
            "time": t,
            "device_key": self.device_key,
            "lang": "vi",
        }
        status, data = await self._post(EP_SEND_OTP, body, auth=False)
        ok = status == 200 and isinstance(data, dict) and data.get("code") == 200
        return {"ok": ok, "status": status, "data": data}

    async def verify_otp(self, otp: str) -> bool:
        """Bước 3: xác thực OTP -> lấy access/refresh token."""
        body = {
            "owner_id": self.username,
            "otp": otp,
            "next_event_name": ACTION_LOGIN,
            "device_key": self.device_key,
        }
        _, data = await self._post(EP_VERIFY_OTP, body, auth=False)
        d = (data or {}).get("data") or {}
        inner = d.get("data") or {}
        access = d.get("accessToken") or inner.get("access_token")
        refresh = d.get("refreshToken") or inner.get("refresh_token")
        if not access:
            return False
        self.access_token = access
        self.refresh_token = refresh
        return True

    async def refresh(self) -> bool:
        """Gia hạn token bằng refresh_token."""
        if not self.refresh_token:
            return False
        body = {"refreshToken": self.refresh_token, "workspaceCode": WORKSPACE}
        try:
            _, data = await self._post(EP_REFRESH, body, auth=False)
        except EpointAuthError:
            return False
        d = (data or {}).get("data") or {}
        access = d.get("accessToken")
        if not access:
            return False
        self.access_token = access
        if d.get("refreshToken"):
            self.refresh_token = d["refreshToken"]
        return True

    # ---- data ------------------------------------------------------------

    async def get_contracts(self) -> list[dict]:
        _, data = await self._get(EP_CONTRACTS)
        return (data or {}).get("data") or []

    async def get_consumption_info(self) -> dict:
        _, data = await self._get(EP_CONSUMPTION_INFO)
        return (data or {}).get("data") or {}

    async def get_compare_month(self) -> dict:
        _, data = await self._get(EP_COMPARE_MONTH)
        return (data or {}).get("data") or {}

    async def get_by_month(self, customer_code: str) -> dict:
        _, data = await self._get(EP_BY_MONTH, params={"customer_code": customer_code})
        return (data or {}).get("data") or {}

    async def get_by_date(self, customer_code: str) -> list[dict]:
        _, data = await self._get(EP_BY_DATE, params={"customer_code": customer_code})
        return ((data or {}).get("data") or {}).get("electric_consumption_details") or []

    async def get_bills(self) -> list[dict]:
        _, data = await self._get(EP_BILLS)
        return (data or {}).get("data") or []
