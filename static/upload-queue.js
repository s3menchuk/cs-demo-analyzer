const UploadQueue = {
 async run(files,{upload,list,onUpdate=()=>{},onAccepted=async()=>{},sleep=ms=>new Promise(r=>setTimeout(r,ms)),cancelled=()=>false}){
  const items=Array.from(files,f=>({file:f,name:f.name,state:'pending',message:'Ожидает отправки'}));
  const publish=()=>onUpdate(items);
  publish();
  for(const item of items){
   if(cancelled())break;
   if(!item.name.toLowerCase().endsWith('.dem')||item.file.size>1024**3){item.state='error';item.message=item.file.size>1024**3?'Файл больше 1 ГБ':'Нужен распакованный .dem';publish();continue;}
   try{
    while(!cancelled()){
     item.state='waiting';item.message='Ожидание места в очереди';publish();
     const matches=await list();
     if(cancelled())break;
     if(matches.filter(m=>m.status==='queued'||m.status==='parsing').length>=3){await sleep(1500);continue;}
     item.state='uploading';item.progress=0;item.message='Загрузка…';publish();
     try{
      const result=await upload(item.file,(message,percent)=>{item.message=message;item.progress=percent;publish();});
      item.id=result.id;item.state='accepted';item.message='Передано на анализ';publish();try{await onAccepted(result);}catch{item.message='Передано на анализ; обновите библиотеку';publish();}break;
     }catch(error){if(error.status===429){await sleep(1500);continue;}throw error;}
    }
   }catch(error){item.state='error';item.message=error.message||'Ошибка загрузки';publish();}
  }
  for(const item of items)if(['pending','waiting'].includes(item.state)){item.state='cancelled';item.message='Отменено';}
  publish();return items;
 }
};
if(typeof module!=='undefined')module.exports=UploadQueue;
