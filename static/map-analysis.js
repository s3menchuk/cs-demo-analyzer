let aggregateReport=null,aggregateMap=null,aggregateMeta=null,aggregateCells=[],aggregateRequest=0,aggregateMapRequest=0;
let aggregateScope=null,aggregateOpening=false;
function aggregateMembers(){return libraryMatches.filter(m=>m.status==='ready'&&(!aggregateScope||m.summary?.map===aggregateScope)&&(aggregateScope||m.summary?.source!=='synthetic'));}
function updateAggregatePlayers(){
 const previous=$('#aggregatePlayer').value,players=new Map();
 for(const m of aggregateMembers())for(const p of m.summary?.players||[])if(!players.has(p.id))players.set(p.id,p.name);
 $('#aggregatePlayer').innerHTML='<option value="">Все игроки</option>'+[...players].sort((a,b)=>a[1].localeCompare(b[1])).map(([id,name])=>`<option value="${esc(id)}">${esc(name)} · ${esc(id)}</option>`).join('');
 if(players.has(previous))$('#aggregatePlayer').value=previous;
}
function mapLibraryChanged(){
 if(summaryVisible&&!aggregateOpening){updateAggregatePlayers();runMapAnalysis().catch(failure);}
}
async function openMapAnalysis(mapName=null){
 aggregateScope=mapName;aggregateOpening=true;
 notice('');pause();selectionRequest++;frameRequest++;profileRequest++;summaryVisible=true;
 $('#dashboard').hidden=true;$('#welcome').hidden=true;$('#mapSummary').hidden=false;$('#mapsNav').classList.add('active');$('#overviewNav').classList.remove('active');
 try{await library();}finally{aggregateOpening=false;}
 if(!summaryVisible||aggregateScope!==mapName)return;
 $('#aggregateScopeDescription').textContent=mapName?`Группа ${mapName}: статистика по всем готовым демкам этой карты. Новые игры добавляются автоматически.`:'Все готовые демки автоматически объединены по картам. Выберите карту для общей статистики и списка входящих игр.';
 $('#aggregateAllMaps').hidden=!mapName;
 updateAggregatePlayers();await runMapAnalysis();
}
async function runMapAnalysis(){
 const request=++aggregateRequest;aggregateMapRequest++;$('#aggregateRun').disabled=false;
 aggregateReport=null;aggregateMap=null;
 $('#aggregateStatus').textContent='Считаю статистику групп карт…';$('#aggregateDetail').hidden=true;$('#aggregateCards').innerHTML='';$('#aggregateRun').disabled=true;
 const params=new URLSearchParams({cell_size:$('#aggregateCell').value,include_knife:String($('#aggregateKnife').checked)});
 if(aggregateScope){params.set('map_name',aggregateScope);params.set('include_synthetic','true');}
 if($('#aggregatePlayer').value)params.set('player_id',$('#aggregatePlayer').value);
 try{
  const report=await api('/api/analysis/maps?'+params);
  if(request!==aggregateRequest||!summaryVisible)return;aggregateReport=report;
  $('#aggregateStatus').textContent=report.maps.length?`Всего демок: ${report.matches_count} · Групп карт: ${report.maps.length}${report.skipped_matches?' · Игрок не участвовал в '+report.skipped_matches+' демках':''}. Статистика включает все готовые демки ${aggregateScope?'этой карты':'каждой карты'}.`:'В этой группе пока нет готовых демок. Они появятся здесь после завершения анализа.';
  $('#aggregateCards').innerHTML=report.maps.map((m,i)=>`<button class="panel aggregate-card" data-map-index="${i}"><strong>${esc(m.map)}</strong><span>${m.matches_count} демо в группе · ${m.rounds} раундов</span><small>${m.totals.kills} K / ${m.totals.deaths} D · K/D ${m.totals.kd} · ADR ${m.totals.adr}</small></button>`).join('');
  $('#aggregateCards').querySelectorAll('button').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.mapIndex);(aggregateScope?selectAggregateMap(i):openMapAnalysis(report.maps[i].map)).catch(failure);});
  if(report.maps.length)await selectAggregateMap(0);
 }catch(e){if(request===aggregateRequest)$('#aggregateStatus').textContent=e.message;}
 finally{if(request===aggregateRequest)$('#aggregateRun').disabled=false;}
}
async function selectAggregateMap(index){
 const report=aggregateReport,map=report?.maps[index];if(!map)return;
 const request=++aggregateMapRequest;await mapReady;const meta=await MapView.load(map.map);
 if(request!==aggregateMapRequest||report!==aggregateReport||!summaryVisible)return;
 aggregateMap=map;aggregateMeta=meta;$('#aggregateDetail').hidden=false;
 $('#aggregateCards').querySelectorAll('button').forEach(b=>b.classList.toggle('chosen',Number(b.dataset.mapIndex)===index));
 $('#aggregateMapTitle').textContent=map.map;$('#aggregateLevel').innerHTML=levelOptions(meta);
 const p=map.totals,entries=[['Игры / раунды',`${map.matches_count} / ${map.rounds}`],['Убийства / смерти',`${p.kills} / ${p.deaths}`],['K/D',p.kd],['ADR',p.adr]];
 $('#aggregateMetrics').innerHTML=entries.map(([label,value])=>`<div class="panel metric"><span class="label">${label}</span><strong>${value}</strong></div>`).join('');
 $('#aggregatePlayers').innerHTML=map.players.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.matches}</td><td>${p.kills}</td><td>${p.deaths}</td><td>${p.assists}</td><td>${p.kills-p.deaths}</td><td>${p.kd}</td><td>${p.adr}</td><td>${p.hs}%</td><td>${p.rounds}</td></tr>`).join('');
 $('#aggregateGames').innerHTML=map.matches.map(m=>`<button class="aggregate-game" data-open-match="${esc(m.id)}">${esc(m.name)}<small>${m.rounds} раундов · Открыть матч ↗</small></button>`).join('');
 $('#aggregateGames').querySelectorAll('button').forEach(b=>b.onclick=()=>selectMatch(b.dataset.openMatch).catch(failure));
 $('#aggregateWarnings').textContent=map.warnings.join(' ');$('#aggregateSelection').textContent='Выберите ячейку на карте.';
 drawAggregateMap();
}
function drawAggregateMap(){
 if(!aggregateMap)return;
 const zones=aggregateMap.balance_zones,level=$('#aggregateLevel').value;
 const {ctx,project,label}=MapView.base($('#aggregateMap'),aggregateMeta,level,BalanceMap.bounds(zones));
 $('#aggregateMapLabel').textContent=label;aggregateCells=BalanceMap.draw(ctx,project,zones,aggregateMeta?.levels.length>1?level:null);
 const m=aggregateMap,p=m.totals;
 $('#aggregateCoverage').textContent=`Координаты убийств: ${m.kills_with_position}/${p.kills} · смертей: ${m.deaths_with_position}/${p.deaths}. Записи с данными событий: ${m.spatial_matches}/${m.matches_count}. Размер ячейки: ${aggregateReport.cell_size} ед. Цветовая интенсивность симметрична относительно нуля в пределах этажа.`;
}
$('#mapsNav').onclick=()=>openMapAnalysis().catch(failure);
$('#aggregateRefresh').onclick=()=>openMapAnalysis(aggregateScope).catch(failure);
$('#aggregateAllMaps').onclick=()=>openMapAnalysis().catch(failure);
$('#aggregateRun').onclick=()=>runMapAnalysis().catch(failure);
for(const id of ['aggregatePlayer','aggregateCell','aggregateKnife'])$('#'+id).onchange=()=>runMapAnalysis().catch(failure);
$('#aggregateLevel').onchange=()=>{drawAggregateMap();$('#aggregateSelection').textContent='Выберите ячейку на карте.';};
$('#aggregateMap').onclick=e=>{const rect=e.currentTarget.getBoundingClientRect(),z=BalanceMap.hit(aggregateCells,(e.clientX-rect.left)*900/rect.width,(e.clientY-rect.top)*900/rect.height);$('#aggregateSelection').textContent=z?BalanceMap.description(z):'В этой ячейке нет событий с координатами.';};
