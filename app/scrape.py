# -*- coding: utf-8 -*-
"""
服务端抓取：小红书笔记链接 -> JSON
返回：标题/正文/话题标签/账号名/数据/封面与头像(base64) + 自动起草的三段分析

要点（踩过的坑）：
  1. 这里抛出的所有异常都必须是 Exception 的子类（ScrapeError），
     绝不能用 SystemExit —— 请求跑在 ThreadingHTTPServer 的线程里，
     BaseException 会击穿 except Exception 让线程静默死亡，前端只看到「网络错误」。
  2. 带 xsec_token 的分享链接才稳定；无 token 的 /explore/ 链接常被登录墙拦下。
  3. 风控页是间歇性的，失败后重试 1 次能显著提高成功率。
"""
import base64, json, os, re, sys, time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
# fetch_note.py 在开发目录里位于 ../_build/，在「分享版」包里则与 scrape.py 同级。
# 两种布局都要能找到，否则同事拷走一个文件夹就跑不起来。
for _p in (os.path.join(_HERE, "..", "_build"), _HERE):
    if os.path.exists(os.path.join(_p, "fetch_note.py")):
        sys.path.insert(0, _p)
        break
from fetch_note import (ScrapeError, NotFoundError, fetch_page, parse_state,  # noqa
                        analyze, pick_url, OPENER, UA)

MAX_TRY = 2          # 风控页间歇出现，重试一次
RETRY_WAIT = 0.8


