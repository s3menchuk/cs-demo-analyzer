let faceitGames=[],faceitDownloads=false;
function faceitStatus(message,error=false){
  $('#faceitStatus').textContent=message;
  $('#faceitStatus').classList.toggle('error',error);
}
async function faceitRequest(url,options){
  const response=await fetch(url,options);
  let value;try{value=await response.json();}catch{throw new Error('Сервер вернул некорректный ответ.');}
  if(!response.ok){const error=new Error(typeof value.detail==='string'?value.detail:`Ошибка ${response.status}`);error.status=response.status;throw error;}
  return value;
}
function faceitId(game){return `faceit_${game.match_id.toLowerCase()}_${game.demo_index}`;}
function renderFaceitGames(){
  $('#faceitMatches').innerHTML=faceitGames.map((game,index)=>{
    const existing=libraryMatches.find(m=>m.id===faceitId(game));
    const already=existing&&existing.status!=='error';
    const reason=already?(existing.status==='ready'?'Уже в библиотеке':'Уже в очереди анализа'):!game.demo_count?game.unavailable_reason:!faceitDownloads?'Для скачивания нужен доступ Downloads API':'';
    return `<div class="faceit-match"><label><input type="checkbox" data-faceit-game="${index}" ${reason?'disabled':''}><span><strong>${esc(game.name)}</strong><small>${new Date(game.finished_at*1000).toLocaleString('ru-RU')}${game.demo_count>1?' · Демо '+(game.demo_index+1):''}${reason?' · '+esc(reason):''}</small></span></label><a href="${esc(game.url)}" target="_blank" rel="noopener noreferrer">Матч ↗</a></div>`;
  }).join('');
  $('#faceitActions').hidden=!faceitGames.length;
  updateFaceitSelection();
}
function updateFaceitSelection(){
  const selected=$('#faceitMatches').querySelectorAll('input:checked:not(:disabled)').length;
  $('#faceitImport').textContent=`Скачать и анализировать${selected?' ('+selected+')':''}`;
  $('#faceitImport').disabled=!selected||uploading;
  $('#faceitSelectAll').disabled=!$('#faceitMatches').querySelector('input:not(:disabled)')||uploading;
}
$('#faceitMatches').addEventListener('change',updateFaceitSelection);
$('#faceitSelectAll').onclick=()=>{
  const inputs=Array.from($('#faceitMatches').querySelectorAll('input:not(:disabled)'));
  const select=inputs.some(input=>!input.checked);inputs.forEach(input=>input.checked=select);updateFaceitSelection();
};
$('#faceitForm').onsubmit=async event=>{
  event.preventDefault();
  if(uploading){faceitStatus('Дождитесь отправки текущих файлов.',true);return;}
  $('#faceitFind').disabled=true;$('#faceitActions').hidden=true;faceitGames=[];$('#faceitMatches').innerHTML='';
  faceitStatus('Получаем последние матчи FACEIT…');
  try{
    const result=await faceitRequest(`/api/faceit/matches?profile=${encodeURIComponent($('#faceitProfile').value.trim())}&limit=${$('#faceitLimit').value}`);
    faceitDownloads=result.downloads_api;
    faceitGames=result.matches.flatMap(game=>Array.from({length:Math.max(1,game.demo_count)},(_,demo_index)=>({...game,demo_index})));
    renderFaceitGames();
    faceitStatus(result.matches.length?`${result.nickname} · Последних завершённых матчей: ${result.matches.length}. Выберите демо для анализа.`:'Завершённые игры CS2 не найдены.');
  }catch(error){faceitStatus(error.message,true);}
  finally{$('#faceitFind').disabled=false;}
};
$('#faceitImport').onclick=async()=>{
  if(uploading){faceitStatus('Дождитесь отправки текущих файлов.',true);return;}
  const selected=Array.from($('#faceitMatches').querySelectorAll('input:checked:not(:disabled)'),input=>faceitGames[Number(input.dataset.faceitGame)]);
  if(!selected.length)return;
  uploading=true;uploadCancelled=false;$('#sampleRate').disabled=true;$('#faceitFind').disabled=true;
  const sample_rate=Number($('#sampleRate').value);
  updateFaceitSelection();faceitStatus('Передаём выбранные игры в очередь. Скачивание и анализ продолжатся на сервере.');
  try{
    const items=await UploadQueue.run(selected.map(game=>({name:`FACEIT · ${game.name} · ${game.demo_index+1}.dem`,size:0,game})),{
      cancelled:()=>uploadCancelled,list:()=>library(),
      onUpdate:items=>{batchItems=items;renderBatch();},
      upload:file=>faceitRequest('/api/faceit/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({match_id:file.game.match_id,demo_index:file.game.demo_index,sample_rate})}),
      onAccepted:()=>library()
    });
    const accepted=items.filter(i=>i.state==='accepted').length;
    faceitStatus(`Передано в очередь: ${accepted}/${items.length}. Прогресс скачивания и анализа показан по каждому демо.`);
    await library();
  }catch(error){faceitStatus(error.message,true);}
  finally{uploading=false;$('#sampleRate').disabled=false;$('#faceitFind').disabled=false;$('#cancelUploads').hidden=true;renderFaceitGames();}
};
faceitRequest('/api/faceit/config').then(config=>{
  faceitDownloads=config.downloads_api;
  $('#faceitSetup').hidden=config.data_api&&config.downloads_api;
  if(!config.data_api)faceitStatus('FACEIT не подключён. Для поиска игр настройте ключ Data API; для импорта демо понадобится Downloads API.');
  else if(!config.downloads_api)faceitStatus('Поиск игр доступен. Для скачивания демо подключите Downloads API.');
  else faceitStatus('Вставьте ссылку на профиль игрока, чтобы найти последние игры CS2.');
}).catch(()=>faceitStatus('Перезапустите сервер, чтобы включить импорт FACEIT.',true));
