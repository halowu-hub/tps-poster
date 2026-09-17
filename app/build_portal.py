# -*- coding: utf-8 -*-
"""
把 _build/template.html 组装成门户页 index.html：
  1) 顶栏重做（品牌 + 主操作 + 「更多」菜单），链接导入栏做成独立的卡片区
  2) 库内联（qrcode / html2canvas）—— 避免浏览器把 <script src> 子资源当 HTML 拦截
  3) 注入 genFromLink / applyFetched：粘贴链接 -> 抓取 -> 自动填版（仍可编辑）
  4) 连通性自检（/api/ping）+ 分类状态提示 + 失败可读化 + 手动兜底

⚠️ 踩坑记录：附加 CSS 必须包在 <style> 里。上一次直接把 CSS 文本插在 </style> 之后，
   浏览器把这段文本当正文渲染，页面顶部出现一行 `.genbar{...}` 乱码。
"""
import base64, io, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "..", "_build")
NOTE = os.path.join(BUILD, "note_out")
OUT = os.path.join(HERE, "index.html")


def b64_jpg(p, q=84):
    im = Image.open(p).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


avatar = b64_jpg(os.path.join(NOTE, "avatar.jpg"))
shot = b64_jpg(os.path.join(NOTE, "cover.jpg"), 82)
flt = ""

# 打开即是一张完整海报（周系列标题固定为 Top Post Sharing；账号/数据/封面/二维码由链接抓取覆盖）
DEMO = {
    "title": "Top Post Sharing",
    "name": "@澳门四季名店宝格丽小瑜",
    "metrics": [
        {"k": "like", "v": "171"},
        {"k": "star", "v": "2"},
        {"k": "share", "v": "1"},
    ],
    "rows": [
        {"label": "封面优点:",
         "text": "**明星颈部特写 + 暖金虚化背景**，Lisa 与宝格丽灵蛇系列高级珠宝同框；人物占画面三分之二，红蓝宝石形成高饱和视觉焦点。"},
        {"label": "文案优点:",
         "text": "以「哇靠美了我一大跳！！！」情绪开场，正文仅 2 句 24 字完全不写产品信息，把种草力全部交给 10 个话题标签。"},
        {"label": "关键词:",
         "text": "品牌词 **#宝格丽 #宝格丽高级珠宝 #宝格丽灵蛇系列** · 明星词 **#lisa #lisa同款 #宝格丽代言人** · 场景词 **#晚宴穿搭** · 流量词 **#时尚视觉盛宴 #时尚圈焦点**"},
    ],
    "floatShow": False,
    "floatW": 185,
    "qrMode": "text",
    "qrText": "https://www.xiaohongshu.com/explore",
    "qrCaption": "扫码查看原文",
    "orbs": True,
}

tpl = open(os.path.join(BUILD, "template.html"), encoding="utf-8").read()
qr_lib = open(os.path.join(BUILD, "libs", "qrcode.js"), encoding="utf-8").read()
h2c_lib = open(os.path.join(BUILD, "libs", "html2canvas.js"), encoding="utf-8").read()
assert "</script" not in qr_lib.lower() and "</script" not in h2c_lib.lower()

# ---------------------------------------------------------------- 1) 库与数据
tpl = (tpl
       .replace("<!--LIBS-->", "")
       .replace("/*__QR_LIB__*/", qr_lib)
       .replace("/*__H2C_LIB__*/", h2c_lib)
       .replace("__AVATAR__", avatar)
       .replace("__SHOT__", shot)
       .replace("__FLOAT__", flt)
       .replace("__DEMO_JSON__", json.dumps(DEMO, ensure_ascii=False, indent=1))
       .replace("const LS = 'tps_poster_v1';", "let LS = 'tps_portal_v1';"))

