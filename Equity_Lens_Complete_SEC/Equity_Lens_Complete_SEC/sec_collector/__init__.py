"""SEC archival collection without a financial-metric whitelist."""
from .client import SECClient
from .parsers import parse_instance, parse_linkbase, parse_filing_summary, parse_html
from .collect import collect_company, collect_filing

__all__ = ['SECClient', 'collect_company', 'collect_filing', 'parse_instance', 'parse_linkbase', 'parse_filing_summary', 'parse_html']
