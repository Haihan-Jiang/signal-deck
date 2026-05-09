#!/usr/bin/env python3
"""Lowest-cost stock paper-trading runner using Alpaca + IEX data.

This module intentionally supports Alpaca paper trading only. It can evaluate a
simple moving-average strategy in dry-run mode, or submit simulated orders to an
Alpaca paper account when --mode paper is selected.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_ENV_PATH = Path.home() / ".signal-deck" / "runtime" / "alpaca.env"
DEFAULT_LOG_PATH = Path.home() / ".signal-deck" / "logs" / "stock_paper_trades.jsonl"
DEFAULT_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
DEFAULT_DATA_BASE_URL = "https://data.alpaca.markets"
DEFAULT_DATA_STREAM_BASE_URL = "wss://stream.data.alpaca.markets"
DEFAULT_BAR_LOOKBACK_DAYS = 7


class AlpacaError(RuntimeError):
    pass


@dataclass
class Quote:
    bid: float | None
    ask: float | None
    last: float | None
    timestamp: str


@dataclass
class StockSignal:
    action: str
    reason: str
    symbol: str
    last_price: float
    bid: float | None
    ask: float | None
    short_sma: float | None
    long_sma: float | None
    position_qty: float
    target_notional: float
    estimated_qty: float
    max_spread_pct: float


def load_env_file(path: Path) -> dict[str, str]:
    """Load simple shell-style KEY=VALUE exports without overriding os.environ."""
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def require_paper_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.netloc.lower()
    if host != "paper-api.alpaca.markets":
        raise AlpacaError(
            "Refusing to use a non-paper Alpaca endpoint. "
            "Set ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets."
        )
    path = parsed.path.rstrip("/")
    if path not in {"", "/v2"}:
        raise AlpacaError("Paper endpoint must be https://paper-api.alpaca.markets without extra path components.")
    return f"{parsed.scheme}://{parsed.netloc}"


def parse_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("Boolean value is not numeric.")
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round_money(value: float) -> str:
    return f"{value:.2f}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TextWebSocket:
    """Minimal RFC6455 text WebSocket client for Alpaca's JSON streams."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout
        self.sock: ssl.SSLSocket | socket.socket | None = None
        self._recv_buffer = b""

    def connect(self) -> None:
        parsed = urllib.parse.urlparse(self.url)
        if parsed.scheme != "wss":
            raise AlpacaError("Only wss:// WebSocket URLs are supported.")
        host = parsed.hostname
        if not host:
            raise AlpacaError("WebSocket URL is missing a host.")
        port = parsed.port or 443
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        raw_sock = socket.create_connection((host, port), timeout=self.timeout)
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(raw_sock, server_hostname=host)
        self.sock.settimeout(self.timeout)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        headers = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            "",
            "",
        ]
        self.sock.sendall("\r\n".join(headers).encode("ascii"))
        response = self._read_http_response()
        if " 101 " not in response.split("\r\n", 1)[0]:
            raise AlpacaError(f"WebSocket handshake failed: {response.splitlines()[0]}")
        expected_accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if expected_accept.lower() not in response.lower():
            raise AlpacaError("WebSocket handshake failed accept-key validation.")

    def _read_http_response(self) -> str:
        chunks: list[bytes] = []
        while True:
            chunk = self._socket().recv(4096)
            if not chunk:
                raise AlpacaError("WebSocket handshake closed before response.")
            chunks.append(chunk)
            joined = b"".join(chunks)
            if b"\r\n\r\n" in joined:
                head, _, rest = joined.partition(b"\r\n\r\n")
                self._recv_buffer += rest
                return (head + b"\r\n\r\n").decode("iso-8859-1", errors="replace")

    def _socket(self) -> ssl.SSLSocket | socket.socket:
        if self.sock is None:
            raise AlpacaError("WebSocket is not connected.")
        return self.sock

    def _read_exact(self, size: int) -> bytes:
        data = b""
        if self._recv_buffer:
            take = min(size, len(self._recv_buffer))
            data += self._recv_buffer[:take]
            self._recv_buffer = self._recv_buffer[take:]
        while len(data) < size:
            try:
                chunk = self._socket().recv(size - len(data))
            except OSError as exc:
                raise AlpacaError(f"WebSocket receive failed: {exc}") from exc
            if not chunk:
                raise AlpacaError("WebSocket connection closed.")
            data += chunk
        return data

    def send_json(self, payload: dict[str, Any]) -> None:
        self.send_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))

    def send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))

        mask = os.urandom(4)
        masked = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
        self._socket().sendall(bytes(header) + mask + masked)

    def recv_json(self) -> Any:
        return json.loads(self.recv_text())

    def recv_text(self) -> str:
        while True:
            first, second = self._read_exact(2)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]

            mask = self._read_exact(4) if masked else b""
            payload = self._read_exact(length) if length else b""
            if masked:
                payload = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))

            if opcode == 0x8:
                raise AlpacaError("WebSocket closed by server.")
            if opcode == 0x9:
                self._send_control_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode != 0x1:
                raise AlpacaError(f"Unsupported WebSocket opcode: {opcode}")
            return payload.decode("utf-8")

    def _send_control_frame(self, opcode: int, payload: bytes) -> None:
        if len(payload) > 125:
            payload = payload[:125]
        header = bytearray([0x80 | opcode, 0x80 | len(payload)])
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
        self._socket().sendall(bytes(header) + mask + masked)

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self._send_control_frame(0x8, b"")
        except Exception:
            pass
        try:
            self.sock.close()
        finally:
            self.sock = None