# ---------------------------------------------------------------- 2) 门户 CSS
PORTAL_CSS = """
<style>
/* ================= 门户：布局骨架 ================= */
body{display:flex;flex-direction:column;overflow:hidden}
.topbar{position:relative;top:auto;height:56px;flex:0 0 56px;z-index:30;gap:14px}
.wrap{height:auto;flex:1 1 auto;min-height:0}
.panel{padding-bottom:40px}

/* ---------- 顶栏 ---------- */
.tb-left{display:flex;align-items:center;gap:11px;min-width:0}
.logo{width:32px;height:32px;border-radius:9px;flex:0 0 auto;display:flex;align-items:center;
  justify-content:center;background:linear-gradient(140deg,#ff5f76,#e8354f 55%,#c92440);
  box-shadow:0 3px 10px rgba(232,53,79,.3)}
.tb-txt{min-width:0}
.tb-title{font-weight:700;font-size:14px;line-height:1.25;white-space:nowrap;letter-spacing:.2px}
.tb-sub{font-size:11px;color:var(--ink3);line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vsep{width:1px;height:20px;background:var(--line);margin:0 1px;flex:0 0 auto}
.menu{position:relative;flex:0 0 auto}
.menu-pop{position:absolute;right:0;top:calc(100% + 7px);background:#fff;border:1px solid var(--line);
  border-radius:11px;box-shadow:0 14px 34px rgba(20,30,50,.16);padding:5px;min-width:162px;z-index:60}
.menu-pop button{display:block;width:100%;text-align:left;border:0;background:none;padding:8px 10px;
  border-radius:8px;cursor:pointer;font-size:12.5px;color:var(--ink)}
.menu-pop button:hover{background:#f4f6fa}
.mline{height:1px;background:var(--line);margin:4px 6px}

/* ---------- 链接导入栏 ---------- */
.linkbar{flex:0 0 auto;padding:14px 18px 0}
.lb-card{position:relative;background:#fff;border:1px solid var(--line);border-radius:15px;
  padding:12px 14px;box-shadow:0 6px 22px rgba(20,30,50,.07);overflow:hidden;transition:border-color .2s}
.lb-card.loading{border-color:#ffd0d8}
.lb-row{display:flex;align-items:center;gap:10px}
.lb-ico{width:34px;height:34px;border-radius:10px;background:#fdeaee;flex:0 0 auto;
  display:flex;align-items:center;justify-content:center}
.lb-row input{flex:1;min-width:0;height:38px;border:1px solid var(--line);border-radius:10px;
  padding:0 12px;font-size:13px;background:#fbfcfe;outline:none;transition:.15s}
.lb-row input::placeholder{color:#a8b0bd}
.lb-row input:focus{border-color:var(--red);background:#fff;box-shadow:0 0 0 3px rgba(232,53,79,.1)}
.lb-gen{height:38px;padding:0 18px;border-radius:10px;font-size:13.5px;font-weight:600;
  display:inline-flex;align-items:center;gap:8px;flex:0 0 auto}
.lb-gen:disabled{opacity:.72;cursor:default}
.spin{width:13px;height:13px;border:2px solid rgba(255,255,255,.45);border-top-color:#fff;
  border-radius:50%;display:none;animation:sp .7s linear infinite}
.lb-gen:disabled .spin{display:inline-block}
@keyframes sp{to{transform:rotate(360deg)}}
.lb-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:10px;padding-left:44px}
.stat{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:600;white-space:nowrap}
.stat i{width:7px;height:7px;border-radius:50%;background:currentColor;flex:0 0 auto}
.stat.idle{color:#98a0ad} .stat.load{color:#c47f16} .stat.ok{color:#12a150} .stat.err{color:var(--red)}
.lb-hints{font-size:11.5px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lb-chk{display:flex;align-items:center;gap:6px;margin-left:auto;font-size:12px;color:var(--ink2);cursor:pointer;user-select:none;white-space:nowrap;flex:0 0 auto}
.lb-chk input{width:14px;height:14px;accent-color:#e8354f;cursor:pointer;margin:0}
.lb-prog{position:absolute;left:0;right:0;bottom:0;height:2px;overflow:hidden;background:transparent}
.lb-prog i{display:block;height:100%;width:34%;opacity:0;transform:translateX(-100%);
  background:linear-gradient(90deg,rgba(232,53,79,0),#e8354f 45%,#ff8b9c 60%,rgba(232,53,79,0))}
.lb-card.loading .lb-prog i{opacity:1;animation:sl 1.1s ease-in-out infinite}
@keyframes sl{from{transform:translateX(-110%)}to{transform:translateX(330%)}}

/* 生成成功：收起输入、换成一条摘要 */
.lb-done{display:none;align-items:center;gap:11px;background:#fff;border:1px solid #d5f0e0;
  border-radius:15px;padding:10px 13px;box-shadow:0 6px 22px rgba(20,30,50,.07)}
.linkbar.collapsed .lb-card{display:none}
.linkbar.collapsed .lb-done{display:flex}
.lb-ok{display:inline-flex;align-items:center;gap:5px;color:#12a150;font-weight:700;font-size:12px;
  background:#eafaf0;border-radius:8px;padding:4px 9px;flex:0 0 auto}
.lb-done img{width:38px;height:38px;border-radius:50%;object-fit:cover;background:#f2f4f8;
  border:1px solid var(--line);flex:0 0 auto}
.lb-done-txt{min-width:0;flex:1}
.lb-done-txt .dn{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lb-done-txt .dm{font-size:11.5px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* 告警 / 错误条 */
.lb-warn,.lb-err{display:flex;align-items:flex-start;gap:10px;margin-top:10px;padding:10px 13px;
  border-radius:12px;font-size:12px;line-height:1.6}
.lb-warn{background:#fff8ec;border:1px solid #ffe1b3;color:#8a5a12}
.lb-err{background:#fff5f6;border:1px solid #ffd3da;color:#8e2231}
.lb-warn .grow,.lb-err .grow{flex:1;min-width:0}
.lb-warn b,.lb-err b{font-weight:700}
.lb-warn span,.lb-err span{display:block;opacity:.92}
.lb-ico-w{width:18px;height:18px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;
  justify-content:center;font-size:12px;font-weight:700;color:#fff;margin-top:1px}
.lb-warn .lb-ico-w{background:#e0a13a}
.lb-share{display:flex;align-items:flex-start;gap:10px;margin-top:10px;padding:11px 13px;border-radius:12px;
  font-size:12.5px;line-height:1.65;background:#eef5ff;border:1px solid #cfe1ff;color:#17416f}
.lb-share .grow{flex:1;min-width:0}
.lb-share b{font-weight:700}
.lb-share span{display:block;opacity:.94}
.lb-share code{background:#fff;border:1px solid #b9d3f5;border-radius:5px;padding:1px 6px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#12457f}
.lb-share .lb-ico-s{flex:0 0 auto;width:18px;height:18px;border-radius:50%;background:#2f7fd8;color:#fff;
  font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px}
.lb-err .lb-ico-w{background:var(--red)}
.lb-warn code,.lb-err code{background:#fff;border:1px solid currentColor;border-radius:5px;
  padding:0 5px;font-size:11px;opacity:.9}

@media (max-width:1220px){.tb-sub{display:none}}
@media (max-width:1040px){.lb-hints{display:none}}
</style>
"""
tpl = tpl.replace("</head>", PORTAL_CSS + "\n</head>")

