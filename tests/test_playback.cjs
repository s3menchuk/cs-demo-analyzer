const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const sandbox={};
vm.runInNewContext(fs.readFileSync('static/replay.js','utf8'),sandbox);
vm.runInNewContext(fs.readFileSync('static/playback.js','utf8')+';globalThis.Controller=PlaybackController;',sandbox);
function setup(){
  let wall=0,id=0,pending=new Map();
  const state={tick:0,end:10000,tickrate:64,speed:1,ready:true},updates=[];
  const player=new sandbox.Controller({context:()=>({...state}),onTick:tick=>{state.tick=tick;},onState:value=>updates.push(value),
    now:()=>wall,requestFrame:fn=>{const handle=id++;pending.set(handle,fn);return handle;},cancelFrame:handle=>pending.delete(handle)});
  return {player,state,updates,pending,step(ms){wall+=ms;const callbacks=[...pending.values()];pending.clear();callbacks.forEach(fn=>fn(wall));}};
}
{
  const t=setup();t.player.start();t.step(500);assert.equal(t.state.tick,32);
  const stale=[...t.pending.values()][0];
  t.player.seek(()=>{t.state.tick=3200;});
  assert.equal(t.player.playing,true);assert.equal(t.pending.size,1);
  stale(1000);assert.equal(t.state.tick,3200);assert.equal(t.pending.size,1);
  t.step(500);assert.equal(t.state.tick,3232,'Seek must rebase the clock at the new tick');
  assert.deepEqual(t.updates,[true],'Seek must not switch playback to pause');
  t.player.pause();t.player.seek(()=>{t.state.tick=100;});t.step(1000);
  assert.equal(t.state.tick,100);assert.equal(t.player.playing,false);assert.equal(t.pending.size,0);
}
{
  const t=setup();t.player.start();t.player.suspend();t.state.ready=false;
  t.player.resume();assert.equal(t.player.playing,true);assert.equal(t.pending.size,0);
  // A second round switch while the first is loading retains the same intent.
  t.player.suspend();t.step(5000);t.state.ready=true;t.state.tick=6000;t.player.resume();t.step(1000);
  assert.equal(t.state.tick,6064);assert.equal(t.pending.size,1);
}
{
  const t=setup();t.player.start();t.player.suspend();t.state.ready=false;
  t.player.pause();t.state.ready=true;t.player.resume();t.step(1000);
  assert.equal(t.player.playing,false);assert.equal(t.pending.size,0,'Pause during loading must not be undone');
}
{
  const t=setup();t.player.start();t.step(500);t.state.speed=2;t.player.resume();t.step(500);
  assert.equal(t.state.tick,96,'Speed change must preserve the current position');
  t.player.seek(()=>{t.state.tick=t.state.end;});t.step(16);
  assert.equal(t.state.tick,t.state.end);assert.equal(t.player.playing,false);assert.equal(t.pending.size,0);
}
{
  const t=setup();t.state.ready=false;t.player.start();assert.equal(t.player.playing,true);
  t.state.ready=true;t.player.resume();t.step(1000);assert.equal(t.state.tick,64);
}
// Native browser frame functions require the Window receiver, unlike ordinary test callbacks.
vm.runInNewContext(`
  globalThis.performance={now:()=>0};
  globalThis.requestAnimationFrame=function(fn){if(this!==globalThis)throw new Error('Wrong frame receiver');return 1;};
  globalThis.cancelAnimationFrame=function(id){if(this!==globalThis)throw new Error('Wrong cancel receiver');};
  const nativeController=new PlaybackController({context:()=>({ready:true,tick:0,end:100,tickrate:64,speed:1}),onTick:()=>{},onState:()=>{}});
  nativeController.start();nativeController.pause();
`,sandbox);
console.log('Seek play/pause preservation, round loading, stale callbacks, speed and end-of-round checks passed');
