const assert=require('node:assert/strict');
const {number,text,period,groups,label}=require('../static/round-presentation.js');
const rounds=Array.from({length:40},(_,i)=>({number:i+2,display_number:i+1,is_knife:false,
  player_sides:{a:i<12?'T':i<27?'CT':i<33?'T':i<39?'CT':'T',b:i<12?'CT':i<27?'T':i<33?'CT':i<39?'T':'CT'}}));
assert.equal(number(rounds,2),1);
const phases=groups(rounds,'a');
assert.deepEqual(phases.map(g=>[g.phase.key,g.rounds.length]),[
 ['main-1',12],['main-2',12],['ot-1-1',3],['ot-1-2',3],['ot-2-1',3],['ot-2-2',3],['ot-3-1',3],['ot-3-2',1]
]);
assert.equal(label(phases[0]),'Основное · 1-я половина · T · Р1–12');
assert.equal(label(phases[1]),'Основное · 2-я половина · CT · Р13–24');
assert.equal(label(phases[2]),'ОТ 1 · 1-я половина · CT · Р25–27');
assert.equal(label(phases[4]),'ОТ 2 · 1-я половина · T · Р31–33');
// A new overtime starts even if the player's side stays the same.
assert.equal(phases[1].side,phases[2].side);
assert.equal(phases[3].side,phases[4].side);
assert.equal(groups(rounds,'b')[0].side,'CT');
assert.equal(groups(rounds,'missing').length,8);
const withKnife=[{number:1,display_number:null,is_knife:true,player_sides:{a:'T'}},...rounds];
assert.equal(number(withKnife,1),null);
assert.equal(text(withKnife,1),'Ножевой');
assert.equal(text(withKnife,1,true),'Ножевой');
assert.equal(text(withKnife,2),'Раунд 1');
assert.equal(text(withKnife,2,true),'Р1');
const shown=groups(withKnife,'a',[1]);
assert.equal(shown.length,phases.length+1);
assert.equal(label(shown[0]),'Ножевой · T');
assert.deepEqual(shown.slice(1),phases);
assert.equal(period(25).key,'ot-1-1');
assert.equal(period(28).key,'ot-1-2');
assert.equal(period(31).key,'ot-2-1');
assert.equal(period(34).key,'ot-2-2');
assert.equal(rounds[0].number,2);
console.log('Unnumbered knife, main halves, MR3 overtime series and navigation IDs: OK');