# ---------------------------------------------------------------- 3) 顶栏 + 链接栏
NEW_HEADER = """<div class="topbar">
  <div class="tb-left">
    <div class="logo">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M13.6 2 4.2 13.4h6L10.4 22l9.4-11.4h-6L13.6 2z" fill="#fff"/></svg>
    </div>
    <div class="tb-txt">
      <div class="tb-title">每周海报生成器</div>
      <div class="tb-sub">Top Post Sharing · 粘贴小红书笔记链接，自动生成 1080px 分享海报</div>
    </div>
  </div>
  <div class="acts">
    <button class="btn sm" id="btn-copy">复制图片</button>
    <button class="btn sm pri" id="btn-png2">下载 PNG (2x)</button>
    <button class="btn sm" id="btn-png3">3x</button>
    <div class="vsep"></div>
    <div class="menu" id="menu-more">
      <button class="btn sm" id="btn-more">更多</button>
      <div class="menu-pop hidden" id="menu-pop">
        <button id="btn-share">分享给同事…</button>
        <div class="mline"></div>
        <button id="btn-exp">导出配置（含图，可存档）</button>
        <button id="btn-imp">导入配置</button>
        <div class="mline"></div>
        <button id="btn-reset">恢复为示例</button>
      </div>
    </div>
  </div>
</div>

<section class="linkbar" id="linkbar">
  <div class="lb-card" id="lb-card">
    <div class="lb-row">
      <span class="lb-ico" aria-hidden="true">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M10.6 13.4a4 4 0 0 0 5.66 0l3.03-3.03a4 4 0 0 0-5.66-5.66L12.4 5.94" stroke="#e8354f" stroke-width="2" stroke-linecap="round"/><path d="M13.4 10.6a4 4 0 0 0-5.66 0L4.71 13.63a4 4 0 0 0 5.66 5.66l1.23-1.23" stroke="#e8354f" stroke-width="2" stroke-linecap="round"/></svg>
      </span>
      <input type="text" id="f-link" spellcheck="false" autocomplete="off"
             placeholder="粘贴小红书笔记链接（App 里「分享 → 复制链接」），粘贴后自动开始生成">
      <button class="btn pri lb-gen" id="btn-gen"><span class="spin"></span><span id="gen-txt">一键生成海报</span></button>
    </div>
    <div class="lb-foot">
      <span class="stat idle" id="gen-stat"><i></i><b>就绪 · 等待链接</b></span>
      <label class="lb-chk" for="f-playbook" title="额外生成第 4 段「可复用打法」：把这条笔记沉淀成下周能直接照做的动作 + 验收标准。取消勾选则只出三段，海报维持原始的 1099 高度。">
        <input type="checkbox" id="f-playbook" checked> ＋可复用打法（第 4 段，海报会略高）
      </label>
      <span class="lb-hints">自动抓取：账号名 · 头像 · 赞藏数据 · 封面 → 手机屏 · 第 2 张图 → 悬浮小图 · 二维码</span>
    </div>
    <div class="lb-prog"><i></i></div>
  </div>

  <div class="lb-done" id="lb-done">
    <span class="lb-ok">✓ 已自动生成</span>
    <img id="done-av" alt="">
    <div class="lb-done-txt">
      <div class="dn" id="done-name"></div>
      <div class="dm" id="done-meta"></div>
    </div>
    <button class="btn sm" id="btn-reopen" style="flex:0 0 auto">换一条链接</button>
  </div>

  <div class="lb-warn hidden" id="lb-warn">
    <span class="lb-ico-w">!</span>
    <div class="grow"><b>本地抓取服务未连接</b><span id="warn-msg"></span></div>
    <button class="btn sm" id="btn-reconn" style="flex:0 0 auto">重新连接</button>
  </div>

  <div class="lb-err hidden" id="lb-err">
    <span class="lb-ico-w">!</span>
    <div class="grow"><b id="err-msg"></b><span id="err-hint"></span></div>
    <button class="btn sm" id="btn-err-retry" style="flex:0 0 auto">重试</button>
  </div>

  <div class="lb-share hidden" id="lb-share">
    <span class="lb-ico-s">↗</span>
    <div class="grow" id="share-body"></div>
    <button class="btn sm" id="btn-share-copy" style="flex:0 0 auto">复制链接</button>
    <button class="btn sm" id="btn-share-close" style="flex:0 0 auto">关闭</button>
  </div>
</section>

<div class="wrap">"""

