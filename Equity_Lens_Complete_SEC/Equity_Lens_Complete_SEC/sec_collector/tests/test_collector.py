import json, tempfile, unittest
from pathlib import Path
from sec_collector.parsers import parse_instance,parse_linkbase,parse_schema,parse_html,parse_filing_summary,annotate_instance
from sec_collector.collect import collect_filing,filing_rows,safe_name
from sec_collector.export import company_fact_rows

INSTANCE=b'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:g="urn:gaap" xmlns:custom="urn:custom" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<xbrli:context id="a"><xbrli:entity><xbrli:identifier scheme="sec">1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="s"><xbrli:entity><xbrli:identifier>1</xbrli:identifier><xbrli:segment><xbrldi:typedMember dimension="custom:ProductAxis"><custom:Product>ABC</custom:Product></xbrldi:typedMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><g:Revenue contextRef="a" unitRef="USD" decimals="0" id="r">9007199254740993</g:Revenue><custom:EquityRollforward contextRef="a" unitRef="USD">0</custom:EquityRollforward><custom:Inventory contextRef="s" unitRef="USD">12</custom:Inventory><custom:DebtNoteTextBlock contextRef="a">&lt;p&gt;Debt &amp; maturity&lt;/p&gt;</custom:DebtNoteTextBlock><custom:Unavailable contextRef="a" unitRef="USD" xsi:nil="true"/></xbrli:xbrl>'''
SUMMARY=b'''<FilingSummary><MyReports><Report><HtmlFileName>R1.htm</HtmlFileName><ShortName>Consolidated Statements of Equity</ShortName><MenuCategory>Statements</MenuCategory><Role>urn:equity</Role><Position>1</Position></Report><Report><HtmlFileName>R2.htm</HtmlFileName><ShortName>Debt</ShortName><MenuCategory>Notes</MenuCategory><Role>urn:debt</Role><Position>2</Position></Report><Report><ReportType>Book</ReportType><ShortName>All Reports</ShortName></Report></MyReports></FilingSummary>'''
SCHEMA=b'''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:custom"><xs:element name="EquityRollforward" id="custom_EquityRollforward"/></xs:schema>'''
PRE=b'''<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"><link:presentationLink xlink:type="extended" xlink:role="urn:equity"><link:loc xlink:type="locator" xlink:label="a" xlink:href="custom.xsd#custom_EquityRollforward"/><link:loc xlink:type="locator" xlink:label="b" xlink:href="gaap.xsd#g_Revenue"/><link:presentationArc xlink:type="arc" xlink:from="a" xlink:to="b" order="1"/></link:presentationLink></link:linkbase>'''
HTML=b'<html><body><p>All disclosures</p><table><tr><th rowspan="2">Metric</th><th colspan="2">Year</th></tr><tr><th>2025</th><th>2024</th></tr><tr><td>Revenue</td><td>100</td><td>90</td></tr></table></body></html>'
class Tests(unittest.TestCase):
 def test_every_fact_and_dimension(self):
  result=parse_instance(INSTANCE,'source','accession','2026-01-01');self.assertEqual(len(result['facts']),5)
  self.assertEqual(result['facts'][0]['value_decimal'],'9007199254740993');self.assertEqual(result['facts'][1]['value_decimal'],'0')
  self.assertFalse(result['facts'][2]['consolidated']);self.assertEqual(result['facts'][2]['context']['dimensions'][0]['kind'],'typedMember')
  self.assertIn('<p>',result['facts'][3]['value_raw']);self.assertTrue(result['facts'][4]['nil'])
 def test_fraction_preserves_exact_components(self):
  fraction=INSTANCE.replace(b'</xbrli:xbrl>',b'<custom:Ratio contextRef="a" unitRef="USD"><xbrli:numerator>1</xbrli:numerator><xbrli:denominator>3</xbrli:denominator></custom:Ratio></xbrli:xbrl>')
  fact=parse_instance(fraction)['facts'][-1]
  self.assertEqual(fact['status'],'fraction');self.assertIsNone(fact['value_decimal'])
  self.assertEqual(fact['value_fraction'],{'numerator':'1','denominator':'3'})
 def test_roles_and_all_statements(self):
  reports=parse_filing_summary(SUMMARY);self.assertEqual(len(reports),2);self.assertEqual(reports[0]['category'],'equity');self.assertEqual(reports[1]['category'],'footnotes')
  result=annotate_instance(parse_instance(INSTANCE),reports,[parse_linkbase(PRE)],[parse_schema(SCHEMA)])
  self.assertEqual(result['facts'][1]['presentation_roles'][0]['category'],'equity');self.assertEqual(len(result['facts']),5)
 def test_tables(self):
  table=parse_html(HTML.decode())['tables'][0];self.assertEqual(table['grid'][1],['Metric','2025','2024']);self.assertEqual(table['grid'][2],['Revenue','100','90'])
 def test_no_whitelist(self):
  rows=list(company_fact_rows({'facts':{'custom':{'Anything':{'units':{'pure':[{'val':0}]}}}}}));self.assertEqual(rows[0]['concept'],'Anything');self.assertEqual(rows[0]['val'],0)
 def test_complete_collection_and_explicit_partial(self):
  root='https://www.sec.gov/Archives/edgar/data/1/000000000125000001/'
  sources={'index.json':json.dumps({'directory':{'item':[{'name':n} for n in ['FilingSummary.xml','R1.htm','R2.htm','instance.xml','custom.xsd','custom_pre.xml','primary.htm','exhibit.pdf']]}}).encode(),'FilingSummary.xml':SUMMARY,'R1.htm':HTML,'R2.htm':HTML,'instance.xml':INSTANCE,'custom.xsd':SCHEMA,'custom_pre.xml':PRE,'primary.htm':HTML,'exhibit.pdf':b'%PDF'}
  class Client:
   def get_bytes(self,url):return sources[url.removeprefix(root)]
  with tempfile.TemporaryDirectory() as temp:
   result=collect_filing(Client(),'0000000001',{'accessionNumber':'0000000001-25-000001','primaryDocument':'primary.htm'},temp,True)
   self.assertEqual(result['status'],'complete_for_selected_filing');self.assertEqual(result['fact_count'],5);self.assertEqual(result['report_count'],2)
   folder=Path(temp)/'0000000001-25-000001';self.assertTrue((folder/'organized/equity/R1/report.json').exists());self.assertTrue((folder/'organized/footnotes/R2/table_001.tsv').exists());self.assertTrue((folder/'originals/exhibit.pdf').exists())
 def test_paths(self):
  with self.assertRaises(ValueError):safe_name('../outside')
  self.assertEqual(len(list(filing_rows({'accessionNumber':['x'],'form':['10-K']}))),1)