def build_stock_stream_url(base_url: str, feed: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/v2/{feed}"


class AlpacaPaperClient:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper_base_url: str = DEFAULT_PAPER_BASE_URL,
        data_base_url: str = DEFAULT_DATA_BASE_URL,
        data_stream_base_url: str = DEFAULT_DATA_STREAM_BASE_URL,
        timeout: float = 10.0,
    ) -> None:
        if not api_key or not secret_key:
            raise AlpacaError("Missing Alpaca API credentials.")
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper_base_url = require_paper_base_url(paper_base_url)
        self.data_base_url = data_base_url.rstrip("/")
        self.data_stream_base_url = data_stream_base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls, timeout: float = 10.0) -> "AlpacaPaperClient":
        api_key = (
            os.environ.get("APCA_API_KEY_ID")
            or os.environ.get("ALPACA_API_KEY_ID")
            or ""
        ).strip()
        secret_key = (
            os.environ.get("APCA_API_SECRET_KEY")
            or os.environ.get("ALPACA_API_SECRET_KEY")
            or ""
        ).strip()
        paper_base_url = os.environ.get("ALPACA_PAPER_BASE_URL", DEFAULT_PAPER_BASE_URL).strip()
        data_base_url = os.environ.get("ALPACA_DATA_BASE_URL", DEFAULT_DATA_BASE_URL).strip()
        data_stream_base_url = os.environ.get("ALPACA_DATA_STREAM_BASE_URL", DEFAULT_DATA_STREAM_BASE_URL).strip()
        return cls(
            api_key=api_key,
            secret_key=secret_key,
            paper_base_url=paper_base_url,
            data_base_url=data_base_url,
            data_stream_base_url=data_stream_base_url,
            timeout=timeout,
        )

    def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
        url = f"{base_url}{path}{query}"
        payload = None
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
        }
        if body is not None:
            payload = json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            raise AlpacaError(f"Alpaca HTTP {exc.code} {path}: {raw_error}") from exc
        except urllib.error.URLError as exc:
            raise AlpacaError(f"Alpaca request failed: {exc}") from exc

        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AlpacaError(f"Alpaca returned non-JSON response: {raw[:200]}") from exc

    def get_account(self) -> dict[str, Any]:
        return self._request("GET", self.paper_base_url, "/v2/account")

    def get_clock(self) -> dict[str, Any]:
        return self._request("GET", self.paper_base_url, "/v2/clock")

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        try:
            payload = self._request("GET", self.paper_base_url, f"/v2/positions/{symbol.upper()}")
        except AlpacaError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            self.paper_base_url,
            "/v2/orders",
            params={"status": "open", "symbols": symbol.upper(), "limit": 50},
        )
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, dict)]

    def get_latest_quote(self, symbol: str, feed: str = "iex") -> Quote:
        payload = self._request(
            "GET",
            self.data_base_url,
            f"/v2/stocks/{symbol.upper()}/quotes/latest",
            params={"feed": feed},
        )
        quote = payload.get("quote") if isinstance(payload, dict) else None
        if not isinstance(quote, dict):
            raise AlpacaError("Alpaca market data response missing quote.")
        return Quote(
            bid=parse_float(quote.get("bp")),
            ask=parse_float(quote.get("ap")),
            last=None,
            timestamp=str(quote.get("t") or ""),
        )

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        feed: str = "iex",
        lookback_days: int = DEFAULT_BAR_LOOKBACK_DAYS,
    ) -> list[dict[str, Any]]:
        start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat().replace("+00:00", "Z")
        payload = self._request(
            "GET",
            self.data_base_url,
            f"/v2/stocks/{symbol.upper()}/bars",
            params={
                "timeframe": timeframe,
                "limit": limit,
                "feed": feed,
                "adjustment": "split",
                "start": start,
                "sort": "desc",
            },
        )
        bars = payload.get("bars") if isinstance(payload, dict) else None
        if bars is None:
            return []
        if not isinstance(bars, list):
            raise AlpacaError("Alpaca market data response missing bars.")
        clean_bars = [row for row in bars if isinstance(row, dict)]
        clean_bars.reverse()
        return clean_bars

    def submit_market_buy_notional(self, symbol: str, notional: float) -> dict[str, Any]:
        return self._request(
            "POST",
            self.paper_base_url,
            "/v2/orders",
            body={
                "symbol": symbol.upper(),
                "notional": round_money(notional),
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
            },
        )

    def submit_market_sell_qty(self, symbol: str, qty: float) -> dict[str, Any]:
        return self._request(
            "POST",
            self.paper_base_url,
            "/v2/orders",
            body={
                "symbol": symbol.upper(),
                "qty": f"{qty:.8f}".rstrip("0").rstrip("."),
                "side": "sell",
                "type": "market",
                "time_in_force": "day",
            },
        )

    def stock_stream_url(self, feed: str) -> str:
        return build_stock_stream_url(self.data_stream_base_url, feed)


