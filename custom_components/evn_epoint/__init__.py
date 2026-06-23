"""Integration EVN ePoint cho Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EpointApi
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_KEY,
    CONF_REFRESH_TOKEN,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import EpointCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Khởi tạo từ config entry."""
    session = async_get_clientsession(hass)
    api = EpointApi(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_DEVICE_KEY],
        entry.data.get(CONF_ACCESS_TOKEN),
        entry.data.get(CONF_REFRESH_TOKEN),
    )
    coordinator = EpointCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gỡ config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
