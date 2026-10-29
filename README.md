# LEX TH Parcel Tracking for Home Assistant

Track **LEX TH (Lazada Express Thailand)** parcels in Home Assistant. Add a tracking number from the UI and get a status sensor with the full delivery timeline. No account, API key or cookies needed.

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-custom%20integration-41BDF5?logo=home-assistant&logoColor=white)
![IoT class](https://img.shields.io/badge/iot__class-cloud__polling-blue)
![Version](https://img.shields.io/badge/version-0.1.0-green)

## Features

- UI setup (config flow), no YAML
- One config entry per parcel, each with its own device and a **Status** sensor
- Normalized status (`in_transit`, `delivered`, ...) plus the raw LEX TH status code
- Full timeline (newest first) with UTC timestamps, locations and providers
- English and Thai (ไทย) translations, with a language choice when adding a parcel
- Polls every 30 minutes, one request per parcel per poll
- No extra Python requirements

> **Note:** LEX TH has no official public API. This integration uses the same JSON endpoint as the public [lex.th tracking page](https://lex.th/tracking). It works without authentication today but may break if LEX TH changes it. See [Limitations](#limitations).

## Installation

### Manual

1. Download or clone this repository.
2. Copy the `custom_components/lex_th` folder into your Home Assistant config directory, so you end up with:

   ```text
   <config>/
   └── custom_components/
       └── lex_th/
           ├── __init__.py
           ├── config_flow.py
           ├── const.py
           ├── manifest.json
           ├── sensor.py
           └── translations/
               ├── en.json
               └── th.json
   ```

3. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **LEX TH Parcel Tracking**.
3. Enter the **tracking number** (for example `LEXPU0719633081`) and pick a **language**.
4. Click **Submit**.

Repeat for every parcel you want to track. Each parcel becomes its own entry and device.

| Field | Description |
| --- | --- |
| Tracking number | 8-32 letters and digits. Lowercase input is converted to uppercase. |
| Language | `English` or `ไทย`. Sets the sensor name and the `status_text` attribute (see below). |

To stop tracking a parcel, delete its entry under **Settings → Devices & services → LEX TH Parcel Tracking**.

### Setup errors

| Message | Cause |
| --- | --- |
| Invalid tracking number | Not 8-32 letters/digits. |
| Cannot reach the LEX TH tracking service | Network problem, or LEX TH rejected the request. |
| This parcel is already being tracked | An entry for this number already exists. |

## Entities

Each parcel creates one device named `LEX TH <tracking number>` with one sensor:

`sensor.lex_th_<tracking_number>_status` (for example `sensor.lex_th_lexpu0719633081_status`)

### States

The state is one of these fixed values, so it is safe to use in automations:

| State | Meaning |
| --- | --- |
| `not_found` | LEX TH has no data for this number (yet). Not treated as an error. |
| `picked_up` | Parcel was picked up by LEX TH. |
| `in_transit` | Parcel is moving between hubs or sorting centers. |
| `out_for_delivery` | Parcel is out with a courier. |
| `delivered` | Parcel was delivered. |
| `problem` | Failed delivery, return, cancellation, damage or similar. |
| `unknown` | Status code not recognized. Check `raw_status`. |

State names shown in the UI are translated to your Home Assistant user language (English or Thai).

### Attributes

| Attribute | Description |
| --- | --- |
| `tracking_number` | The tracking number. |
| `status_text` | Localized state text in the language chosen at setup (for example `In transit` or `อยู่ระหว่างขนส่ง`). |
| `raw_status` | Raw LEX TH status code, for example `domestic_ib_success_in_sort_center`. |
| `provider` | Shipping provider, for example `LEX TH`. |
| `last_location` | Location of the newest event, for example `บางเสาธง`. |
| `last_update` | Time of the newest event, ISO 8601 in UTC. |
| `package_code` | LEX TH internal package code. |
| `tracking_url` | Link to the official tracking page. |
| `timeline` | List of events, newest first. Each has `status`, `time` (UTC), `location` and `provider`. |

`timeline` is excluded from the recorder to keep your database small.

> **About the language option:** Home Assistant picks the language of the UI and of state names per *user*, and an integration cannot override that. The language chosen during setup only controls the sensor's name and the `status_text` attribute.

## Examples

### Notify when a parcel is delivered

```yaml
automation:
  - alias: "Parcel delivered"
    triggers:
      - trigger: state
        entity_id: sensor.lex_th_lexpu0719633081_status
        to: "delivered"
    actions:
      - action: notify.notify
        data:
          title: "Parcel delivered"
          message: "{{ trigger.to_state.attributes.tracking_number }} was delivered."
```

### Notify on any status change

```yaml
automation:
  - alias: "Parcel status changed"
    triggers:
      - trigger: state
        entity_id: sensor.lex_th_lexpu0719633081_status
    conditions:
      - condition: template
        value_template: "{{ trigger.from_state.state not in ['unavailable', 'unknown'] }}"
    actions:
      - action: notify.notify
        data:
          message: >
            {{ trigger.to_state.attributes.tracking_number }}:
            {{ trigger.to_state.attributes.status_text }}
            ({{ trigger.to_state.attributes.last_location }})
```

### Show the timeline on a dashboard

```yaml
type: markdown
title: Parcel
content: >
  **{{ state_attr('sensor.lex_th_lexpu0719633081_status', 'status_text') }}**
  ([track]({{ state_attr('sensor.lex_th_lexpu0719633081_status', 'tracking_url') }}))

  {% for e in state_attr('sensor.lex_th_lexpu0719633081_status', 'timeline') %}
  - {{ as_timestamp(e.time) | timestamp_custom('%d %b %H:%M', true) }} · {{ e.location }} · `{{ e.status }}`
  {% endfor %}
```

## How it works

- Each poll sends one `POST https://lex.th/api/get_package_history` with `{"trackingNumber": "<number>"}`.
- `processTime` values (epoch milliseconds) are converted to UTC datetimes and the timeline is sorted newest first.
- A response with no `data` is reported as `not_found`.
- Network errors, timeouts (20 s), non-200 responses and `success: false` make the sensor `unavailable` and are logged. The integration retries on the next poll.
- Raw status codes are mapped to the states above. "Pickup" codes are checked before "success/sign" codes so a pickup is never read as delivered.

## Limitations

- **Unofficial endpoint.** The lex.th page loads bot-protection scripts. Plain requests work today, but LEX TH may block them later. If that happens the sensor goes `unavailable` and the log shows the HTTP error.
- **Only two raw status codes are verified:** `domestic_ib_success_in_sort_center` (→ `in_transit`) and `domestic_pickup/sign_in_success` (→ `picked_up`). Codes for out for delivery, delivered and problems are best-guess matches and may need adjusting. If you see `unknown`, check `raw_status` and open an issue with the code.
- A newly created tracking number may show `not_found` until LEX TH has indexed it.
- Parcels are not removed automatically after delivery. Delete the entry yourself.
- Polling interval is fixed at 30 minutes.

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.lex_th: debug
```

| Symptom | What to check |
| --- | --- |
| Integration not found in the list | Folder must be `custom_components/lex_th` and Home Assistant must be restarted. |
| `Cannot reach the LEX TH tracking service` | Can your HA host reach `https://lex.th`? Check DNS, firewall and proxy. |
| Sensor `unavailable` | Look for `LEX TH API returned HTTP ...` in the log. |
| State `unknown` | Unrecognized status code. See `raw_status`. |
| State `not_found` | Number not indexed yet, or typed wrong. |

## Disclaimer

This project is not affiliated with, endorsed by or supported by Lazada or LEX TH. It relies on a public web endpoint that may change at any time. Use at your own risk.
