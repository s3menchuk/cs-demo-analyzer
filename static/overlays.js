const Overlays = {
  kinds: {
    smoke:{label:'Дым',color:'#c6d0de',radius:144,icon:'M8 11h8v10H8z M10 8h4v3 M9 15h6 M10 5c-4-3 4-3 1-6 M15 7c-3-3 4-3 1-6'},
    he:{label:'Осколочная граната',color:'#ffb167',radius:55,icon:'M9 7h6l3 5v6l-3 4H9l-3-4v-6z M10 3h5v4 M15 3h4v5 M7 12h10 M6 17h12 M10 8v13 M14 8v13'},
    flash:{label:'Световая граната',color:'#fff0a5',radius:55,icon:'M8 8h8v14H8z M10 4h5v4 M15 4h4v6 M13 10l-3 5h4l-3 5 M4 4L2 2 M20 4l2-2 M4 8H1 M20 8h3'},
    fire:{label:'Зажигательная граната / Молотов',color:'#ff8359',radius:110,icon:'M9 8h6v5l3 4v5H6v-5l3-4z M9 5h6v3 M12 5c-5-3 2-4 1-7 6 5 5 7-1 7 M9 17h6'},
    decoy:{label:'Ложная граната',color:'#a1d6e8',radius:65,icon:'M8 8h8v14H8z M10 4h5v4 M10 12h4 M10 16h4 M4 10c-3 2-3 6 0 8 M20 10c3 2 3 6 0 8 M1 7c-5 4-5 10 0 14 M23 7c5 4 5 10 0 14'}
  },
  markers:[],
  icon(kind){
    const style=this.kinds[kind]||this.kinds.he;
    return `<svg class="grenade-icon" viewBox="-4 -4 32 32" fill="none" stroke="${style.color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${style.icon}"/></svg>`;
  },
  vector(yaw){const rad=yaw*Math.PI/180;return {x:Math.cos(rad),y:Math.sin(rad)};},
  gaze(ctx,p,project,color){
    if(!p.alive||!Number.isFinite(p.yaw))return;
    const v=this.vector(p.yaw),[x,y]=project(p),[tx,ty]=project({x:p.x+v.x*100,y:p.y+v.y*100});
    const length=Math.hypot(tx-x,ty-y)||1,dx=(tx-x)/length,dy=(ty-y)/length;
    ctx.save();ctx.fillStyle=color;ctx.globalAlpha=.95;
    ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+dx*29,y+dy*29);ctx.stroke();
    ctx.beginPath();ctx.moveTo(x+dx*32,y+dy*32);ctx.lineTo(x+dx*23-dy*4,y+dy*23+dx*4);ctx.lineTo(x+dx*23+dy*4,y+dy*23-dx*4);ctx.closePath();ctx.fill();ctx.restore();
  },
  position(track,tick,interpolate=true){
    if(tick<track.start||tick>track.end||!track.points.length)return null;
    const i=Replay.index(track.points,tick),a=track.points[i],b=track.points[i+1];
    if(!interpolate||!b||tick<=a.tick)return a;
    const t=(tick-a.tick)/(b.tick-a.tick);
    return {tick,x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,z:a.z+(b.z-a.z)*t};
  },
  matches(g,owner,side){return (!owner||g.owner_id===owner)&&(!side||g.side===side);},
  draw(ctx,project,meta,level,tracks,effects,tick,tickrate,options){
    this.markers=[];
    let flying=0,active=0;
    ctx.save();
    for(const g of tracks){
      if(!this.matches(g,options.owner,options.side))continue;
      const point=this.position(g,tick,options.interpolate);
      if(!point||!MapView.onLevel(meta,point,level))continue;
      flying++;
      const style=this.kinds[g.kind]||this.kinds.he;
      if(options.trails){
        ctx.strokeStyle=style.color;ctx.lineWidth=2;ctx.globalAlpha=.65;ctx.beginPath();let drawing=false;
        for(const p of [...g.points.filter(p=>p.tick>=tick-tickrate*1.5&&p.tick<=tick),point]){
          if(!MapView.onLevel(meta,p,level)){drawing=false;continue;}
          const [x,y]=project(p);if(drawing)ctx.lineTo(x,y);else ctx.moveTo(x,y);drawing=true;
        }
        ctx.stroke();ctx.globalAlpha=1;
      }
      this.marker(ctx,project(point),style);
      this.markers.push({point:project(point),label:style.label,owner:g.owner_name});
    }
    for(const e of effects){
      if(tick<e.start||tick>=e.end||!this.matches(e,options.owner,options.side)||!MapView.onLevel(meta,e,level))continue;
      active++;
      const style=this.kinds[e.kind]||this.kinds.he,[x,y]=project(e),[rx,ry]=project({x:e.x+style.radius,y:e.y});
      const radius=Math.max(8,Math.hypot(rx-x,ry-y));
      const burst=e.kind==='he'||e.kind==='flash',progress=(tick-e.start)/Math.max(1,e.end-e.start);
      ctx.globalAlpha=burst?.45*(1-progress):.25;ctx.fillStyle=style.color;ctx.beginPath();ctx.arc(x,y,radius*(burst?.4+.6*progress:1),0,Math.PI*2);ctx.fill();
      ctx.globalAlpha=.7;ctx.strokeStyle=style.color;ctx.lineWidth=1.5;ctx.setLineDash(e.kind==='smoke'?[5,5]:[]);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;
      this.marker(ctx,[x,y],style);
      this.markers.push({point:[x,y],label:style.label,owner:e.owner_name});
    }
    ctx.restore();return {flying,active};
  },
  marker(ctx,[x,y],style){
    ctx.save();
    ctx.fillStyle='#111923';ctx.strokeStyle=style.color;ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(x,y,14,0,Math.PI*2);ctx.fill();ctx.stroke();
    ctx.save();ctx.translate(x-9,y-9);ctx.scale(.75,.75);ctx.lineWidth=1.8;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke(new Path2D(style.icon));ctx.restore();
    ctx.restore();
  }
};
