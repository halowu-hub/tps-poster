# -*- coding: utf-8 -*-
"""
渲染校验：把一个海报 HTML 丢进 headless Chrome，检查
  - 各元素 1x 坐标、海报总高
  - 卡片每一行的行盒（发现孤儿行）
  - 导出 canvas 尺寸 + 二维码区域是否有内容
用法: python3 verify.py <海报.html>
"""
import os, re, subprocess, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PROBE = r'''
<script>
(function(){
  window.confirm=()=>true;
  const log=[]; const err=[];
  const flush=()=>{ document.title='V::'+log.join(' || ')+' ||ERR='+err.length; };
  window.addEventListener('error', e=>{ err.push(e.message); flush(); });
  const L=s=>{ log.push(s); flush(); };
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  (async()=>{
    await sleep(500);
    const p=document.querySelector('#poster');
    const b=p.getBoundingClientRect(); const z=b.width/540;
    const f=el=>{ if(!el) return null; const r=el.getBoundingClientRect();
      return {x:+((r.left-b.left)/z).toFixed(1), y:+((r.top-b.top)/z).toFixed(1),
              w:+(r.width/z).toFixed(1), h:+(r.height/z).toFixed(1)}; };
    L('posterH='+p.offsetHeight+' designW='+b.width.toFixed(0));
    L('avatar='+JSON.stringify(f(document.querySelector('#p-avatar'))));
    L('name='+JSON.stringify(f(document.querySelector('#p-name'))));
    L('phone='+JSON.stringify(f(document.querySelector('.p-phone'))));
    L('card='+JSON.stringify(f(document.querySelector('#p-card'))));
    L('qrwrap='+JSON.stringify(f(document.querySelector('.qrwrap'))));
    L('qrNat='+(document.querySelector('#p-qr').naturalWidth||0));
    L('floatHidden='+document.querySelector('#p-float').classList.contains('hidden'));
    // 头像/封面是否真的加载出来了
    L('avatarNat='+(document.querySelector('#p-avatar').naturalWidth||0)
      +' shotNat='+(document.querySelector('#p-shot').naturalWidth||0));
    // 行盒 dump：检测孤儿行
    const rows=[...document.querySelectorAll('#p-rows .crow')];
    rows.forEach((row,i)=>{
      const t=row.querySelector('.ctext');
      const rng=document.createRange(); const idx=[];
      const walk=(n)=>{ if(n.nodeType===3){ for(let k=0;k<n.length;k++) idx.push([n,k]); }
                        else for(const c of n.childNodes) walk(c); };
      walk(t);
      const lines=[];
      idx.forEach(([node,k])=>{ rng.setStart(node,k); rng.setEnd(node,k+1);
        const r=rng.getBoundingClientRect(); const top=Math.round(r.top/z);
        const last=lines[lines.length-1];
        if(!last||Math.abs(last.top-top)>3) lines.push({top, x:+(r.left/z).toFixed(1),
          right:+(r.right/z).toFixed(1), n:1});
        else { last.right=Math.max(last.right,+(r.right/z).toFixed(1)); last.n++; }
      });
      const widths=lines.map(l=>+(l.right-l.x).toFixed(1));
      L('row'+i+' lines='+lines.length+' widths='+JSON.stringify(widths));
    });
    // 导出
    try{
      const c=await toCanvas();
      const cx=c.getContext('2d');
      const band=(a,bb)=>{ const y=Math.floor(c.height*a), h=Math.max(1,Math.floor(c.height*(bb-a)));
        const d=cx.getImageData(0,y,c.width,h).data; let n=0,tt=0;
        for(let i=0;i<d.length;i+=4){tt++; if(d[i]<140&&d[i+1]<140&&d[i+2]<140)n++;} return (n/tt).toFixed(4); };
      L('canvas='+c.width+'x'+c.height+' qrBand='+band(0.78,0.92)+' topBand='+band(0,0.04));
      L('pngLen='+c.toDataURL('image/png').length);
    }catch(e){ L('EXPORT_ERR '+e.message); }
    L('DONE');
  })();
})();
</script>
'''


def main():
    src = os.path.abspath(sys.argv[1])
    tool = open(src, encoding='utf-8').read()
    probe = os.path.join(HERE, '_probe_run.html')
    open(probe, 'w', encoding='utf-8').write(tool.replace('</body>', PROBE + '</body>'))

    out = subprocess.run([CHROME, '--headless=new', '--no-sandbox', '--disable-gpu',
                          '--hide-scrollbars', '--window-size=1600,1200',
                          '--virtual-time-budget=30000', '--dump-dom',
                          'file://' + probe], capture_output=True, text=True)
    m = re.search(r'<title>V::(.*?)</title>', out.stdout, re.S)
    if not m:
        print('没拿到探针结果，stderr 片段：')
        print(out.stderr[-1500:])
        return
    for part in m.group(1).split(' || '):
        print(part)


if __name__ == '__main__':
    main()
