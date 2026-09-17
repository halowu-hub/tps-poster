# -*- coding: utf-8 -*-
"""把 template.html + 两个库 + 示例图 组装成单文件「每周海报生成器.html」"""
import base64, io, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF = ('/Users/wutingxiang/Library/Containers/com.tencent.xinWeChat/Data/Documents/'
       'xwechat_files/wu920-TX404_d41f/temp/RWTemp/2026-09/'
       '291a3997a44f70babf95d09c16876e3b.jpg')
OUT = os.path.join(HERE, '..', '每周海报生成器.html')


def b64_jpg(im, q=88):
    buf = io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=q, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


src = Image.open(REF).convert('RGB')
avatar = b64_jpg(src.crop((130, 195, 400, 465)))
shot = b64_jpg(src.crop((533, 212, 972, 1224)), 84)
flt = b64_jpg(src.crop((505, 440, 875, 895)))

DEMO = {
    "title": "Top Post Sharing",
    "name": "@账号名\n第二行（可留空）",
    "metrics": [
        {"k": "like",  "v": "171", "emoji": "🔥"},
        {"k": "star",  "v": "2",   "emoji": "🔥"},
        {"k": "share", "v": "1",   "emoji": "🔥"},
    ],
    "rows": [
        {"label": "封面优点:", "text": "**热门断货墨镜产品专柜实拍**，直观呈现到货信息"},
        {"label": "文案优点:", "text": "清晰告知热门产品到货，列出具体产品系列+优惠信息"},
        {"label": "关键词:",   "text": "地点+热门产品+优惠钩子"},
        {"label": "热门墨镜:", "text": "**品牌：**MIUMIU **型号：**11W（窄框猫眼/赵露思同款）\n09W（大框猫眼/王安宇同款）"},
    ],
    "floatShow": False,
    "floatW": 185,
    "qrMode": "text",
    "qrText": "https://www.xiaohongshu.com/explore",
    "qrCaption": "扫码查看全文",
    "orbs": True,
}

tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
qr_lib = open(os.path.join(HERE, 'libs', 'qrcode.js'), encoding='utf-8').read()
h2c_lib = open(os.path.join(HERE, 'libs', 'html2canvas.js'), encoding='utf-8').read()
assert '</script' not in qr_lib.lower() and '</script' not in h2c_lib.lower()

html = (tpl
        .replace('<!--LIBS-->', '')
        .replace('/*__QR_LIB__*/', qr_lib)
        .replace('/*__H2C_LIB__*/', h2c_lib)
        .replace('__AVATAR__', avatar)
        .replace('__SHOT__', shot)
        .replace('__FLOAT__', flt)
        .replace('__DEMO_JSON__', json.dumps(DEMO, ensure_ascii=False, indent=1)))

out = os.path.abspath(OUT)
open(out, 'w', encoding='utf-8').write(html)
print('工具 ->', out, round(len(html.encode()) / 1024), 'KB')