_i = tpl.index('<div class="topbar">')
_j = tpl.index('<div class="wrap">')
assert tpl.count('<div class="wrap">') == 1 and tpl.count('<div class="topbar">') == 1
tpl = tpl[:_i] + NEW_HEADER + tpl[_j + len('<div class="wrap">'):]

# ---------------------------------------------------------------- 4) 左侧提示文案
OLD_TIPS = """      <b>每周三步走</b>：① 换头像 / 手机截图（点框上传，或直接 <kbd>⌘V</kbd> 粘贴）② 改账号名与三个数字 ③ 改下方卡片文案 → 「下载 PNG」<br>
      版式固定不用动；下次打开自动恢复上次内容（也可「导出配置」存档，下周「导入配置」继续改）。"""
NEW_TIPS = """      <b>每周三步走</b>：① 把 KOS 笔记链接粘到上方 → 自动抓取并填好整张海报 ② 按需微调下方「卡片内容」的三段分析
      ③ 「下载 PNG (2x)」导出 1080 宽分享图<br>
      账号名 / 头像 / 赞藏数据 / 封面 / 二维码全部自动抓取，下面这些字段可随时手工改；同一篇笔记的编辑会分别存档。"""
assert OLD_TIPS in tpl, "左侧提示文案未匹配"
tpl = tpl.replace(OLD_TIPS, NEW_TIPS)

