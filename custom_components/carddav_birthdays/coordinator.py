"""CardDAV birthday data coordinator."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp
import vobject

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CARDDAV_REFETCH_INTERVAL,
    CONF_PASSWORD,
    CONF_SERVER_URL,
    CONF_UPCOMING_DAYS,
    CONF_USERNAME,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

ADDRESSBOOK_QUERY = """<?xml version="1.0" encoding="utf-8" ?>
<C:addressbook-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:carddav">
  <D:prop>
    <D:getetag/>
    <C:address-data>
      <C:prop name="FN"/>
      <C:prop name="BDAY"/>
    </C:address-data>
  </D:prop>
</C:addressbook-query>"""

NS = {
    "D": "DAV:",
    "C": "urn:ietf:params:xml:ns:carddav",
}


def _parse_bday(bday_str: str) -> date | None:
    """Parse a vCard BDAY value into a date. Returns None if unparseable."""
    s = bday_str.strip()
    # Full date: 19850315 or 1985-03-15
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    # Year-less: --0315 or --03-15
    for prefix in ("--",):
        if s.startswith(prefix):
            tail = s[len(prefix):].replace("-", "")
            try:
                parsed = datetime.strptime(tail, "%m%d")
                return date(1, parsed.month, parsed.day)
            except ValueError:
                pass
    return None


def _days_until_next_birthday(bday: date, today: date) -> int:
    """Return the number of days from today until the next occurrence of this birthday."""
    try:
        next_bd = bday.replace(year=today.year)
    except ValueError:
        # Feb 29 on non-leap year → use Mar 1
        next_bd = date(today.year, 3, 1)
    if next_bd < today:
        try:
            next_bd = bday.replace(year=today.year + 1)
        except ValueError:
            next_bd = date(today.year + 1, 3, 1)
    return (next_bd - today).days


def _age_at_next(bday: date, today: date) -> int | None:
    """Return the age the person will turn on their next birthday. None if year unknown."""
    if bday.year == 1:
        return None
    days = _days_until_next_birthday(bday, today)
    next_year = (today + timedelta(days=days)).year
    return next_year - bday.year


def _parse_vcards(xml_body: str) -> list[dict[str, Any]]:
    """Extract contacts with birthday info from a CardDAV REPORT response."""
    contacts: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError as exc:
        _LOGGER.warning("Failed to parse CardDAV XML response: %s", exc)
        return contacts

    for response in root.findall("D:response", NS):
        for prop_ok in response.findall("D:propstat/D:prop/C:address-data", NS):
            vcard_text = prop_ok.text
            if not vcard_text:
                continue
            try:
                vcard = vobject.readOne(vcard_text)
            except Exception:
                continue
            bday_val = getattr(vcard, "bday", None)
            if bday_val is None:
                continue
            bday = _parse_bday(str(bday_val.value))
            if bday is None:
                continue
            fn = getattr(vcard, "fn", None)
            name = fn.value.strip() if fn else "Unknown"
            contacts.append({"name": name, "birthday": bday})

    return contacts


class CardDAVBirthdayCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches contacts from CardDAV and calculates birthday datasets."""

    def __init__(self, hass: HomeAssistant, entry_data: dict) -> None:
        self._server_url = entry_data[CONF_SERVER_URL].rstrip("/")
        self._username = entry_data[CONF_USERNAME]
        self._password = entry_data[CONF_PASSWORD]
        self._upcoming_days = entry_data.get(CONF_UPCOMING_DAYS, 30)
        self._contacts: list[dict[str, Any]] = []
        self._last_fetch: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _fetch_contacts(self) -> None:
        """Fetch vCards from the CardDAV server and cache parsed contacts."""
        auth = aiohttp.BasicAuth(self._username, self._password)
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": "1",
        }
        timeout = aiohttp.ClientTimeout(total=30)
        session = async_get_clientsession(self.hass)
        try:
            async with session.request(
                "REPORT",
                self._server_url,
                data=ADDRESSBOOK_QUERY,
                headers=headers,
                auth=auth,
                timeout=timeout,
            ) as resp:
                if resp.status not in (207, 200):
                    raise UpdateFailed(
                        f"CardDAV REPORT returned HTTP {resp.status}"
                    )
                body = await resp.text()
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"Cannot connect to CardDAV server: {exc}") from exc

        self._contacts = _parse_vcards(body)
        self._last_fetch = datetime.now()
        _LOGGER.debug("Fetched %d contacts with birthdays", len(self._contacts))

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh from CardDAV if needed, then recalculate sensor datasets."""
        needs_fetch = (
            self._last_fetch is None
            or (datetime.now() - self._last_fetch) >= CARDDAV_REFETCH_INTERVAL
        )
        if needs_fetch:
            await self._fetch_contacts()

        today = date.today()
        week_end = today + timedelta(days=7)
        upcoming_end = today + timedelta(days=self._upcoming_days)

        today_contacts = []
        this_week_contacts = []
        upcoming_contacts = []
        next_birthday_entry: dict | None = None
        min_days: int | None = None

        for contact in self._contacts:
            bday: date = contact["birthday"]
            days = _days_until_next_birthday(bday, today)
            age_next = _age_at_next(bday, today)

            entry = {
                "name": contact["name"],
                "days_until": days,
                "date": bday.replace(year=today.year).isoformat()
                if days < 365
                else bday.isoformat(),
                "age_at_next": age_next,
            }

            if days == 0:
                today_contacts.append(
                    {"name": contact["name"], "age": age_next}
                )
            if 0 <= days < 7:
                this_week_contacts.append(entry)
            if 0 <= days < self._upcoming_days:
                upcoming_contacts.append(entry)
            if min_days is None or days < min_days:
                min_days = days
                next_birthday_entry = entry

        this_week_contacts.sort(key=lambda x: x["days_until"])
        upcoming_contacts.sort(key=lambda x: x["days_until"])

        return {
            "today": today_contacts,
            "this_week": this_week_contacts,
            "next": next_birthday_entry,
            "upcoming": upcoming_contacts,
            "upcoming_days": self._upcoming_days,
        }
