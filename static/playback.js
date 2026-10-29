/* Playback intent survives seeking and asynchronous round loading. */
class PlaybackController {
  constructor({context,onTick,onState,requestFrame=fn=>globalThis.requestAnimationFrame(fn),cancelFrame=id=>globalThis.cancelAnimationFrame(id),now=()=>performance.now()}){
    Object.assign(this,{context,onTick,onState,requestFrame,cancelFrame,now});
    this.playing=false;this.frame=null;this.generation=0;
  }
  suspend(){
    if(this.frame!==null)this.cancelFrame(this.frame);
    this.frame=null;this.generation++;
  }
  pause(){this.suspend();this.playing=false;this.onState(false);}
  start(){this.playing=true;this.onState(true);this.resume();}
  resume(){
    if(!this.playing)return;
    this.suspend();
    const c=this.context();if(!c.ready)return;
    const generation=this.generation,wallStart=this.now();
    const animate=now=>{
      if(!this.playing||generation!==this.generation)return;
      this.frame=null;
      const tick=Replay.tickAt(c.tick,now-wallStart,c.speed,c.tickrate,c.end);
      this.onTick(tick);
      if(!this.playing||generation!==this.generation)return;
      if(tick>=c.end){this.pause();return;}
      this.frame=this.requestFrame(animate);
    };
    this.frame=this.requestFrame(animate);
  }
  seek(update){this.suspend();update();this.resume();}
}
