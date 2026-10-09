// Dependency-free localhost adapter for the deployed Cloudflare-style Worker.
import http from 'node:http';
import worker from './worker/index.js';
const store=new Map();
globalThis.caches={default:{
 async match(request){const entry=store.get(request.url);if(!entry||Date.now()>entry.until)return undefined;return new Response(entry.body,{status:entry.status,headers:entry.headers});},
 async put(request,response){const body=await response.text();const headers=Object.fromEntries(response.headers);const ttl=Number((headers['cache-control']||'').match(/max-age=(\d+)/)?.[1]||3600);if(store.size>=100)store.delete(store.keys().next().value);store.set(request.url,{body,headers,status:response.status,until:Date.now()+ttl*1000});}
}};
// Shared per-process SEC request spacing; requests do not bypass provider errors.
const networkFetch=globalThis.fetch;let queue=Promise.resolve(),lastSec=0;
globalThis.fetch=async(input,init)=>{const url=new URL(typeof input==='string'?input:input.url);if(url.hostname==='www.sec.gov'||url.hostname==='data.sec.gov'){let release;const prior=queue;queue=new Promise(resolve=>{release=resolve});await prior;try{const wait=Math.max(0,300-(Date.now()-lastSec));if(wait)await new Promise(resolve=>setTimeout(resolve,wait));lastSec=Date.now();return await networkFetch(input,init);}finally{release();}}return networkFetch(input,init);};
const port=Number(process.env.PORT||8501);if(!Number.isInteger(port)||port<1||port>65535)throw Error('PORT must be 1–65535.');
const server=http.createServer(async(req,res)=>{try{const parts=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>50*1024*1024){res.writeHead(413);res.end('Request exceeds 50 MB');return;}parts.push(chunk);}const request=new Request('http://127.0.0.1:'+port+(req.url||'/'),{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(parts)}:{})});const response=await worker.fetch(request);res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));}catch(err){res.writeHead(500,{'Content-Type':'application/json'});res.end(JSON.stringify({error:err.message}));}});
server.listen(port,'127.0.0.1',()=>{console.log('Equity Lens is running at http://127.0.0.1:'+port);console.log('Open that address in your browser. Press Ctrl+C to stop.');});