def sma(values: list[float], window: int) -> float | None:
    if window <= 0:
        raise ValueError("SMA window must be > 0.")
    if len(values) < window:
        return None
    return sum(values[-window:]) / float(window)


def close_prices_from_bars(bars: list[dict[str, Any]]) -> list[float]:
    closes: list[float] = []
    for bar in bars:
        close = parse_float(bar.get("c"))
        if close is not None and close > 0:
            closes.append(close)
    return closes


def compute_stock_signal(
    symbol: str,
    bars: list[dict[str, Any]],
    quote: Quote,
    position_qty: float,
    buying_power: float,
    max_notional: float,
    short_window: int,
    long_window: int,
    min_order_notional: float,
    max_spread_pct: float,
) -> StockSignal:
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window.")
    if max_notional <= 0:
        raise ValueError("max_notional must be > 0.")
    if min_order_notional <= 0:
        raise ValueError("min_order_notional must be > 0.")
    if max_spread_pct < 0:
        raise ValueError("max_spread_pct cannot be negative.")

    closes = close_prices_from_bars(bars)
    if not closes:
        raise ValueError("No usable close prices were found.")

    last_price = closes[-1]
    short_sma = sma(closes, short_window)
    long_sma = sma(closes, long_window)
    reference_bid = quote.bid if quote.bid and quote.bid > 0 else last_price
    reference_ask = quote.ask if quote.ask and quote.ask > 0 else last_price
    spread_pct = 0.0
    if reference_bid > 0 and reference_ask >= reference_bid:
        midpoint = (reference_bid + reference_ask) / 2.0
        if midpoint > 0:
            spread_pct = (reference_ask - reference_bid) / midpoint

    target_notional = min(max_notional, max(0.0, buying_power * 0.95))
    estimated_qty = 0.0 if last_price <= 0 else target_notional / last_price

    if short_sma is None or long_sma is None:
        return StockSignal(
            action="HOLD",
            reason="insufficient_bars",
            symbol=symbol.upper(),
            last_price=last_price,
            bid=quote.bid,
            ask=quote.ask,
            short_sma=short_sma,
            long_sma=long_sma,
            position_qty=position_qty,
            target_notional=target_notional,
            estimated_qty=estimated_qty,
            max_spread_pct=max_spread_pct,
        )

    if position_qty < 0:
        return StockSignal(
            action="HOLD",
            reason="short_position_not_supported",
            symbol=symbol.upper(),
            last_price=last_price,
            bid=quote.bid,
            ask=quote.ask,
            short_sma=short_sma,
            long_sma=long_sma,
            position_qty=position_qty,
            target_notional=target_notional,
            estimated_qty=estimated_qty,
            max_spread_pct=max_spread_pct,
        )

    if spread_pct > max_spread_pct:
        return StockSignal(
            action="HOLD",
            reason=f"spread_too_wide:{spread_pct:.4f}",
            symbol=symbol.upper(),
            last_price=last_price,
            bid=quote.bid,
            ask=quote.ask,
            short_sma=short_sma,
            long_sma=long_sma,
            position_qty=position_qty,
            target_notional=target_notional,
            estimated_qty=estimated_qty,
            max_spread_pct=max_spread_pct,
        )

    if short_sma > long_sma:
        if position_qty > 0:
            reason = "uptrend_already_long"
            action = "HOLD"
        elif target_notional < min_order_notional:
            reason = "buying_power_below_min_order"
            action = "HOLD"
        else:
            reason = "short_sma_above_long_sma"
            action = "BUY"
    elif short_sma < long_sma:
        if position_qty > 0:
            reason = "short_sma_below_long_sma"
            action = "SELL"
        else:
            reason = "downtrend_no_position"
            action = "HOLD"
    else:
        reason = "sma_equal"
        action = "HOLD"

    return StockSignal(
        action=action,
        reason=reason,
        symbol=symbol.upper(),
        last_price=last_price,
        bid=quote.bid,
        ask=quote.ask,
        short_sma=short_sma,
        long_sma=long_sma,
        position_qty=position_qty,
        target_notional=target_notional,
        estimated_qty=estimated_qty,
        max_spread_pct=max_spread_pct,
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")


def summarize_order(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if not order:
        return None
    return {
        "id": order.get("id"),
        "client_order_id": order.get("client_order_id"),
        "symbol": order.get("symbol"),
        "side": order.get("side"),
        "type": order.get("type"),
        "time_in_force": order.get("time_in_force"),
        "qty": order.get("qty"),
        "notional": order.get("notional"),
        "status": order.get("status"),
        "submitted_at": order.get("submitted_at"),
    }


def normalize_stream_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def raise_for_stream_errors(items: list[dict[str, Any]]) -> None:
    for item in items:
        if item.get("T") == "error":
            message = item.get("msg") or item.get("message") or item
            raise AlpacaError(f"Alpaca stream error: {message}")


def authenticate_stock_stream(ws: TextWebSocket, client: AlpacaPaperClient, timeout: float) -> None:
    ws.send_json({"action": "auth", "key": client.api_key, "secret": client.secret_key})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        items = normalize_stream_items(ws.recv_json())
        raise_for_stream_errors(items)
        for item in items:
            if item.get("T") == "success" and item.get("msg") == "authenticated":
                return
    raise AlpacaError("Timed out authenticating Alpaca data stream.")


def subscribe_stock_stream(ws: TextWebSocket, symbol: str) -> None:
    ws.send_json({"action": "subscribe", "quotes": [symbol.upper()], "bars": [symbol.upper()]})


def quote_from_stream_event(event: dict[str, Any], previous: Quote | None = None) -> Quote:
    bid = parse_float(event.get("bp"))
    ask = parse_float(event.get("ap"))
    if bid is None and previous is not None:
        bid = previous.bid
    if ask is None and previous is not None:
        ask = previous.ask
    return Quote(
        bid=bid,
        ask=ask,
        last=previous.last if previous is not None else None,
        timestamp=str(event.get("t") or ""),
    )


def bar_from_stream_event(event: dict[str, Any]) -> dict[str, Any] | None:
    close = parse_float(event.get("c"))
    if close is None or close <= 0:
        return None
    return {
        "t": str(event.get("t") or ""),
        "o": parse_float(event.get("o")),
        "h": parse_float(event.get("h")),
        "l": parse_float(event.get("l")),
        "c": close,
        "v": parse_float(event.get("v")),
    }


def append_or_replace_bar(bars: list[dict[str, Any]], bar: dict[str, Any], limit: int) -> None:
    bar_ts = str(bar.get("t") or "")
    if bars and bar_ts and str(bars[-1].get("t") or "") == bar_ts:
        bars[-1] = bar
    else:
        bars.append(bar)
    if len(bars) > limit:
        del bars[: len(bars) - limit]


def latest_bar_timestamp(bars: list[dict[str, Any]]) -> str:
    if not bars:
        return ""
    return str(bars[-1].get("t") or "")


def evaluate_and_maybe_order(
    args: argparse.Namespace,
    client: AlpacaPaperClient,
    bars: list[dict[str, Any]],
    quote: Quote,
    market_source: str,
    market_event_ts: str,
    extra_timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol = args.symbol.upper()
    account_state_start_ts = now_iso()
    account = client.get_account()
    clock = client.get_clock()
    position = client.get_position(symbol)
    open_orders = client.get_open_orders(symbol)
    account_state_done_ts = now_iso()

    buying_power = parse_float(account.get("buying_power"), 0.0) or 0.0
    position_qty = 0.0
    if position:
        position_qty = parse_float(position.get("qty"), 0.0) or 0.0

    signal_compute_start_ts = now_iso()
    signal = compute_stock_signal(
        symbol=symbol,
        bars=bars,
        quote=quote,
        position_qty=position_qty,
        buying_power=buying_power,
        max_notional=args.max_notional,
        short_window=args.short_window,
        long_window=args.long_window,
        min_order_notional=args.min_order_notional,
        max_spread_pct=args.max_spread_pct,
    )
    signal_compute_done_ts = now_iso()

    blockers: list[str] = []
    if not bool(clock.get("is_open")) and not args.allow_closed_market:
        blockers.append("market_closed")
    if bool(account.get("trading_blocked")):
        blockers.append("account_trading_blocked")
    if open_orders:
        blockers.append("open_order_exists")

    order: dict[str, Any] | None = None
    order_submit_start_ts: str | None = None
    order_submit_done_ts: str | None = None
    order_submit_duration_ms: float | None = None
    if args.mode == "paper" and signal.action in {"BUY", "SELL"} and not blockers:
        order_submit_start_ts = now_iso()
        order_start = time.perf_counter()
        if signal.action == "BUY":
            order = client.submit_market_buy_notional(symbol, signal.target_notional)
        elif signal.action == "SELL":
            order = client.submit_market_sell_qty(symbol, abs(position_qty))
        order_submit_duration_ms = (time.perf_counter() - order_start) * 1000.0
        order_submit_done_ts = now_iso()

    timing = {
        "market_event_ts": market_event_ts,
        "account_state_start_ts": account_state_start_ts,
        "account_state_done_ts": account_state_done_ts,
        "signal_compute_start_ts": signal_compute_start_ts,
        "signal_compute_done_ts": signal_compute_done_ts,
        "order_submit_start_ts": order_submit_start_ts,
        "order_submit_done_ts": order_submit_done_ts,
        "order_submit_duration_ms": order_submit_duration_ms,
    }
    if extra_timing:
        timing.update(extra_timing)

    payload = {
        "ts": now_iso(),
        "mode": args.mode,
        "data_mode": args.data_mode,
        "market_source": market_source,
        "feed": args.feed,
        "timeframe": args.timeframe,
        "symbol": symbol,
        "account": {
            "status": account.get("status"),
            "currency": account.get("currency"),
            "buying_power": account.get("buying_power"),
            "cash": account.get("cash"),
            "trading_blocked": account.get("trading_blocked"),
        },
        "clock": {
            "is_open": clock.get("is_open"),
            "timestamp": clock.get("timestamp"),
            "next_open": clock.get("next_open"),
            "next_close": clock.get("next_close"),
        },
        "bars_count": len(bars),
        "open_orders_count": len(open_orders),
        "blockers": blockers,
        "signal": asdict(signal),
        "order": summarize_order(order),
        "timing": timing,
    }
    append_jsonl(args.log_path, payload)
    return payload


def run_once(args: argparse.Namespace, client: AlpacaPaperClient) -> dict[str, Any]:
    symbol = args.symbol.upper()
    market_fetch_start_ts = now_iso()
    quote = client.get_latest_quote(symbol, feed=args.feed)
    bars = client.get_bars(
        symbol,
        timeframe=args.timeframe,
        limit=max(args.bar_limit, args.long_window + 5),
        feed=args.feed,
        lookback_days=args.bar_lookback_days,
    )
    market_fetch_done_ts = now_iso()
    market_event_ts = quote.timestamp or latest_bar_timestamp(bars)
    return evaluate_and_maybe_order(
        args=args,
        client=client,
        bars=bars,
        quote=quote,
        market_source=f"{args.feed}_rest",
        market_event_ts=market_event_ts,
        extra_timing={
            "market_fetch_start_ts": market_fetch_start_ts,
            "market_fetch_done_ts": market_fetch_done_ts,
        },
    )


def run_stream(args: argparse.Namespace, client: AlpacaPaperClient) -> int:
    if args.timeframe != "1Min":
        raise ValueError("stream data mode currently supports --timeframe 1Min only.")
    symbol = args.symbol.upper()
    bars = client.get_bars(
        symbol,
        timeframe=args.timeframe,
        limit=max(args.bar_limit, args.long_window + 5),
        feed=args.feed,
        lookback_days=args.bar_lookback_days,
    )
    quote = client.get_latest_quote(symbol, feed=args.feed)
    ws = TextWebSocket(client.stock_stream_url(args.feed), timeout=args.timeout)
    evaluations = 0
    try:
        ws.connect()
        authenticate_stock_stream(ws, client, timeout=args.timeout)
        subscribe_stock_stream(ws, symbol)
        while True:
            items = normalize_stream_items(ws.recv_json())
            raise_for_stream_errors(items)
            for item in items:
                event_type = item.get("T")
                if event_type == "q" and item.get("S") == symbol:
                    quote = quote_from_stream_event(item, previous=quote)
                elif event_type == "b" and item.get("S") == symbol:
                    bar = bar_from_stream_event(item)
                    if bar is None:
                        continue
                    append_or_replace_bar(bars, bar, limit=max(args.bar_limit, args.long_window + 5))
                    payload = evaluate_and_maybe_order(
                        args=args,
                        client=client,
                        bars=bars,
                        quote=quote,
                        market_source=f"{args.feed}_websocket",
                        market_event_ts=str(item.get("t") or ""),
                    )
                    evaluations += 1
                    if args.json:
                        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), flush=True)
                    else:
                        print_human(payload)
                    if args.max_iterations is not None and evaluations >= args.max_iterations:
                        return 0
    finally:
        ws.close()


def print_human(payload: dict[str, Any]) -> None:
    signal = payload["signal"]
    blockers = ",".join(payload.get("blockers") or []) or "-"
    order = payload.get("order")
    order_text = f" order={order.get('id')} status={order.get('status')}" if order else ""
    timing = payload.get("timing") if isinstance(payload.get("timing"), dict) else {}
    submit_ms = timing.get("order_submit_duration_ms")
    submit_text = "" if submit_ms is None else f" submit_ms={float(submit_ms):.1f}"
    short_sma = "-" if signal["short_sma"] is None else f"{signal['short_sma']:.2f}"
    long_sma = "-" if signal["long_sma"] is None else f"{signal['long_sma']:.2f}"
    print(
        f"[{payload['ts']}] {payload['mode']} {payload['symbol']} "
        f"source={payload.get('market_source', payload.get('feed'))} "
        f"action={signal['action']} reason={signal['reason']} "
        f"last={signal['last_price']:.2f} short_sma={short_sma} "
        f"long_sma={long_sma} position={signal['position_qty']:.8g} "
        f"blockers={blockers}{order_text}{submit_text}",
        flush=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lowest-cost Alpaca stock paper-trading runner using IEX data."
    )
    parser.add_argument("--symbol", required=True, help="Stock/ETF symbol, e.g. SPY.")
    parser.add_argument(
        "--mode",
        choices=["dry-run", "paper"],
        default="dry-run",
        help="dry-run evaluates only; paper submits simulated Alpaca paper orders.",
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument(
        "--data-mode",
        choices=["rest", "stream"],
        default="rest",
        help="rest polls Alpaca data endpoints; stream evaluates on Alpaca IEX/SIP WebSocket bars.",
    )
    parser.add_argument("--feed", default=None, help="Market data feed; defaults to ALPACA_DATA_FEED or iex.")
    parser.add_argument("--stream-base-url", default=None, help="Defaults to ALPACA_DATA_STREAM_BASE_URL.")
    parser.add_argument("--timeframe", default="1Min")
    parser.add_argument("--bar-limit", type=int, default=60)
    parser.add_argument("--bar-lookback-days", type=int, default=DEFAULT_BAR_LOOKBACK_DAYS)
    parser.add_argument("--short-window", type=int, default=5)
    parser.add_argument("--long-window", type=int, default=20)
    parser.add_argument("--max-notional", type=float, default=10.0)
    parser.add_argument("--min-order-notional", type=float, default=1.0)
    parser.add_argument("--max-spread-pct", type=float, default=0.01)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--allow-closed-market", action="store_true")
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("Input error: --timeout must be > 0.")
    if args.interval <= 0:
        raise SystemExit("Input error: --interval must be > 0.")
    if args.bar_lookback_days <= 0:
        raise SystemExit("Input error: --bar-lookback-days must be > 0.")
    if args.max_iterations is not None and args.max_iterations <= 0:
        raise SystemExit("Input error: --max-iterations must be > 0.")

    load_env_file(args.env_file)
    if args.feed is None:
        args.feed = os.environ.get("ALPACA_DATA_FEED", "iex")
    if args.stream_base_url is None:
        args.stream_base_url = os.environ.get("ALPACA_DATA_STREAM_BASE_URL", DEFAULT_DATA_STREAM_BASE_URL)

    try:
        client = AlpacaPaperClient.from_env(timeout=args.timeout)
    except AlpacaError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    client.data_stream_base_url = str(args.stream_base_url).rstrip("/")

    if args.data_mode == "stream":
        if not args.loop and args.max_iterations is None:
            args.max_iterations = 1
        try:
            return run_stream(args, client)
        except (AlpacaError, ValueError, json.JSONDecodeError) as exc:
            print(f"Run error: {exc}", file=sys.stderr)
            return 1

    iteration = 0
    while True:
        iteration += 1
        try:
            payload = run_once(args, client)
        except (AlpacaError, ValueError) as exc:
            print(f"Run error: {exc}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), flush=True)
        else:
            print_human(payload)

        if not args.loop:
            break
        if args.max_iterations is not None and iteration >= args.max_iterations:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
