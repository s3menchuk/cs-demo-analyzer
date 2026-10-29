let profile = null, profileRequest = 0, profileStyle = 'density', highlightedZone = null, profileHitPoints=[];
let roundKillsScroll = 0, profileBalanceCells=[];

function initPlayerAnalysis() {
  profile=null;profileRequest++;highlightedZone=null;
  roundKillsScroll=0;
  $('#profilePlayer').innerHTML=data.players.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  $('#profileRound').innerHTML='<option value="">Весь матч</option>'+data.rounds.map(r=>`<option value="${r.number}">${roundLabel(r.number)}</option>`).join('');
  $('#profileSide').value='';$('#profileLevel').innerHTML=levelOptions(mapMeta);
  $('#profileMetrics').innerHTML='';$('#profileWarning').hidden=true;
  refreshPlayerAnalysis().catch(failure);
}

async function refreshPlayerAnalysis() {
  const pid=$('#profilePlayer').value;if(!pid)return;
  const request=++profileRequest,id=matchId;
  profile=null;highlightedZone=null;profileHitPoints=[];
  $('#profileName').textContent='Загрузка анализа…';$('#profileEvents').innerHTML='';
  $('#killZones').innerHTML=$('#deathZones').innerHTML='<p class="map-note">Загрузка…</p>';
  $('#profileMetrics').innerHTML='';drawPlayerAnalysis();
  if($('#roundKillsChart').querySelector('button'))roundKillsScroll=$('#roundKillsChart').scrollLeft;
  $('#roundKillsChart').innerHTML='<p class="map-note">Загрузка статистики раундов…</p>';$('#roundKillsTotal').textContent='';
  const params=new URLSearchParams({cell_size:$('#profileCell').value,include_knife:String(data.include_knife||false)});
  if($('#profileRound').value)params.set('round_number',$('#profileRound').value);
  if($('#profileSide').value)params.set('side',$('#profileSide').value);
  const report=await api(`/api/matches/${id}/players/${encodeURIComponent(pid)}/analysis?${params}`);
  if(request!==profileRequest||id!==matchId)return;
  profile=report;
  $('#profileName').textContent=report.player.name;
  $('#profileWarning').textContent=report.warning||'';$('#profileWarning').hidden=!report.warning;
  const p=report.player;
  const entries=[['Убийства',report.kills,'По выбранному периоду и стороне'],['Смерти',report.deaths,'Включая мир и командные убийства'],['ADR · весь матч',p.adr,`${p.damage} HP · ${p.rounds} раундов`],['KAST · весь матч',`${p.kast}%`,`K/D ${p.kd} · HS ${p.hs}%`]];
  $('#profileMetrics').innerHTML=entries.map((m,i)=>`<div class="panel metric ${i===0?'kill-metric':i===1?'death-metric':''}"><span class="label">${m[0]}</span><strong>${report.available||i>1?esc(m[1]):'—'}</strong><p>${esc(m[2])}</p></div>`).join('');
  $('#profileWeapons').innerHTML=report.weapons.length?report.weapons.map(w=>`<div class="weapon-row"><span>${esc(w.name)}</span><b>${w.kills}</b></div>`).join(''):`<p class="map-note">${report.available?'Нет убийств в выбранном периоде':'Статистика оружия доступна после повторной загрузки demo'}</p>`;
  $('#profileSelection').textContent='Нажми на точку или выбери зону справа, чтобы разобрать событие.';
  renderRoundKills();renderProfileEvents();drawPlayerAnalysis();
}