# ---------------------------------------------------------------- 5) 门户 JS
PORTAL_JS = r"""
/* ================= 门户：粘贴链接 → 自动生成 ================= */
const API = (location.protocol === 'file:') ? 'http://127.0.0.1:8731' : '';
const FROM_FILE = (location.protocol === 'file:');
let busy = false;

/* 上次导入的笔记：重开页面时接着编辑那一篇 */
try{
  const last = localStorage.getItem('tps_portal_last');
  if(last) LS = 'tps_portal_' + last;
}catch(e){}

function setStat(kind, text){
  const e = document.querySelector('#gen-stat'); if(!e) return;
  e.className = 'stat ' + kind;
  const b = e.querySelector('b'); if(b) b.textContent = text;
}
function showErr(msg, hint){
  document.querySelector('#err-msg').textContent = msg || '抓取失败';
  document.querySelector('#err-hint').textContent = hint || '';
  document.querySelector('#lb-err').classList.remove('hidden');
}
function hideErr(){ document.querySelector('#lb-err').classList.add('hidden'); }

const STEPS = ['打开笔记页面…','解析正文与话题标签…','下载封面、头像与第 2 张图…','按笔记内容起草策略化分析…'];
let stepT = null;
function startSteps(){
  let i = 0; setStat('load', STEPS[0]); clearInterval(stepT);
  stepT = setInterval(()=>{ i = (i + 1) % STEPS.length; setStat('load', STEPS[i]); }, 1500);
}
function stopSteps(){ clearInterval(stepT); stepT = null; }

/* ---- 连通性自检 ---- */
async function checkConn(quiet){
  try{
    const r = await fetch(API + '/api/ping?t=' + Date.now(), {cache:'no-store'});
    if(!r.ok) throw new Error('HTTP ' + r.status);
    await r.json();
    document.querySelector('#lb-warn').classList.add('hidden');
    if(!quiet) toast('本地服务已连接 ✓');
    return true;
  }catch(e){
    document.querySelector('#warn-msg').innerHTML = FROM_FILE
      ? ' 当前页面是以「本地文件」方式打开的，抓取接口用不了。请改用启动器打开的页面：双击 <code>启动生成器.command</code>。'
      : ' 抓取服务没有响应，可能已经退出。双击 <code>启动生成器.command</code> 重新启动后，点「重新连接」。';
    document.querySelector('#lb-warn').classList.remove('hidden');
    if(!quiet) toast('本地服务未连接');
    return false;
  }
}

/* ---- 主流程 ---- */
async function genFromLink(){
  if(busy) return;
  const input = document.querySelector('#f-link');
  const url = (input.value || '').trim();
  if(!url){ toast('请先粘贴笔记链接'); input.focus(); return; }
  busy = true; hideErr();
  document.querySelector('#lb-warn').classList.add('hidden');
  document.querySelector('#lb-card').classList.add('loading');
  const btn = document.querySelector('#btn-gen');
  btn.disabled = true; document.querySelector('#gen-txt').textContent = '生成中…';
  startSteps();
  try{
    const resp = await fetch(API + '/api/fetch', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url, playbook: document.querySelector('#f-playbook').checked})
    });
    let d = {};
    try{ d = await resp.json(); }catch(_){}
    if(!resp.ok || d.error){
      stopSteps(); setStat('err', '抓取失败');
      showErr(d.error || ('服务返回 HTTP ' + resp.status), d.hint || '');
      toast('抓取失败，请看提示');
      return;
    }
    stopSteps(); setStat('load', '正在填版…');
    await applyFetched(d);
    fillDone(d);
    setStat('ok', '已生成 · 内容可编辑');
    document.querySelector('#linkbar').classList.add('collapsed');
    toast('已自动填好：账号名 / 头像 / 数据 / 封面 / 二维码');
  }catch(err){
    stopSteps(); setStat('err', '连接失败');
    showErr('无法连接本地抓取服务（' + ((err && err.message) || err) + '）',
            FROM_FILE ? '请用「启动生成器.command」打开的页面再试。' : '请重新启动本地服务后重试。');
    checkConn(true);
  }finally{
    document.querySelector('#lb-card').classList.remove('loading');
    btn.disabled = false; document.querySelector('#gen-txt').textContent = '一键生成海报';
    busy = false;
  }
}

/* 把抓到的数据填进海报状态（周系列标题保持 Top Post Sharing 不变） */
async function applyFetched(d){
  if(d.noteId){
    LS = 'tps_portal_' + d.noteId;
    try{ localStorage.setItem('tps_portal_last', d.noteId); }catch(e){}
  }
  const nick = (d.user && d.user.nickname) || d.nickname || '';
  if(nick) S.name = nick.charAt(0) === '@' ? nick : ('@' + nick);

  const st = d.stats || {};
  const val = v => (v === undefined || v === null) ? '' : String(v);
  S.metrics = [
    {k:'like',  v: val(st.like)},
    {k:'star',  v: val(st.collect)},
    {k:'share', v: val(st.share)}
  ];
  S.qrText = d.url || ''; S.qrMode = 'text'; S.qrCaption = d.qrCaption || '扫码查看原文';
  if(d.rows && d.rows.length) S.rows = d.rows;
  /* 悬浮小图 = 笔记的第 2 张图（叠在手机上的第二个画面），自动填入。
     图文笔记才有；视频笔记拿不到第 2 张图就不显示，仍然可以手动上传替换。 */
  S.floatShow = false; S.floatImg = ''; S.floatRaw = '';
  if(d.float){
    const fw = Math.round(S.floatW || 185);
    S.floatRaw = d.float;
    try{ S.floatImg = await fitImage(d.float, fw, Math.round(fw*1.27), 'center'); }
    catch(e){ S.floatImg = d.float; }
    S.floatShow = true;
  }
  if(d.avatar){ S.avatarRaw = d.avatar;
    try{ S.avatar = await fitImage(d.avatar, 135, 135, 'center'); }catch(e){ S.avatar = d.avatar; } }
  if(d.cover){ S.shotRaw = d.cover;
    try{ S.shot = await fitImage(d.cover, 226, 503, 'top'); }catch(e){ S.shot = d.cover; } }
  save(); syncPanel(); render(); applyZoom();
}

function fillDone(d){
  const st = d.stats || {};
  document.querySelector('#done-av').src = d.avatar || '';
  document.querySelector('#done-name').textContent =
    ((d.user && d.user.nickname) || '笔记') + (d.title ? ' · ' + d.title : '');
  const nImg = d.imageCount || 0;
  document.querySelector('#done-meta').textContent =
    '赞 ' + (st.like == null ? '-' : st.like) + ' · 藏 ' + (st.collect == null ? '-' : st.collect) +
    ' · 分享 ' + (st.share == null ? '-' : st.share) + ' · 标签 ' + ((d.tags || []).length) +
    ' 个 · ' + ((d.rows || []).length) + ' 段分析已起草（可直接改）' +
    (d.float ? '｜第 2 张图已叠为悬浮小图' : (nImg > 1 ? '' : '｜本条无第 2 张图'));
}

/* ---- 事件绑定 ---- */
document.querySelector('#btn-gen').addEventListener('click', genFromLink);
const linkInput = document.querySelector('#f-link');
linkInput.addEventListener('keydown', e=>{ if(e.key === 'Enter') genFromLink(); });
/* 粘贴即生成：分享文案里只有一段链接也能用（后端负责提取） */
linkInput.addEventListener('paste', ()=>{ setTimeout(()=>{ if(document.activeElement === linkInput) genFromLink(); }, 140); });
document.querySelector('#btn-err-retry').addEventListener('click', genFromLink);
document.querySelector('#btn-reconn').addEventListener('click', ()=>checkConn(false));
document.querySelector('#btn-reopen').addEventListener('click', ()=>{
  document.querySelector('#linkbar').classList.remove('collapsed');
  linkInput.value = ''; hideErr(); linkInput.focus();
  setStat('idle', '就绪 · 等待链接');
});
const pop = document.querySelector('#menu-pop');
document.querySelector('#btn-more').addEventListener('click', e=>{
  e.stopPropagation(); pop.classList.toggle('hidden');
});
document.addEventListener('click', ()=>pop.classList.add('hidden'));

/* ---- 分享给同事 ---- */
const shareBox = document.querySelector('#lb-share');
function closeShare(){ shareBox.classList.add('hidden'); }
document.querySelector('#btn-share-close').addEventListener('click', closeShare);
document.querySelector('#btn-share-copy').addEventListener('click', async ()=>{
  const t = shareBox.dataset.copy || '';
  if(!t){ toast('当前没有可复制的链接'); return; }
  try{ await navigator.clipboard.writeText(t); toast('已复制：' + t); }
  catch(_){ toast('复制失败，请手动选中链接复制'); }
});
document.querySelector('#btn-share').addEventListener('click', async ()=>{
  pop.classList.add('hidden');
  let info = {};
  try{ info = await (await fetch(API + '/api/ping')).json(); }catch(_){}
  shareBox.dataset.copy = '';
  const box = document.querySelector('#share-body');
  if(info.shared && info.lanUrl){
    shareBox.dataset.copy = info.lanUrl;
    box.innerHTML = '<b>同事这样用（零安装）</b>'
      + '<span>① 确认同事连的是同一个 WiFi / 局域网</span>'
      + '<span>② 把 <code>' + info.lanUrl + '</code> 发给他，浏览器打开即可</span>'
      + '<span>③ 他粘贴小红书链接就能出图，不需要装任何东西</span>';
  }else{
    box.innerHTML = '<b>想让同事也用起来，两种方式</b>'
      + '<span><b>团队共享（推荐）</b>：终端里执行 '
      + '<code>cd app &amp;&amp; TPS_HOST=0.0.0.0 python3 serve.py</code>'
      + '，然后把局域网地址发给同事，他浏览器打开就能用 —— 同事零安装。</span>'
      + '<span><b>人手一份</b>：把「TopPostSharing-分享版」文件夹（或 .zip）发给同事，'
      + '他双击里面的「① 双击我启动.command」即可，同样是零安装。</span>'
      + '<span>分享版打包命令：<code>python3 app/build_share.py</code></span>';
  }
  shareBox.classList.remove('hidden');
});

/* ---- 启动自检 ---- */
setTimeout(()=>checkConn(true), 250);
"""
tpl = tpl.replace("/* ================= 启动 ================= */", PORTAL_JS + "\n/* ================= 启动 ================= */")

open(OUT, "w", encoding="utf-8").write(tpl)
print("门户页 ->", OUT, round(len(tpl.encode()) / 1024), "KB")
