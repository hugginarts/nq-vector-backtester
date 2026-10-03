<div align="center">
  <img src="assets/nq-vector-banner.svg" alt="NQ Vector 5M — MNQ strategy research and backtesting" width="100%">
  <h1>NQ Vector 5M</h1>
  <p><strong>A local-first research lab for MNQ 5-minute strategies.</strong></p>
  <p>Load NinjaTrader minute data, model trade costs, inspect performance, and export a NinjaScript draft for review.</p>
</div>

---

## Overview

NQ Vector 5M is a lightweight Python dashboard for exploring a rules-based MNQ pullback strategy with your own historical CSV data. It runs locally and does not connect to a broker or place orders.

The dashboard accepts NinjaTrader Minute exports (including semicolon-delimited, headerless UTC files) and OHLCV CSV files with headers. Minute data is converted into five-minute bars before the test.

### What it includes

- Responsive local dashboard designed to run on a computer or Android with Termux.
- Configurable fast and slow EMAs, ATR, R-multiple target, session, daily trade cap, and daily loss limit.
- MNQ point value, round-trip commission, and per-side slippage inputs.
- Net PnL, win rate, expectancy, profit factor, maximum drawdown, average R, equity curve, and trade log.
- Optional NinjaScript C# export using the selected parameters, for review and validation in NinjaTrader.
- Conservative same-bar assumption: if a stop and target are both touched in one bar, the stop is counted first.

## Strategy outline

The included example looks for a pullback in the direction of the EMA trend, checks price against the session VWAP, and uses a confirmation candle before entering at the next bar's open. Stops are placed beyond a recent swing with an ATR margin; the target is set as a multiple of risk. The daily loss limit prevents additional entries after it is reached.

This is an experimental backtesting tool. A positive result on one CSV does not establish an edge or predict future performance. Validate data quality, costs, different market conditions, out-of-sample periods, and NinjaTrader results before paper trading. The exported NinjaScript is a draft for review; it has not been certified for live trading.

## Requirements

- Python 3.9 or newer
- No third-party Python packages
- A local MNQ CSV export from NinjaTrader or another OHLCV source

## Run on desktop

```bash
python nq_vector_5m.py
```

Then open **http://127.0.0.1:8765** in your browser, choose a CSV, set the assumptions, and run the backtest. Keep the terminal open while using the dashboard. Press `Ctrl+C` to stop the local server.

## Run on Android with Termux

```bash
pkg install python
python nq_vector_5m.py
```

Keep Termux open and visit **http://127.0.0.1:8765** in Chrome on the same phone.

## CSV notes

The parser supports:

- NinjaTrader Minute rows with six fields: timestamp, open, high, low, close, volume; semicolon delimiters and no header are supported.
- OHLCV CSV files with common timestamp and price column names.
- UTC timestamps from NinjaTrader exports, converted to New York session time.

Use minute data when testing intraday entries. Daily data cannot reproduce the five-minute strategy rules. Check the CSV date range, missing bars, timestamp convention, and contract rollover handling before trusting any result. Do not commit broker exports or other private market data to a public repository.

## NinjaTrader export

After a backtest, use **Export NinjaScript C# (.cs)** to download a strategy draft configured with the current inputs. Import and compile it in NinjaTrader, then compare its trades with this panel in Strategy Analyzer and test it in simulation. Configure commission and slippage in NinjaTrader to match the assumptions. Do not run it live based only on this panel's results.

## Repository contents

```text
nq-vector-5m-backtester/
├── assets/
│   └── nq-vector-banner.svg
├── .gitignore
├── README.md
└── nq_vector_5m.py
```

---

<div align="center">
  <sub>Built for transparent strategy research. Backtests are estimates, not promises.</sub>
</div>

## Descripción en español

**NQ Vector 5M** es un panel local de Python para probar una estrategia de retroceso en MNQ con barras de cinco minutos y archivos CSV propios. Permite modelar comisión y deslizamiento, revisar métricas y operaciones, y generar un borrador NinjaScript C# para validar en NinjaTrader. No se conecta a un broker ni envía órdenes. Los resultados históricos no garantizan rentabilidad futura; valida los datos, los costos y periodos fuera de muestra antes de pasar a simulación.
