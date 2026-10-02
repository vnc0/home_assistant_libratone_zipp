"""Extended Libratone Zipp client.

The upstream library (python-libratone-zipp) ignores several commands the speaker
understands. They were found by decompiling the official Android app
(com.libratone.v3.model.LSSDPNode / luci.MIDCONST) and verified against a Zipp 2.

All commands use the same UDP framing as the library: GET = command type 1,
SET = command type 2, both sent to speaker:7777, answers arrive on 7778/3333.
"""
from __future__ import annotations

import logging
import re
import threading
import time

# Prefer vendored lib during dev. Fall back to PyPI if not present
try:
    from .vendor.python_libratone_zipp.python_libratone_zipp import LibratoneZipp  # type: ignore
except Exception:  # pragma: no cover
    from python_libratone_zipp import LibratoneZipp  # type: ignore

_LOGGER = logging.getLogger(__name__)

# Command ids (MIDCONST in the Android app)
CMD_PLAY_CONTROL = 40          # data: PLAY/STOP/PAUSE/NEXT/PREV/MUTE/UNMUTE
CMD_MAX_VOLUME = 300           # data: "0".."100", speaker-side volume cap
CMD_LED_LEVEL = 296            # data: "0".."2", LED brightness level
CMD_VOICE_PROMPT = 293         # data: "1" on, "0" off
CMD_STEREO_SET = 512           # data: "0" stereo, "1" left, "2" right
CMD_STEREO_GET = 515           # answer on 515 (GET) and 512 (SET/notify)

# Commands whose answers are cached in ZippExtended.extra
_EXTRA_REPLY_KEYS = {
    CMD_MAX_VOLUME: "max_volume",
    CMD_LED_LEVEL: "led_level",
    CMD_VOICE_PROMPT: "voice_prompt",
    CMD_STEREO_GET: "stereo_type",
    CMD_STEREO_SET: "stereo_type",
}

STEREO_TYPES = {"0": "stereo", "1": "left", "2": "right"}
STEREO_TYPE_IDS = {v: k for k, v in STEREO_TYPES.items()}

# Sleep timer: the library stores remaining seconds, 2 bytes little endian
MAX_TIMER_SECONDS = 65535

# Seconds between consecutive GETs of one poll cycle (the speaker drops bursts)
_GET_SPACING = 0.3

# Seconds to wait after a SET before reading the value back
_CONFIRM_DELAY = 0.8


