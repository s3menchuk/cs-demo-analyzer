const BalanceMap = {
  bounds(zones){return zones.flatMap(z=>[{x:z.min_x,y:z.min_y},{x:z.min_x+z.size,y:z.min_y+z.size}]);},
  draw(ctx,project,zones,level){
    const visible=zones.filter(z=>!level||z.level===level),max=Math.max(1,...visible.map(z=>Math.abs(z.delta)));
    return visible.map(z=>{
      const a=project({x:z.min_x,y:z.min_y}),b=project({x:z.min_x+z.size,y:z.min_y+z.size});
      const x=Math.min(a[0],b[0]),y=Math.min(a[1],b[1]),w=Math.abs(a[0]-b[0]),h=Math.abs(a[1]-b[1]);
      const color=z.delta>0?'#6fe0b1':z.delta<0?'#ff777d':'#a6afbf';
      ctx.fillStyle=color;ctx.globalAlpha=z.delta===0?.25:.22+.58*Math.abs(z.delta)/max;ctx.fillRect(x,y,w,h);
      ctx.globalAlpha=.85;ctx.strokeStyle=color;ctx.lineWidth=1;ctx.strokeRect(x,y,w,h);ctx.globalAlpha=1;
      if(w>19&&h>15){ctx.fillStyle='#0b111b';ctx.font='bold 13px Consolas';ctx.textAlign='center';ctx.fillText(z.delta>0?'+'+z.delta:String(z.delta),x+w/2,y+h/2+4);}
      return {...z,x,y,w,h};
    });
  },
  hit(cells,x,y){return cells.find(c=>x>=c.x&&x<=c.x+c.w&&y>=c.y&&y<=c.y+c.h);},
  description(z){return `Убийства: ${z.kills} · Смерти: ${z.deaths} · K−D: ${z.delta>0?'+':''}${z.delta}`;}
};
if(typeof module!=='undefined')module.exports=BalanceMap;
