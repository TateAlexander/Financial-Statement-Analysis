import assert from 'node:assert/strict';
import vm from 'node:vm';
import worker,{statements,ratios,forecastAnnual,priceForecast,valuation,documentExtract,fitRidge,fundamentalForecast} from './worker/index.js';
const raw={facts:{'us-gaap':{}}};
function add(tag,unit,vals){raw.facts['us-gaap'][tag]={label:tag,units:{[unit]:vals}};}
const rows=(values,flow=true)=>values.map((val,i)=>({val,end:(2019+i)+'-12-31',...(flow?{start:(2019+i)+'-01-01'}:{}),filed:(2020+i)+'-02-20',form:'10-K',accn:'0000000000-00-000001'}));
add('Revenues','USD',rows([100,110,121,133.1,146.41,161.051,177.1561]));
add('Assets','USD',rows([200,220,242,266.2,292.82,322.102,354.3122],false));
add('NetIncomeLoss','USD',rows([10,11,12.1,13.31,14.641,16.1051,17.71561]));
add('OperatingIncomeLoss','USD',rows([20,22,24.2,26.62,29.282,32.2102,35.43122]));
add('NetCashProvidedByUsedInOperatingActivities','USD',rows([15,16.5,18.15,19.965,21.9615,24.15765,26.573415]));
add('PaymentsToAcquirePropertyPlantAndEquipment','USD',rows([5,5.5,6.05,6.655,7.3205,8.05255,8.857805]));
add('AssetsCurrent','USD',rows([50,55,60.5,66.55,73.205,80.5255,88.57805],false));
add('LiabilitiesCurrent','USD',rows([25,27.5,30.25,33.275,36.6025,40.26275,44.289025],false));
const s=statements(raw);assert.equal(s.annual.length,7);const rs=ratios(s.annual.at(-1),s.annual.at(-2),'Information Technology',false);
assert.equal(rs.find(r=>r.name==='Current ratio').value,2);
assert.equal(rs.find(r=>r.name==='Inventory turnover').status,'not_applicable');
assert.equal(rs.find(r=>r.name==='Debt / assets').value,null);
assert.equal(rs.find(r=>r.name==='DSO proxy').value,null);
assert.equal(rs.find(r=>r.name==='ROA').value>0,true);
assert.equal(ratios(s.annual.at(-1),s.annual.at(-2),'Financials').find(r=>r.name==='Current ratio').status,'not_applicable');
const f=forecastAnnual(s.annual);assert.equal(f.available,true);assert.ok(Math.abs(f.growth-.1)<1e-6);
assert.equal(forecastAnnual(s.annual.slice(0,3)).available,false);
assert.equal(priceForecast([]).available,false);
assert.equal(valuation(s.annual.at(-1),{price:10,shares:100,currency:'EUR'},f).available,false);
assert.equal(valuation(s.annual.at(-1),{price:10,shares:100,currency:'USD'},f,'Information Technology',{cashflowMethod:'sbc_adjusted'}).dcfValue,null);
const d=documentExtract('<table><tr><td>Debt</td><td>100</td></tr></table><ix:nonFraction name="custom:Debt" contextRef="c" unitRef="usd" scale="6">100</ix:nonFraction>');
assert.equal(d.facts[0].tag,'custom:Debt');assert.equal(d.tables.length,1);
assert.equal(fitRidge(Array.from({length:10},()=>({x:[1,1],y:.2})),[1,1]).toFixed(4),'0.2000');
assert.equal(fundamentalForecast(raw,s.annual,[],{},'Financials').available,false);
const longRaw={facts:{'us-gaap':{}}};
for(const [tag,scale]of [['Revenues',100],['OperatingIncomeLoss',20],['NetIncomeLoss',10],['NetCashProvidedByUsedInOperatingActivities',15],['Assets',200]]){
 longRaw.facts['us-gaap'][tag]={units:{USD:Array.from({length:20},(_,i)=>({val:scale*1.06**i,end:(2005+i)+'-12-31',...(tag==='Assets'?{}:{start:(2005+i)+'-01-01'}),filed:(2006+i)+'-02-20',form:'10-K'}))}};
}
const history=[];for(let d=new Date('2005-01-01T00:00:00Z');d<new Date('2026-01-01T00:00:00Z');d.setUTCDate(d.getUTCDate()+1)){if(d.getUTCDay()!==0&&d.getUTCDay()!==6)history.push({date:d.toISOString().slice(0,10),close:100*Math.exp(history.length*.0002)});}
const ls=statements(longRaw),model=fundamentalForecast(longRaw,ls.annual,history,{price:300,asof:'2026-01-01'},'Information Technology');assert.equal(model.available,true);assert.ok(model.low<=model.high);assert.ok(model.validation.length>=5);
longRaw.facts['us-gaap'].OperatingIncomeLoss.units.USD.push({val:999999,end:'2010-12-31',start:'2010-01-01',filed:'2030-01-01',form:'10-K/A'});
const noLeak=fundamentalForecast(longRaw,ls.annual,history,{price:300,asof:'2026-01-01'},'Information Technology');assert.deepEqual(noLeak.validation,model.validation);
const home=await worker.fetch(new Request('https://test.invalid/'));const html=await home.text();assert.equal(home.status,200);new vm.Script(html.match(/<script>([\s\S]*)<\/script>/)[1]);
const invalid=await worker.fetch(new Request('https://test.invalid/api/analyze',{method:'POST',body:JSON.stringify({ticker:'AAPL',email:'invalid'})}));assert.equal(invalid.status,400);
// Entire endpoint is tested with fixture-only sources: no requests leave Node.
globalThis.caches={default:{match:async()=>null,put:async()=>{}}};
globalThis.fetch=async url=>{
 if(String(url).includes('company_tickers'))return new Response(JSON.stringify({0:{ticker:'TEST',cik_str:1}}));
 if(String(url).includes('companyfacts'))return new Response(JSON.stringify(raw));
 if(String(url).includes('/submissions/'))return new Response(JSON.stringify({name:'Fixture',sic:'3571',filings:{recent:{}}}));
 return new Response('Unavailable',{status:429});
};
const response=await worker.fetch(new Request('https://test.invalid/api/analyze',{method:'POST',body:JSON.stringify({ticker:'TEST',email:'fixture@tests.invalid',sector:'Information Technology'})}));assert.equal(response.status,200);const result=await response.json();assert.equal(result.market.error,'Yahoo HTTP 429');assert.equal(result.valuation.available,false);assert.equal(result.ratios.find(r=>r.name==='Current ratio').value,2);
console.log('Passed: aligned statements, missing-data guards, sector eligibility, forecasts, ridge, document extraction, frontend syntax and mocked endpoint failures.');

