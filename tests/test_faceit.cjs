const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
function element(id){
  if(!elements.has(id))elements.set(id,{hidden:false,classList:{toggle(){}},addEventListener(){},querySelectorAll:()=>[],querySelector:()=>null});
  return elements.get(id);
}
const context=vm.createContext({$:element,libraryMatches:[],uploading:false,
  esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  fetch:async()=>({ok:true,json:async()=>({data_api:false,downloads_api:false})})});
vm.runInContext(fs.readFileSync('static/faceit.js','utf8'),context);
vm.runInContext(`faceitDownloads=true;faceitGames=[
  {match_id:'one',name:'<Alpha>',finished_at:100,demo_count:1,demo_index:0,url:'https://www.faceit.com/en/cs2/room/one'},
  {match_id:'two',name:'Beta',finished_at:200,demo_count:0,demo_index:0,unavailable_reason:'No demo',url:'https://www.faceit.com/en/cs2/room/two'}
];renderFaceitGames();`,context);
let html=element('#faceitMatches').innerHTML;
assert.match(html,/&lt;Alpha>/);
assert.equal((html.match(/disabled/g)||[]).length,1);
assert.match(html,/No demo/);
context.libraryMatches=[{id:'faceit_one_0',status:'ready'}];
vm.runInContext('renderFaceitGames()',context);
html=element('#faceitMatches').innerHTML;
assert.equal((html.match(/disabled/g)||[]).length,2);
assert.match(html,/Уже в библиотеке/);
vm.runInContext('faceitDownloads=false;libraryMatches=[];renderFaceitGames()',context);
assert.match(element('#faceitMatches').innerHTML,/Downloads API/);
console.log('FACEIT selection: escaping, unavailable demos, duplicates and missing access: OK');
