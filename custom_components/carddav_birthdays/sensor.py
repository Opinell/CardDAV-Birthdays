"""Birthday sensors for CardDAV Birthdays integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CardDAVBirthdayCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CardDAVBirthdayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BirthdaysTodaySensor(coordinator, entry),
        BirthdaysThisWeekSensor(coordinator, entry),
        NextBirthdaySensor(coordinator, entry),
        UpcomingBirthdaysSensor(coordinator, entry),
    ])


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="CardDAV Birthdays",
        manufacturer="CardDAV",
        model="Birthday Tracker",
        entry_type="service",
    )


class _BirthdayBaseSensor(CoordinatorEntity[CardDAVBirthdayCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: CardDAVBirthdayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry)


class BirthdaysTodaySensor(_BirthdayBaseSensor):
    _attr_name = "Birthdays Today"
    _attr_icon = "mdi:cake-variant"
    _attr_native_unit_of_measurement = "contacts"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_birthdays_today"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("today", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"contacts": self.coordinator.data.get("today", [])}


class BirthdaysThisWeekSensor(_BirthdayBaseSensor):
    _attr_name = "Birthdays This Week"
    _attr_icon = "mdi:calendar-week"
    _attr_native_unit_of_measurement = "contacts"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_birthdays_this_week"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("this_week", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"contacts": self.coordinator.data.get("this_week", [])}


class NextBirthdaySensor(_BirthdayBaseSensor):
    _attr_name = "Next Birthday"
    _attr_icon = "mdi:cake"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_next_birthday"

    @property
    def native_value(self) -> str | None:
        entry = self.coordinator.data.get("next")
        return entry["name"] if entry else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self.coordinator.data.get("next")
        if not entry:
            return {}
        return {
            "days_until": entry["days_until"],
            "date": entry["date"],
            "age_at_next": entry["age_at_next"],
        }


class UpcomingBirthdaysSensor(_BirthdayBaseSensor):
    _attr_name = "Upcoming Birthdays"
    _attr_icon = "mdi:calendar-star"
    _attr_native_unit_of_measurement = "contacts"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_upcoming_birthdays"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("upcoming", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "contacts": self.coordinator.data.get("upcoming", []),
            "window_days": self.coordinator.data.get("upcoming_days", 30),
        }