// Filing-context tests use real Inline XBRL structure, including typed dimensions.
const contextual=documentExtract(`<xbrli:context id="annual"><xbrli:entity><xbrli:identifier scheme="sec">1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="segment"><xbrli:entity><xbrli:identifier>1</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="custom:RegionAxis">custom:EuropeMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
<ix:nonFraction name="custom:ShareExpense" contextRef="annual" unitRef="usd" scale="3" sign="-" format="ixt:num-dot-decimal">1,234</ix:nonFraction>
<ix:nonFraction name="custom:ShareExpense" contextRef="segment" unitRef="usd" scale="3">100</ix:nonFraction>
<ix:nonFraction name="custom:BadTransform" contextRef="annual" unitRef="usd" format="custom:unrecognized">1,000</ix:nonFraction>
<ix:nonNumeric name="custom:DebtPolicy" contextRef="annual" continuedAt="more">Debt policy</ix:nonNumeric><ix:continuation id="more">continued details</ix:continuation>`);
assert.equal(contextual.facts[0].value,-1234000);assert.equal(contextual.facts[0].unit,'USD');assert.equal(contextual.facts[0].context.start,'2025-01-01');assert.equal(contextual.facts[1].consolidated,false);assert.equal(contextual.facts[2].value,null);assert.equal(contextual.textFacts[0].text,'Debt policy continued details');
const {mapDocument,recalculate,residualBand}=await import('./worker/index.js');
const report={annual:s.annual,sector:'Information Technology',inventoryModel:false,market:{price:10,shares:100,currency:'USD'}};
const mapped=mapDocument(structuredClone(report),{...contextual,url:'https://www.sec.gov/Archives/edgar/data/1/123/report.htm'},[{index:0,key:'sbc'}]);assert.equal(mapped.applied,1);assert.equal(mapped.report.annual.at(-1).values.sbc,-1234000);assert.equal(mapped.report.mappingLog.length,1);
assert.throws(()=>mapDocument(structuredClone(report),contextual,[{index:1,key:'sbc'}]),/consolidated/);
assert.equal(residualBand([1,2,3],.8),null);assert.equal(residualBand([1,2,3,4],.8).radius,4);
assert.throws(()=>recalculate(structuredClone(report),{discount:.02,terminal:.03}),/Invalid DCF/);
const sc=structuredClone(raw);sc.facts['us-gaap'].NetIncomeLoss.units.USD.push({val:999,start:'2025-02-01',end:'2025-12-31',form:'10-K',filed:'2026-05-01'});assert.notEqual(statements(sc).annual.at(-1).values.income,999);
// Current and prior YTD bridge must share fiscal starts; per-share averages are never added.
for(const [tag,cur,old]of [['Revenues',90,80],['NetCashProvidedByUsedInOperatingActivities',30,20],['PaymentsToAcquirePropertyPlantAndEquipment',10,8]]){sc.facts['us-gaap'][tag].units.USD.push({val:cur,start:'2026-01-01',end:'2026-06-30',filed:'2026-08-01',form:'10-Q'},{val:old,start:'2025-01-01',end:'2025-06-30',filed:'2025-08-01',form:'10-Q'});}
const ttm=statements(sc).ttm;assert.equal(ttm.end,'2026-06-30');assert.ok(Math.abs(ttm.values.revenue-(177.1561+90-80))<1e-6);assert.equal(ttm.values.eps,null);assert.equal(ttm.sources.revenue.components.length,3);
const gaps=[s.annual[0],...s.annual.slice(2)];assert.equal(forecastAnnual(gaps).available,false);
assert.ok(model.selectionWindows>=4&&model.calibrationWindows>=4);assert.equal(model.interval.rank,Math.ceil((model.calibrationWindows+1)*.8));
// Execute the shipped frontend's render functions in a minimal DOM to verify every view.
const els=new Map();const el=id=>{if(!els.has(id))els.set(id,{value:'',innerHTML:'',textContent:'',classList:{toggle(){}},addEventListener(){}});return els.get(id);};
const sandbox={document:{getElementById:el,querySelectorAll:()=>[]},localStorage:{getItem:()=>null,setItem(){}},sessionStorage:{getItem:()=>null,setItem(){}},Intl,URL,Blob,setTimeout,console};vm.createContext(sandbox);vm.runInContext(html.match(/<script>([\s\S]*)<\/script>/)[1],sandbox);
const renderReport={...result,ttm,olderHistory:[],filings:[],market:{price:10,currency:'USD',history:[],shares:100},warnings:[],revenueForecast:f,priceForecast:{available:false,reason:'No history'},fundamentalForecast:model,valuation:{available:true,dcfUpside:.2,ps:3,dcfAssumptions:{growth:.04,discount:.1,terminal:.02,horizon:5,baseCashflow:10}}};
vm.runInContext('data='+JSON.stringify(renderReport),sandbox);
for(const view of ['overview','sec','statements','ratios','forecast','peers','filings','method']){vm.runInContext('tab='+JSON.stringify(view)+';render()',sandbox);assert.ok(el('view').innerHTML.length>100,view);}
vm.runInContext('peers=[{...data,ticker:"HIGH",valuation:{dcfUpside:.5}}, {...data,ticker:"LOW",valuation:{dcfUpside:.1}}]',sandbox);el('rank').value='dcfUpside';vm.runInContext('drawPeers()',sandbox);assert.ok(el('peerTable').innerHTML.indexOf('HIGH')<el('peerTable').innerHTML.indexOf('LOW'));
console.log('Passed: context scaling/dimensions/continuations, exact fiscal starts, TTM bridge, reviewed mapping, independent interval quantile, all eight frontend views and descending peer ranking.');

