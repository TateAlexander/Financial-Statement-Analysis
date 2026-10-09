# Equity Lens research site

Private SEC research workspace. Company Facts and submissions are collected server-side;
market history comes from Yahoo's HTTP chart endpoint. All raw Company Facts concepts
remain in exported reports. A real contact email is required for SEC requests.

## Collection and statements

The Complete SEC data view retains every returned Company Facts observation and
collects every indexed rendered report plus the extracted XBRL instance for a
selected filing. `sec_collector` additionally preserves original bytes, complete
submission history, local schemas and relationships, exact numeric strings and
structured tables in JSONL, CSV, TSV and SQLite. See `SEC_COLLECTION.md` and the
collector README for selection flags and limits. Analytical aliases do not limit
this archival dataset.

Annual statements use exact fiscal start/end matches, USD units, standard consolidated
US-GAAP concepts and latest disclosed values. Same-end balances accompany annual flows.
Prior annual balances are used in average-balance ratios only when years are consecutive.
Latest balance data is separate. TTM flows use annual + current YTD − matched prior YTD;
per-share figures and average shares are not bridged by adding averages. Unavailable
components remain null. Annual ratios and TTM summaries are labelled separately.

Income, balance and cash-flow analytical views are organized independently of original
filing tables. Sources retain tags, filing dates, accessions, units and periods. Derived
values retain their component observations. Debt calculations require all applicable
mapped components; undisclosed short debt is not assumed to be zero.

Recent and older submission-history files can be inspected. Filing directory discovery
lists exhibits and XBRL files. Original SEC documents remain directly accessible.
Primary HTML and Inline XBRL extraction retains numeric facts, units, scaling, sign,
contexts, explicit/typed dimensions, text blocks and continuations. Unknown numeric
transforms and fractions are flagged for review, not interpreted speculatively.

Consolidated standard facts can fill matching annual statement gaps. Custom concepts
can be mapped explicitly to a named metric after review. Matching period/unit checks
apply; dimensional segment facts cannot substitute for consolidated ratios. Mapping
logs and filing URLs remain in exports. This parser is not a full XBRL conformance
processor and does not resolve every external calculation/presentation linkbase.

## Ratio library

Liquidity, capital returns, profitability, working-capital efficiency, leverage,
coverage, cash quality, reinvestment and growth have independent metric registrations.
Inventory ratios require a physical-inventory business model. All 11 sectors have
additional relevant disclosure metrics. Banking/insurance, energy, utilities, REIT,
SaaS and operational inputs frequently require reviewed filing mappings.

Statuses distinguish calculated, missing inputs, invalid/incomplete and not applicable.
Noncalculated rows never retain an apparently usable numerical value. Ratios preserve
current/prior source facts. Proxies (credit sales, purchases, reported equity, EBITDA,
ROIC, bank loans and claims) are labelled. SEC SIC financial classifications activate
financial safeguards even if the visitor selects a general operating-company sector.
The selector is not a licensed GICS classification.

## Forecasts

Revenue: at least six positive consecutive annual observations; rolling one-year MAE
compares flat, median growth and log-linear trend. Forecast horizon is one fiscal year
beyond the last annual report, not necessarily twelve months from today. Revenue
validation uses latest-restated history, not a point-in-time investment backtest.

Ratio-guided return: revenue growth, operating margin, net income/year-end assets,
and CFO/revenue feed a company-specific ridge regression (fixed penalty 10).
Historical features use filing-date cutoffs and exact annual period matches. Each
rolling training set contains outcomes already matured by its prediction anchor.
Six training years and at least eight later validation outcomes are required.
Earlier validation outcomes select ridge or the no-change baseline; a model frozen
before the later calibration period predicts calibration outcomes. If ridge does
not beat the no-change baseline in selection, no-change is selected.

Price benchmark: flat versus momentum uses nonoverlapping 252-trading-day outcomes.
At least eight annual outcomes are needed; earlier outcomes select the model and
later outcomes calibrate its residuals. No invented forecast replaces insufficient
history.

Intervals: symmetric 80% residual intervals in log-return space use the calibration
absolute-error order statistic at ceil((n+1)*0.8). No interval is produced when that
rank exceeds available calibration observations. Selection and calibration outcomes
are separate. Time-dependent financial returns are not demonstrably exchangeable,
so these intervals have no proven future coverage. They are prediction intervals,
not confidence intervals for intrinsic value. No independent final test establishes
out-of-sample investment performance. Historical adjusted returns include dividends;
targets are total-return-equivalent price levels. Banks/insurers/real estate return
regressions are withheld until appropriate specialized features are implemented.

## Valuation and peers

Equity DCF scenario: reported CFO − CapEx by default; optional disclosed-SBC-adjusted
variant uses CFO − CapEx − SBC. Both assume zero net borrowing and constant cash margin/shares.
Growth, cost of equity, terminal growth and 3–10 year horizon are editable. Discount
rate must exceed terminal growth. No duplicate debt subtraction or cash addition.
Missing SBC suppresses only the SBC-adjusted variant; it is not treated as zero.
Nonpositive cash flow suppresses the scenario. Financials/REIT DCFs
are withheld. Current prices and SEC share counts may have different observation dates.

Multiples, FCF yield and a constant-P/S revenue scenario are separate from the return
model. Peers can be entered manually or drawn from broad-sector curated examples.
Up to eight peer requests run sequentially. Ranking applies only to successfully
analyzed companies using the chosen metric. DCF upside/yield sort descending and
valuation multiples ascending. None establishes the cheapest company in a complete
sector or independently demonstrates undervaluation. Discount, terminal growth and
horizon settings are shared across peer requests; company revenue growth stays local.

## Verification and remaining work

`node tests.mjs` tests period alignment, TTM arithmetic, absent inputs, financial
eligibility, fiscal gaps, future disclosure leakage, ridge fitting, residual quantile
correction, document dimensions/scaling/continuations, reviewed mapping, DCF guards,
all eight frontend view render functions and descending peer ranking. Sources are
fixture-only. Worker/frontend syntax and deployment build artifacts are validated.
Browser visual QA and live SEC/Yahoo end-to-end analysis are not established by these
tests. Provider denial/rate limits are surfaced explicitly. Publishing success does
not imply successful upstream data retrieval.

Remaining substantial work: complete XBRL validation/presentation reconstruction,
company-specific footnote interpretation, specialist intrinsic valuations, genuine
matched industry universes and independently tested cross-company return models.
