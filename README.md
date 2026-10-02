# Libratone Zipp controller for Home Assistant

This aims to control a Libratone Zipp speaker within [Home Assistant](https://www.home-assistant.io/) using [this Python library](https://github.com/Chouffy/python_libratone_zipp).

## Limitations / Known bugs

* Major:
    * On Bluetooth and when the music is playing, you only get "Play" button, not Pause.
* Minor:
    * After a restart of Home Assistant, the integration can be in an "unknown" state before the 1st music is played

## Usage

### Installation via [HACS](https://hacs.xyz/)

1. Search for *Libratone Zipp* in the integration tab of HACS
1. Click *Install*
1. Restart Home Assistant
1. Go to _Settings_ → _Devices & services_ → _Add integration_ and search for **Libratone Zipp**
1. Add the IP of the speaker and a name
1. Repeat the last step if you have multiple speakers

Note: if you're using Docker/devcontainer, you need to forward `3333/udp` and `7778/udp`. 

## Additional entities (4.2.0)

Besides the media player, each speaker now gets a device with these entities. They were found by
decompiling the official Android app (`com.libratone.v3.model.LSSDPNode`, `luci.MIDCONST`) and
verified on a Zipp 2 (firmware 1536). Values are read from the speaker every 60 s and updated
immediately after a change from Home Assistant.

| Platform | Entity | Command | Notes |
|-|-|-|-|
| sensor | Battery | 256 / 257 | % |
| binary_sensor | Charging | 1284 | the app treats `1` as charging; the raw value is an attribute |
| sensor (diagnostic) | Wi-Fi signal | 529 | dBm, `quality_percent` attribute; payload `ssid,rssi,quality/max` |
| sensor (diagnostic) | Firmware, Firmware update, Serial number | 5, 66, 769 | serial number is disabled by default |
| button | Favorite 1-5 | 277 | plays the preset; see Favorites below |
| switch | Mute | 40 (`MUTE` / `UNMUTE`), 520 | also available as media player mute |
| number | Sleep timer | 15 | minutes, 0 = off; payload `2<seconds>` to set, `F0` to cancel |
| number (config) | Maximum volume | 300 | speaker-side volume cap, 0-100 |
| number (config) | LED level | 296 | 0-2 |
| switch (config) | Voice prompts | 293 | `1` / `0` |
| select | Room setting | 517 / 519 / 525 | names come from the speaker |
| select (config) | Speaker channel | 515 / 512 | `0` stereo, `1` left, `2` right (for two paired speakers) |

Implementation notes:

* `extras.py` subclasses the library's `LibratoneZipp` (`ZippExtended`) and caches the replies for the
  extra commands. The upstream receive loop does not catch exceptions, so one malformed reply
  (an empty Player JSON) used to stop the result thread; `ZippExtended` catches them.
* The speaker silently drops GETs that arrive in a burst, so a poll cycle spaces them out by 0.3 s.
* Commands that were seen on the speaker but are not used yet: 301 (LED percent), 613 (LED all off),
  1285 (private mode), 1541 (play mode), 545 (room correction), 10 / 128 / 123 (output source).

### Favorites (preset stations)

The speaker has five preset slots (command 275 reads them, 276 writes one):

```json
{"channel_id": 1, "channel_identity": "77320", "channel_name": "Klassik Radio Classic Dreams", "channel_type": "vtuner"}
```

* The media player's `source_list` now contains the station names; `select_source` accepts a name or a slot number.
* `button.<name>_favorite_1` ... `_5` play a preset; the station name is the `station` attribute (the
  entity name stays fixed so entity ids do not change when a preset is replaced).
* Service `libratone_zipp.set_favorite` (`favorite` 1-5, `station_id`, optional `name` and `channel_type`,
  default `vtuner`) replaces a preset. `station_id` is the vTuner station id, the same value the speaker
  reports as `channel_identity` for existing presets. There is no local station search: the app browses
  stations through the vendor's cloud API, which this integration does not use.

### Firmware

`Firmware` is the version number reported by command 5 (1536 on the tested Zipp 2). `Firmware update`
(diagnostic) shows what the speaker itself reports: command 66 with data `0` answers
`{"state": n, "err": n}`; states are `none` (0), `available` (1), `downloading` (2), `ready` (3),
`updating` (4), `updated` (5) and `mandatory` (6), taken from the app's log texts. The integration only
reads this state; installing is not implemented (the app starts it with command 66 and data `1`).

## Features

### Functionality coverage

Current coverage suits me, even if the python integration has much more options. Don't expect new features (only maintenance) but feel free to open an issue or submit a PR!

* v1.0
    * [x] Set up entity in home assistant
    * [x] Basic playback status
    * [x] Calculate status
* v2.0
    * [x] Set a sound mode (voicing)
    * [x] Use human names for Voicing / Sound mode
    * [x] Retrieve basic playback status: play, pause, stop, next, prev
    * [x] Set volume
    * [x] Retrieve volume
    * [x] Set to immediate standby (sleep)
    * [x] Retrieve current Voicing
    * [x] (kinda) Play a favorite (but it's only number)
* v3.0
    * [x] Retrieve current title and sub-title
* v4.0
    * [x] Manage multiple speakers
    * [x] Add/Remove speakers via Web interface (no `configuration.yaml` anymore!)
* v4.1 
    * [x] Implement SoundSpace Link


Other functionalities - Not planned right now:

* Module
    * [ ] Make the module async
    * [ ] Submit it for official integration!
    * [ ] Add support for other libratone speakers
* Current Playback info
    * [ ] Retrieve current playback source
    * [ ] Retrieve media type: bluetooth, spotify, aux, radio, ...
* Standby
    * [x] Set a standby timer (number entity `Sleep timer`)
    * [x] Retrieve a standby timer
* Voicing & Room Setting
    * [x] Set Room Setting (select entity `Room setting`)
    * [x] Retrieve current Room Setting
* Favorites
    * [ ] Play a favorite (proper title)
    * [ ] Set a Favorite
* Extended current playback info
    * [ ] Set extended playback status: shuffle, repeat
    * [ ] Retrieve extended playback status: shuffle, repeat
    * [ ] Set Source
    * [ ] Retrieve current source
* Multi-room
    * [x] Set speaker mode (stereo, left, right) (select entity `Speaker channel`)
    * [ ] Add better media player cards

## Acknowledgment

This work is based on the following:

* The first Libratone command list is [coming from this work from Benjamin Hanke](https://www.loxwiki.eu/display/LOX/Libratone+Zipp+WLan+Lautsprecher)
* Entity to use: [Media Player](https://developers.home-assistant.io/docs/core/entity/media-player)
* Example of [integrations](https://www.home-assistant.io/integrations/#media-player):
    * Simple: [Harman Kardon AVR integration](https://www.home-assistant.io/integrations/harman_kardon_avr/) which use [this module](https://github.com/Devqon/hkavr)
    * Simple: [Clementine Music Player integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/clementine/media_player.py) which use [this module]()
    * Async: [Frontier Silicon integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/frontier_silicon) with [this module](https://github.com/zhelev/python-afsapi/tree/master/afsapi)
    * Async with extended features: [Yamaha integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/yamaha/) with [this module](https://github.com/wuub/rxv)

## License

See LICENSE file.
