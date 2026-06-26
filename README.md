# CardDAV Birthdays

A [HACS](https://hacs.xyz) custom integration for Home Assistant that reads birthday data from a CardDAV address book and exposes it as sensors. Use those sensors to trigger push notifications, TTS announcements, or any other Home Assistant automation.

## Features

- Connects to any CardDAV server (Nextcloud, Radicale, Baikal, Apple iCloud, Fastmail, …)
- Provides four aggregate sensors updated every hour
- Contact data is re-fetched from the server once per day
- Configured entirely through the Home Assistant UI — no YAML editing required

## Sensors

| Entity | State | Attributes |
|---|---|---|
| `sensor.carddav_birthdays_today` | Count of birthdays today | `contacts: [{name, age}]` |
| `sensor.carddav_birthdays_this_week` | Count in next 7 days | `contacts: [{name, days_until, date, age_at_next}]` |
| `sensor.carddav_next_birthday` | Name of next person | `days_until, date, age_at_next` |
| `sensor.carddav_upcoming_birthdays` | Count in window | `contacts: [{…}]`, `window_days` |

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **⋮** → **Custom repositories**
3. Add `https://github.com/Opinell/carddav-birthdays` as an **Integration**
4. Search for **CardDAV Birthdays** and install it
5. Restart Home Assistant

### Manual

Copy `custom_components/carddav_birthdays/` into your HA `custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **CardDAV Birthdays**
3. Fill in:
   - **CardDAV server URL** — the full URL to your address book (see examples below)
   - **Username** and **Password**
   - **Upcoming birthdays window** — how many days ahead `upcoming_birthdays` looks (default: 30)

### Server URL examples

| Service | URL pattern |
|---|---|
| Nextcloud | `https://your.nextcloud.com/remote.php/dav/addressbooks/users/USERNAME/contacts/` |
| Radicale | `http://localhost:5232/USERNAME/contacts/` |
| Baikal | `https://your.baikal.com/dav.php/addressbooks/USERNAME/default/` |
| Apple iCloud | `https://contacts.icloud.com/XXXXXXXX/carddavhome/card/` (use an app-specific password) |

## Example Automations

### Push notification on birthday day

```yaml
automation:
  alias: "Birthday push notification"
  trigger:
    - platform: time
      at: "08:00:00"
  condition:
    - condition: numeric_state
      entity_id: sensor.carddav_birthdays_today
      above: 0
  action:
    - action: notify.mobile_app_your_phone
      data:
        title: "Birthday today!"
        message: >
          {{ state_attr('sensor.carddav_birthdays_today', 'contacts')
             | map(attribute='name') | join(', ') }}
          {{ 'has' if state_attr('sensor.carddav_birthdays_today', 'contacts') | count == 1 else 'have' }}
          a birthday today!
```

### TTS announcement on birthday day

```yaml
automation:
  alias: "Birthday TTS announcement"
  trigger:
    - platform: time
      at: "09:00:00"
  condition:
    - condition: numeric_state
      entity_id: sensor.carddav_birthdays_today
      above: 0
  action:
    - action: tts.speak
      target:
        entity_id: tts.home_assistant_cloud  # or your TTS provider
      data:
        media_player_entity_id: media_player.living_room_speaker
        message: >
          Today is the birthday of
          {{ state_attr('sensor.carddav_birthdays_today', 'contacts')
             | map(attribute='name') | join(' and ') }}!
```

### Reminder the day before

```yaml
automation:
  alias: "Birthday reminder tomorrow"
  trigger:
    - platform: time
      at: "18:00:00"
  condition:
    - condition: template
      value_template: >
        {{ state_attr('sensor.carddav_next_birthday', 'days_until') == 1 }}
  action:
    - action: notify.mobile_app_your_phone
      data:
        title: "Birthday tomorrow!"
        message: >
          {{ states('sensor.carddav_next_birthday') }} has a birthday tomorrow!
```

## Troubleshooting

- **Cannot connect**: Check that the URL is reachable from your HA instance and ends with a `/`
- **Invalid auth**: For Apple iCloud, use an [app-specific password](https://support.apple.com/en-us/102654), not your Apple ID password
- **No birthdays showing**: Verify your contacts have the birthday field set and that the vCard `BDAY` property is present
- **Debug logging**: Add to `configuration.yaml`:
  ```yaml
  logger:
    logs:
      custom_components.carddav_birthdays: debug
  ```
