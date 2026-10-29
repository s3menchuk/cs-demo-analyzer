const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time = (s) => `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
let matchId = '', data = null, frames = [], currentRound = 1, frameIndex = 0, heat = false;
let playbackTick = 0, roundBounds = [];
let roundGrenades = [], roundEffects = [], libraryMatches = [], deletingMatch = null;
let renamingId = null;
let roundBombs = [], roundBombEvents = [], roundShots = [];
let sortKey = 'kills', ascending = false, radarImage = null, frameRequest = 0, selectionRequest = 0, lastWarning = '', uploading = false, librarySignature = '';
let mapMeta = null, summaryVisible = false, uploadCancelled = false, batchItems = [];
let replayFocus = null;
const playback = new PlaybackController({
  context:()=>({ready:frames.length>0,tick:playbackTick,tickrate:data?.tickrate||64,
    end:data?.rounds.find(r=>r.number===currentRound)?.end||0,speed:Number($('#speed').value)}),
  onTick:tick=>{setPlaybackTick(tick);if(replayFocus&&tick-replayFocus.tick>(data?.tickrate||64)*.5)replayFocus=null;draw();},
  onState:playing=>{$('#play').textContent=playing?'Ⅱ':'▶';$('#play').setAttribute('aria-label',playing?'Пауза':'Воспроизвести');}
});
const mapReady = MapView.init();
function customRadar() {return radarImage ? {image:radarImage,pos_x:Number($('#posX').value),pos_y:Number($('#posY').value),scale:Math.max(.01,Number($('#mapScale').value)||5)} : null;}
async function setupMap(name) {
  await mapReady;
  return MapView.load(name);
}
function levelOptions(meta) {return (meta?.levels || [{id:'default',label:'Основной этаж'}]).map(l=>`<option value="${l.id}">${esc(l.label)}</option>`).join('');}
async function api(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) { let message = `Ошибка ${res.status}`; try {const detail=(await res.json()).detail;message=typeof detail==='string'?detail:Array.isArray(detail)?detail.map(e=>e.msg).join('; '):message;} catch {} throw new Error(message); }
  return res.json();
}
function notice(message, error = false) { $('#notice').textContent = message; $('#notice').hidden = !message; $('#notice').classList.toggle('error',error); }
function failure(e) { notice(e.message || 'Не удалось выполнить запрос',true); }
function progressBar(value, label) {
  const percent=Number.isFinite(value)?Math.max(0,Math.min(100,value)):null;
  return `<progress class="analysis-progress" max="100" ${percent===null?'':`value="${percent}"`} aria-label="${esc(label)}"></progress>`;
}
function renderBatch() {
  const items=batchItems.map(item=>{
    const match=libraryMatches.find(m=>m.id===item.id);
    if(!match||item.state!=='accepted')return item;
    const message=match.status==='ready'?'Анализ завершён · 100%':match.status==='error'?match.error:match.status==='queued'?'В очереди на анализ':`${match.stage||'Начало анализа'} · ${match.progress||0}% (по этапам)`;
    return {...item,message,state:match.status,progress:match.progress};
  });
  for(const match of libraryMatches){
    if(['queued','parsing'].includes(match.status)&&!items.some(i=>i.id===match.id)){
      batchItems.push({id:match.id,name:match.name,state:'accepted'});
      items.push({id:match.id,name:match.name,state:match.status,progress:match.progress,message:match.status==='queued'?'В очереди на анализ':`${match.stage||'Начало анализа'} · ${match.progress||0}% (по этапам)`});
    }
  }
  $('#uploadBatch').hidden=!items.length;
  $('#cancelUploads').hidden=!uploading||uploadCancelled;
  if(!items.length)return;
  const ready=items.filter(i=>i.state==='ready').length,errors=items.filter(i=>i.state==='error').length;
  $('#batchTitle').textContent=`Загрузка и анализ · Готово ${ready}/${items.length}${errors?' · Ошибок: '+errors:''}`;
  $('#batchFiles').innerHTML=items.map(i=>`<div class="batch-file ${i.state==='error'?'error':''}"><span>${esc(i.name)}</span><small>${esc(i.message)}</small>${['error','cancelled'].includes(i.state)?'':progressBar(i.state==='ready'?100:['uploading','parsing'].includes(i.state)?i.progress:null,i.state==='uploading'?'Загрузка файла':'Анализ demo по этапам')}</div>`).join('');
}
async function library() {
  const list = await api('/api/matches');
  libraryMatches=list;
  renderBatch();
  const signature = JSON.stringify([matchId, summaryVisible, summaryVisible?aggregateScope:null, list.map(m=>[m.id,m.name,m.status,m.error,m.progress,m.stage,m.summary?.map])]);
  if (signature !== librarySignature) {
  librarySignature = signature;
  const row=m=>`<div class="library-row"><button class="library-item ${m.id===matchId?'chosen':''}" data-id="${esc(m.id)}" title="${esc(m.name)}"><strong>${esc(m.name)}</strong><small class="${m.status==='error'?'error':''}">${m.summary?.map?esc(m.summary.map)+' · ':''}${esc(({queued:'В очереди…',parsing:'Разбор demo…',error:'Ошибка обработки',ready:m.summary?.source==='synthetic'?'Учебный матч':`${m.summary?.rounds.length} раундов`})[m.status])} · ${new Date(m.created).toLocaleDateString('ru-RU')}</small></button><button class="library-rename" data-rename="${esc(m.id)}" aria-label="Переименовать ${esc(m.name)}" title="Переименовать demo">✎</button><button class="library-delete" data-delete="${esc(m.id)}" aria-label="Удалить ${esc(m.name)}" title="${m.status==='queued'||m.status==='parsing'?'Дождитесь завершения обработки':'Удалить матч'}" ${m.status==='queued'||m.status==='parsing'?'disabled':''}>×</button></div>`;
  $('#library').innerHTML=list.length?LibraryGroups.group(list).map(g=>`<section class="library-map-group">${g.map&&g.ready?`<button class="library-map-title ${summaryVisible&&aggregateScope===g.map?'chosen':''}" data-library-map="${esc(g.map)}"><strong>${esc(g.map)}</strong><small>${g.ready} демо · Общая статистика ↗</small></button>`:`<div class="library-map-title"><strong>${esc(g.map||'Обработка и ошибки')}</strong></div>`}<details ${!summaryVisible&&g.items.some(m=>m.id===matchId)?'open':''}><summary>Демки (${g.items.length})</summary>${g.items.map(row).join('')}</details></section>`).join(''):'<p class="muted">Здесь появятся твои матчи</p>';
  $('#library').querySelectorAll('[data-library-map]').forEach(b=>b.onclick=()=>openMapAnalysis(b.dataset.libraryMap).catch(failure));
  $('#library').querySelectorAll('[data-id]').forEach(b => b.onclick = () => selectMatch(b.dataset.id).catch(failure));
  $('#library').querySelectorAll('[data-delete]').forEach(b => b.onclick = () => openDelete(b.dataset.delete));
  $('#library').querySelectorAll('[data-rename]').forEach(b => b.onclick = () => openRename(b.dataset.rename));
  if(typeof mapLibraryChanged==='function')mapLibraryChanged();
  }
  const selected = list.find(m => m.id===matchId);
  if(selected&&data)$('#matchName').textContent=selected.name;
  if (selected && selected.status !== 'ready') {
    notice(selected.status==='error' ? selected.error : selected.status==='queued'?'Матч в очереди на анализ.':`${selected.stage||'Анализ выполняется'} · ${selected.progress||0}% (по этапам). Результаты появятся автоматически.`,selected.status==='error');
  } else if (selected?.status === 'ready' && !data && !summaryVisible) { await selectMatch(selected.id); }
  return list;
}
function openRename(id){
  const match=libraryMatches.find(m=>m.id===id);if(!match)return;
  renamingId=id;$('#renameInput').value=match.name;$('#renameError').textContent='';$('#renameDialog').showModal();$('#renameInput').focus();$('#renameInput').select();
}
async function saveRename(event){
  event.preventDefault();
  const id=renamingId,name=$('#renameInput').value.trim();
  if(!id)return;
  if(!name||name.length>240||/[\x00-\x1f\x7f]/.test(name)){$('#renameError').textContent='Введите название от 1 до 240 символов без переносов строк.';return;}
  $('#saveRename').disabled=true;$('#cancelRename').disabled=true;$('#renameError').textContent='';
  try{
    const result=await api(`/api/matches/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
    const match=libraryMatches.find(m=>m.id===id);if(match)match.name=result.name;
    if(matchId===id)$('#matchName').textContent=result.name;
    $('#renameDialog').close();await library();
  }catch(e){if($('#renameDialog').open)$('#renameError').textContent=e.message;else failure(e);}
  finally{$('#saveRename').disabled=false;$('#cancelRename').disabled=false;}
}
function openDelete(id){
  const match=libraryMatches.find(m=>m.id===id);if(!match)return;
  deletingMatch=match;$('#deleteName').textContent=match.name+' · '+new Date(match.created).toLocaleString('ru-RU');$('#deleteError').textContent='';$('#deleteDialog').showModal();
}
async function confirmDelete(){
  const match=deletingMatch;if(!match)return;
  const wasSummary=summaryVisible;
  $('#confirmDelete').disabled=true;$('#cancelDelete').disabled=true;
  try{
    await api(`/api/matches/${match.id}`,{method:'DELETE'});$('#deleteDialog').close();
    if(matchId===match.id){
      pause();selectionRequest++;frameRequest++;profileRequest++;matchId='';data=null;profile=null;frames=[];roundBounds=[];roundGrenades=[];roundEffects=[];radarImage=null;replayFocus=null;
      $('#dashboard').hidden=true;$('#welcome').hidden=false;
    }
    const list=await library();
    if(wasSummary){$('#welcome').hidden=true;$('#dashboard').hidden=true;return;}
    if(!matchId){const next=list.find(m=>m.status==='ready');if(next)await selectMatch(next.id);else notice('Матч удалён из библиотеки.');}
  }catch(e){if($('#deleteDialog').open)$('#deleteError').textContent=e.message;else failure(e);}
  finally{$('#confirmDelete').disabled=false;$('#cancelDelete').disabled=false;}
}
function showMatchWorkspace(){
  summaryVisible=false;$('#mapSummary').hidden=true;$('#mapsNav').classList.remove('active');$('#overviewNav').classList.add('active');
  $('#dashboard').hidden=!data;$('#welcome').hidden=!!data;
}
async function selectMatch(id, includeKnife = false) {
  showMatchWorkspace();
  const req = ++selectionRequest;
  pause(); frameRequest++; matchId = id; data = null; frames = []; roundBounds=[]; roundGrenades=[];roundEffects=[];radarImage = null;
  $('#radarImage').value=''; $('#dashboard').hidden=true; $('#welcome').hidden=false;
  const list = await api('/api/matches');
  if (req!==selectionRequest) return;
  const m = list.find(m => m.id===id);
  if (!m) throw new Error('Матч не найден');
  if (m.status !== 'ready') { await library(); return; }
  const result = await api(`/api/matches/${id}?include_knife=${includeKnife}`);
  if (req!==selectionRequest) return;
  const meta = await setupMap(result.map);
  if (req!==selectionRequest) return;
  data = result; mapMeta=meta;
  $('#knifeOption').hidden=!data.knife_rounds?.length; $('#showKnife').checked=includeKnife;
  $('#replayLevel').innerHTML=levelOptions(meta); $('#resetRadar').hidden=true;
  if(meta){$('#posX').value=meta.pos_x;$('#posY').value=meta.pos_y;$('#mapScale').value=meta.scale;}
  lastWarning = [...data.warnings,...((data.schema_version||1)<2?['Для анализа мест убийств и смертей загрузите этот .dem повторно: старая версия сохранила только общую статистику и снимки перемещений.']:[]),...((data.schema_version||1)<3?['Гранаты и направление взгляда не сохранялись этой версией. Для их отображения загрузите .dem повторно.']:[]),...((data.schema_version||1)<4?['Для таймеров, событий бомбы и стрельбы загрузите demo повторно.']:[])].join('\n'); notice(lastWarning);
  $('#welcome').hidden = true; $('#dashboard').hidden=false;
  $('#mapName').textContent=data.map; $('#matchName').textContent=m.name;
  $('#sourceLabel').textContent=data.source==='synthetic'?'УЧЕБНЫЙ МАТЧ · СИНТЕТИЧЕСКИЕ ДАННЫЕ':'АНАЛИЗ ЗАВЕРШЁН · CS2 DEMO';
  $('#roundCount').textContent=data.rounds.filter(r=>!r.is_knife).length;
  updateSamplingInfo();
  $('#duration').textContent=time(data.rounds.reduce((n,r)=>n+(r.end-r.start)/data.tickrate,0));
  renderMetrics(); renderPlayers(); renderInsights();
  $('#playerFilter').innerHTML='<option value="">Все игроки</option>'+data.players.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  $('#playerFilter').value=''; $('#sideFilter').value='';
  initPlayerAnalysis();
  $('#roundPerspective').innerHTML=data.players.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  renderRoundStrip();
  tab('overview'); await loadRound(data.rounds[0].number); await library();
}
function roundNumber(id){return RoundPresentation.number(data?.rounds||[],id);}
function roundLabel(id,short=false){return RoundPresentation.text(data?.rounds||[],id,short);}
function renderRoundStrip(){
  if(!data)return;
  const groups=RoundPresentation.groups(data.rounds,$('#roundPerspective').value,data.knife_rounds);
  $('#roundStrip').innerHTML=groups.map(g=>`<div class="round-phase side-${g.side} ${g.knife?'knife-phase':''}"><div class="round-phase-label">${esc(RoundPresentation.label(g))}</div><div class="round-phase-cells">${g.rounds.map(r=>`<button class="round-cell ${r.is_knife?'knife-round':''} ${r.winner==='T'?'t':''} ${r.number===currentRound?'current':''}" data-round="${r.number}" title="${roundLabel(r.number)}, победа ${r.winner}"><b>${r.winner==='CT'?'◇':'◆'}</b><small>${r.is_knife?'Ножевой':String(roundNumber(r.number)).padStart(2,'0')}</small></button>`).join('')}</div></div>`).join('');
  $('#roundStrip').querySelectorAll('button').forEach(b=>b.onclick=()=>{tab('replay');loadRound(Number(b.dataset.round)).catch(failure);});
}
$('#roundPerspective').onchange=renderRoundStrip;
function renderMetrics() {
  const competitive=data.rounds.filter(r=>!r.is_knife);
  const ct = competitive.filter(r=>r.winner==='CT').length;
  const kills=data.players.reduce((n,p)=>n+p.kills,0), hs=data.players.reduce((n,p)=>n+p.headshots,0);
  const best=[...data.players].sort((a,b)=>b.adr-a.adr)[0];
  const metrics=[['Победы сторон',`${ct} <small>:</small> ${competitive.length-ct}`,'CT / T · с учётом смены сторон','◈'],['Убийства противников',kills,'За все завершённые раунды','⌁'],['Убийства в голову',`${kills?Math.round(hs/kills*100):0}<small>%</small>`,'Доля от убийств противников','⊕'],['Лидер по ADR',best?best.adr:0,best?best.name:'Нет игроков','↗']];
  $('#metrics').innerHTML=metrics.map((m,i)=>`<div class="panel metric ${i===3?'accent':''}"><span class="label">${m[0]}</span><span class="metric-icon">${m[3]}</span><strong>${m[1]}</strong><p>${esc(m[2])}</p></div>`).join('');
}
function renderPlayers() {
  if(!data) return;
  const players=[...data.players].sort((a,b)=> (typeof a[sortKey]==='string'?a[sortKey].localeCompare(b[sortKey]):a[sortKey]-b[sortKey])*(ascending?1:-1));
  $('#players').innerHTML=players.map(p=>`<tr data-player="${esc(p.id)}" tabindex="0" role="button" aria-label="Позиции игрока ${esc(p.name)}"><td><div class="player-name"><span class="avatar ${p.side==='T'?'t':''}">${esc(p.name.slice(0,2).toUpperCase())}</span>${esc(p.name)}</div></td><td>${p.kills}</td><td class="muted">${p.deaths}</td><td class="muted">${p.assists}</td><td>${p.kd.toFixed(2)}</td><td class="adr">${p.adr.toFixed(1)}</td><td>${p.hs}%</td><td>${p.kast}%<div class="kast-bar"><span style="width:${p.kast}%"></span></div></td><td class="muted">${p.opening_kills}</td></tr>`).join('');
  $('#players').querySelectorAll('tr').forEach(row=>{const action=()=>{$('#profilePlayer').value=row.dataset.player;tab('playerAnalysis');refreshPlayerAnalysis().catch(failure);};row.onclick=action;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();action();}};});
}
function insights() {
  const ranked=[...data.players].sort((a,b)=>b.adr-a.adr), best=ranked[0];
  const entry=[...data.players].sort((a,b)=>b.opening_kills-a.opening_kills)[0];
  const stable=[...data.players].sort((a,b)=>b.kast-a.kast)[0];
  return best ? [
    {title:'Наибольший средний урон',value:`${best.adr} ADR`,text:`${best.name} наносит больше всего урона за раунд: ${best.damage} HP за ${best.rounds} раундов участия.`},
    {title:'Первый контакт',value:`${entry.opening_kills} entry`,text:`${entry.name}: ${entry.opening_kills} первых убийств и ${entry.opening_deaths} первых смертей. Эти события помогают найти раунды для разбора начальных дуэлей.`},
    {title:'Участие в раундах',value:`${stable.kast}% KAST`,text:`${stable.name} чаще остальных убивал, помогал, выживал или был разменян. Сравни эту метрику с ADR и ролью игрока.`}
  ] : [];
}
function renderInsights() {
  const ranked=[...data.players].sort((a,b)=>b.adr-a.adr), max=ranked[0]?.adr || 1;
  $('#damageChart').innerHTML=ranked.slice(0,6).map(p=>`<div class="damage-row"><span>${esc(p.name)}</span><div class="bar-track"><i style="width:${p.adr/max*100}%"></i></div><b>${p.adr}</b></div>`).join('');
  const notes=insights();
  $('#quickInsights').innerHTML=notes.slice(0,2).map(n=>`<p><b>${esc(n.title)}.</b> ${esc(n.text)}</p>`).join('');
  $('#insightCards').innerHTML=notes.map(n=>`<article class="panel insight-card"><div class="eyebrow">${esc(n.title)}</div><div class="insight-value">${esc(n.value)}</div><p>${esc(n.text)}</p></article>`).join('');
}
function tab(name) {
  document.querySelectorAll('.tab-content').forEach(el=>el.hidden=el.id!==name);
  document.querySelectorAll('[data-tab]').forEach(el=>{el.classList.toggle('selected',el.dataset.tab===name);el.setAttribute('aria-selected',el.dataset.tab===name);});
  if(name==='replay') draw(); else pause();
  if(name==='playerAnalysis') drawPlayerAnalysis();
}
async function loadRound(number) {
  playback.suspend(); replayFocus=null; currentRound=number; const req=++frameRequest, id=matchId;
  frames=[]; roundBounds=[];roundGrenades=[];roundEffects=[];roundBombs=[];roundBombEvents=[];roundShots=[]; frameIndex=0; draw();
  $('#timeline').disabled=true;
  $('#roundTitle').textContent=roundLabel(number);
  document.querySelectorAll('.round-cell').forEach(b=>b.classList.toggle('current',Number(b.dataset.round)===number));
  let next;
  try{next=await api(`/api/matches/${id}/rounds/${number}`);}
  catch(e){if(req!==frameRequest||id!==matchId)return;pause();throw e;}
  if(req!==frameRequest||id!==matchId) return;
  frames=next; roundBounds=Replay.bounds(frames); frameIndex=0;
  const events=data.events.filter(e=>e.round===number), round=data.rounds.find(r=>r.number===number);
  roundGrenades=(data.grenades||[]).filter(g=>g.round===number);roundEffects=(data.utility_effects||[]).filter(g=>g.round===number);
  roundBombs=(data.bombs||[]).filter(b=>b.round===number);roundBombEvents=(data.bomb_events||[]).filter(e=>e.round===number);roundShots=(data.shots||[]).filter(e=>e.round===number);
  playbackTick=round.start;$('#timeline').max=Math.max(0,round.end-round.start);$('#timeline').value=0;
  $('#timeline').disabled=false;
  $('#eventCount').textContent=`${events.length} EVENTS`;
  $('#killfeed').innerHTML=events.length?events.map(e=>`<button class="kill-row" data-tick="${e.tick}"><span class="kill-time">${time((e.tick-round.start)/data.tickrate)} ${e.headshot?'· HEADSHOT':''}</span><span class="${e.side==='CT'?'ct':'t'}">${esc(e.attacker)}</span><span class="weapon">${esc(e.weapon)} →</span><span>${esc(e.victim)}</span></button>`).join(''):'<p class="map-note">В этом раунде нет убийств</p>';
  $('#killfeed').querySelectorAll('button').forEach(b=>b.onclick=()=>seekPlayback(Number(b.dataset.tick),{focus:events.find(e=>e.tick===Number(b.dataset.tick))}));
  $('#utilityFeed').innerHTML=roundEffects.length?roundEffects.map(e=>`<button class="kill-row utility-row" data-utility-tick="${e.start}" title="${esc(Overlays.kinds[e.kind]?.label||e.kind)}" aria-label="${esc(Overlays.kinds[e.kind]?.label||e.kind)}: ${esc(e.owner_name)}"><span class="kill-time">${time((e.start-round.start)/data.tickrate)}</span>${Overlays.icon(e.kind)}<span>${esc(e.owner_name)}</span></button>`).join(''):`<p class="map-note">${data.capabilities?.grenades?'В этом раунде нет событий гранат.':'Данные гранат отсутствуют. Загрузите demo повторно.'}</p>`;
  $('#utilityFeed').querySelectorAll('button').forEach(b=>b.onclick=()=>seekPlayback(Number(b.dataset.utilityTick),{positions:true}));
  const bombNames={bomb_beginplant:'Начало установки',bomb_abortplant:'Установка прервана',bomb_planted:'C4 установлена',bomb_begindefuse:'Начало обезвреживания',bomb_abortdefuse:'Обезвреживание прервано',bomb_defused:'C4 обезврежена',bomb_exploded:'C4 взорвалась'};
  $('#bombFeed').innerHTML=roundBombEvents.length?roundBombEvents.map(e=>`<button class="kill-row" data-action-tick="${e.tick}"><span class="kill-time">${time((e.tick-round.start)/data.tickrate)}</span>${bombNames[e.type]||esc(e.type)}${e.site?' · '+esc(e.site):''} · ${esc(e.actor)}</button>`).join(''):'<p class="map-note">Нет событий бомбы</p>';
  $('#shotSummary').textContent=`Выстрелы · ${roundShots.length}`;
  $('#shotFeed').innerHTML=roundShots.map(e=>`<button class="kill-row" data-action-tick="${e.tick}"><span class="kill-time">${Replay.formatTime((e.tick-round.start)/data.tickrate)}</span>${esc(e.shooter)} · ${esc(e.weapon)}</button>`).join('');
  document.querySelectorAll('[data-action-tick]').forEach(b=>b.onclick=()=>seekPlayback(Number(b.dataset.actionTick),{positions:true}));
  draw();
  playback.resume();
  return true;
}
function updateSamplingInfo(){
  if(!data)return;
  const hz=Replay.sampleRate(data);
  $('#savedSampleRate').textContent=`СОХРАНЕНО ${hz} СНИМКОВ/СЕК`;
  $('#samplingNote').textContent=`Частота этого матча: ${hz} снимков/сек, шаг ${(1000/hz).toLocaleString('ru-RU',{maximumFractionDigits:3})} мс. ${$('#interpolation').checked?'Промежуточные положения сглаживаются; это не дополнительные записанные снимки.':'Показаны только сохранённые снимки.'} Для другой частоты загрузите .dem заново с выбранной настройкой.`;
}
function setPlaybackTick(tick){
  const round=data?.rounds.find(r=>r.number===currentRound);if(!round)return;
  playbackTick=Math.max(round.start,Math.min(round.end,tick));
  frameIndex=Replay.index(frames,playbackTick);$('#timeline').value=Math.round(playbackTick-round.start);
}
function seekPlayback(tick,{focus=null,positions=false}={}){
  playback.seek(()=>{
    replayFocus=focus;
    if(positions){heat=false;$('#positionsMode').classList.add('selected');$('#heatMode').classList.remove('selected');}
    setPlaybackTick(tick);draw();
  });
}
function pause(){playback.pause();}
function play(){
  if(playback.playing){pause();return;}if(!data)return;
  replayFocus=null;heat=false;$('#positionsMode').classList.add('selected');$('#heatMode').classList.remove('selected');
  const round=data.rounds.find(r=>r.number===currentRound);
  if(!round)return;
  if(frames.length&&playbackTick>=round.end)setPlaybackTick(round.start);
  playback.start();
}
function draw() {
  const canvas=$('#radar');
  Overlays.markers=[];canvas.removeAttribute('title');
  const selected=$('#replayLevel').value || 'default';
  const {ctx,project,label}=MapView.base(canvas,mapMeta,selected,roundBounds,customRadar());
  $('#radarLabel').textContent=label;
  const round=data?.rounds.find(r=>r.number===currentRound);
  const tactical=round?RoundState.state(round,frames,roundBombs,roundBombEvents,playbackTick,data.tickrate,Number($('#fallbackFuse').value)||40):null;
  renderRoundHud(tactical,round);
  if(tactical&&$('#showBomb').checked)RoundState.drawBomb(ctx,project,mapMeta,selected,tactical,playbackTick,data.tickrate);
  $('#overlayNote').textContent=`Стрелка — горизонтальное направление взгляда (yaw). Дым и огонь показаны условными областями вокруг центра; это не точная форма эффекта. ${!data?.capabilities?.view_angles?'Для углов взгляда нужен повторный разбор demo.':''}`;
  const frame=Replay.snapshot(frames,playbackTick,data?.tickrate||64,$('#interpolation').checked);
  if(!frame){ctx.fillStyle='#a6b5c8';ctx.font='16px Segoe UI';ctx.textAlign='center';ctx.fillText('Нет снимков позиций',canvas.width/2,canvas.height/2);$('#clock').textContent='0:00.000';$('#duelFocus').hidden=true;$('#utilityStatus').textContent='';return;}
  const filter=p=>(!$('#playerFilter').value||p.id===$('#playerFilter').value)&&(!$('#sideFilter').value||p.side===$('#sideFilter').value)&&MapView.onLevel(mapMeta,p,selected);
  if(heat){
    const bins=new Map();
    for(const f of frames)for(const p of f.players)if(p.alive&&filter(p)){const [x,y]=project(p),key=`${Math.floor(x/16)},${Math.floor(y/16)}`;bins.set(key,(bins.get(key)||0)+1);}
    let max=1;for(const v of bins.values())max=Math.max(max,v);
    for(const [key,count] of bins){const [x,y]=key.split(',').map(Number);const alpha=.15+.7*Math.sqrt(count/max);ctx.fillStyle=`rgba(245,163,91,${alpha})`;ctx.fillRect(x*16,y*16,16,16);}
  }else{
    if($('#showGrenades').checked){
      const counts=Overlays.draw(ctx,project,mapMeta,selected,roundGrenades,roundEffects,playbackTick,data.tickrate,{owner:$('#playerFilter').value,side:$('#sideFilter').value,interpolate:$('#interpolation').checked,trails:$('#showTrails').checked,names:$('#names').checked});
      $('#utilityStatus').textContent=`В полёте: ${counts.flying} · Активных эффектов: ${counts.active}`;
    }else $('#utilityStatus').textContent='Гранаты скрыты';
    for(const p of frame.players.filter(filter)){
      const [x,y]=project(p),color=p.side==='CT'?'#69b7e7':'#edb968';ctx.globalAlpha=p.alive?1:.25;
      if($('#showGaze').checked)Overlays.gaze(ctx,p,project,color);
      ctx.fillStyle=color;ctx.strokeStyle=color;ctx.lineWidth=2;
      if(p.alive){ctx.beginPath();ctx.arc(x,y,8,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#0b1016';ctx.stroke();}
      else{ctx.beginPath();ctx.moveTo(x-5,y-5);ctx.lineTo(x+5,y+5);ctx.moveTo(x+5,y-5);ctx.lineTo(x-5,y+5);ctx.stroke();}
      if($('#names').checked){ctx.font='12px Segoe UI';ctx.textAlign='center';ctx.fillStyle='#dce6f0';ctx.fillText(p.name,x,y-16);}
      ctx.globalAlpha=1;
    }
    if($('#showShots').checked){
      const count=RoundState.drawShots(ctx,project,mapMeta,selected,roundShots,playbackTick,data.tickrate,$('#playerFilter').value,$('#sideFilter').value);
      $('#utilityStatus').textContent+=` · Выстрелов сейчас: ${count}`;
    }
  }
  if(heat)$('#utilityStatus').textContent='Слои гранат и взгляда доступны в режиме «Позиции».';
  $('#duelFocus').hidden=!replayFocus;
  if(replayFocus){
    const e=replayFocus;
    const a=e.attacker_position,v=e.victim_position;
    $('#duelFocus').textContent=`Точные позиции события ${Replay.formatTime((e.tick-round.start)/data.tickrate)}: ${e.attacker} → ${e.victim} · ${e.weapon}. Частота снимков матча: ${Replay.sampleRate(data)}/сек.`;
    if(a&&v&&MapView.onLevel(mapMeta,a,selected)&&MapView.onLevel(mapMeta,v,selected)){
      const [ax,ay]=project(a),[vx,vy]=project(v);ctx.strokeStyle='#fff0b7';ctx.lineWidth=2;ctx.setLineDash([7,6]);ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(vx,vy);ctx.stroke();ctx.setLineDash([]);
    }
    for(const [point,color,name] of [[a,'#6fe0b1',e.attacker],[v,'#ff777d',e.victim]]){
      if(!point||!MapView.onLevel(mapMeta,point,selected))continue;
      const [x,y]=project(point);ctx.strokeStyle=color;ctx.lineWidth=3;ctx.beginPath();ctx.arc(x,y,13,0,Math.PI*2);ctx.stroke();ctx.fillStyle=color;ctx.textAlign='center';ctx.font='bold 13px Segoe UI';ctx.fillText(name,x,y-20);
    }
  }
  $('#clock').textContent=Replay.formatTime((playbackTick-round.start)/data.tickrate);
  $('#killfeed').querySelectorAll('[data-tick]').forEach(b=>b.classList.toggle('future',Number(b.dataset.tick)>playbackTick));
  $('#alive').innerHTML=`<span>CT ${frame.players.filter(p=>p.alive&&p.side==='CT').length} в живых</span><span>T ${frame.players.filter(p=>p.alive&&p.side==='T').length} в живых</span>`;
}
function renderRoundHud(state,round){
  const c=state?.clock,b=state?.bomb;
  $('#roundTimerLabel').textContent=state?.phase==='freeze'?'Подготовка':state?.phase==='paused'?'Пауза':'Таймер раунда';
  $('#roundCountdown').textContent=state?.finished?'Завершён':b?.state==='planted'?'C4 активна':RoundState.countdown(c?.seconds);
  $('#roundCountdown').classList.toggle('urgent',!!c&&c.seconds<10&&!state.finished);
  $('#roundPhase').textContent=state?.finished?`Победа ${round.winner}`:c?.paused?'Отсчёт приостановлен':c?.freeze?'До начала раунда':b?.state==='planted'?'После установки исход определяет C4':'До истечения игрового времени';
  $('#bombTimerLabel').textContent=b?`C4 · ${b.site?'Плент '+b.site:'ID '+(b.raw_site??'?')}`:'C4';
  $('#bombCountdown').textContent=!b?'Не установлена':b.state==='planted'?(b.approximate?'≈ ':'')+RoundState.countdown(b.remaining):b.state==='defused'?'Обезврежена':b.state==='exploded'?'Взрыв':'Раунд завершён';
  const sources={recorded_explosion:'По событию взрыва этой demo',server_cvar:'По серверному mp_c4timer',measured_other_rounds:'Оценка по другим взрывам матча',unknown:'Оценка по введённому таймеру'};
  $('#bombPhase').textContent=b?(sources[b.fuse_source]||''):'Место установки появится после события';
  $('#bombAction').textContent=b?.defuse?RoundState.countdown(b.defuse.remaining):state?.planting?'Установка…':'—';
  $('#bombActor').textContent=b?.defuse?`${b.defuse.actor} · ${b.defuse.has_kit?'с набором':'без набора'}`:state?.planting?state.planting.actor:'';
  $('#fallbackFuseControl').hidden=!b||b.fuse_source!=='unknown'||b.state!=='planted';
  $('#tacticalNote').textContent='Пленты A/B отмечены по overview. Маркер C4 — позиция установившего в событии установки. Линия выстрела показывает направление взгляда, без расчёта разброса, попаданий и преград.';
}
async function upload(files){
  if(!files||uploading)return;
  const batch=typeof files.name==='string'?[files]:Array.from(files);if(!batch.length)return;
  uploading=true;uploadCancelled=false;$('#uploadBatch').hidden=false;$('#cancelUploads').hidden=false;
  const sampleRate=$('#sampleRate').value;$('#sampleRate').disabled=true;$('#demoFile').value='';
  let first=true;
  try{
    const items=await UploadQueue.run(batch,{
      cancelled:()=>uploadCancelled,
      list:()=>library(),
      onUpdate:items=>{
        batchItems=items;
        renderBatch();
      },
      upload:(file,progress)=>new Promise((resolve,reject)=>{
        const xhr=new XMLHttpRequest();xhr.open('POST',`/api/upload?name=${encodeURIComponent(file.name)}&sample_rate=${sampleRate}`);xhr.setRequestHeader('Content-Type','application/octet-stream');
        xhr.upload.onprogress=e=>{if(e.lengthComputable)progress(`Загрузка ${Math.round(e.loaded/e.total*100)}%`,Math.round(e.loaded/e.total*100));};
        xhr.onload=()=>{let res;try{res=JSON.parse(xhr.responseText);}catch{reject(new Error('Сервер вернул некорректный ответ'));return;}if(xhr.status>=200&&xhr.status<300)resolve(res);else{const error=new Error(typeof res.detail==='string'?res.detail:'Ошибка загрузки');error.status=xhr.status;reject(error);}};
        xhr.onerror=()=>reject(new Error('Соединение с сервером прервано'));xhr.send(file);
      }),
      onAccepted:async result=>{if(first){first=false;await selectMatch(result.id);}else await library();}
    });
    notice(`Отправлено на анализ: ${items.filter(i=>i.state==='accepted').length} из ${items.length}. Демки автоматически добавятся в группы своих карт.`);
    if(items.filter(i=>i.state==='accepted').length>1)await openMapAnalysis();
  }finally{uploading=false;$('#sampleRate').disabled=false;$('#cancelUploads').hidden=true;}
}
$('#cancelUploads').onclick=()=>{uploadCancelled=true;$('#cancelUploads').hidden=true;};

document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
document.querySelectorAll('[data-sort]').forEach(th=>{th.tabIndex=0;const action=()=>{ascending=sortKey===th.dataset.sort?!ascending:th.dataset.sort==='name';sortKey=th.dataset.sort;renderPlayers();};th.onclick=action;th.onkeydown=e=>{if(e.key==='Enter')action();};});
$('#moreInsights').onclick=()=>tab('insights');$('#overviewNav').onclick=()=>{showMatchWorkspace();tab('overview');window.scrollTo({top:0,behavior:'smooth'});};
$('#refresh').onclick=()=>library().catch(failure);
$('#deleteCurrent').onclick=()=>openDelete(matchId);
$('#renameCurrent').onclick=()=>openRename(matchId);
$('#renameForm').onsubmit=saveRename;
$('#cancelRename').onclick=()=>$('#renameDialog').close();
$('#renameDialog').addEventListener('cancel',e=>{if($('#saveRename').disabled)e.preventDefault();});
$('#cancelDelete').onclick=()=>$('#deleteDialog').close();
$('#confirmDelete').onclick=confirmDelete;
$('#deleteDialog').addEventListener('cancel',e=>{if($('#confirmDelete').disabled)e.preventDefault();});
$('#sample').onclick=async()=>{const b=$('#sample');b.disabled=true;try{const m=await api('/api/sample',{method:'POST'});await selectMatch(m.id);}catch(e){failure(e);}finally{b.disabled=false;}};
$('#demoFile').onchange=e=>upload(e.target.files).catch(failure);
$('#timeline').oninput=e=>{const round=data?.rounds.find(r=>r.number===currentRound);if(round)seekPlayback(round.start+Number(e.target.value));};$('#play').onclick=play;
$('#speed').onchange=()=>playback.resume();
$('#interpolation').onchange=()=>{updateSamplingInfo();draw();};
$('#sampleRate').onchange=()=>{$('#samplingHint').textContent=`Новые загрузки: ${$('#sampleRate').value} снимков/сек. Частота сохранённых матчей не меняется.`;};
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
['playerFilter','sideFilter','names','replayLevel','posX','posY','mapScale','showGaze','showGrenades','showTrails','showBomb','showShots','fallbackFuse'].forEach(id=>$('#'+id).onchange=()=>{draw();drawPlayerAnalysis();});
$('#positionsMode').onclick=()=>{heat=false;$('#positionsMode').classList.add('selected');$('#heatMode').classList.remove('selected');draw();};
$('#heatMode').onclick=()=>{heat=true;pause();$('#heatMode').classList.add('selected');$('#positionsMode').classList.remove('selected');draw();};
$('#radarImage').onchange=e=>{const file=e.target.files[0];if(!file)return;const url=URL.createObjectURL(file),img=new Image(),id=matchId;img.onload=()=>{URL.revokeObjectURL(url);if(matchId!==id)return;radarImage=img;$('#resetRadar').hidden=false;draw();drawPlayerAnalysis();};img.onerror=()=>{URL.revokeObjectURL(url);failure(new Error('Не удалось открыть изображение радара'));};img.src=url;};
$('#resetRadar').onclick=()=>{radarImage=null;$('#radarImage').value='';$('#resetRadar').hidden=true;draw();drawPlayerAnalysis();};
let dragDepth=0;
window.addEventListener('dragenter',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();dragDepth++;$('#dropOverlay').hidden=false;}});
window.addEventListener('dragover',e=>e.preventDefault());
window.addEventListener('dragleave',()=>{if(--dragDepth<=0){dragDepth=0;$('#dropOverlay').hidden=true;}});
window.addEventListener('drop',e=>{e.preventDefault();dragDepth=0;$('#dropOverlay').hidden=true;upload(e.dataTransfer.files).catch(failure);});
library().then(list=>{if(list.some(m=>m.status==='ready'))return openMapAnalysis();}).catch(failure);
setInterval(()=>{library().catch(()=>{});},1500);

