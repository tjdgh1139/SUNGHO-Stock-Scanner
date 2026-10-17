# ATLAS RC15 — recovered requirements and release gate (2026-10-16)

Source: user decisions across prior ATLAS/SUNGHO-Stock-Scanner conversations, cross-checked with VERIFICATION_KO.md. This is a task tracker, not evidence of deployed functionality.

## Automatic PT/KST preopen implementation (2026-10-16)
- [x] GitHub Actions schedule KST 07:00, 07:50, 07:55 (PT previous day 15:00/15:50/15:55 PDT; 14:00/14:50/14:55 PST); market holiday gate XKRX
- [x] Historical EOD-only WATCH shortlist from disclosed initial 24 Korean symbols; verified public FinanceDataReader dry-run: 24 attempted, 6 passed, 5 displayed. This is NOT full-market coverage or verified future winners.
- [x] App loads same-session published snapshot automatically (45s cache) with no manual Scan and PT/KST timestamp labels; actual scheduled GitHub publication and remote Streamlit rendering remain to verify.
- [x] A uses NXT authenticated WS source gating 08:00 onward; B independently reranks NXT candidates if same WS has valid NX ticks, then KRX regular session.
- [ ] Connect official preopen news/catalysts and investor EOD flow to background scoring; currently technical EOD-only
- [ ] Verify first real scheduled job and GitHub push rights, snapshot availability and deployed app on Sunday PT / Monday KST
- [ ] Replace browser-open-only WS with persistent authenticated market-hours worker and durable predictions/outcomes; no claims of 24/7 monitoring

## P0 — user priority: discover leaders BEFORE the breakout (2026-10-16)
- [x] Pure catalyst-to-sector-to-leader evidence ranking with fail-closed tests (feature branch; NOT wired to a verified live news feed)
- [ ] Pre-open KR/US independent pipeline: official filings, company IR, verified news, earnings, CPI/FOMC, macro, geopolitics/war and supply chain; use actual publication timestamps, source links, dedupe and cross-source confirmation
- [ ] Determine directional sector exposure with uncertainty, then map beneficiaries, competitors and *sector leaders* by liquidity, relative strength, volume/turnover acceleration and same-time baseline
- [ ] Overlay investor EOD flows vs real-time program/trade/book data separately; VWAP, MA20, Bollinger, RSI, MACD/OSC, distance, spread and invalidation; avoid late breakout chasing
- [ ] Publish only the strongest KR TOP3 and US TOP3 *before* surge in separate on-screen panels; update during sessions, cancel stale/failed candidates and show source timestamp, price, entry/stop/target, rationale and risk
- [ ] Capture predictions at issue time, subsequent 5m/30m/EOD/3d outcomes and fees/slippage, assess hit rate, net expectancy, drawdown and false positives vs a naive momentum baseline; no success claim without out-of-sample evidence
- [ ] Verify news providers' actual auth, rate limits, licensing and stream deployment; do not claim autonomous 24/7 monitoring from an open Streamlit tab

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
