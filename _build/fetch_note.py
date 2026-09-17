# -*- coding: utf-8 -*-
"""
小红书笔记链接 -> 结构化数据 + 封面/头像本地图
用法: python3 fetch_note.py "<链接或分享文案>" [输出目录]
产出: <输出目录>/note.json, cover.jpg, avatar.jpg
"""
import sys, os, re, json, gzip, html as htmlmod
import urllib.request, urllib.error

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ScrapeError(Exception):
    """抓取失败（消息可直接展示给用户）。

    注意：这里绝不能用 SystemExit —— 本模块同时被 app/serve.py 的请求线程调用，
    BaseException 会击穿 http.server 的 except Exception，导致线程静默死亡、
    前端只看到「网络错误」。CLI 入口在 main() 里统一转成 SystemExit。
    """
    def __init__(self, msg, hint=""):
        super().__init__(msg)
        self.hint = hint


class NotFoundError(ScrapeError):
    """链接指向的页面不存在（404）：重试也没有意义"""


def get(url, referer=None, timeout=30):
    hdr = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        hdr["Referer"] = referer
    req = urllib.request.Request(url, headers=hdr)
    r = OPENER.open(req, timeout=timeout)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return r, raw


def pick_url(text):
    m = re.search(r"https?://[^\s，,。；;）)】\]]+", text)
    if not m:
        raise ScrapeError("没找到链接", "请粘贴小红书笔记链接（或 App 里「分享 → 复制链接」的整段文字）")
    return m.group(0).rstrip('.,;)')


def fetch_page(url):
    """跟一次重定向（xhslink 短链），返回最终 URL 和 HTML"""
    r, raw = get(url)
    final = r.geturl()
    if "xiaohongshu.com" not in final and "xhslink" in url:
        r, raw = get(final)
        final = r.geturl()
    return final, raw.decode("utf-8", "ignore")


def parse_state(html):
    i = html.find("__INITIAL_STATE__=")
    if i < 0:
        raise ScrapeError(
            "没有拿到笔记数据（小红书返回了验证页/登录页）",
            "通常是该链接的访问凭证已失效，或这条笔记不是公开状态；"
            "请在 App 里重新「分享 → 复制链接」，用新链接再试一次。")
    s = html[i + len("__INITIAL_STATE__="):]
    s = s[: s.find("</script>")]
    # XHS 会塞 undefined，替换成 null
    s = re.sub(r"(?<![\w\"'])undefined(?![\w\"'])", "null", s)
    try:
        return json.loads(s)
    except Exception:
        raise ScrapeError("笔记数据解析失败（页面结构已变化或被风控拦截）",
                          "稍后重试；若持续失败请把链接发我排查。")


def analyze(note):
    """把原始 note 拆成海报需要的字段"""
    n = note["note"]
    user = n.get("user", {}) or {}
    it = n.get("interactInfo", {}) or {}
    raw_desc = n.get("desc", "") or ""
    tags = [t["name"] for t in (n.get("tagList") or [])]
    # 正文去掉话题标签
    body = re.sub(r"#[^#\[\]]+\[话题\]#", "", raw_desc).strip()
    imgs = []
    for im in (n.get("imageList") or []):
        imgs.append({
            "w": im.get("width"), "h": im.get("height"),
            "url": im.get("urlDefault") or im.get("urlPre") or im.get("url"),
        })
    is_video = (n.get("type") == "video") or bool(n.get("video"))

    def num(v):
        try:
            return int(str(v).strip() or 0)
        except Exception:
            return 0

    return {
        "noteId": n.get("noteId") or note.get("currentNoteId"),
        "type": "video" if is_video else "normal",
        "xsecToken": n.get("xsecToken", ""),
        "title": (n.get("title") or "").strip(),
        "body": body,
        "rawDesc": raw_desc,
        "tags": tags,
        "ipLocation": n.get("ipLocation", ""),
        "publishTime": n.get("time"),
        "user": {
            "nickname": user.get("nickname", ""),
            "avatar": user.get("avatar", ""),
            "userId": user.get("userId", ""),
        },
        "stats": {
            "like": num(it.get("likedCount")),
            "collect": num(it.get("collectedCount")),
            "comment": num(it.get("commentCount")),
            "share": num(it.get("shareCount")),
        },
        "images": imgs,
    }


def download(url, out, referer="https://www.xiaohongshu.com/"):
    try:
        _, raw = get(url, referer=referer)
        if len(raw) < 1000:
            return False
        open(out, "wb").write(raw)
        return True
    except Exception as e:
        print("  下载失败", type(e).__name__, e)
        return False


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    text = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/poster_build/note_out"
    os.makedirs(outdir, exist_ok=True)

    try:
        _run(text, outdir)
    except ScrapeError as e:
        # CLI 场景把可读错误转成退出码；库调用方（serve.py）会拿到 ScrapeError 本身
        raise SystemExit("抓取失败：%s" % e)


def _run(text, outdir):
    url = pick_url(text)
    print("链接:", url)
    final, page = fetch_page(url)
    print("落地:", final)
    state = parse_state(page)
    ndm = state.get("note", {}).get("noteDetailMap", {})
    if not ndm:
        raise ScrapeError("链接里的笔记打不开（可能已失效、被删除，或需要登录）",
                          "请在 App 里重新「分享 → 复制链接」后重试。")
    nid, holder = next(iter(ndm.items()))
    if not holder.get("note"):
        raise ScrapeError("该笔记没有返回内容（可能已删除 / 仅粉丝可见）",
                          "换一条公开笔记的链接试试。")

    data = analyze(holder)
    data["url"] = final if "xiaohongshu.com" in final else url
    data["shareUrl"] = url

    # 下载封面（及第 2、3 张备用图）+ 头像
    for idx, key in ((0, "coverFile"), (1, "imgFile2"), (2, "imgFile3")):
        if len(data["images"]) <= idx:
            break
        p = os.path.join(outdir, "cover.jpg" if idx == 0 else "img%d.jpg" % (idx + 1))
        if download(data["images"][idx]["url"], p):
            data[key] = p
            print("  图%d ->" % (idx + 1), p, os.path.getsize(p) // 1024, "KB")
    if data["user"]["avatar"]:
        a = os.path.join(outdir, "avatar.jpg")
        if download(data["user"]["avatar"], a):
            data["avatarFile"] = a
            print("  头像 ->", a, os.path.getsize(a) // 1024, "KB")

    p = os.path.join(outdir, "note.json")
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("数据 ->", p)
    print(json.dumps({k: v for k, v in data.items()
                      if k not in ("images", "rawDesc")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
