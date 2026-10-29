/* Shared calibrated projection for replay, player events, and world-space zones. */
const MapView = {
  catalog: {}, images: new Map(),
  async init() {
    const response = await fetch('/api/maps');
    if (!response.ok) throw new Error('Не удалось загрузить каталог карт');
    this.catalog = await response.json();
  },
  async load(name) {
    const meta = this.catalog[name];
    if (!meta) return null;
    await Promise.all(meta.levels.map(level => new Promise(resolve => {
      if (this.images.has(level.image)) {resolve();return;}
      const img = new Image();
      img.onload = () => {this.images.set(level.image,img);resolve();};
      img.onerror = () => resolve();
      img.src=level.image;
    })));
    return meta;
  },
  level(meta, z) {
    return meta?.levels.find(l=>(l.min_z===null||z>=l.min_z)&&(l.max_z===null||z<l.max_z))?.id || 'default';
  },
  onLevel(meta, point, selected) {
    return !meta || meta.levels.length<2 || this.level(meta,point.z)===selected;
  },
  base(canvas, meta, selected, points, custom=null) {
    const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
    ctx.globalAlpha=1;ctx.clearRect(0,0,w,h);ctx.fillStyle='#101821';ctx.fillRect(0,0,w,h);
    const level=meta?.levels.find(l=>l.id===selected) || meta?.levels[0];
    const img=custom?.image || this.images.get(level?.image);
    const config=custom || meta;
    if (img && config) {
      const size=Math.min(w,h),ox=(w-size)/2,oy=(h-size)/2;
      ctx.drawImage(img,ox,oy,size,size);
      const project=p=>[ox+(p.x-config.pos_x)/config.scale/1024*size,oy+(config.pos_y-p.y)/config.scale/1024*size];
      return {ctx,project,label:custom?'СВОЙ РАДАР':`${meta.name.toUpperCase()} · ${level.label.toUpperCase()}`,calibrated:true};
    }
    ctx.strokeStyle='#22303f';ctx.lineWidth=1;
    for(let x=0;x<w;x+=45){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
    for(let y=0;y<h;y+=45){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(const p of points){if(!p)continue;minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);}
    if(!Number.isFinite(minX)){minX=minY=0;maxX=maxY=1000;}
    const s=Math.min((w-130)/Math.max(maxX-minX,1),(h-130)/Math.max(maxY-minY,1));
    const project=p=>[w/2+(p.x-(minX+maxX)/2)*s,h/2-(p.y-(minY+maxY)/2)*s];
    return {ctx,project,label:'НЕТ ВСТРОЕННОГО РАДАРА · СЕТКА X/Y',calibrated:false};
  }
};
