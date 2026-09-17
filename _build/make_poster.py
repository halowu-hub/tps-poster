# -*- coding: utf-8 -*-
"""
用 fetch_note.py 抓到的笔记数据，自动生成一张已填好的「Top Post Sharing」海报工具页面。

用法:
  python3 make_poster.py --note note_out/note.json \
                        [--analysis analysis.json] \
                        [--title "Top Post Sharing"] \
                        [--out ../输出/20260908_xxx.html]

自动填入：头像 / 账号名 / 点赞·收藏·分享 / 笔记封面（手机屏）/ 二维码（笔记链接）
需要人工确认：卡片里的 封面 / 文案 / 关键词 三段分析（来自 analysis.json，可改）
"""
import argparse, base64, io, json, os, re, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, 'template.html')
QR_LIB = os.path.join(HERE, 'libs', 'qrcode.js')
H2C_LIB = os.path.join(HERE, 'libs', 'html2canvas.js')

# 手机屏内尺寸 222x499（1x），封面按此比例居中裁剪，避免被拉伸
SCREEN_W, SCREEN_H = 222, 499
SCALE = 2  # 内嵌图按 2x 存，导出更清晰


def b64_jpg(im, q=88):
    buf = io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=q, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def crop_to(im, ratio, anchor=0.5):
    """按目标宽高比居中裁剪（anchor 0=偏上 0.5=居中 1=偏下）"""
    w, h = im.size
    cur = w / h
    if cur > ratio:          # 太宽 -> 裁两边
        nw = int(round(h * ratio))
        x = int((w - nw) * 0.5)
        return im.crop((x, 0, x + nw, h))
    else:                    # 太高 -> 裁上下
        nh = int(round(w / ratio))
        y = int((h - nh) * anchor)
        return im.crop((0, y, w, y + nh))


def make(note, analysis, title):
    nick = note['user']['nickname']

    # ---- 头像 ----
    avatar = ''
    if note.get('avatarFile') and os.path.exists(note['avatarFile']):
        im = Image.open(note['avatarFile'])
        im = crop_to(im, 1.0)
        im = im.resize((360, 360), Image.LANCZOS)
        avatar = b64_jpg(im, 90)

    # ---- 封面 -> 手机屏 ----
    shot = ''
    if note.get('coverFile') and os.path.exists(note['coverFile']):
        im = Image.open(note['coverFile'])
        im = crop_to(im, SCREEN_W / SCREEN_H, anchor=0.0)   # 偏上取，保住头部
        im = im.resize((SCREEN_W * SCALE, SCREEN_H * SCALE), Image.LANCZOS)
        shot = b64_jpg(im, 86)

    # ---- 悬浮小图：笔记有多图时取第 2 张 ----
    flt, float_show = '', False
    if len(note.get('images', [])) > 1 and note.get('imgFile2') and os.path.exists(note['imgFile2']):
        im = Image.open(note['imgFile2'])
        im = crop_to(im, 370 / 455)
        im = im.resize((370, 455), Image.LANCZOS)
        flt = b64_jpg(im)
        float_show = True

    st = note['stats']
    demo = {
        'title': title,
        'name': '@' + nick,
        'metrics': [
            {'k': 'like',  'v': str(st['like']),    'emoji': '🔥'},
            {'k': 'star',  'v': str(st['collect']), 'emoji': '🔥'},
            {'k': 'share', 'v': str(st['share']),   'emoji': '🔥'},
        ],
        'rows': analysis['rows'],
        'floatShow': float_show,
        'floatW': 185,
        'qrMode': 'text',
        'qrText': note.get('url') or note.get('shareUrl', ''),
        'qrCaption': '扫码查看全文',
        'orbs': True,
    }

    tpl = open(TPL, encoding='utf-8').read()
    qr_lib = open(QR_LIB, encoding='utf-8').read()
    h2c_lib = open(H2C_LIB, encoding='utf-8').read()
    assert '</script' not in qr_lib.lower() and '</script' not in h2c_lib.lower()

    html = (tpl
            .replace('<!--LIBS-->', '')
            .replace('/*__QR_LIB__*/', qr_lib)
            .replace('/*__H2C_LIB__*/', h2c_lib)
            .replace('__AVATAR__', avatar)
            .replace('__SHOT__', shot)
            .replace('__FLOAT__', flt)
            .replace('__DEMO_JSON__', json.dumps(demo, ensure_ascii=False, indent=1)))
    # 每周一页各存各的编辑内容，互不覆盖
    html = html.replace("const LS = 'tps_poster_v1';",
                        "const LS = 'tps_poster_v1_%s';" % note['noteId'])
    return html, demo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--note', required=True)
    ap.add_argument('--analysis', default=os.path.join(HERE, 'analysis.json'))
    ap.add_argument('--title', default='Top Post Sharing')
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    note = json.load(open(a.note, encoding='utf-8'))
    analysis = json.load(open(a.analysis, encoding='utf-8'))

    html, demo = make(note, analysis, a.title)

    if not a.out:
        d = time.strftime('%Y%m%d', time.localtime(
            (note.get('publishTime') or time.time() * 1000) / 1000))
        safe = re.sub(r'[^\w\u4e00-\u9fff-]', '', note['title'])[:16] or note['noteId'][:8]
        a.out = os.path.join(HERE, '..', '输出', '%s_%s.html' % (d, safe))
    a.out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(html)

    print('海报 ->', a.out, round(len(html.encode()) / 1024), 'KB')
    print('账号:', demo['name'])
    print('指标:', ' / '.join(m['v'] for m in demo['metrics']))
    print('二维码:', (demo['qrText'][:60] + '...') if len(demo['qrText']) > 60 else demo['qrText'])
    print('卡片行:', '、'.join(r['label'] for r in demo['rows']))


if __name__ == '__main__':
    main()