class DatasetTests(unittest.TestCase):
 def test_company_export_keeps_all_history_and_sql(self):
  import sqlite3
  from sec_collector.collect import collect_company
  sources={'index.json':json.dumps({'directory':{'item':[{'name':n} for n in ['FilingSummary.xml','R1.htm','R2.htm','instance.xml','custom.xsd','custom_pre.xml','primary.htm']]}}).encode(),'FilingSummary.xml':SUMMARY,'R1.htm':HTML,'R2.htm':HTML,'instance.xml':INSTANCE,'custom.xsd':SCHEMA,'custom_pre.xml':PRE,'primary.htm':HTML}
  class Client:
   def resolve(self,symbol):return '0000000001'
   def get_json(self,url):
    if 'companyfacts' in url:return {'facts':{'ifrs-full':{'UnexpectedMetric':{'units':{'EUR':[{'val':0,'end':'2025-12-31','form':'20-F'}]}}}}}
    if 'submissions-001' in url:return {'accessionNumber':['0000000001-24-000002'],'form':['DEF 14A'],'filingDate':['2024-01-01'],'primaryDocument':['proxy.htm']}
    return {'name':'Fixture','filings':{'recent':{'accessionNumber':['0000000001-25-000001'],'form':['10-K'],'filingDate':['2025-01-01'],'primaryDocument':['primary.htm']},'files':[{'name':'CIK0000000001-submissions-001.json'}]}}
   def get_bytes(self,url):return sources[url.rsplit('/',1)[-1]]
  with tempfile.TemporaryDirectory() as temp:
   result=collect_company(Client(),'FIXTURE',temp,max_filings=1)
   self.assertEqual(result['companyfacts_observations'],1);self.assertEqual(result['discovered_filings'],2);self.assertEqual(result['filings'][0]['fact_count'],5)
   db=sqlite3.connect(Path(temp)/'sec_data.sqlite')
   self.assertEqual(db.execute('SELECT value_text FROM company_facts').fetchone()[0],'0')
   self.assertEqual(db.execute("SELECT value_decimal FROM filing_facts WHERE concept='Revenue'").fetchone()[0],'9007199254740993')
   self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0],2);db.close()

if __name__=='__main__':unittest.main()