class ZippExtended(LibratoneZipp):
    """LibratoneZipp plus the extra commands used by the additional entities."""

    def __init__(self, host):
        # Must exist before the parent starts its keep-alive thread
        self.extra: dict[str, str] = {}
        self._extra_lock = threading.Lock()
        super().__init__(host)

    # --- receiving ---------------------------------------------------------

    def process_zipp_message(self, packet, receive_port):
        try:
            if len(packet) >= 10:
                command = (packet[3] << 8) | packet[4]
                key = _EXTRA_REPLY_KEYS.get(command)
                if key is not None:
                    value = bytes(packet[10:]).decode("ascii", "ignore").strip()
                    if value != "":
                        with self._extra_lock:
                            self.extra[key] = value
        except Exception:  # never break the parent's message handling
            _LOGGER.debug("Could not parse extra Zipp message", exc_info=True)
        try:
            super().process_zipp_message(packet, receive_port)
        except Exception:
            # The upstream hub's receive loop does not catch exceptions, so one malformed
            # reply (e.g. an empty Player JSON) would otherwise kill the result thread
            # and every later answer would be dropped.
            _LOGGER.debug("Error while processing Zipp message", exc_info=True)

    # --- polling -----------------------------------------------------------

    def get_all(self):
        """Parent GETs plus the extra values (called every keep-alive period).

        The speaker answers GETs one at a time and silently drops packets that arrive
        in a burst, so the requests are spaced out.
        """
        getters = (
            self.currpowermode_get,
            self.chargingstatus_get,
            self.volume_get,
            self.voicing_get,
            self.room_get,
            self.player_get,
            self.signalstrenght_get,
            self.mutestatus_get,
            self.batterylevel_get,
            self.timer_get,
            self.playstatus_get,
            lambda: self.get_control_command(command=CMD_MAX_VOLUME),
            lambda: self.get_control_command(command=CMD_LED_LEVEL),
            lambda: self.get_control_command(command=CMD_VOICE_PROMPT),
            lambda: self.get_control_command(command=CMD_STEREO_GET),
        )
        for getter in getters:
            getter()
            time.sleep(_GET_SPACING)

    def get_extra(self, key: str) -> str | None:
        with self._extra_lock:
            return self.extra.get(key)

    def _remember(self, key: str, value) -> None:
        with self._extra_lock:
            self.extra[key] = str(value)

    def _confirm(self, getter) -> None:
        """Re-read a value shortly after changing it (the speaker applies SETs a moment later)."""
        time.sleep(_CONFIRM_DELAY)
        getter()

    # --- mute --------------------------------------------------------------

    def mute(self):
        self.mutestatus = "MUTE"
        ok = self.set_control_command(CMD_PLAY_CONTROL, "MUTE")
        self._confirm(self.mutestatus_get)
        return ok

    def unmute(self):
        self.mutestatus = "UNMUTE"
        ok = self.set_control_command(CMD_PLAY_CONTROL, "UNMUTE")
        self._confirm(self.mutestatus_get)
        return ok

    @property
    def is_muted(self) -> bool | None:
        """mutestatus is 'UNMUTE' or 'MUTE,<previous volume>'."""
        status = getattr(self, "mutestatus", None)
        if not status:
            return None
        return status.upper().startswith("MUTE")

    # --- sleep timer -------------------------------------------------------

    def timer_set_seconds(self, seconds: int):
        seconds = max(1, min(int(seconds), MAX_TIMER_SECONDS))
        self.timer = seconds
        ok = self.timer_set(seconds)
        self._confirm(self.timer_get)
        return ok

    def timer_off(self):
        self.timer = None
        ok = self.timer_cancel()
        self._confirm(self.timer_get)
        return ok

    # --- settings ----------------------------------------------------------

    def max_volume_set(self, value: int):
        value = max(0, min(int(value), 100))
        self._remember("max_volume", value)
        ok = self.set_control_command(CMD_MAX_VOLUME, str(value))
        self._confirm(lambda: self.get_control_command(CMD_MAX_VOLUME))
        return ok

    def led_level_set(self, value: int):
        value = max(0, min(int(value), 2))
        self._remember("led_level", value)
        ok = self.set_control_command(CMD_LED_LEVEL, str(value))
        self._confirm(lambda: self.get_control_command(CMD_LED_LEVEL))
        return ok

    def voice_prompt_set(self, enabled: bool):
        self._remember("voice_prompt", "1" if enabled else "0")
        ok = self.set_control_command(CMD_VOICE_PROMPT, "1" if enabled else "0")
        self._confirm(lambda: self.get_control_command(CMD_VOICE_PROMPT))
        return ok

    def stereo_type_set(self, name: str):
        type_id = STEREO_TYPE_IDS[name]
        self._remember("stereo_type", type_id)
        ok = self.set_control_command(CMD_STEREO_SET, type_id)
        self._confirm(lambda: self.get_control_command(CMD_STEREO_GET))
        return ok

    # --- parsed read-only values -------------------------------------------

    @property
    def battery_percent(self) -> int | None:
        try:
            return int(str(self.batterylevel).strip())
        except (TypeError, ValueError):
            return None

    @property
    def is_charging(self) -> bool | None:
        """The app treats charging status 1 as 'charging' (2/0 as not charging)."""
        status = getattr(self, "chargingstatus", None)
        if status is None or str(status).strip() == "":
            return None
        return str(status).strip() == "1"

    @property
    def wifi_rssi(self) -> int | None:
        """signalstrenght looks like ' ,-45,65/70' (ssid, rssi dBm, quality/max)."""
        parts = str(getattr(self, "signalstrenght", "") or "").split(",")
        if len(parts) < 2:
            return None
        try:
            return int(parts[1])
        except ValueError:
            return None

    @property
    def wifi_quality_percent(self) -> int | None:
        match = re.search(r"(\d+)\s*/\s*(\d+)", str(getattr(self, "signalstrenght", "") or ""))
        if not match or int(match.group(2)) == 0:
            return None
        return round(100 * int(match.group(1)) / int(match.group(2)))
