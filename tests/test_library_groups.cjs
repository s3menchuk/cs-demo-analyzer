const assert=require('node:assert/strict');const {group}=require('../static/library-groups.js');
const result=group([
 {id:'a',name:'one.dem',status:'ready',summary:{map:'de_mirage'}},
 {id:'b',name:'one.dem',status:'ready',summary:{map:'de_dust2'}},
 {id:'c',name:'different.dem',status:'ready',summary:{map:'de_mirage'}},
 {id:'d',status:'parsing'}, {id:'e',status:'error'}
]);
assert.equal(result.length,3);assert.equal(result[0].map,'de_mirage');assert.equal(result[0].ready,2);
assert.deepEqual(result[0].items.map(m=>m.id),['a','c']);assert.equal(result[1].map,'de_dust2');assert.equal(result[2].map,null);
assert.equal(result[2].ready,0);assert.equal(group([]).length,0);
console.log('Automatic library grouping uses map metadata and separates pending files: OK');
