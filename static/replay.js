/* Playback follows demo ticks, not the number of frames delivered by the browser. */
const Replay = {
  sampleRate(match) {return match?.sample_rate || 1/(match?.sample_seconds || 1);},
  angle(a,b,t){return ((a+((b-a+540)%360-180)*t+180)%360+360)%360-180;},
  index(frames,tick) {
    let lo=0,hi=frames.length;
    while(lo<hi){const mid=(lo+hi)>>>1;if(frames[mid].tick<=tick)lo=mid+1;else hi=mid;}
    return Math.max(0,lo-1);
  },
  snapshot(frames,tick,tickrate=64,interpolate=true) {
    if(!frames.length)return null;
    const index=this.index(frames,tick),a=frames[index],b=frames[index+1];
    if(!interpolate||!b||tick<=a.tick||b.tick-a.tick>tickrate*1.5)return a;
    const t=Math.min(1,(tick-a.tick)/(b.tick-a.tick));
    const next=new Map(b.players.map(p=>[p.id,p]));
    return {tick,round:a.round,players:a.players.map(p=>{
      const q=next.get(p.id);
      // Never smooth a death, respawn, side/floor change, or teleport.
      if(!q||p.alive!==q.alive||p.side!==q.side||!p.alive||Math.abs((q.z||0)-(p.z||0))>128||Math.hypot(q.x-p.x,q.y-p.y)>Math.max(128,(b.tick-a.tick)/tickrate*400))return p;
      return {...p,x:p.x+(q.x-p.x)*t,y:p.y+(q.y-p.y)*t,z:(p.z||0)+((q.z||0)-(p.z||0))*t,
        yaw:Number.isFinite(p.yaw)&&Number.isFinite(q.yaw)?this.angle(p.yaw,q.yaw,t):p.yaw,
        pitch:Number.isFinite(p.pitch)&&Number.isFinite(q.pitch)?p.pitch+(q.pitch-p.pitch)*t:p.pitch};
    })};
  },
  bounds(frames) {
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(const f of frames)for(const p of f.players)if(p.alive){minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);}
    return Number.isFinite(minX)?[{x:minX,y:minY},{x:maxX,y:maxY}]:[];
  },
  tickAt(start,elapsedMs,speed,tickrate,end){return Math.min(end,start+Math.max(0,elapsedMs)*speed*tickrate/1000);},
  formatTime(seconds) {
    const ms=Math.max(0,Math.floor(seconds*1000));
    return `${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
  }
};
