# Complete SEC collection, separate from analytical metric mappings

The source now contains two compatible entry points:

1. The existing Node.js website has a **Complete SEC data** view. It displays every
   returned Company Facts observation, exports all observations, obtains the full
   filing report index, collects every indexed report and the extracted XBRL instance,
   and organizes original income, balance, cash-flow, comprehensive-income, equity
   and footnote reports. Documents are fetched sequentially from SEC. Per-document
   errors are displayed. The collection stops only after the current request if the
   visitor presses Stop. Exports preserve all collected reports and source references.
2. The new `sec_collector` Python package provides durable local bulk collection.
   It also retrieves older submission history, originals, schemas, presentation,
   calculation, definition and label/reference networks, structured report tables,
   all instance facts and an SQLite index. See `sec_collector/README.md`.

The extraction scope has no metric-name whitelist. Ratio mappings remain a separate
analytical layer. Adding a custom ratio no longer requires downloading the company
again if its input already exists in the collected dataset.

## Source and scope

Company Facts provides all returned standard-taxonomy, entity-wide observations.
It does not include all custom or dimensional facts. Those come from the extracted
instance and original filings. Every source value is preserved before analytical
mapping. Original rendered report text and tables avoid reducing whole statements
to selected revenue/assets/debt aliases.

The website collects a selected filing on demand. The local collector defaults to
recent matching annual/quarterly filings; `--all-filings` collects all matching
history and `--forms ALL --all-documents` additionally downloads every discovered
form's archive documents. A selected filing is not the same as the entire company
history. Manifests report the exact selection, download errors and parse errors.

PDF/image exhibits are retained as original binary files with `--all-documents`;
no OCR is performed. Old/non-XBRL filings may have no FilingSummary or extracted XML.
Original files are retained and structural absence is reported. Full external
standard taxonomies are not recursively downloaded. Both parsers preserve raw
source; neither claims complete XBRL validation or accounting interpretation.

## Analytical fixes in this update

- Stock compensation supports standard reported expense and cash-flow tags.
- Broader reported productive-asset purchases are a labelled CapEx proxy when
  PP&E-specific payments are unavailable; the original concept remains retained.
- Receivables, depreciation, marketable securities and interest mappings expanded.
- Inventory may be derived from disclosed FIFO inventory less LIFO reserve.
- COGS may be derived from aligned revenue minus gross profit.
- DCF offers reported CFO-minus-CapEx and separate disclosed-SBC-adjusted variants.
  Missing SBC does not automatically block the reported-FCF variant or equal zero.
- Coverage uses applicable ratios as its denominator and reports exclusions.

Fresh KR, WMK and WMT Company Facts were used to verify the cash-flow gates. This
is not validation of intrinsic-value accuracy or of the current market quotes.
Original model/valuation assumptions and financial-sector safeguards still apply.