function renderRoundKills(){
  if(!profile)return;
  const series=profile.round_kills||[];
  if(!profile.available){$('#roundKillsChart').innerHTML='<p class="map-note">Для статистики по раундам загрузите demo повторно.</p>';$('#roundKillsTotal').textContent='';return;}
  const max=Math.max(1,...series.map(r=>r.kills)),total=series.reduce((sum,r)=>sum+r.kills,0);
  $('#roundKillsTotal').textContent=`ЗА МАТЧ: ${total} K · ${data.rounds.filter(r=>!r.is_knife).length} ИГРОВЫХ РАУНДОВ${data.include_knife&&data.knife_rounds?.length?' + НОЖЕВОЙ':''}`;
  const counts=new Map(series.map(r=>[r.number,r.kills]));
  const groups=RoundPresentation.groups(data.rounds,$('#profilePlayer').value,data.knife_rounds);
  $('#roundKillsChart').innerHTML=series.length?groups.map(g=>`<div class="round-kill-phase side-${g.side} ${g.knife?'knife-phase':''}"><div class="round-phase-label">${esc(RoundPresentation.label(g))}</div><div class="round-kill-phase-columns">${g.rounds.map(r=>{
    const kills=counts.get(r.number)||0;
    return `<button class="round-kill-column ${r.is_knife?'knife-round':''} ${Number($('#profileRound').value)===r.number?'selected':''}" data-kill-count="${Math.min(5,kills)}" data-kill-round="${r.number}" aria-pressed="${Number($('#profileRound').value)===r.number}" aria-label="${roundLabel(r.number)}: ${kills} киллов, сторона ${g.side}" title="${roundLabel(r.number)}: ${kills} киллов · ${g.side}"><strong>${kills}</strong><span class="round-kill-track"><i class="${kills===0?'zero':''}" style="height:${kills===0?3:Math.max(6,kills/max*100)}%"></i></span><small>${roundLabel(r.number,true)}</small></button>`;
  }).join('')}</div></div>`).join(''):'<p class="map-note">Нет завершённых раундов</p>';
  $('#roundKillsChart').scrollLeft=roundKillsScroll;
  $('#roundKillsChart').querySelectorAll('button').forEach(b=>b.onclick=()=>{
    $('#profileRound').value=$('#profileRound').value===b.dataset.killRound?'':b.dataset.killRound;
    refreshPlayerAnalysis().catch(failure);
  });
}

function profilePoints() {
  if(!profile)return [];
  const mode=$('#profileMode').value,level=$('#profileLevel').value;
  return [...(mode!=='deaths'?profile.kill_points.map(p=>({...p,kind:'kill'})):[]),
    ...(mode!=='kills'?profile.death_points.map(p=>({...p,kind:'death'})):[])]
    .filter(p=>MapView.onLevel(mapMeta,p,level));
}

function renderZones(kind) {
  if(!profile)return;
  const level=$('#profileLevel').value;
  const zones=profile[kind+'_zones'].filter(z=>!mapMeta||mapMeta.levels.length<2||z.level===level).slice(0,5);
  const target=kind==='kill'?$('#killZones'):$('#deathZones');
  target.innerHTML=zones.length?zones.map((z,i)=>`<button class="zone-row ${kind}" data-zone="${i}"><span class="zone-rank">${String(i+1).padStart(2,'0')}</span><span><b>X ${Math.round(z.x)} · Y ${Math.round(z.y)}</b><small>Раунды ${z.rounds.map(id=>roundLabel(id,true)).join(', ')} · ${z.share}% событий с координатами</small></span><strong>${z.count}</strong></button>`).join(''):`<p class="map-note">${profile.available?'Нет событий с координатами на этом этаже':'Для анализа зон загрузите demo повторно'}</p>`;
  target.querySelectorAll('button').forEach(b=>b.onclick=()=>{
    if(profileStyle==='balance')setProfileStyle('density');
    highlightedZone={...zones[Number(b.dataset.zone)],kind};
    $('#profileMode').value=kind==='kill'?'kills':'deaths';
    const points=profile[kind+'_points'].filter(p=>p.level===highlightedZone.level&&p.x>=highlightedZone.min_x&&p.x<highlightedZone.min_x+highlightedZone.size&&p.y>=highlightedZone.min_y&&p.y<highlightedZone.min_y+highlightedZone.size);
    $('#profileSelection').innerHTML=`<b>${kind==='kill'?'Зона убийств':'Зона смертей'} · ${points.length} событий.</b> ${points.map((p,i)=>`<button class="text-button" data-zone-event="${i}">${roundLabel(p.round,true)} · ${eventTime(p)} ↗</button>`).join(' ')}`;
    $('#profileSelection').querySelectorAll('[data-zone-event]').forEach(el=>el.onclick=()=>jumpToProfileEvent(points[Number(el.dataset.zoneEvent)]).catch(failure));
    drawPlayerAnalysis();renderProfileEvents();
  });
}

