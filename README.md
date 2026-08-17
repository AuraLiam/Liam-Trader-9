# لیام تریدر ۹

Liam Trader 9 — Hamid's SMC signal panel (v4.8). Standalone home:
`Auraliam/Liam-Trader-9`; the old `.sognal` repo belongs to the other
panel and is never read or written from here.

## Regression test

```bash
python3 -m http.server 8901 --directory . &
npm i playwright  # once
node tests/regression.mjs
```
All 15 checks must print true (Binance is mocked; no network needed).
