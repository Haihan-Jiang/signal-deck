from __future__ import annotations

import unittest

from stock_paper_trader import (
    AlpacaError,
    Quote,
    append_or_replace_bar,
    build_stock_stream_url,
    compute_stock_signal,
    normalize_stream_items,
    require_paper_base_url,
)


def make_bars(values: list[float]) -> list[dict[str, float]]:
    return [{"c": value} for value in values]


class StockPaperTraderTests(unittest.TestCase):
    def test_buy_signal_when_short_sma_crosses_above_long_sma(self) -> None:
        bars = make_bars([10, 10, 10, 10, 10, 12, 13, 14, 15, 16])
        signal = compute_stock_signal(
            symbol="spy",
            bars=bars,
            quote=Quote(bid=15.99, ask=16.01, last=None, timestamp=""),
            position_qty=0,
            buying_power=100,
            max_notional=10,
            short_window=3,
            long_window=5,
            min_order_notional=1,
            max_spread_pct=0.01,
        )
        self.assertEqual(signal.action, "BUY")
        self.assertEqual(signal.symbol, "SPY")

    def test_hold_when_already_long_in_uptrend(self) -> None:
        bars = make_bars([10, 10, 10, 10, 10, 12, 13, 14, 15, 16])
        signal = compute_stock_signal(
            symbol="spy",
            bars=bars,
            quote=Quote(bid=15.99, ask=16.01, last=None, timestamp=""),
            position_qty=0.5,
            buying_power=100,
            max_notional=10,
            short_window=3,
            long_window=5,
            min_order_notional=1,
            max_spread_pct=0.01,
        )
        self.assertEqual(signal.action, "HOLD")
        self.assertEqual(signal.reason, "uptrend_already_long")

    def test_sell_signal_when_short_sma_below_long_sma_and_long(self) -> None:
        bars = make_bars([16, 16, 16, 16, 16, 14, 13, 12, 11, 10])
        signal = compute_stock_signal(
            symbol="spy",
            bars=bars,
            quote=Quote(bid=9.99, ask=10.01, last=None, timestamp=""),
            position_qty=0.5,
            buying_power=100,
            max_notional=10,
            short_window=3,
            long_window=5,
            min_order_notional=1,
            max_spread_pct=0.01,
        )
        self.assertEqual(signal.action, "SELL")

    def test_hold_when_spread_too_wide(self) -> None:
        bars = make_bars([10, 10, 10, 10, 10, 12, 13, 14, 15, 16])
        signal = compute_stock_signal(
            symbol="spy",
            bars=bars,
            quote=Quote(bid=15.0, ask=16.0, last=None, timestamp=""),
            position_qty=0,
            buying_power=100,
            max_notional=10,
            short_window=3,
            long_window=5,
            min_order_notional=1,
            max_spread_pct=0.01,
        )
        self.assertEqual(signal.action, "HOLD")
        self.assertTrue(signal.reason.startswith("spread_too_wide"))

    def test_hold_when_existing_position_is_short(self) -> None:
        bars = make_bars([10, 10, 10, 10, 10, 12, 13, 14, 15, 16])
        signal = compute_stock_signal(
            symbol="spy",
            bars=bars,
            quote=Quote(bid=15.99, ask=16.01, last=None, timestamp=""),
            position_qty=-0.5,
            buying_power=100,
            max_notional=10,
            short_window=3,
            long_window=5,
            min_order_notional=1,
            max_spread_pct=0.01,
        )
        self.assertEqual(signal.action, "HOLD")
        self.assertEqual(signal.reason, "short_position_not_supported")

    def test_rejects_non_paper_alpaca_endpoint(self) -> None:
        with self.assertRaises(AlpacaError):
            require_paper_base_url("https://api.alpaca.markets")

    def test_builds_iex_stream_url(self) -> None:
        self.assertEqual(
            build_stock_stream_url("wss://stream.data.alpaca.markets/", "iex"),
            "wss://stream.data.alpaca.markets/v2/iex",
        )

    def test_append_or_replace_bar_keeps_latest_limit(self) -> None:
        bars = [{"t": "1", "c": 1.0}, {"t": "2", "c": 2.0}]
        append_or_replace_bar(bars, {"t": "2", "c": 2.5}, limit=2)
        self.assertEqual(bars, [{"t": "1", "c": 1.0}, {"t": "2", "c": 2.5}])
        append_or_replace_bar(bars, {"t": "3", "c": 3.0}, limit=2)
        self.assertEqual(bars, [{"t": "2", "c": 2.5}, {"t": "3", "c": 3.0}])

    def test_normalizes_stream_items(self) -> None:
        self.assertEqual(normalize_stream_items({"T": "success"}), [{"T": "success"}])
        self.assertEqual(normalize_stream_items([{"T": "q"}, "bad"]), [{"T": "q"}])


if __name__ == "__main__":
    unittest.main()
