"""Orchestration: retain every available fact; organize full filing report indexes."""
from __future__ import annotations
import csv, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from .export import write_json, write_jsonl, write_csv, company_fact_rows
from .parsers import parse_filing_summary, parse_instance, parse_linkbase, parse_schema, parse_html, annotate_instance, xml_root, local

FORMS_DEFAULT={'10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','40-F','40-F/A'}

def filing_rows(columns):
    for i,accession in enumerate(columns.get('accessionNumber',[])):
        yield {key:values[i] if i<len(values) else None for key,values in columns.items() if isinstance(values,list)}

def safe_name(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',name):raise ValueError(f'Invalid SEC document basename: {name!r}')
    return name

def archive_url(cik, accession):
    if not str(cik).isdigit() or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession):raise ValueError('Invalid CIK or accession.')
    return f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/'

def collect_filing(client, cik, filing, output_dir, all_documents=False, progress=None):
    accession=filing['accessionNumber'];root=archive_url(cik,accession);folder=Path(output_dir)/accession
    folder.mkdir(parents=True,exist_ok=True)
    manifest={'accession':accession,'cik':cik,'filing':filing,'archive_url':root,'retrieved_at':datetime.now(timezone.utc).isoformat(),'downloads':[],'errors':[],'reports':[],'status':'collecting'}
    write_json(folder/'manifest.json',manifest)
    def download(name):
        name=safe_name(name);path=folder/'originals'/name;url=root+quote(name)
        try:
            data=client.get_bytes(url)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            manifest['downloads'].append({'name':name,'url':url,'bytes':len(data),'path':str(path.relative_to(folder))})
            return data
        except Exception as exc:
            manifest['errors'].append({'name':name,'url':url,'error':str(exc)});return None
    index_bytes=download('index.json')
    if index_bytes is None:
        manifest['status']='failed';write_json(folder/'manifest.json',manifest);return manifest
    import json
    index=json.loads(index_bytes);items=index.get('directory',{}).get('item',[]);names={row['name'] for row in items if row.get('type')!='dir'}
    summary=download('FilingSummary.xml') if 'FilingSummary.xml' in names else None
    if summary:
        try:manifest['reports']=parse_filing_summary(summary)
        except Exception as exc:manifest['errors'].append({'name':'FilingSummary.xml','error':str(exc)})
    else:manifest['errors'].append({'name':'FilingSummary.xml','error':'No rendered report index is available for this filing; original documents are retained.'})
    write_json(folder/'report_index.json',manifest['reports'])
    selected=set()
    if filing.get('primaryDocument'):selected.add(filing['primaryDocument'])
    selected.update(r.get('HtmlFileName') or r.get('XmlFileName') for r in manifest['reports'])
    selected.update(name for name in names if name.lower().endswith(('.xml','.xsd')))
    if all_documents:selected.update(names)
    selected.discard(None);selected-= {'index.json','FilingSummary.xml'}
    instances=[];linkbases=[];schemas=[];primary_extracted=None
    reports_by_file={r.get('HtmlFileName') or r.get('XmlFileName'):r for r in manifest['reports']}
    for counter,name in enumerate(sorted(selected),1):
        if progress:progress(f'{accession}: document {counter}/{len(selected)} — {name}')
        try:data=download(name)
        except Exception as exc:manifest['errors'].append({'name':str(name),'error':str(exc)});continue
        if data is None:continue
        try:
            lower=name.lower()
            if lower.endswith(('.htm','.html')):
                document=parse_html(data.decode('utf-8',errors='replace'))
                if name in reports_by_file:
                    meta=reports_by_file[name];category=meta['category'];report_dir=folder/'organized'/category/Path(name).stem
                    write_json(report_dir/'report.json',{'metadata':meta,'source_url':root+name,**document})
                    (report_dir/'text.txt').write_text(document['text'],encoding='utf-8')
                    for table_i,table in enumerate(document['tables'],1):
                        with (report_dir/f'table_{table_i:03}.tsv').open('w',encoding='utf-8-sig',newline='') as stream:csv.writer(stream,delimiter='\t').writerows(table['grid'])
                elif name==filing.get('primaryDocument'):
                    primary_extracted=document;write_json(folder/'primary_document.json',{'source_url':root+name,**document})
            elif lower.endswith('.xsd'):
                schema=parse_schema(data);schemas.append(schema);write_json(folder/'taxonomy'/f'{Path(name).stem}.json',schema)
            elif lower.endswith('.xml'):
                xml_element,_=xml_root(data)
                if local(xml_element.tag)=='xbrl':
                    instance=parse_instance(data,root+name,accession,filing.get('filingDate',''));instance['source_file']=name;instances.append(instance)
                    embedded=parse_linkbase(data,root+name)
                    if embedded['networks']:linkbases.append(embedded);write_json(folder/'relationships'/f'{Path(name).stem}_embedded.json',embedded)
                else:
                    linkbase=parse_linkbase(data,root+name)
                    if linkbase['networks']:
                        linkbases.append(linkbase);write_json(folder/'relationships'/f'{Path(name).stem}.json',linkbase)
        except Exception as exc:manifest['errors'].append({'name':name,'stage':'parse','error':str(exc)})
        write_json(folder/'manifest.json',manifest)
    facts=[]
    for instance in instances:
        annotate_instance(instance,manifest['reports'],linkbases,schemas)
        facts.extend(instance['facts'])
        write_json(folder/'xbrl'/Path(instance.get('source_file','instance')).stem/'contexts.json',instance['contexts'])
        write_json(folder/'xbrl'/Path(instance.get('source_file','instance')).stem/'units.json',instance['units'])
        write_json(folder/'xbrl'/Path(instance.get('source_file','instance')).stem/'namespaces.json',instance['namespaces'])
    # Never collapse observations merely because values or concept names coincide.
    write_jsonl(folder/'xbrl'/'facts.jsonl',facts)
    write_csv(folder/'xbrl'/'facts.csv',facts, ['id','qname','namespace','concept','value_decimal','value_raw','status','context_ref','context','unit_ref','unit','decimals','consolidated','presentation_roles','source_url','accession','filed'])
    for category in sorted({role['category'] for fact in facts for role in fact['presentation_roles'] if role.get('category')}):
        write_jsonl(folder/'organized'/category/'tagged_facts.jsonl',(f for f in facts if any(r.get('category')==category for r in f['presentation_roles'])))
    if not instances:manifest['errors'].append({'stage':'xbrl','error':'No extracted XML instance found. Original Inline XBRL HTML and rendered reports remain retained; XML instance facts were not fabricated.'})
    manifest.update({'fact_count':len(facts),'numeric_fact_count':sum(f['status'] in {'numeric','fraction'} for f in facts),'text_fact_count':sum(f['status']=='text' for f in facts),'report_count':len(manifest['reports']),'statement_count':sum(r['category'] in {'income_statement','balance_sheet','cash_flow','equity','comprehensive_income','other_statements'} for r in manifest['reports']),'footnote_report_count':sum(r['category']=='footnotes' for r in manifest['reports']),'status':'partial' if manifest['errors'] else 'complete_for_selected_filing'})
    write_json(folder/'manifest.json',manifest)
    return manifest