function eventTime(p){const round=data.rounds.find(r=>r.number===p.round);return time((p.tick-round.start)/data.tickrate);}

function renderProfileEvents() {
  const points=profilePoints().sort((a,b)=>a.tick-b.tick);
  $('#profileEventCount').textContent=`${points.length} EVENTS`;
  $('#profileEvents').innerHTML=points.length?points.map((p,i)=>`<button class="profile-event ${p.kind}" data-event="${i}"><span class="event-kind">${p.kind==='kill'?'↗ Убийство':'× Смерть'}</span><b>${esc(p.opponent)}</b><span>${esc(p.weapon)} ${p.headshot?'· HS':''}</span><small>${roundLabel(p.round)} · ${eventTime(p)} ↗</small></button>`).join(''):`<p class="map-note">${profile.available?'Нет событий с координатами для выбранных фильтров.':'События игрока будут доступны после повторной загрузки demo.'}</p>`;
  $('#profileEvents').querySelectorAll('button').forEach(b=>b.onclick=()=>jumpToProfileEvent(points[Number(b.dataset.event)]).catch(failure));
}

async function jumpToProfileEvent(point) {
  const id=matchId,pid=profile.player.id;
  tab('replay');$('#playerFilter').value=pid;$('#sideFilter').value='';$('#replayLevel').value=point.level||'default';
  const loaded=await loadRound(point.round);
  if(!loaded||id!==matchId||currentRound!==point.round)return;
  const focus=data.events.find(e=>e.tick===point.tick&&e.round===point.round&&((e.attacker_id===pid&&e.victim===point.opponent)||(e.victim_id===pid&&e.attacker===point.opponent)));
  seekPlayback(point.tick,{focus,positions:true});
}

function drawPlayerAnalysis() {
  const canvas=$('#profileMap');if(!canvas||!data)return;
  const fallback=data.events.flatMap(e=>[e.attacker_position,e.victim_position]).filter(Boolean);
  const {ctx,project,label}=MapView.base(canvas,mapMeta,$('#profileLevel').value,fallback,customRadar());
  $('#profileMapLabel').textContent=label;profileHitPoints=[];
  if(!profile){ctx.fillStyle='#c6d2df';ctx.font='16px Segoe UI';ctx.textAlign='center';ctx.fillText('Загрузка данных игрока…',450,450);return;}
  const points=profilePoints();
  const color=kind=>kind==='kill'?'#6fe0b1':'#ff777d';
  profileBalanceCells=[];
  $('#profileBalanceLegend').hidden=profileStyle!=='balance';
  if(profileStyle==='balance')profileBalanceCells=BalanceMap.draw(ctx,project,profile.balance_zones||[],mapMeta?.levels.length>1?$('#profileLevel').value:null);
  if(profileStyle==='density'){
    const kinds=$('#profileMode').value==='both'?['kill','death']:[$('#profileMode').value==='kills'?'kill':'death'];
    let max=1;for(const k of kinds)for(const z of profile[k+'_zones'])max=Math.max(max,z.count);
    for(const kind of kinds)for(const z of profile[kind+'_zones']){
      if(mapMeta?.levels.length>1&&z.level!==$('#profileLevel').value)continue;
      const [x,y]=project({x:z.min_x,y:z.min_y+z.size}),[x2,y2]=project({x:z.min_x+z.size,y:z.min_y});
      ctx.fillStyle=color(kind);ctx.globalAlpha=.18+.45*z.count/max;ctx.fillRect(x,y,x2-x,y2-y);
      ctx.globalAlpha=.8;ctx.strokeStyle=color(kind);ctx.lineWidth=1;ctx.strokeRect(x,y,x2-x,y2-y);ctx.globalAlpha=1;
      const offset=kinds.length>1?(kind==='kill'?-9:9):0;
      ctx.fillStyle='#081119';ctx.beginPath();ctx.arc((x+x2)/2+offset,(y+y2)/2,9,0,Math.PI*2);ctx.fill();
      ctx.fillStyle=color(kind);ctx.font='bold 12px Consolas';ctx.textAlign='center';ctx.fillText(String(z.count),(x+x2)/2+offset,(y+y2)/2+4);
    }
  }
  for(const p of points){
    const [x,y]=project(p);profileHitPoints.push({...p,px:x,py:y});
    if(profileStyle!=='points')continue;
    ctx.fillStyle=color(p.kind);ctx.strokeStyle='#0c1119';ctx.lineWidth=2;
    ctx.beginPath();ctx.arc(x,y,p.kind==='kill'?6:7,0,Math.PI*2);ctx.fill();ctx.stroke();
    if(p.kind==='death'){ctx.strokeStyle='#261317';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x-3,y-3);ctx.lineTo(x+3,y+3);ctx.moveTo(x+3,y-3);ctx.lineTo(x-3,y+3);ctx.stroke();}
  }
  if(highlightedZone){
    const z=highlightedZone,[x,y]=project({x:z.min_x,y:z.min_y+z.size}),[x2,y2]=project({x:z.min_x+z.size,y:z.min_y});
    ctx.strokeStyle='#fff3ce';ctx.lineWidth=3;ctx.strokeRect(x,y,x2-x,y2-y);
  }
  $('#profileCoverage').textContent=profile.available?`Координаты убийств: ${profile.kills_with_position}/${profile.kills}. Координаты смертей: ${profile.deaths_with_position}/${profile.deaths}. Показано на выбранном этаже: ${points.length} событий. Позиции взяты непосредственно из событий demo.`:'Координаты событий отсутствуют в старом формате результатов. Для пространственного анализа требуется повторная загрузка demo.';
  renderZones('kill');renderZones('death');
}