def _get_bytes(url, referer="https://www.xiaohongshu.com/"):
    hdr = {
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "image/avif,image/webp,image/apng,image/png,image/jpeg,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=hdr)
    r = OPENER.open(req, timeout=30)
    return r.read()


def _b64(raw):
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def _image_urls(n):
    """笔记里的全部配图地址，按原始顺序（第 0 张是封面）"""
    out = []
    for im in (n.get("imageList") or []):
        u = im.get("urlDefault") or im.get("urlPre") or im.get("url")
        if u:
            out.append(u)
    return out


def _cover_url(n):
    """优先取 imageList 首图；视频笔记退回 video.cover / firstFrameUrl"""
    us = _image_urls(n)
    if us:
        return us[0]
    vid = n.get("video") or {}
    return vid.get("cover") or vid.get("firstFrameUrl") or vid.get("url")


# ---------------------------------------------------------------- 分析起草
# 说明：这三段是「有据可依的草稿」——所有数字/标签都来自抓取到的真实数据，
# 只是把客观事实组织成点评口吻；用户可以随时在网页里改写。

BRAND_WORDS = [
    "宝格丽", "bvlgari", "兰蔻", "lancome", "雅诗兰黛", "estee", "娇兰", "guerlain",
    "阿玛尼", "armani", "迪奥", "dior", "香奈儿", "chanel", "卡地亚", "cartier",
    "蒂芙尼", "tiffany", "梵克雅宝", "vca", "古驰", "gucci", "普拉达", "prada",
    "爱马仕", "hermes", "路易威登", "lv", "罗意威", "loewe", "海蓝之谜", "la mer",
    "祖玛珑", "jo malone", "科颜氏", "kiehl", "希思黎", "sisley", "瑞妍", "cellcosmet",
    "法尔曼", "valmont", "赫莲娜", "helena", "莱珀妮", "laprairie", "fresh", "馥蕾诗",
    "dfs", "四季", "t广场", "丝芙兰", "sogo", "连卡佛",
]
SCENE_WORDS = ["穿搭", "晚宴", "婚礼", "度假", "妆容", "口红", "珠宝", "香水", "美甲",
               "发色", "派对", "通勤", "日常", "约会", "旅行", "露营", "健身", "妆教",
               "护肤", "开箱", "探店", "街拍", "妆造"]
FLOW_WORDS = ["氛围感", "视觉盛宴", "焦点", "趋势", "爆款", "必入", "攻略", "热搜",
              "时尚", "高级感", "松弛感", "多巴胺", "显白", "氛围", "美学", "灵感"]


def classify_tags(tags, title, nickname=""):
    """把话题标签分成 品牌词 / 明星词 / 场景词 / 流量词

    账号自己名字的标签（品牌常把店名/柜哥名做成话题）会干扰阅读，直接剔除。
    """
    latin_title = set(re.findall(r"[A-Za-z][A-Za-z0-9']{2,}", (title or "").lower()))
    nick_cjk = set(re.findall(r"[\u4e00-\u9fa5]", nickname or ""))
    out = {"品牌": [], "明星": [], "场景": [], "流量": []}
    for t in tags:
        if t in out["品牌"]:
            continue
        # 账号自家标签（品牌常把店名/柜哥名做成话题）会干扰阅读，剔除。
        # 注意昵称与标签可能繁简不同（澳門 vs 澳门），直接字符串比对会漏，
        # 改用汉字集合重合度判断。
        if len(nick_cjk) >= 4:
            tcjk = set(re.findall(r"[\u4e00-\u9fa5]", t))
            if tcjk and len(nick_cjk & tcjk) / len(nick_cjk) >= 0.7:
                continue
        low = t.lower()
        if any(b in low for b in BRAND_WORDS):
            out["品牌"].append(t)
            continue
        if ("同款" in t) or ("代言" in t) or (set(re.findall(r"[A-Za-z][A-Za-z0-9']{2,}", low)) & latin_title):
            out["明星"].append(t)
            continue
        if any(s in t for s in SCENE_WORDS):
            out["场景"].append(t)
            continue
        out["流量"].append(t)
    return out


def _hook(body):
    """正文开场钩子：取第一句（最多 16 字）"""
    if not body:
        return ""
    first = re.split(r"[。！？!?\n]", body)[0].strip()
    return first[:16]


def _hook_type(first):
    """开场钩子类型——决定这条内容靠什么抓住前 2 秒"""
    if re.search(r"[！!]", first):
        return "情绪惊叹"
    if re.search(r"[？?]|吗|怎么|如何|为什么", first):
        return "提问"
    if re.search(r"\d|折|元|价|免费|攻略|教程|清单|合集", first):
        return "直给利益"
    return "平铺直叙"


def _cjk(s):
    return len(re.findall(r"[\u4e00-\u9fa5]", s or ""))


def _pct(v):
    """百分比按量级给精度：别把 0.008% 显示成 0%（那样这条验收标准就没意义了）"""
    a = abs(v or 0)
    if a >= 10:
        return "%.0f%%" % v
    if a >= 1:
        return "%.1f%%" % v
    if a >= 0.1:
        return "%.2f%%" % v
    return "%.3f%%" % v


def _fit(s, n):
    """超长时按句号截断，避免把海报撑变形"""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    for sep in ("。", "；", "，"):
        i = cut.rfind(sep)
        if i > n * 0.6:
            return cut[: i + 1]
    return cut + "…"


def _compose(head, tail, n):
    """把「判断 + 数据」段和「可复用 / 验收标准」段拼成一行，总长不超过 n。

    先给 tail（结论句）占好位置，再拿剩余预算去裁 head。
    如果反过来先拼再截，_fit 会把最有价值的结论句整句切掉——
    那正是「反空话」里要求的那条可落地动作 / 可验证标准。
    """
    head = (head or "").strip().rstrip("。；， ｜")
    tail = (tail or "").strip()
    if not tail:
        return _fit(head, n)
    room = max(24, n - len(tail) - 1)
    head = _fit(head, room).rstrip("。；， ｜…")
    if head.count("**") % 2:          # 裁断处可能留下落单的加粗标记，补上
        head += "**"
    return (head + "。" + tail) if head else tail


def draft_rows(d, with_playbook=True):
    """按抓取到的真实数据起草四段分析（可编辑）

    语言口径借鉴小红书账号诊断 skill 的「反空话」约束：
    每条结论必须同时具备 ①数据支撑 ②可落地动作 ③可验证标准，
    禁止出现「提升内容质量」这类没有动作、没有数据的表述。
    """
    tags = d.get("tags") or []
    body = re.sub(r"\s+", " ", (d.get("body") or "")).strip()
    st = d.get("stats") or {}
    like = st.get("like", 0) or 0
    collect = st.get("collect", 0) or 0
    comment = st.get("comment", 0) or 0
    share = st.get("share", 0) or 0
    inter = like + collect + comment + share
    is_video = d.get("type") == "video"
    imgs = d.get("images") or []
    cjk = _cjk(body)
    tag_n = len(tags)

    ratio, vertical = "", False
    if imgs and imgs[0].get("w") and imgs[0].get("h"):
        w, h = imgs[0]["w"], imgs[0]["h"]
        vertical = h >= w
        ratio = "竖版 %.1f:1" % (h / w) if vertical else "横版 %.1f:1" % (w / h)

    # ---------- ① 封面：判断 → 数据 → 动作 ----------
    if is_video:
        c_type = "视频笔记 · 首帧即封面"
    elif len(imgs) > 1:
        c_type = "图文笔记 · %d 图" % len(imgs)
    else:
        c_type = "图文笔记 · 单图封面"
    if cjk <= 30:
        load = "正文仅 %d 字、不写产品参数" % cjk
    else:
        load = "正文 %d 字" % cjk
    cover_head = "**%s**%s，%s —— **画面独自承担转化**" % (
        c_type, ("（%s）" % ratio) if ratio else "", load)
    cover_tail = ("可复用：选封面时锁死「主体占画面 2/3 + 1 秒可辨认主角」，"
                  "竖版优先（信息流铺满，比横版多约一屏停留）。")

    # ---------- ② 文案：判断 → 数据 → 动作 ----------
    hk = _hook(body)
    # 用未截断的原文判断钩子类型：_hook 会把句末的「！」切掉，
    # 导致「哇靠美了我一大跳！！！」被误判成平铺直叙。
    htype = _hook_type(body[:24])
    copy_head = "**%s式开场**" % htype
    if hk:
        copy_head += "（「%s」）" % hk[:12]
    copy_head += "，正文 %d 字 / 标签 %d 个" % (cjk, tag_n)
    if tag_n >= 5 and cjk and tag_n >= cjk / 12:
        copy_head += "——**标签的信息量大于正文**，种草点全部外包给标签流量池，正文只管情绪"
        copy_tail = "可复用：正文压到 30 字内只放情绪钩子，产品信息交给 8-10 个标签承接。"
    else:
        copy_head += "，正文与标签分工清晰"
        copy_tail = "可复用：开头 15 字内必须给到钩子（惊叹 / 提问 / 利益三选一），后续再补信息。"
    if inter:
        cr = (collect / like) if like else 0
        if like and comment == 0:
            verdict = "赞 %d / 藏 %d / 评 0，**零评论** → 纯视觉冲击型，靠刷过即种草，不靠讨论" % (like, collect)
        elif cr >= 0.30:
            verdict = "收藏率是赞的 %.0f%%，**高收藏** → 用户「先存后看」，内容有留存价值" % (cr * 100)
        elif cr >= 0.10:
            verdict = "收藏率 %.0f%%，**中等收藏** → 情绪与实用各占一半" % (cr * 100)
        else:
            verdict = "赞 %d / 藏 %d，收藏率 %s → **偏情绪消费**，看完即走" % (
                like, collect, _pct(cr * 100))
        copy_head += "。" + verdict
    else:
        copy_head += "。互动尚未积累，可作冷启动基线样本"

    # ---------- ③ 关键词：结构判断 → 词表 → 配比动作 ----------
    cls = classify_tags(tags, d.get("title") or "", (d.get("user") or {}).get("nickname", ""))
    parts = []
    for key, name in (("品牌", "品牌词"), ("明星", "明星词"), ("场景", "场景词"), ("流量", "流量词")):
        if cls[key]:
            parts.append("%s **%s**" % (name, " ".join("#" + t for t in cls[key][:6])))
    if parts:
        miss = [n for k, n in (("品牌", "品牌"), ("明星", "明星"), ("场景", "场景"), ("流量", "流量")) if not cls[k]]
        kw_head = " · ".join(parts)
        # 「覆盖了哪几类」用短标签表达，省下的宽度留给「可复用」那句
        kw_head += (" ｜缺 %s 词" % "/".join(miss)) if miss else " ｜四类全覆盖"
        kw_tail = "可复用：固定「品牌 2 + 场景 1 + 流量 2」的配比，别只堆品牌词（会掉出泛流量池）。"
    else:
        kw_head = "这条笔记没有话题标签"
        kw_tail = "可复用：补 5-8 个，按「品牌 2 + 场景 1 + 流量 2」配比铺。"

    rows = [
        {"label": "封面优点:", "text": _compose(cover_head, cover_tail, 150)},
        {"label": "文案优点:", "text": _compose(copy_head, copy_tail, 165)},
        {"label": "关键词:", "text": _compose(kw_head, kw_tail, 175)},
    ]

    # ---------- ④ 可复用打法：把这条笔记沉淀成下周能直接用的动作 ----------
    if with_playbook:
        acts = []
        if is_video:
            acts.append("视频首帧单独挑（别用默认帧），首帧决定完播")
        elif len(imgs) > 1:
            acts.append("第 1 张图按封面标准单独做，后几张放细节/对比")
        else:
            acts.append("单图笔记把信息压在一张图内，配色不超过 3 种")
        if tag_n >= 5:
            acts.append("标签沿用本条「%s」结构，下次照抄配比再换词" % (
                "/".join([n for k, n in (("品牌", "品牌"), ("场景", "场景"), ("流量", "流量")) if cls[k]]) or "品牌+流量"))
        else:
            acts.append("标签补到 5-8 个，覆盖品牌 + 场景 + 流量三类")
        if like and comment == 0:
            acts.append("想拉讨论度就在结尾加一个开放式提问，把零评论补上")
        # 验收标准是「反空话」里最值钱的一句（可验证效果），必须留住：
        # 交给 _compose 先给它占好位置，再拿剩余预算去裁动作。
        crit = "验收标准：下次同类型笔记，收藏率不低于本条的 %s、互动量不低于 %d。" % (
            _pct((collect / like * 100) if like else 10), inter if inter else 1)
        pb_head = "；".join(acts[:3])
        rows.append({"label": "可复用打法:", "text": _compose(pb_head, crit, 150)})

    return rows


# ---------------------------------------------------------------- 主流程
def _parse(url):
    final, page = fetch_page(url)
    # 小红书对不存在的笔记会跳到 /404 页；这种重试没用，直接给出准确原因
    if "/404" in final or "页面不见了" in page[:4000]:
        if "xsec_token" not in url:
            raise NotFoundError(
                "这条链接缺少访问凭证（xsec_token），小红书直接返回了 404",
                "请在小红书 App 里点「分享 → 复制链接」，用带 xsec_token 的完整链接再试。")
        raise NotFoundError(
            "这条链接打不开：小红书返回 404（笔记不存在或链接不完整）",
            "请确认链接有没有被截断；如果笔记已被删除，换一条公开笔记再试。")
    state = parse_state(page)                 # 失败会抛 ScrapeError（含 hint）
    ndm = state.get("note", {}).get("noteDetailMap", {})
    if not ndm:
        raise ScrapeError(
            "链接里的笔记打不开（可能已失效、被删除，或需要登录）",
            "请在 App 里重新「分享 → 复制链接」后，用新链接再试一次。")
    nid, holder = next(iter(ndm.items()))
    if not holder.get("note"):
        raise ScrapeError("该笔记没有返回内容（可能已删除 / 仅粉丝可见）",
                          "换一条公开笔记的链接试试。")
    return final, holder


def scrape(text, log=print, with_playbook=True):
    url = pick_url(text)
    if "xsec_token" not in url:
        log("[warn] 链接没有 xsec_token，可能被登录墙拦下:", url[:110])

    last = None
    for attempt in range(1, MAX_TRY + 1):
        try:
            final, holder = _parse(url)
            break
        except NotFoundError as e:              # 404 重试没意义
            log("[404] %s" % e)
            raise
        except ScrapeError as e:
            last = e
            log("[fail %d/%d] %s" % (attempt, MAX_TRY, e))
            if attempt < MAX_TRY:
                time.sleep(RETRY_WAIT)
    else:
        raise last

    d = analyze(holder)
    d["url"] = final if "xiaohongshu.com" in final else url
    n = holder["note"]

    # 头像
    av = d["user"].get("avatar")
    if av:
        try:
            d["avatar"] = _b64(_get_bytes(av))
        except Exception as e:
            log("[warn] 头像下载失败:", type(e).__name__, e)
            d["avatar"] = ""
    else:
        d["avatar"] = ""
    # 封面
    cu = _cover_url(n)
    if cu:
        try:
            d["cover"] = _b64(_get_bytes(cu))
        except Exception as e:
            log("[warn] 封面下载失败:", type(e).__name__, e)
            d["cover"] = ""
    else:
        d["cover"] = ""

    # 第 2 张图 -> 海报上叠在手机上的「悬浮小图」（第二画面）
    # 图文笔记才有；视频笔记 imageList 通常只有 1 张，这种情况下不显示悬浮小图。
    us = _image_urls(n)
    d["float"] = ""
    d["imageCount"] = len(us)
    if len(us) > 1:
        try:
            d["float"] = _b64(_get_bytes(us[1]))
            log("[float] 第 2 张图已取为悬浮小图")
        except Exception as e:
            log("[warn] 第 2 张图下载失败:", type(e).__name__, e)
            d["float"] = ""

    d["qrCaption"] = "扫码查看原文"
    d["rows"] = draft_rows(d, with_playbook=bool(with_playbook))
    d.pop("images", None)       # 图片只留 base64 首图，其余裁掉以缩小响应体
    d.pop("rawDesc", None)
    return d


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 scrape.py <笔记链接>")
        raise SystemExit(1)
    try:
        out = scrape(sys.argv[1])
        print(json.dumps(out, ensure_ascii=False, indent=1))
    except ScrapeError as e:
        print("抓取失败：%s" % e)
        if e.hint:
            print("提示：%s" % e.hint)
        raise SystemExit(1)