def collect_company(client, symbol, output_dir, max_filings=2, forms=None, accession=None, all_documents=False, include_older_history=True, progress=None):
    cik=client.resolve(symbol);root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    raw=client.get_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')
    submissions=client.get_json(f'https://data.sec.gov/submissions/CIK{cik}.json')
    write_json(root/'companyfacts_raw.json',raw);write_json(root/'submissions_raw.json',submissions)
    observations=list(company_fact_rows(raw));write_jsonl(root/'companyfacts_all.jsonl',observations);write_csv(root/'companyfacts_all.csv',observations)
    history=list(filing_rows(submissions.get('filings',{}).get('recent',{})));history_errors=[]
    if include_older_history:
        for older in submissions.get('filings',{}).get('files',[]):
            name=safe_name(older['name'])
            if not re.fullmatch(r'CIK\d{10}-submissions-\d+\.json',name):continue
            try:
                old=client.get_json('https://data.sec.gov/submissions/'+name)
                write_json(root/'submission_history'/name,old);history.extend(filing_rows(old))
            except Exception as exc:history_errors.append({'name':name,'error':str(exc)})
    history=list({f['accessionNumber']:f for f in history}.values());history.sort(key=lambda f:(f.get('filingDate') or '',f['accessionNumber']),reverse=True)
    write_json(root/'filings_all.json',history);write_csv(root/'filings_all.csv',history)
    forms=FORMS_DEFAULT if forms is None else set(forms)
    selected=[f for f in history if (not forms or f.get('form') in forms) and (not accession or f['accessionNumber']==accession)]
    if accession and not selected:raise ValueError('Requested accession is not present in the collected company history or selected forms.')
    if max_filings is not None:selected=selected[:max_filings]
    manifests=[]
    for filing in selected:
        try:manifests.append(collect_filing(client,cik,filing,root/'filings',all_documents,progress))
        except Exception as exc:manifests.append({'accession':filing['accessionNumber'],'status':'failed','errors':[{'error':str(exc)}]})
    dataset={'schema_version':'2.0','cik':cik,'entity_name':submissions.get('name'),'symbol':symbol,'retrieved_at':datetime.now(timezone.utc).isoformat(),'companyfacts_observations':len(observations),'companyfacts_concepts':sum(len(v) for v in raw.get('facts',{}).values()),'discovered_filings':len(history),'collected_filings':len(manifests),'history_errors':history_errors,'filings':manifests,'selection':{'max_filings':max_filings,'forms':sorted(forms),'accession':accession,'all_documents':all_documents},'scope':'All returned Company Facts concepts and observations; all discovered filing metadata; selected full filings only. Original bytes and unmapped facts remain preserved.'}
    write_json(root/'dataset_manifest.json',dataset)
    from .database import build_database
    try:dataset['sqlite_database']=str(build_database(root))
    except Exception as exc:dataset['database_error']=str(exc)
    write_json(root/'dataset_manifest.json',dataset)
    return dataset
