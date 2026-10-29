const assert=require('node:assert/strict');
const queue=require('../static/upload-queue.js');
(async()=>{
 const sent=[],updates=[];let polls=0,waits=0,retry=0;
 const result=await queue.run(['a.dem','bad.txt','broken.dem','b.dem'].map(name=>({name,size:1})),{
  list:async()=>++polls===1?[{status:'parsing'},{status:'queued'},{status:'queued'}]:[],
  sleep:async()=>{waits++},onUpdate:items=>updates.push(items.map(i=>i.state)),
  upload:async file=>{sent.push(file.name);if(file.name==='broken.dem')throw new Error('bad header');if(file.name==='b.dem'&&!retry++){const e=new Error('full');e.status=429;throw e;}return {id:file.name};}
 });
 assert.deepEqual(result.map(i=>i.state),['accepted','error','error','accepted']);
 assert.deepEqual(sent,['a.dem','broken.dem','b.dem','b.dem']);assert.equal(waits,2);
 let cancelled=false;
 const cancel=await queue.run([{name:'one.dem',size:1},{name:'two.dem',size:1}],{
  list:async()=>[],cancelled:()=>cancelled,upload:async()=>({id:'one'}),onAccepted:async()=>{cancelled=true}
 });
 assert.deepEqual(cancel.map(i=>i.state),['accepted','cancelled']);
 let attempted=false;cancelled=false;
 const waiting=await queue.run([{name:'a.dem',size:1}],{list:async()=>{cancelled=true;return []},cancelled:()=>cancelled,upload:async()=>{attempted=true;return {id:'a'}}});
 assert.equal(waiting[0].state,'cancelled');assert.equal(attempted,false);
 const accepted=await queue.run([{name:'a.dem',size:1}],{list:async()=>[],upload:async()=>({id:'a'}),onAccepted:async()=>{throw new Error('UI unavailable')}});
 assert.equal(accepted[0].state,'accepted');
 console.log('Batch capacity, HTTP 429 retry, per-file failures and cancellation: OK');
})().catch(e=>{console.error(e);process.exit(1)});
