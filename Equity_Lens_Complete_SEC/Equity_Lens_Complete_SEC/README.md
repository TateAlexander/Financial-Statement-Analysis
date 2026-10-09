# Equity Lens — complete SEC collection

## Website on your Windows computer

1. Extract the ZIP fully.
2. Open the extracted Equity_Lens_Complete_SEC folder.
3. Double-click start_windows.bat (Node.js LTS must be installed).
4. Open http://127.0.0.1:8501 in your browser.
5. Enter a ticker and real contact email, then use the Complete SEC data tab.

Alternatively, open PowerShell in this folder and run `npm start`.
No npm install is needed. Keep the terminal open while using the website.

## Full local dataset

Your Python 3.11 works; no pip packages are needed. Open PowerShell in this folder:

```powershell
$env:SEC_USER_AGENT="Your Name your-real-email@example.com"
py -3.11 -m sec_collector WMT --max-filings 4 --output WMT_SEC
```

Replace the sample identity with your real name/email. This saves all Company Facts
observations, all discovered filing metadata, and four selected annual/quarterly
filings with their original reports, footnotes, tagged facts and relationships.

For every discovered filing form and every archive document:

```powershell
py -3.11 -m sec_collector WMT --forms ALL --all-filings --all-documents --output WMT_Everything
```

This may download thousands of documents. The default collects only two recent
matching annual/quarterly filings. For a specific annual filing, use --accession.
See sec_collector/README.md for full instructions, output structure and Python/SQL
examples. SEC_COLLECTION.md explains the extraction and analytical changes.

Original statements and disclosures are organized separately from ratio inputs.
Exports include JSON, JSONL, CSV, TSV and sec_data.sqlite. Failed downloads and
parses are recorded. PDFs/images are preserved with --all-documents; no OCR runs.
Old/non-XBRL filings may lack structured report indexes or extracted instances.

## Verification

`npm test` checks the website logic.
`py -3.11 -m unittest discover -s sec_collector/tests -v` checks the collector.

Python package code: sec_collector/. Website code: worker/index.js.
Local server: local-server.mjs. Financial assumptions: METHODOLOGY.md.
