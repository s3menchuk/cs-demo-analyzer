const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const panels={'#dashboard':{hidden:false},'#replay':{hidden:false}};
let toggles=0,seeks=[],dialog=false;
const context=vm.createContext({$:s=>panels[s],data:{tickrate:64},frames:[{}],playbackTick:640,
  document:{querySelector:()=>dialog},play:()=>toggles++,seekPlayback:tick=>seeks.push(tick)});
vm.runInContext(source.slice(source.indexOf('function replayKeyboard('),source.indexOf("document.addEventListener('keydown',replayKeyboard)")),context);
function key(key,extra={}){
  const e={key,target:{closest:()=>false},preventDefault(){this.prevented=true},...extra};
  context.replayKeyboard(e);return e;
}
assert.equal(key(' ').prevented,true);assert.equal(toggles,1);
key(' ',{repeat:true});assert.equal(toggles,1);
key('ArrowLeft');key('ArrowRight');assert.deepEqual(seeks,[320,960]);
assert.equal(key(' ',{target:{closest:()=>true,id:'play'}}).prevented,true);
assert.equal(toggles,2);
assert.equal(key('ArrowLeft',{target:{closest:()=>true,id:'timeline'}}).prevented,true);
for(const target of [{closest:()=>true,id:'renameInput'},{closest:()=>true,id:'speed'},{isContentEditable:true}]){
  assert.equal(key(' ',{target}).prevented,undefined);
}
dialog=true;assert.equal(key(' ').prevented,undefined);dialog=false;
panels['#replay'].hidden=true;assert.equal(key('ArrowRight').prevented,undefined);panels['#replay'].hidden=false;
assert.equal(key('ArrowRight',{ctrlKey:true}).prevented,undefined);
context.frames=[];assert.equal(key(' ').prevented,undefined);
console.log('Replay keyboard: toggle, 5-second seek, focus, dialogs and visibility: OK');
