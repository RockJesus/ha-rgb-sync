"""Generic network transport for HTTP / TCP / UDP RGB controllers."""

from __future__ import annotations

import asyncio
import codecs
import socket
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import DEFAULT_NET_BODY, NET_HTTP, NET_TCP, NET_UDP
from .base import BaseTransport, TransportError, render_payload

if TYPE_CHECKING:
    from ..models import DeviceState

RGB = tuple[int, int, int]


def render_bytes(template: str, state: "DeviceState", append_newline: bool = False) -> bytes:
    """Render a template to bytes, allowing ``\\xNN`` escape sequences."""
    text = render_payload(template, state)
    if append_newline and not text.endswith("\n"):
        text += "\n"
    if "\\x" in text:
        try:
            return codecs.decode(text, "unicode_escape").encode("latin-1")
        except (UnicodeDecodeError, ValueError):
            return text.encode("utf-8")
    return text.encode("utf-8")


class NetworkTransport(BaseTransport):
    """Talks to any LAN controller through a configurable endpoint."""

    def __init__(self, hass: Any, device: dict[str, Any]) -> None:
        super().__init__(hass, device)
        self.protocol = str(device.get("net_protocol") or NET_HTTP)
        self.host = str(device.get("host", "")).strip()
        self.port = int(device.get("port") or (80 if self.protocol == NET_HTTP else 5577))
        self.path = str(device.get("path") or "")
        self.method = str(device.get("method") or "POST").upper()
        self.body = str(device.get("body") or DEFAULT_NET_BODY)
        self.headers: dict[str, str] = dict(device.get("headers") or {})
        self.append_newline = bool(device.get("append_newline", False))
        self.min_interval = 1 / 10.0 if self.protocol == NET_UDP else 1 / 8.0
        self._writer: asyncio.StreamWriter | None = None
        self._reader: asyncio.StreamReader | None = None
        self._sock: socket.socket | None = None

    @property
    def url(self) -> str:
        if self.host.startswith(("http://", "https://")):
            base = self.host.rstrip("/")
            if self.port not in (80, 443) and ":" not in base.split("//", 1)[1]:
                base = f"{base}:{self.port}"
            return base + self.path
        return f"http://{self.host}:{self.port}{self.path}"

    async def async_setup(self) -> None:
        if not self.host:
            raise TransportError("host is empty")
        if self.protocol == NET_UDP:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._sock.setblocking(False)
            except OSError as err:  # pragma: no cover - platform dependent
                raise TransportError(str(err)) from err

    async def async_probe(self) -> bool:
        started = time.monotonic()
        try:
            if self.protocol == NET_HTTP:
                session = async_get_clientsession(self.hass)
                async with session.get(self.url, timeout=5) as response:
                    await response.read()
                    if response.status >= 500:
                        raise TransportError(f"HTTP {response.status}")
            elif self.protocol == NET_TCP:
                await self._ensure_connection()
            else:
                if not self.host:
                    raise TransportError("host is empty")
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)
            return False
        self._mark_ok(time.monotonic() - started)
        return True

    async def async_apply(self, state: "DeviceState") -> None:
        try:
            await self._send(render_bytes(self.body, state, self.append_newline))
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)
            raise TransportError(str(err)) from err
        self._mark_ok()

    async def async_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        if not state.on or not frame or self._throttled():
            return
        red, green, blue = frame[len(frame) // 2]
        frame_state = type(state)(
            on=True,
            brightness=255,
            rgb=(red, green, blue),
            effect=state.effect,
            speed=state.speed,
            palette=state.palette,
        )
        try:
            await self._send(render_bytes(self.body, frame_state, self.append_newline))
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)

    async def _send(self, payload: bytes) -> None:
        if self.protocol == NET_HTTP:
            session = async_get_clientsession(self.hass)
            headers = {"Content-Type": "application/json", **self.headers}
            async with session.request(
                self.method,
                self.url,
                data=payload if self.method in ("POST", "PUT", "PATCH") else None,
                headers=headers,
                timeout=5,
            ) as response:
                await response.read()
                if response.status >= 400:
                    raise TransportError(f"HTTP {response.status}")
            return

        if self.protocol == NET_TCP:
            writer = await self._ensure_connection()
            writer.write(payload)
            await writer.drain()
            return

        if self.protocol == NET_UDP:
            if self._sock is None:
                raise TransportError("UDP socket not ready")
            await self.hass.loop.sock_sendto(self._sock, payload, (self.host, self.port))
            return

        raise TransportError(f"unsupported protocol {self.protocol}")

    async def _ensure_connection(self) -> asyncio.StreamWriter:
        if self._writer is not None and not self._writer.is_closing():
            return self._writer
        reader, writer = await asyncio.open_connection(self.host, self.port)
        self._reader = reader
        self._writer = writer
        return writer

    async def async_close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (AttributeError, RuntimeError):  # pragma: no cover
                pass
        self._writer = None
        self._reader = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None