['profilePlayer','profileRound','profileSide','profileCell'].forEach(id=>$('#'+id).onchange=()=>refreshPlayerAnalysis().catch(failure));
['profileMode','profileLevel'].forEach(id=>$('#'+id).onchange=()=>{highlightedZone=null;$('#profileSelection').textContent='Выбери точку или зону для разбора.';drawPlayerAnalysis();if(profile)renderProfileEvents();});
function setProfileStyle(style){
  profileStyle=style;
  for(const [id,value] of [['profileDensity','density'],['profilePoints','points'],['profileBalance','balance']])$('#'+id).classList.toggle('selected',style===value);
  $('#profileMode').disabled=style==='balance';
  if(style==='balance')$('#profileMode').value='both';
  highlightedZone=null;drawPlayerAnalysis();if(profile)renderProfileEvents();
}
$('#profileDensity').onclick=()=>setProfileStyle('density');
$('#profilePoints').onclick=()=>setProfileStyle('points');
$('#profileBalance').onclick=()=>setProfileStyle('balance');
$('#profileMap').onclick=e=>{
  if(!profile)return;
  const rect=e.currentTarget.getBoundingClientRect(),x=(e.clientX-rect.left)*900/rect.width,y=(e.clientY-rect.top)*900/rect.height;
  if(profileStyle==='balance'){const zone=BalanceMap.hit(profileBalanceCells,x,y);$('#profileSelection').textContent=zone?BalanceMap.description(zone)+' · сетка '+zone.size+' ед.':'В этой ячейке нет событий с координатами.';return;}
  const p=profileHitPoints.reduce((best,p)=>Math.hypot(p.px-x,p.py-y)<Math.hypot((best?.px??Infinity)-x,(best?.py??Infinity)-y)?p:best,null);
  if(!p||Math.hypot(p.px-x,p.py-y)>22)return;
  $('#profileSelection').innerHTML=`<b>${p.kind==='kill'?'Убийство':'Смерть'} · ${esc(p.opponent)}</b> · ${esc(p.weapon)} · ${roundLabel(p.round,true)} ${eventTime(p)} <button id="jumpDuel" class="text-button">Посмотреть раунд ↗</button>`;
  $('#jumpDuel').onclick=()=>jumpToProfileEvent(p).catch(failure);
};
