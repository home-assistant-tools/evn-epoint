"""Coordinator: định kỳ lấy hợp đồng + tiêu thụ + hóa đơn từ ePoint."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EpointApi, EpointAuthError, EpointError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class EpointCoordinator(DataUpdateCoordinator[dict]):
    """Lấy dữ liệu điện cho mọi hợp đồng đã liên kết."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: EpointApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.api = api

    def _persist_tokens(self) -> None:
        """Lưu token mới (sau khi refresh) vào config entry."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                CONF_ACCESS_TOKEN: self.api.access_token,
                CONF_REFRESH_TOKEN: self.api.refresh_token,
            },
        )

    async def _fetch(self) -> dict:
        contracts = await self.api.get_contracts()
        primary_code = None
        for c in contracts:
            if c.get("primary_contract"):
                primary_code = c.get("customer_code") or c.get("ma_khang")
                break
        if primary_code is None and contracts:
            primary_code = contracts[0].get("customer_code") or contracts[0].get(
                "ma_khang"
            )

        # Hóa đơn: lấy 1 lần, đánh index theo mã khách hàng
        bills_by_code: dict[str, dict] = {}
        try:
            for b in await self.api.get_bills():
                code = b.get("customer_code") or b.get("ma_khang")
                if code:
                    bills_by_code[code] = b
        except EpointError as err:
            _LOGGER.warning("Không lấy được hóa đơn: %s", err)

        by_month: dict[str, dict] = {}
        by_date: dict[str, list] = {}
        for c in contracts:
            code = c.get("customer_code") or c.get("ma_khang")
            if not code:
                continue
            try:
                by_month[code] = await self.api.get_by_month(code)
            except EpointError as err:
                _LOGGER.warning("byMonth %s lỗi: %s", code, err)
            try:
                by_date[code] = await self.api.get_by_date(code)
            except EpointError as err:
                _LOGGER.warning("byDate %s lỗi: %s", code, err)

        info: dict = {}
        compare: dict = {}
        try:
            info = await self.api.get_consumption_info()
        except EpointError as err:
            _LOGGER.warning("consumption/info lỗi: %s", err)
        try:
            compare = await self.api.get_compare_month()
        except EpointError as err:
            _LOGGER.warning("compare-month lỗi: %s", err)

        return {
            "contracts": contracts,
            "primary_code": primary_code,
            "info": info,
            "compare": compare,
            "by_month": by_month,
            "by_date": by_date,
            "bills": bills_by_code,
        }

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch()
        except EpointAuthError:
            # Thử gia hạn token rồi lấy lại
            if await self.api.refresh():
                self._persist_tokens()
                try:
                    return await self._fetch()
                except EpointAuthError as err:
                    raise ConfigEntryAuthFailed(str(err)) from err
                except EpointError as err:
                    raise UpdateFailed(str(err)) from err
            raise ConfigEntryAuthFailed(
                "Phiên ePoint hết hạn, cần đăng nhập lại"
            )
        except EpointError as err:
            raise UpdateFailed(str(err)) from err
