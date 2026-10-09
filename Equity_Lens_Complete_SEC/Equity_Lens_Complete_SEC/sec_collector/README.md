# Full SEC Data Collector

Python 3.10+; standard library only. This collector does not restrict downloads
to a list of financial ratios. It retains every returned Company Facts concept
and every observation, including zero values, all units, all fiscal periods,
filing dates and accession numbers. It also collects complete selected filings
from the SEC archive, including the original rendered reports.

## Run on Windows

Open PowerShell in the extracted project folder (the folder containing
`sec_collector` and `local-server.mjs`). Your installed Python 3.11 works:

```powershell
$env:SEC_USER_AGENT="Your Name your-real-email@example.com"
py -3.11 -m sec_collector WMT --max-filings 4 --output WMT_SEC
```

Replace the sample identity with your real name/contact email before running.
No pip install is needed. The email is only sent to SEC and is not exported.
The default selects the two newest matching annual/quarterly filings. Increase
`--max-filings` or use an accession to include the annual report you want.

Collect a specific annual filing:

```powershell
py -3.11 -m sec_collector WMT --accession 0000104169-26-000055 --output WMT_Annual
```

Collect the entire annual/quarterly history and every archive document:

```powershell
py -3.11 -m sec_collector WMT --all-filings --all-documents --output WMT_All
```

Include all filing forms, such as 8-Ks, proxy statements and registrations:

```powershell
py -3.11 -m sec_collector WMT --forms ALL --all-filings --all-documents --output WMT_Everything
```

This can mean thousands of documents. Downloads are sequential and cached.
Identified failed downloads/parses are retained in manifests; no partial dataset
is silently described as complete. Re-running benefits from the source cache.

## Organized output

- `companyfacts_raw.json`: original aggregate API data, without metric filtering.
- `companyfacts_all.jsonl` / `.csv`: every aggregated concept observation.
- `submissions_raw.json`, `submission_history/`: current and older history data.
- `filings_all.json` / `.csv`: every discovered filing record, all forms.
- `sec_data.sqlite`: queryable company facts, filing facts, reports and filings.
- `dataset_manifest.json`: scope, counts, selected filings and errors.
- `filings/<accession>/originals/`: exact downloaded SEC source bytes.
- `filings/<accession>/report_index.json`: the SEC's report ordering and titles.
- `filings/<accession>/organized/income_statement/`: complete original report tables/text.
- `.../balance_sheet/`, `.../cash_flow/`, `.../equity/`, `.../comprehensive_income/`.
- `.../footnotes/`: notes, accounting policies, tables and detailed schedules.
- `.../other_disclosures/` and `.../other_statements/`: retain unclassified reports.
- Every report has its complete table cells, rowspan/colspan metadata and TSV grids.
- `.../xbrl/facts.jsonl` / `.csv`: every standard/custom instance fact.
- `.../xbrl/<instance>/`: periods, entities, explicit/typed dimensions and units.
- `.../relationships/`: presentation, calculation, definition, label/reference and
  embedded footnote networks, preserving ordering, weights and preferred labels.
- `.../taxonomy/`: local schema concepts, IDs and role definitions.

Numeric instance values use exact decimal strings instead of floating-point
rounding. Nil, zero, absent and unparseable values remain distinguishable.
Text blocks and dimensional/segment facts remain available. Facts are linked
to original presentation roles; unclassified facts are still retained.

## Build on it

```python
from sec_collector import SECClient, collect_company

client = SECClient("Your Name your-real-email@example.com")
manifest = collect_company(client, "KR", "KR_SEC", max_filings=4)
```

```python
import sqlite3
connection = sqlite3.connect("KR_SEC/sec_data.sqlite")
rows = connection.execute("""
    SELECT concept, end, value_decimal, presentation_roles_json
    FROM filing_facts
    WHERE consolidated = 1 AND concept LIKE '%Revenue%'
    ORDER BY end DESC
""").fetchall()
```

Modules separate HTTP access, parsing, collection, exports, SQL indexing and CLI.
The analysis app's metric aliases do not constrain this collector.

## Limits

Full archives are not one JSON endpoint. Company Facts omits custom/dimensional
facts, so selected full filings are downloaded as a second layer. Some older or
non-XBRL filings have no rendered report index or extracted XML instance; their
original documents remain retained and this is reported. PDF/image-only exhibits
are preserved with `--all-documents`, but OCR is not performed. External full
standard taxonomies are not recursively downloaded. Raw XML relationships are
preserved; this is not a complete XBRL conformance or calculation-validation
engine. Data retrieval does not automatically make all ratios or valuations
applicable or correct.

Tests: `python -m unittest discover -s sec_collector/tests -v`.
