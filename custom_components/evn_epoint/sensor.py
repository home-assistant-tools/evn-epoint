"""Cảm biến EVN ePoint: tiêu thụ hôm nay / tháng này (tạm tính) / tiền điện / lịch sử."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EpointCoordinator


def _to_float(v: Any) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _is_primary(data: dict, code: str) -> bool:
    return data.get("primary_code") == code


def _today_kwh(data: dict, code: str) -> float | None:
    lst = data.get("by_date", {}).get(code) or []
    return _to_float(lst[0]["electric_consumption"]) if lst else None


def _month_kwh(data: dict, code: str, month: int, year_key: str) -> float | None:
    bm = data.get("by_month", {}).get(code) or {}
    block = bm.get(year_key) or {}
    return _to_float(block.get(str(month)))


def _this_month_kwh(data: dict, code: str) -> float | None:
    # Hợp đồng chính: dùng ước tính từ consumption/info; còn lại: byMonth tháng hiện tại
    if _is_primary(data, code):
        v = _to_float((data.get("info") or {}).get("electric_consumption"))
        if v is not None:
            return v
    return _month_kwh(data, code, dt_util.now().month, "this_year")


def _last_month_kwh(data: dict, code: str) -> float | None:
    now = dt_util.now()
    if now.month == 1:
        return _month_kwh(data, code, 12, "last_year")
    return _month_kwh(data, code, now.month - 1, "this_year")


def _this_month_cost(data: dict, code: str) -> float | None:
    return _to_float((data.get("info") or {}).get("electric_consumption_price"))


def _latest_bill(data: dict, code: str) -> dict:
    bills = (data.get("bills", {}).get(code) or {}).get("bills") or []
    return bills[0] if bills else {}


def _attr_today(data: dict, code: str) -> dict:
    lst = data.get("by_date", {}).get(code) or []
    return {
        "last_date": lst[0]["date"] if lst else None,
        "daily": [
            {"date": d.get("date"), "kwh": _to_float(d.get("electric_consumption"))}
            for d in lst
        ],
    }


def _attr_this_month(data: dict, code: str) -> dict:
    info = data.get("info") or {}
    bm = data.get("by_month", {}).get(code) or {}
    return {
        "uoc_tinh_kwh": info.get("electric_consumption") if _is_primary(data, code) else None,
        "tien_tam_tinh": info.get("electric_consumption_price") if _is_primary(data, code) else None,
        "phan_tram_so_thang_truoc": info.get("ti_le_so_voi_thang_truoc") if _is_primary(data, code) else None,
        "this_year": bm.get("this_year"),
        "last_year": bm.get("last_year"),
    }


def _attr_bill(data: dict, code: str) -> dict:
    b = _latest_bill(data, code)
    all_bills = (data.get("bills", {}).get(code) or {}).get("bills") or []
    return {
        "ky": f"{b.get('month')}/{b.get('year')}" if b else None,
        "tu_ngay": b.get("from"),
        "den_ngay": b.get("to"),
        "da_thanh_toan": bool(b.get("da_thanh_toan")) if b else None,
        "san_luong_kwh": b.get("electric_consumption"),
        "lich_su_hoa_don": all_bills,
    }


@dataclass(frozen=True, kw_only=True)
class EpointSensorDesc(SensorEntityDescription):
    """Mô tả sensor ePoint."""

    value_fn: Callable[[dict, str], Any]
    attr_fn: Callable[[dict, str], dict] | None = None
    primary_only: bool = False


KWH = UnitOfEnergy.KILO_WATT_HOUR

SENSORS: tuple[EpointSensorDesc, ...] = (
    EpointSensorDesc(
        key="today_kwh",
        name="Tiêu thụ hôm nay",
        native_unit_of_measurement=KWH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=_today_kwh,
        attr_fn=_attr_today,
    ),
    EpointSensorDesc(
        key="this_month_kwh",
        name="Tiêu thụ tháng này (tạm tính)",
        native_unit_of_measurement=KWH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-month",
        value_fn=_this_month_kwh,
        attr_fn=_attr_this_month,
    ),
    EpointSensorDesc(
        key="this_month_cost",
        name="Tiền điện tạm tính tháng này",
        native_unit_of_measurement="VND",
        device_class=SensorDeviceClass.MONETARY,
        icon="mdi:cash",
        value_fn=_this_month_cost,
        primary_only=True,
    ),
    EpointSensorDesc(
        key="last_month_kwh",
        name="Tiêu thụ tháng trước",
        native_unit_of_measurement=KWH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-arrow-left",
        value_fn=_last_month_kwh,
    ),
    EpointSensorDesc(
        key="latest_bill_cost",
        name="Tiền điện hóa đơn gần nhất",
        native_unit_of_measurement="VND",
        device_class=SensorDeviceClass.MONETARY,
        icon="mdi:receipt-text",
        value_fn=lambda d, c: _to_float(_latest_bill(d, c).get("electric_consumption_price")),
        attr_fn=_attr_bill,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Tạo sensor cho từng hợp đồng đã liên kết."""
    coordinator: EpointCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[EpointSensor] = []
    for contract in coordinator.data.get("contracts", []):
        code = contract.get("customer_code") or contract.get("ma_khang")
        if not code:
            continue
        is_primary = coordinator.data.get("primary_code") == code
        for desc in SENSORS:
            if desc.primary_only and not is_primary:
                continue
            entities.append(EpointSensor(coordinator, desc, contract, code))
    async_add_entities(entities)


class EpointSensor(CoordinatorEntity[EpointCoordinator], SensorEntity):
    """Một cảm biến gắn với một hợp đồng EVN."""

    _attr_has_entity_name = True
    entity_description: EpointSensorDesc

    def __init__(
        self,
        coordinator: EpointCoordinator,
        description: EpointSensorDesc,
        contract: dict,
        code: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._code = code
        self._attr_unique_id = f"{code}_{description.key}"
        name = contract.get("display_name") or contract.get("name") or code
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, code)},
            name=f"{name} ({code})",
            manufacturer="EVN ePoint",
            model=contract.get("dviqly") or contract.get("cty_dluc") or "EVN",
            configuration_url="https://evnpoint.com",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data, self._code)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data, self._code)
