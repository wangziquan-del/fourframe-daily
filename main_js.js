
function K(tf,sym){return ((window.KDATA||{})[tf]||{})[sym];}
function showTf(tf,btn){document.querySelectorAll('.tf-tab').forEach(x=>x.classList.remove('active'));document.getElementById('tf-'+tf).classList.add('active');document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));btn.classList.add('active')}
let curSym=null,curTf='15min';
function renderLevel(){const d=K(curTf,curSym);if(!d)return;document.getElementById('m-sym').textContent=curSym;document.getElementById('m-name').textContent=d.name;document.getElementById('m-price').textContent=d.price.toLocaleString();const dirColor=d.strat.dir.includes('多')?'#4A8060':(d.strat.dir.includes('空')?'#C05050':'#D4AF37');document.getElementById('m-entry').textContent=d.strat.dir+' ｜ '+d.strat.entry;document.getElementById('m-entry').style.color=dirColor;document.getElementById('m-tp1').textContent=d.strat.tp1;document.getElementById('m-tp2').textContent=d.strat.tp2;document.getElementById('m-sl').textContent=d.strat.sl;document.getElementById('m-trail').textContent='移动止盈：'+d.strat.trail;document.getElementById('m-det').innerHTML=['评分 '+d.score,'江恩 '+d.gann+'%','RSI '+d.rsi].map(x=>'<i>'+x+'</i>').join('');drawKline(d.bars)}
function openDetail(tf,sym){curSym=sym;curTf=tf;document.querySelectorAll('.m-levels button').forEach(b=>b.classList.toggle('active',b.id==='lv-'+tf));renderLevel();document.getElementById('modal').classList.add('show')}
function openSum(sym){const tfs=['15min','60min','日线'];const tf=tfs.find(t=>K(t,sym))||tfs[0];curSym=sym;curTf=tf;tfs.forEach(t=>{const btn=document.getElementById('lv-'+t);const has=!!K(t,sym);btn.disabled=!has;btn.classList.toggle('active',t===tf)});renderLevel();document.getElementById('modal').classList.add('show')}
function showLevel(tf){if(!curSym)return;curTf=tf;document.querySelectorAll('.m-levels button').forEach(b=>b.classList.toggle('active',b.id==='lv-'+tf));renderLevel()}
function closeDetail(){document.getElementById('modal').classList.remove('show')}
function drawKline(bars){
  const cv=document.getElementById('m-chart'),ctx=cv.getContext('2d'),W=cv.width,H=cv.height;
  ctx.clearRect(0,0,W,H);if(!bars||!bars.length)return;
  const n=bars.length,px=6,plotH=H*0.72,vpH=H*0.20,gap=14;
  let hi=Math.max(...bars.map(b=>b.h)),lo=Math.min(...bars.map(b=>b.l));
  const pad=(hi-lo)*0.06,priceH=plotH-gap;
  const yP=p=>gap+(hi+pad-p)/(hi-lo+2*pad)*priceH;
  const xP=i=>px+i*(W-2*px)/n;
  ctx.strokeStyle='#e6e0d5';ctx.lineWidth=1;ctx.strokeRect(px,gap,W-2*px,plotH-gap);
  const cw=Math.max(1.5,(W-2*px)/n*0.6);
  for(let i=0;i<n;i++){
    const b=bars[i],up=b.c>=b.o;
    ctx.strokeStyle=up?'#C05050':'#4A8060';ctx.fillStyle=up?'#C05050':'#4A8060';
    ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(xP(i),yP(b.h));ctx.lineTo(xP(i),yP(b.l));ctx.stroke();
    const yO=yP(b.o),yC=yP(b.c),top=Math.min(yO,yC),hgt=Math.max(1,Math.abs(yO-yC));
    ctx.fillRect(xP(i)-cw/2,top,cw,hgt);
  }
  const closes=bars.map(b=>b.c);
  [[5,'#D4AF37'],[10,'#3B5998'],[20,'#4A8060']].forEach(([p,col])=>{
    ctx.strokeStyle=col;ctx.lineWidth=1.4;ctx.beginPath();let started=false;
    for(let i=p-1;i<n;i++){const v=closes.slice(i-p+1,i+1).reduce((a,c)=>a+c,0)/p;const x=xP(i),y=yP(v);if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y)}
    ctx.stroke();
  });
  const vmax=Math.max(...bars.map(b=>b.v))||1;
  for(let i=0;i<n;i++){const b=bars[i],up=b.c>=b.o;const vh=b.v/vmax*vpH;ctx.fillStyle=up?'rgba(192,80,80,.35)':'rgba(74,128,96,.35)';ctx.fillRect(xP(i)-cw/2,H-vh,cw,vh)}
  ctx.fillStyle='#9c938e';ctx.font='10px JetBrains Mono';ctx.fillText('H '+hi.toLocaleString(),px+6,16);ctx.fillText('L '+lo.toLocaleString(),px+6,H-4);
}
function exportCSV(){let csv='品种,名称,级别,分类,评分,现价,方向,进场,止盈1,止盈2,止损
';['15min','60min','日线'].forEach(tf=>{Object.keys((window.KDATA||{})[tf]||{}).forEach(sym=>{const d=(window.KDATA||{})[tf][sym],s=d.strat;csv+=[sym,d.name,tf,d.cat,d.score,d.price,s.dir,s.entry,s.tp1,s.tp2,s.sl].join(',')+'
'})});const blob=new Blob(['﻿'+csv],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='四框架选品_'+new Date().toISOString().slice(0,10)+'.csv';a.click()}
function copyShare(){const d=new Date().toLocaleString('zh-CN');let txt='四框架每日选品 '+d+'
================
';['15min','60min','日线'].forEach(tf=>{txt+='
【'+tf+'】
';Object.keys((window.KDATA||{})[tf]||{}).forEach(sym=>{const x=(window.KDATA||{})[tf][sym];txt+=sym+' '+x.name+' '+x.strat.dir+' 进场'+x.strat.entry+' 止盈'+x.strat.tp1+'/'+x.strat.tp2+' 止损'+x.strat.sl+'
'})});navigator.clipboard.writeText(txt).then(()=>alert('已复制分享文本'))}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail()});
