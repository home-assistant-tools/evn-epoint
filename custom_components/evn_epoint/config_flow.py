"""Luồng cấu hình: đăng nhập SĐT + mật khẩu, rồi nhập OTP."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EpointApi, EpointError, new_device_key
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_KEY,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_USERNAME,
    DEFAULT_CHANNEL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_OTP = vol.Schema({vol.Required("otp"): str})


class EpointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Cấu hình tích hợp EVN ePoint."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            session = async_get_clientsession(self.hass)
            device_key = new_device_key()
            api = EpointApi(session, username, device_key)
            try:
                res = await api.login_request(password, DEFAULT_CHANNEL)
                data = res.get("data") or {}
                err_code = data.get("error_code")
                # Đăng nhập thẳng được (thiết bị đã tin cậy)
                inner = (data.get("data") or {}) if isinstance(data, dict) else {}
                if (data.get("data") or {}).get("accessToken") or inner.get(
                    "access_token"
                ):
                    return await self._finish(
                        username,
                        device_key,
                        (data.get("data") or {}).get("accessToken")
                        or inner.get("access_token"),
                        (data.get("data") or {}).get("refreshToken")
                        or inner.get("refresh_token"),
                    )
                if err_code == "ERR_LOGIN_PASSWORD_INVALID":
                    errors["base"] = "invalid_auth"
                else:
                    # Thiết bị mới -> chọn kênh + gửi OTP
                    await api.channel_available()
                    otp_res = await api.send_otp(DEFAULT_CHANNEL)
                    if not otp_res["ok"]:
                        errors["base"] = "otp_send_failed"
                    else:
                        self._data = {
                            CONF_USERNAME: username,
                            CONF_DEVICE_KEY: device_key,
                        }
                        return await self.async_step_otp()
            except EpointError as err:
                _LOGGER.error("Lỗi đăng nhập ePoint: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = EpointApi(
                session, self._data[CONF_USERNAME], self._data[CONF_DEVICE_KEY]
            )
            try:
                if await api.verify_otp(user_input["otp"].strip()):
                    return await self._finish(
                        api.username,
                        api.device_key,
                        api.access_token,
                        api.refresh_token,
                    )
                errors["base"] = "invalid_otp"
            except EpointError as err:
                _LOGGER.error("Lỗi xác thực OTP: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="otp", data_schema=STEP_OTP, errors=errors
        )

    async def _finish(
        self, username: str, device_key: str, access: str, refresh: str | None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(username)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"EVN ePoint {username}",
            data={
                CONF_USERNAME: username,
                CONF_DEVICE_KEY: device_key,
                CONF_ACCESS_TOKEN: access,
                CONF_REFRESH_TOKEN: refresh,
            },
        )
