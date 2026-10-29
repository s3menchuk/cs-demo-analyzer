/* Display labels never replace the original round IDs used for seeking. */
const RoundPresentation = (() => {
  function number(rounds, id) {
    const round=rounds.find(r=>r.number===id);
    return round && Object.hasOwn(round,'display_number') ? round.display_number : id;
  }
  function text(rounds,id,short=false){
    const n=number(rounds,id);
    return n===null?'Ножевой':`${short?'Р':'Раунд '}${n}`;
  }
  function period(n,knife=false){
    if(knife||n===null)return {key:'knife',title:'Ножевой'};
    if(n<=24){const half=n<=12?1:2;return {key:`main-${half}`,title:`Основное · ${half}-я половина`};}
    const overtime=Math.floor((n-25)/6)+1,half=Math.floor(((n-25)%6)/3)+1;
    return {key:`ot-${overtime}-${half}`,title:`ОТ ${overtime} · ${half}-я половина`};
  }
  function groups(rounds, pid, knifeRounds=[]) {
    const result=[];
    for(const round of rounds){
      const side=round.player_sides?.[pid] || '?', knife=round.is_knife||knifeRounds.includes(round.number);
      const phase=period(number(rounds,round.number),knife),previous=result[result.length-1];
      if(!previous||previous.side!==side||previous.phase.key!==phase.key)result.push({side,knife,phase,rounds:[round]});
      else previous.rounds.push(round);
    }
    return result;
  }
  function label(group) {
    const first=group.rounds[0],last=group.rounds[group.rounds.length-1];
    const side=group.side==='?'?'Сторона неизвестна':group.side;
    if(group.knife)return `Ножевой · ${side}`;
    return `${group.phase.title} · ${side} · Р${first.display_number??first.number}${first===last?'':'–'+(last.display_number??last.number)}`;
  }
  return {number,text,period,groups,label};
})();
if(typeof module!=='undefined')module.exports=RoundPresentation;
