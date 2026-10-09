"""Reusable lossless JSON/JSONL, relational CSV, and table exports."""
import csv, json
from pathlib import Path

def write_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def write_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as stream:
        for row in rows: stream.write(json.dumps(row, ensure_ascii=False)+'\n')

def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list,dict)) else v for k,v in row.items()})

def company_fact_rows(raw):
    for namespace, concepts in raw.get('facts', {}).items():
        for concept, obj in concepts.items():
            for unit, observations in obj.get('units', {}).items():
                for observation in observations:
                    yield {'namespace':namespace,'concept':concept,'label':obj.get('label'), 'description':obj.get('description'),'unit':unit,**observation}
