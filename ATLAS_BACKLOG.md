# ATLAS RC15 — recovered requirements and release gate (2026-10-16)

Source: user decisions across prior ATLAS/SUNGHO-Stock-Scanner conversations, cross-checked with VERIFICATION_KO.md. This is a task tracker, not evidence of deployed functionality.

## P0 — complete before release
- [x] Baseline CI compile + 26 regression checks on GitHub Actions (main)
- [x] Isolated candidate buying-flow evaluator and tests (feature branch; integration pending)
- [ ] Merge flow evaluator into actual Streamlit scanner refresh pipeline; same-time historical baseline, never stale/unknown BUY
- [ ] Authenticated KIS domestic REST live quote verification with observed timestamp and price
- [ ] Authenticated KIS KRX/NXT/UN WebSocket trade/order-book/program payload verification, with freshness, reconnect and no double subscription
- [ ] Check exact KIS investor-category data availability. Do NOT label program flows as foreign/institution flows.
- [ ] Show 005930 Samsung Electronics, 000660 SK hynix, 009150 Samsung Electro-Mechanics with price, change, cumulative volume, turnover, VWAP, source, delay and quote time
- [ ] Live auto re-ranking and candidate replacement; rejected pre-open picks must not stay BUY
- [ ] Stop/target/entry range + invalidation + BUY/SELL/WAIT and risk/reward; verify no execution/orders
- [ ] Live DART announcements and NAVER news (if secrets configured), timestamps, no stale/future headlines
- [ ] Validate remote Streamlit app's actual deployed build ID and live end-to-end scan; capture reproducible evidence
- [ ] Run regression, AppTest, and during-market KIS REST/WS checks; no release declaration before pass

## P1 — previously requested features, not a blocker for first validated RC15
- [ ] KOSPI/KOSDAQ, domestic index futures and *night futures* with real provider, contract month, timestamp and market hours; do not treat missing data as zero
- [ ] US Nasdaq/S&P500/SOX, SOXL (3x ETF, distinct from SOX), US Treasury 2/10/30y yields, dollar/KRW, Brent and futures; show regular vs extended vs delayed
- [ ] Korea/US holiday and early-close official calendars
- [ ] CPI/PPI/PCE/FOMC/speeches/earnings/event calendar; before-open and event-time notifications, 3/5/10 minute post-release reaction checks
- [ ] 1st KR pre-open, 2nd 5-min pre-open, 3rd NXT 11:30–11:40, intraday scan and replacement; confirm actual NXT session timetable from official provider
- [ ] Volume/value relative-to-same-clock baseline, opening-low, VWAP, box breakout/breakdown, 20-day MA, BB, RSI, MACD, MACD oscillator, displacement
- [ ] Separate short/swing/long horizon; foreign/institution/retail/program flow where legally and technically available
- [ ] Candlestick phone-readable charts, red up/blue down in KR convention, currency KRW/USD, time in PT/KST with seconds
- [ ] US broad universe beyond 11 watchlist tickers; score and trade-performance validation, realistic slippage/fees, out-of-sample tests
- [ ] Persistent per-user settings/audit, durable DB and app uptime/alerts
- [ ] News/filings for SK hynix, Kumho Engineering preferred, Samsung, MU, NVDA and macro/geopolitics; verified factual catalysts only

## Operational safety
- Keep live v4 intact until RC15 evidence passes. The user authorized improvements and deployment decisions, but no unsafe live release.
- No GitHub/Streamlit secrets in commits, logs or chat; no broker orders.
- Do not claim 24/7 live monitoring unless running and verified. No fabricated quotes or predictive certainty.
- Label all status items as implemented / tested with fixture / verified with live source / deployed.
