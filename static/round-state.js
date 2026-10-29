const RoundState = {
  clockAt(frames,tick,tickrate){
    if(!frames.length)return null;
    const i=Replay.index(frames,tick),a=frames[i],c=a.clock;
    if(!c)return null;
    const b=frames[i+1];
    let elapsed=0;
    if(!c.paused){
      const limit=b?Math.min(b.tick-a.tick,tickrate*1.5):tickrate;
      elapsed=Math.max(0,Math.min(tick-a.tick,limit))/tickrate;
      if(b?.clock&&b.round===a.round&&b.tick>a.tick){
        const ratio=Math.max(0,Math.min(1,(tick-a.tick)/(b.tick-a.tick)));
        elapsed=Math.max(0,(b.clock.game_time-c.game_time)*ratio);
      }
    }
    return {...c,seconds:Math.max(0,c.seconds-elapsed),game_time:c.game_time+elapsed};
  },
  state(round,frames,bombs,events,tick,tickrate,fallbackFuse=40){
    const clock=this.clockAt(frames,tick,tickrate);
    const decision=round.decision_tick??round.end,finished=tick>=decision;
    const session=[...bombs].reverse().find(b=>b.planted_tick<=tick)||null;
    let bomb=null;
    if(session){
      const resolved=session.resolved_tick!==null&&session.resolved_tick!==undefined&&tick>=session.resolved_tick;
      const state=resolved?session.outcome:finished?'round_ended':'planted';
      const configured=Number.isFinite(session.fuse_seconds)?session.fuse_seconds:Math.max(1,Math.min(3600,Number(fallbackFuse)||40));
      const elapsed=clock&&Number.isFinite(session.planted_game_time)?Math.max(0,clock.game_time-session.planted_game_time):(tick-session.planted_tick)/tickrate;
      bomb={...session,state,remaining:state==='planted'?Math.max(0,configured-elapsed):null,
        approximate:!['recorded_explosion','server_cvar'].includes(session.fuse_source),defuse:null};
      const latest=[...events].reverse().find(e=>e.tick<=tick&&e.tick>=session.planted_tick&&['bomb_begindefuse','bomb_abortdefuse','bomb_defused','bomb_exploded'].includes(e.type));
      if(state==='planted'&&latest?.type==='bomb_begindefuse'){
        const seconds=latest.has_kit?5:10,beginClock=this.clockAt(frames,latest.tick,tickrate);
        const elapsedDefuse=clock&&beginClock?clock.game_time-beginClock.game_time:(tick-latest.tick)/tickrate;
        bomb.defuse={actor:latest.actor,has_kit:latest.has_kit,remaining:Math.max(0,seconds-elapsedDefuse),progress:Math.max(0,Math.min(1,elapsedDefuse/seconds))};
      }
    }
    const lastPlant=[...events].reverse().find(e=>e.tick<=tick&&['bomb_beginplant','bomb_abortplant','bomb_planted'].includes(e.type));
    const planting=!finished&&!session&&lastPlant?.type==='bomb_beginplant'?lastPlant:null;
    return {clock,bomb,planting,finished,phase:finished?'ended':clock?.paused?'paused':clock?.freeze?'freeze':bomb?.state==='planted'?'bomb':'live'};
  },
  countdown(seconds){
    if(!Number.isFinite(seconds))return '—';
    const tenths=Math.max(0,Math.ceil(seconds*10));
    return `${Math.floor(tenths/600)}:${String(Math.floor(tenths/10)%60).padStart(2,'0')}.${tenths%10}`;
  },
  shotVisible(shot,tick,tickrate){return tick>=shot.tick&&tick-shot.tick<tickrate*.16;},
  drawShots(ctx,project,meta,level,shots,tick,tickrate,owner,side){
    let visible=0;ctx.save();
    for(const shot of shots){
      const p=shot.position;
      if(!this.shotVisible(shot,tick,tickrate)||!p||!MapView.onLevel(meta,p,level)||(owner&&shot.shooter_id!==owner)||(side&&shot.side!==side))continue;
      visible++;const age=(tick-shot.tick)/tickrate,alpha=1-age/.16,[x,y]=project(p);
      ctx.globalAlpha=alpha;ctx.strokeStyle='#ffd37c';ctx.fillStyle='#fff1b4';ctx.lineWidth=2;
      ctx.beginPath();ctx.arc(x,y,5+age*25,0,Math.PI*2);ctx.fill();
      if(Number.isFinite(shot.yaw)){
        const v=Overlays.vector(shot.yaw),length=500*Math.cos((shot.pitch||0)*Math.PI/180);
        const [tx,ty]=project({x:p.x+v.x*length,y:p.y+v.y*length});
        ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(tx,ty);ctx.stroke();
      }
    }
    ctx.restore();return visible;
  },
  drawBomb(ctx,project,meta,level,state,tick,tickrate){
    ctx.save();
    for(const site of meta?.sites||[]){
      if((site.level||'default')!==level)continue;
      const [x,y]=project(site);ctx.strokeStyle='#e6c07e';ctx.fillStyle='#0d1520cc';ctx.lineWidth=1.5;
      ctx.beginPath();ctx.arc(x,y,17,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.fillStyle='#e6c07e';ctx.textAlign='center';ctx.font='bold 16px Segoe UI';ctx.fillText(site.name,x,y+6);
    }
    const bomb=state.bomb,p=bomb?.position||state.planting?.position;
    if(p&&MapView.onLevel(meta,p,level)){
      const [x,y]=project(p),active=bomb?.state==='planted';
      const color=bomb?.state==='defused'?'#6fe0b1':bomb?.state==='exploded'?'#ff8d5b':'#ff6c78';
      ctx.strokeStyle=color;ctx.lineWidth=3;ctx.fillStyle='#141722';ctx.globalAlpha=bomb?.state==='round_ended'?.5:1;
      ctx.beginPath();ctx.arc(x,y,14+(active?3*Math.sin(tick/tickrate*8):0),0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.fillStyle=color;ctx.font='bold 10px Consolas';ctx.textAlign='center';ctx.fillText('C4',x,y+4);
      if(active){ctx.font='bold 13px Consolas';ctx.fillText((bomb.approximate?'≈':'')+this.countdown(bomb.remaining),x,y-23);}
      if(bomb?.defuse){ctx.strokeStyle='#6fe0b1';ctx.lineWidth=4;ctx.beginPath();ctx.arc(x,y,22,-Math.PI/2,-Math.PI/2+bomb.defuse.progress*Math.PI*2);ctx.stroke();}
    }
    ctx.restore();
  }
};