const {filingSummary,instanceExtract}=await import('./worker/index.js');
const catalog=filingSummary('<FilingSummary><MyReports><Report><HtmlFileName>R8.htm</HtmlFileName><ShortName>Statements of Shareholders Equity</ShortName><MenuCategory>Statements</MenuCategory><Position>8</Position></Report><Report><HtmlFileName>R9.htm</HtmlFileName><ShortName>Debt note</ShortName><MenuCategory>Notes</MenuCategory><Position>9</Position></Report></MyReports></FilingSummary>','https://www.sec.gov/Archives/edgar/data/1/123/');
assert.equal(catalog[0].category,'Equity statements');assert.equal(catalog[1].category,'Footnotes');
const xmlInstance=instanceExtract('<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:custom="urn:custom"><xbrli:context id="c"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><custom:NewEquityFact contextRef="c" unitRef="u" decimals="0">9007199254740993</custom:NewEquityFact><custom:Missing contextRef="c" xsi:nil="true"/><custom:DisclosureTextBlock contextRef="c">&lt;p&gt;Full disclosure&lt;/p&gt;</custom:DisclosureTextBlock></xbrli:xbrl>','source');
assert.equal(xmlInstance.facts.length,3);assert.equal(xmlInstance.facts[0].raw,'9007199254740993');assert.equal(xmlInstance.facts[1].status,'nil');assert.equal(xmlInstance.facts[2].status,'text');
assert.ok(valuation(s.annual.at(-1),{price:10,shares:100,currency:'USD'},f,'Consumer Staples').dcfValue>0);
assert.equal(valuation(s.annual.at(-1),{price:10,shares:100,currency:'USD'},f,'Consumer Staples',{cashflowMethod:'sbc_adjusted'}).dcfValue,null);
console.log('Passed: full report index, equity/footnote organization, unrestricted custom instance facts, exact raw numeric strings, and independent DCF cash-flow variants.');