$('#showKnife').onchange=()=>selectMatch(matchId,$('#showKnife').checked).catch(failure);

$('#radar').addEventListener('mousemove',event=>{
  const canvas=event.currentTarget,rect=canvas.getBoundingClientRect();
  const x=(event.clientX-rect.left)*canvas.width/rect.width,y=(event.clientY-rect.top)*canvas.height/rect.height;
  const marker=[...Overlays.markers].reverse().find(m=>Math.hypot(x-m.point[0],y-m.point[1])<=16);
  if(marker)canvas.title=`${marker.label}${marker.owner?' · '+marker.owner:''}`;
  else canvas.removeAttribute('title');
});
$('#radar').addEventListener('mouseleave',event=>event.currentTarget.removeAttribute('title'));

$('#utilityLegend').innerHTML=Object.keys(Overlays.kinds).map(kind=>`<span title="${esc(Overlays.kinds[kind].label)}" aria-label="${esc(Overlays.kinds[kind].label)}">${Overlays.icon(kind)}</span>`).join('');

function updateRadarFit(){
  const toolbar=$('.radar-panel>.playback');
  // Leave space for the sticky toolbar, its bottom gap and viewport margins.
  const height=Math.max(1,window.innerHeight-toolbar.getBoundingClientRect().height-40);
  $('#radarViewport').style.setProperty('--radar-fit-height',`${height}px`);
}
function setRadarScale(value){
  const fit=value==='fit'||![50,75,100,125,150,200].includes(Number(value));
  $('#radarScale').value=fit?'fit':String(value);
  $('#radarViewport').classList.toggle('radar-fit',fit);
  $('#radarMap').style.width=fit?'':`${Number(value)}%`;
  $('#radarViewport').scrollTop=0;$('#radarViewport').scrollLeft=0;
  updateRadarFit();
}
$('#radarScale').onchange=event=>setRadarScale(event.target.value);
window.addEventListener('resize',updateRadarFit);
new ResizeObserver(updateRadarFit).observe($('.radar-panel>.playback'));
setRadarScale('fit');

function replayKeyboard(event){
  if(event.defaultPrevented||event.isComposing||event.ctrlKey||event.metaKey||event.altKey||event.shiftKey)return;
  if(![' ','ArrowLeft','ArrowRight'].includes(event.key))return;
  if($('#dashboard').hidden||$('#replay').hidden||!data||!frames.length||document.querySelector('dialog[open]'))return;
  const target=event.target;
  if(target?.isContentEditable)return;
  if(target?.closest('input,textarea,select,button,a,summary,[role="button"],[role="tab"],[contenteditable]')&&!['play','timeline'].includes(target.id))return;
  event.preventDefault();
  if(event.key===' '){if(!event.repeat)play();return;}
  const seconds=event.key==='ArrowLeft'?-5:5;
  seekPlayback(playbackTick+seconds*data.tickrate);
}
document.addEventListener('keydown',replayKeyboard);
