"""Financial Shenanigans-inspired SEC 10-K red-flag screener.
Install: pip install requests pandas
Run: python financial_shenanigans_screener.py AAPL
Set SEC_USER_AGENT to 'Your Name your.email@example.com' before running.
"""
import os
import sys
import time
import requests
import pandas as pd

UA = os.environ.get('Tate Smith', 'tate2002s@gmail.com')
if UA == 'Research Screener research@example.com':
    raise SystemExit('Set SEC_USER_AGENT to your real name and email, e.g. "Jane Doe jane@example.com".')
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate', 'Host': 'data.sec.gov'})


def get_json(url):
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def find_cik(ticker):
    # The ticker file is hosted on www.sec.gov, not data.sec.gov.
    r = requests.get('https://www.sec.gov/files/company_tickers.json',
                     headers={'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate'}, timeout=30)
    r.raise_for_status()
    for item in r.json().values():
        if item['ticker'].upper() == ticker.upper():
            return int(item['cik_str']), item['title']
    raise ValueError(f'Ticker not found in SEC listing: {ticker}')


# Each item is a tuple of alternative standard US-GAAP XBRL tags.
TAGS = {
    'revenue': ('RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues',
                'SalesRevenueNet', 'RevenueFromContractWithCustomerIncludingAssessedTax'),
    'net_income': ('NetIncomeLoss',),
    'cfo': ('NetCashProvidedByUsedInOperatingActivities',),
    'receivables': ('AccountsNotesAndOtherReceivablesNetCurrent',
                    'AccountsReceivableNetCurrent'),
    'inventory': ('InventoryNet',),
    'cogs': ('CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold'),
    'assets': ('Assets',),
    'intangibles': ('Goodwill',),
    'capex': ('PaymentsToAcquirePropertyPlantAndEquipment',),
}
FLOW = {'revenue', 'net_income', 'cfo', 'cogs', 'capex'}


def annual_points(facts, key):
    """Select full-year 10-K values; for stocks, select FY-end balance-sheet values.
    Latest-filed value for each fiscal year is used (may include restatements).
    """
    gaap = facts.get('facts', {}).get('us-gaap', {})
    for tag in TAGS[key]:
        values = gaap.get(tag, {}).get('units', {}).get('USD', [])
        chosen = {}
        for p in values:
            if p.get('form') not in ('10-K', '10-K/A') or p.get('fp') != 'FY':
                continue
            if not p.get('fy') or not p.get('end') or not p.get('filed'):
                continue
            if key in FLOW:
                if not p.get('start'):
                    continue
                duration = (pd.Timestamp(p['end']) - pd.Timestamp(p['start'])).days
                if not 330 <= duration <= 380:
                    continue
            else:
                # Balance sheet values are instant values; FY can refer to comparative periods.
                # Only accept observations ending near the reported fiscal year end.
                if abs(pd.Timestamp(p['end']).year - int(p['fy'])) > 1:
                    continue
            year = pd.Timestamp(p['end']).year
            # For 52/53-week fiscal years, year of fiscal-year end is consistent across metrics.
            old = chosen.get(year)
            if old is None or (p['filed'], p.get('accn', '')) > (old['filed'], old.get('accn', '')):
                chosen[year] = p
        if chosen:
            return {y: float(p['val']) for y, p in chosen.items()}
    return {}


def pct_change(current, prior):
    if pd.isna(current) or pd.isna(prior) or prior <= 0:
        return float('nan')
    return current / prior - 1


def run(ticker):
    cik, name = find_cik(ticker)
    facts = get_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')
    series = {k: annual_points(facts, k) for k in TAGS}
    years = sorted(set().union(*(s.keys() for s in series.values())))
    df = pd.DataFrame(index=years, data={k: pd.Series(v) for k, v in series.items()})
    df = df.sort_index().tail(6)
    if len(df) < 2:
        raise ValueError('Not enough comparable SEC annual XBRL data for this company.')
    df['revenue_growth'] = df['revenue'].pct_change(fill_method=None)
    df['receivables_growth'] = df['receivables'].pct_change(fill_method=None)
    df['inventory_growth'] = df['inventory'].pct_change(fill_method=None)
    df['dso'] = 365 * df['receivables'] / df['revenue'].where(df['revenue'] > 0)
    df['dio'] = 365 * df['inventory'] / df['cogs'].where(df['cogs'] > 0)
    df['accrual_ratio'] = (df['net_income'] - df['cfo']) / df['assets'].where(df['assets'] > 0)
    df['cfo_to_income'] = df['cfo'] / df['net_income'].where(df['net_income'] > 0)
    df['goodwill_assets'] = df['intangibles'] / df['assets'].where(df['assets'] > 0)
    latest, previous = df.iloc[-1], df.iloc[-2]
    flags = []
    missing = []

    def check(name, condition, available, reason):
        if not available:
            missing.append(name)
        elif condition:
            flags.append((name, reason))

    def has(*values):
        return all(pd.notna(x) for x in values)

    check('Receivables outpace sales',
          latest['receivables_growth'] - latest['revenue_growth'] > .15,
          has(latest['receivables_growth'], latest['revenue_growth']),
          'Receivables growth exceeds revenue growth by over 15 percentage points.')
    check('DSO deterioration', latest['dso'] - previous['dso'] > 7,
          has(latest['dso'], previous['dso']),
          'Days sales outstanding increased by over 7 days.')
    check('Earnings exceed operating cash flow',
          latest['net_income'] > 0 and latest['cfo'] < .7 * latest['net_income'],
          has(latest['net_income'], latest['cfo']),
          'Operating cash flow is below 70% of positive net income.')
    check('High accruals', latest['accrual_ratio'] > .10,
          has(latest['accrual_ratio']),
          '(Net income minus operating cash flow) exceeds 10% of assets.')
    check('Inventory outpaces sales',
          latest['inventory_growth'] - latest['revenue_growth'] > .15,
          has(latest['inventory_growth'], latest['revenue_growth']),
          'Inventory growth exceeds revenue growth by over 15 percentage points.')
    check('Inventory days deterioration', latest['dio'] - previous['dio'] > 10,
          has(latest['dio'], previous['dio']),
          'Days inventory outstanding increased by over 10 days.')

    print(f'\n{name} ({ticker.upper()}) | Latest annual period end: {df.index[-1]}')
    print('Financials in USD millions unless ratio/day; latest available restated filings may be used.')
    columns = ['revenue', 'net_income', 'cfo', 'receivables', 'inventory', 'cogs',
               'dso', 'dio', 'accrual_ratio']
    view = df[columns].tail(4).copy()
    for c in ['revenue', 'net_income', 'cfo', 'receivables', 'inventory', 'cogs']:
        view[c] /= 1_000_000
    print(view.round(2).to_string(na_rep='N/A'))
    evaluated = 6 - len(missing)
    print(f'\nRed flags: {len(flags)} / {evaluated} evaluable checks (6 total)')
    for name, why in flags:
        print(f'  [FLAG] {name}: {why}')
    if not flags:
        print('  No flags exceeded these thresholds.')
    if missing:
        print('  Not evaluated (missing/non-comparable data): ' + ', '.join(missing))
    print('\nThese are screening heuristics, NOT a fraud probability or investment recommendation.')
    print('Review the 10-K footnotes, accounting policies, acquisitions and industry context.')
    df.to_csv(f'{ticker.upper()}_financial_red_flags.csv', index_label='fiscal_end_year')
    print(f'Saved: {ticker.upper()}_financial_red_flags.csv')


if __name__ == '__main__':
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else 'DNUT')
    except (ValueError, requests.RequestException) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
