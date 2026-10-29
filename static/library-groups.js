const LibraryGroups = {
 group(matches){
  const groups=new Map();
  for(const match of matches){
   const name=match.summary?.map||null,key=name||'__pending__';
   if(!groups.has(key))groups.set(key,{map:name,items:[],ready:0});
   const group=groups.get(key);group.items.push(match);if(match.status==='ready')group.ready++;
  }
  return [...groups.values()].sort((a,b)=>a.map===null?1:b.map===null?-1:b.ready-a.ready||a.map.localeCompare(b.map));
 }
};
if(typeof module!=='undefined')module.exports=LibraryGroups;
