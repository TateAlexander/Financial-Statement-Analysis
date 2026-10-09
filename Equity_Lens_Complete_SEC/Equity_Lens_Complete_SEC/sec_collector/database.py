"""Optional relational index over the loss-preserving exported dataset."""
import json, sqlite3
from pathlib import Path

def build_database(output_dir):
    root=Path(output_dir);db=root/'sec_data.sqlite'
    connection=sqlite3.connect(db)
    try:
        connection.executescript('''
        DROP TABLE IF EXISTS company_facts;
        DROP TABLE IF EXISTS filing_facts;
        DROP TABLE IF EXISTS reports;
        DROP TABLE IF EXISTS filings;
        CREATE TABLE company_facts(namespace TEXT, concept TEXT, label TEXT, unit TEXT, start TEXT, end TEXT, filed TEXT, form TEXT, accession TEXT, value_text TEXT, observation_json TEXT);
        CREATE TABLE filing_facts(accession TEXT, concept TEXT, namespace TEXT, context_ref TEXT, start TEXT, end TEXT, unit_json TEXT, value_decimal TEXT, value_raw TEXT, status TEXT, consolidated INTEGER, dimensions_json TEXT, presentation_roles_json TEXT, source_url TEXT, fact_json TEXT);
        CREATE TABLE reports(accession TEXT, category TEXT, name TEXT, menu_category TEXT, role TEXT, html_file TEXT, metadata_json TEXT);
        CREATE TABLE filings(accession TEXT PRIMARY KEY, form TEXT, filed TEXT, report_date TEXT, status TEXT, manifest_path TEXT);
        CREATE INDEX company_facts_concept_period ON company_facts(concept,end);
        CREATE INDEX filing_facts_concept_period ON filing_facts(concept,end);
        CREATE INDEX reports_category ON reports(category);
        ''')
        with (root/'companyfacts_all.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                f=json.loads(line)
                connection.execute('INSERT INTO company_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(f.get('namespace'),f.get('concept'),f.get('label'),f.get('unit'),f.get('start'),f.get('end'),f.get('filed'),f.get('form'),f.get('accn'),str(f['val']) if 'val' in f else None,line.strip()))
        for path in sorted((root/'filings').glob('*/manifest.json')):
            m=json.loads(path.read_text());meta=m.get('filing',{});acc=m['accession']
            connection.execute('INSERT INTO filings VALUES(?,?,?,?,?,?)',(acc,meta.get('form'),meta.get('filingDate'),meta.get('reportDate'),m.get('status'),str(path.relative_to(root))))
            for r in m.get('reports',[]):
                connection.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?)',(acc,r.get('category'),r.get('ShortName'),r.get('MenuCategory'),r.get('Role'),r.get('HtmlFileName') or r.get('XmlFileName'),json.dumps(r)))
            facts=path.parent/'xbrl/facts.jsonl'
            if facts.exists():
                with facts.open(encoding='utf-8') as stream:
                    for line in stream:
                        f=json.loads(line);ctx=f.get('context') or {}
                        connection.execute('INSERT INTO filing_facts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(acc,f.get('concept'),f.get('namespace'),f.get('context_ref'),ctx.get('start'),ctx.get('end'),json.dumps(f.get('unit')),f.get('value_decimal'),f.get('value_raw'),f.get('status'),int(f.get('consolidated',False)),json.dumps(ctx.get('dimensions',[])),json.dumps(f.get('presentation_roles',[])),f.get('source_url'),line.strip()))
        connection.commit()
    finally:connection.close()
    return db
