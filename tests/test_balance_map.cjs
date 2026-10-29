const assert=require('node:assert/strict');const map=require('../static/balance-map.js');
const ctx={fillRect(){},strokeRect(){},fillText(){}};
const zones=[{min_x:-256,min_y:0,size:256,level:'upper',kills:3,deaths:1,delta:2},{min_x:0,min_y:0,size:256,level:'lower',kills:0,deaths:1,delta:-1}];
const cells=map.draw(ctx,p=>[p.x,-p.y],zones,'upper');
assert.equal(cells.length,1);assert.equal(map.hit(cells,-100,-100).delta,2);assert.equal(map.hit(cells,20,20),undefined);
assert.ok(map.description(cells[0]).includes('+2'));assert.equal(map.bounds(zones).length,4);
console.log('Balance projection, floor filtering and cell hit testing: OK');
