"""Loss-preserving SEC report, HTML table, XBRL and linkbase parsers."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import BytesIO
import re
import xml.etree.ElementTree as ET

XBRLI='http://www.xbrl.org/2003/instance'
XLINK='http://www.w3.org/1999/xlink'
XSI='http://www.w3.org/2001/XMLSchema-instance'

def local(name): return name.rsplit('}',1)[-1].split(':')[-1]
def text(element): return ''.join(element.itertext()).strip() if element is not None else ''
def xml_root(data):
    data = data.encode() if isinstance(data, str) else data
    if b'<!DOCTYPE' in data.upper(): raise ValueError('DTD-bearing XML requires explicit review; original bytes are retained.')
    namespaces = dict((prefix or '', uri) for _,(prefix,uri) in ET.iterparse(BytesIO(data),events=['start-ns']))
    return ET.fromstring(data), namespaces

def report_category(name, menu=''):
    n=name.lower()
    if menu.lower() not in {'statements', 'statement'}:
        if menu.lower() in {'notes','tables','details','policies'}: return 'footnotes'
        return 'other_disclosures'
    if 'comprehensive' in n: return 'comprehensive_income'
    if 'balance sheet' in n or 'financial position' in n: return 'balance_sheet'
    if 'cash flow' in n or 'cashflow' in n: return 'cash_flow'
    if any(x in n for x in ['equity','stockholder','shareholder','changes in net assets']): return 'equity'
    if any(x in n for x in ['income','operations','earnings','profit','loss']): return 'income_statement'
    return 'other_statements'

def parse_filing_summary(data):
    root, _=xml_root(data)
    reports=[]
    for element in root.iter():
        if local(element.tag)!='Report': continue
        row={local(child.tag):text(child) for child in element}
        if row.get('ReportType')=='Book' and not row.get('HtmlFileName') and not row.get('XmlFileName'):continue
        row['instance']=element.get('instance')
        row['category']=report_category(row.get('ShortName',''),row.get('MenuCategory',''))
        row['position']=int(row.get('Position') or len(reports)+1)
        reports.append(row)
    return sorted(reports,key=lambda row:row['position'])

def parse_instance(data, source_url='', accession='', filed=''):
    root,namespaces=xml_root(data)
    contexts={}; units={}; facts=[]
    for element in root.iter():
        if element.tag=='{'+XBRLI+'}context':
            identifier=next((e for e in element.iter() if local(e.tag)=='identifier'),None)
            period=next((e for e in element if local(e.tag)=='period'),None)
            dates={local(e.tag):text(e) for e in period} if period is not None else {}
            dimensions=[]
            for member in element.iter():
                if local(member.tag) in {'explicitMember','typedMember'}:
                    dimensions.append({'axis':member.get('dimension'),'member':text(member), 'kind':local(member.tag),'xml':ET.tostring(member,encoding='unicode')})
            contexts[element.get('id')]={'id':element.get('id'),'entity':text(identifier),'entity_scheme':identifier.get('scheme') if identifier is not None else None,'start':dates.get('startDate'),'end':dates.get('endDate') or dates.get('instant'),'instant':dates.get('instant'),'forever':'forever' in dates,'dimensions':dimensions,'xml':ET.tostring(element,encoding='unicode')}
        elif element.tag=='{'+XBRLI+'}unit':
            numerator=[];denominator=[]
            den=next((e for e in element.iter() if local(e.tag)=='unitDenominator'),None)
            denominator=[text(e) for e in den.iter() if local(e.tag)=='measure'] if den is not None else []
            num=next((e for e in element.iter() if local(e.tag)=='unitNumerator'),None)
            numerator=[text(e) for e in (num if num is not None else element).iter() if local(e.tag)=='measure']
            units[element.get('id')]={'id':element.get('id'),'numerator':numerator,'denominator':denominator,'xml':ET.tostring(element,encoding='unicode')}
    prefixes={uri:prefix for prefix,uri in namespaces.items() if prefix}
    for element in root.iter():
        context_ref=element.get('contextRef')
        if not context_ref: continue
        namespace=element.tag[1:].split('}')[0] if element.tag.startswith('{') else ''
        name=local(element.tag); value=text(element); context=contexts.get(context_ref); unit=units.get(element.get('unitRef'))
        numeric=None; fraction_value=None; status='text'
        if element.get('{'+XSI+'}nil') in {'true','1'}: status='nil'
        elif element.get('unitRef'):
            try:
                if any(local(child.tag)=='numerator' for child in element):
                    num=next(e for e in element if local(e.tag)=='numerator');den=next(e for e in element if local(e.tag)=='denominator')
                    fraction_value={'numerator':text(num),'denominator':text(den)};status='fraction'
                else:
                    parsed=Decimal(value)
                    if parsed.is_finite():numeric=str(parsed);status='numeric'
                    else:status='nonfinite'
            except (InvalidOperation,ZeroDivisionError,StopIteration): status='requires_review'
        facts.append({'id':element.get('id'),'namespace':namespace,'concept':name,'qname':(prefixes.get(namespace,namespace)+':'+name),'context_ref':context_ref,'context':context,'unit_ref':element.get('unitRef'),'unit':unit,'decimals':element.get('decimals'),'precision':element.get('precision'),'nil':status=='nil','value_raw':value,'value_decimal':numeric,'value_fraction':fraction_value,'status':status,'consolidated':bool(context and not context['dimensions']),'source_url':source_url,'accession':accession,'filed':filed,'attributes':dict(element.attrib),'xml':ET.tostring(element,encoding='unicode')})
    return {'namespaces':namespaces,'contexts':contexts,'units':units,'facts':facts}

def parse_linkbase(data, source_url=''):
    root,namespaces=xml_root(data);networks=[]
    for link in root.iter():
        if link.get('{'+XLINK+'}type')!='extended': continue
        role=link.get('{'+XLINK+'}role'); locators={}; resources={};arcs=[]
        for child in link:
            kind=child.get('{'+XLINK+'}type');label=child.get('{'+XLINK+'}label')
            if kind=='locator':locators[label]={'href':child.get('{'+XLINK+'}href'),'attributes':dict(child.attrib)}
            elif kind=='resource':resources.setdefault(label,[]).append({'text':text(child),'type':local(child.tag),'attributes':dict(child.attrib),'xml':ET.tostring(child,encoding='unicode')})
            elif kind=='arc':arcs.append({'from':child.get('{'+XLINK+'}from'),'to':child.get('{'+XLINK+'}to'),'arcrole':child.get('{'+XLINK+'}arcrole'),'order':child.get('order'),'weight':child.get('weight'),'preferred_label':child.get('preferredLabel'),'attributes':dict(child.attrib)})
        networks.append({'type':local(link.tag),'role':role,'locators':locators,'resources':resources,'arcs':arcs,'source_url':source_url})
    return {'namespaces':namespaces,'networks':networks}

def parse_schema(data):
    root,namespaces=xml_root(data);concepts=[];roles=[]
    for element in root.iter():
        if local(element.tag)=='element' and element.get('name'):
            concepts.append({'name':element.get('name'),'id':element.get('id'),'namespace':root.get('targetNamespace'),'attributes':dict(element.attrib)})
        elif local(element.tag)=='roleType':
            roles.append({'role':element.get('roleURI'),'id':element.get('id'),'definition':text(next((e for e in element if local(e.tag)=='definition'),None))})
    return {'namespaces':namespaces,'concepts':concepts,'roles':roles}

class FilingHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tables=[];self.stack=[];self.parts=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        at=dict(attrs)
        if tag in {'script','style'}:self.ignore+=1
        if tag in {'p','div','br','tr','h1','h2','h3','h4'} and not self.ignore:self.parts.append('\n')
        if tag=='table':self.stack.append({'attributes':at,'rows':[],'cell':None})
        elif tag=='tr' and self.stack:self.stack[-1]['rows'].append([])
        elif tag in {'td','th'} and self.stack:
            current=self.stack[-1]
            if not current['rows']:current['rows'].append([])
            cell={'text':'','parts':[],'type':tag,'attributes':at,'rowspan':self.span(at.get('rowspan')),'colspan':self.span(at.get('colspan'))}
            current['rows'][-1].append(cell);current['cell']=cell
        elif tag=='br':
            for current in self.stack:
                if current['cell']:current['cell']['parts'].append('\n')
    @staticmethod
    def span(value):
        try:return max(1,min(1000,int(value or 1)))
        except ValueError:return 1
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.ignore=max(0,self.ignore-1)
        if tag in {'td','th'} and self.stack:self.stack[-1]['cell']=None
        elif tag=='table' and self.stack:
            table=self.stack.pop()
            for row in table['rows']:
                for cell in row:cell['text']=re.sub(r'[ \t\r\f\v]+',' ',''.join(cell.pop('parts'))).strip()
            table.pop('cell');table['grid']=self.expand(table['rows']);self.tables.append(table)
    def handle_data(self,data):
        if self.ignore:return
        self.parts.append(data)
        for current in self.stack:
            if current['cell']:current['cell']['parts'].append(data)
    @staticmethod
    def expand(rows):
        occupied={};grid=[]
        for r,row in enumerate(rows):
            c=0
            for cell in row:
                while (r,c) in occupied:c+=1
                for dr in range(cell['rowspan']):
                    for dc in range(cell['colspan']):occupied[(r+dr,c+dc)]=cell['text']
                c+=cell['colspan']
            last=max((col for rr,col in occupied if rr==r),default=-1)
            grid.append([occupied.get((r,col),'') for col in range(last+1)])
        return grid

def parse_html(html):
    parser=FilingHTMLParser();parser.feed(html);parser.close()
    return {'text':re.sub(r'\n[ \t]*\n+','\n\n',''.join(parser.parts)).strip(),'tables':parser.tables}

def annotate_instance(instance, report_index, linkbases, schemas):
    """Relate facts to actual filing presentation roles without discarding unmatched facts."""
    ids={c['id']:(c['namespace'],c['name']) for schema in schemas for c in schema['concepts'] if c.get('id')}
    role_reports={r.get('Role'):r for r in report_index};membership={};labels={}
    for linkbase in linkbases:
        for net in linkbase['networks']:
            if net['type']=='presentationLink':
                report=role_reports.get(net['role'],{})
                for loc in net['locators'].values():
                    identifier=(loc['href'] or '').split('#')[-1]
                    key=ids.get(identifier)
                    if key is None and '_' in identifier:key=tuple(identifier.split('_',1))
                    if key:membership.setdefault(key,[]).append({'role':net['role'],'name':report.get('ShortName'),'category':report.get('category'),'report_file':report.get('HtmlFileName')})
            elif net['type']=='labelLink':
                for arc in net['arcs']:
                    identifier=(net['locators'].get(arc['from'],{}).get('href') or '').split('#')[-1]
                    key=ids.get(identifier)
                    if key is None and '_' in identifier:key=tuple(identifier.split('_',1))
                    if key:labels.setdefault(key,[]).extend(net['resources'].get(arc['to'],[]))
    for fact in instance['facts']:
        keys=[(fact['namespace'],fact['concept']),(fact['qname'].split(':',1)[0],fact['concept'])]
        fact['presentation_roles']=next((membership[k] for k in keys if k in membership),[])
        fact['labels']=next((labels[k] for k in keys if k in labels),[])
    return instance
