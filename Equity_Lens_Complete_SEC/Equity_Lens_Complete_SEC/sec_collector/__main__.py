import argparse, os
from pathlib import Path
from .client import SECClient
from .collect import collect_company

def main():
    p=argparse.ArgumentParser(description='Collect full SEC facts, filing reports, equity statements, footnotes, custom XBRL and taxonomy relationships.')
    p.add_argument('symbol',help='Ticker or numeric CIK')
    p.add_argument('--identity',default=os.getenv('SEC_USER_AGENT') or ('Equity Lens Collector '+os.environ['SEC_EMAIL'] if os.getenv('SEC_EMAIL') else None),help='Your name/application and real contact email; or set SEC_USER_AGENT')
    p.add_argument('--output',default=None,help='Output directory; default: SEC_<symbol>')
    p.add_argument('--max-filings',type=int,default=2,help='Number of matching filings; default 2. Use --all-filings for the complete matching history.')
    p.add_argument('--all-filings',action='store_true',help='Collect all matching discovered filings; may involve thousands of documents.')
    p.add_argument('--forms',default='10-K,10-K/A,10-Q,10-Q/A,20-F,20-F/A,40-F,40-F/A',help='Comma-separated forms, or ALL for every discovered form')
    p.add_argument('--accession',help='Collect a single exact accession number')
    p.add_argument('--all-documents',action='store_true',help='Also retain every archive item: exhibits, PDF, images and other binary files')
    p.add_argument('--recent-history-only',action='store_true',help='Do not load older submissions metadata')
    p.add_argument('--cache-dir',default='.sec_cache')
    p.add_argument('--quiet',action='store_true')
    args=p.parse_args()
    if args.max_filings<1:p.error('--max-filings must be positive')
    try:
        client=SECClient(args.identity,args.cache_dir)
        output=args.output or ('SEC_'+str(args.symbol).upper())
        result=collect_company(client,args.symbol,output,max_filings=None if args.all_filings else (1 if args.accession else args.max_filings),forms=[] if args.forms.upper()=='ALL' else args.forms.split(','),accession=args.accession,all_documents=args.all_documents,include_older_history=not args.recent_history_only,progress=None if args.quiet else lambda msg:print(msg,flush=True))
        print(f"Saved {result['companyfacts_observations']:,} API observations across {result['companyfacts_concepts']:,} concepts; {result['discovered_filings']:,} filing records; {result['collected_filings']} full filings to {Path(output).resolve()}")
        for filing in result['filings']:print(f"  {filing['accession']}: {filing['status']}; {filing.get('fact_count',0):,} XBRL facts; {filing.get('report_count',0)} reports; {len(filing.get('errors',[]))} errors")
    except Exception as exc:p.exit(1,f'Collection failed: {exc}\n')

if __name__=='__main__':main()
