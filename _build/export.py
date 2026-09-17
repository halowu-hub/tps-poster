# -*- coding: utf-8 -*-
"""
把海报 HTML 用 headless Chrome 导出成 PNG（等于工具里点「下载 PNG」的结果），
并解码图上的二维码，确认扫出来就是笔记链接。

用法: python3 export.py <海报.html> [输出.png]
"""
import os, re, subprocess, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

HARNESS = r'''
<script>
(function(){
  window.confirm=()=>true;
  (async()=>{
    await new Promise(r=>setTimeout(r,600));
    document.querySelector('.topbar').style.display='none';
    document.querySelector('.panel').style.display='none';
    const st=document.querySelector('.stage');
    st.style.cssText='padding:0;background:#fff';
    document.querySelector('.stage-head').style.display='none';
    const sc=document.querySelector('#scaler');
    sc.style.transform='none'; sc.style.width='540px'; sc.style.height='auto';
    const c=await toCanvas();
    document.body.innerHTML='';
    document.body.style.margin='0'; document.body.style.background='#fff';
    const box=document.createElement('div');
    box.style.cssText='width:'+c.width+'px;height:'+c.height+'px;overflow:hidden;position:relative';
    c.style.cssText='position:absolute;left:0;top:0;width:'+c.width+'px;height:'+c.height+'px';
    box.appendChild(c); document.body.appendChild(box);
    document.title='done-'+c.width+'x'+c.height;
  })();
})();
</script>
'''


def run(harness_path, extra):
    return subprocess.run([CHROME, '--headless=new', '--no-sandbox', '--disable-gpu',
                           '--hide-scrollbars', '--force-device-scale-factor=1'] + extra +
                          ['file://' + harness_path], capture_output=True, text=True)


def main():
    src = os.path.abspath(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '_export.png')
    html = open(src, encoding='utf-8').read()
    h = os.path.join(HERE, '_export_run.html')
    open(h, 'w', encoding='utf-8').write(html.replace('</body>', HARNESS + '</body>'))

    # 1) 先问出 canvas 尺寸
    r = run(h, ['--window-size=1600,1200', '--virtual-time-budget=30000', '--dump-dom'])
    m = re.search(r'<title>done-(\d+)x(\d+)</title>', r.stdout)
    if not m:
        print('导出失败，stderr 尾部：')
        print(r.stderr[-1200:])
        return 1
    W, H = int(m.group(1)), int(m.group(2))
    print('canvas = %dx%d' % (W, H))

    # 2) 按画布尺寸截图
    run(h, ['--window-size=%d,%d' % (W, H + 40), '--virtual-time-budget=30000',
            '--screenshot=' + out])
    im = Image.open(out).convert('RGB')
    print('截图 =', im.size)
    if im.size[1] > H:
        im = im.crop((0, 0, W, H))
    qr = Image.open(h.replace('_export_run.html', '_qr.png')) if False else None
    im.save(out)
    print('PNG ->', out)

    # 3) 解码二维码，确认扫出来就是笔记链接
    try:
        import zxingcpp
        res = None
        for region in ((0.38, 0.83, 0.62, 0.97), (0.0, 0.75, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)):
            x0, y0, x1, y1 = region
            box = im.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1)))
            box = box.resize((box.width * 2, box.height * 2), Image.LANCZOS)
            r = zxingcpp.read_barcode(box)
            if r:
                res = r
                break
        print('二维码 ->', (res.text if res else '❌ 解码失败'))
    except ImportError:
        print('（未安装 zxing-cpp，跳过二维码解码）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
