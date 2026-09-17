# -*- coding: utf-8 -*-
"""
Top Post Sharing · 链接自动生成门户 本地服务
  GET  /                 -> 门户页 index.html
  GET  /api/ping         -> 健康检查（前端用它判断「服务是否已连接」）
  POST /api/fetch        -> {"url": "笔记链接"} -> 笔记结构化 JSON（含 base64 头像/封面）
  GET  /libs/<file>      -> 静态资源

设计要点：
  * 每个请求跑在独立线程（ThreadingHTTPServer），异常一律兜住并回 4xx JSON —— 服务不会因为
    一次抓取失败而静默挂掉（历史 bug：ScrapeError 曾是 SystemExit，会打穿 except Exception）。
  * 全量 CORS 头：即使门户页是以 file:// 直接打开的，也能访问 127.0.0.1:8731。
  * 仅监听 127.0.0.1，不对外网暴露。
仅依赖标准库。
"""
import json, os, sys, time, traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import urllib.parse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "..", "_build")
# 端口优先级：环境变量 PORT（Render/Heroku 注入）> TPS_PORT > 8731
# 监听地址：TPS_HOST=0.0.0.0 才对外（云端必须）
PORT = int(os.environ.get("PORT") or os.environ.get("TPS_PORT", "8731"))
HOST = os.environ.get("TPS_HOST", "127.0.0.1")
VERSION = "2.1"

sys.path.insert(0, HERE)
for _p in (os.path.join(HERE, "..", "_build"), HERE):
    if os.path.exists(os.path.join(_p, "fetch_note.py")):
        sys.path.insert(0, _p)
        break
from scrape import scrape  # noqa
from fetch_note import ScrapeError  # noqa

LOG_PATH = os.path.join(HERE, "server.log")


def _snapshot(url, data):
    """把一次成功的抓取落盘，方便事后复现排查（尤其是「为什么没出悬浮小图」这类问题）。

    只存元信息 + 用到的三张图，不存原始 HTML。失败不影响主流程。
    """
    try:
        import base64 as _b, re as _re
        root = os.path.join(HERE, "..", "输出", "缓存")
        root = os.path.abspath(root)
        nid = (data.get("noteId") or _re.sub(r"[^a-zA-Z0-9]", "", url)[-16:] or "note")
        d = os.path.join(root, str(nid))
        os.makedirs(d, exist_ok=True)
        meta = {k: v for k, v in data.items() if k not in ("avatar", "cover", "float")}
        meta["_url"] = url
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        for key, fn in (("cover", "cover.jpg"), ("float", "float.jpg"), ("avatar", "avatar.jpg")):
            v = data.get(key) or ""
            if v.startswith("data:image"):
                raw = _b.b64decode(v.split(",", 1)[1])
                with open(os.path.join(d, fn), "wb") as f:
                    f.write(raw)
    except Exception:
        pass


def log(*args):
    """日志：接受任意个参数（scrape.py 会以 log(msg, extra) 形式回调）"""
    parts = []
    for a in args:
        parts.append(a if isinstance(a, str) else repr(a))
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), " ".join(parts))
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    return line


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TopPostSharing/" + VERSION

    # ---------- 通用响应 ----------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # file:// 打开的门户页访问 127.0.0.1 属于 private network 请求
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fp, ctype):
        try:
            data = open(fp, "rb").read()
        except Exception:
            self._json(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    # ---------- 路由 ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/index.html"):
            fp = os.path.join(HERE, "index.html")
            if not os.path.isfile(fp):
                self._json(500, {"error": "index.html 不存在，请先运行 build_portal.py"})
                return
            self._file(fp, "text/html; charset=utf-8")
        elif p == "/api/ping":
            shared = HOST == "0.0.0.0"
            self._json(200, {
                "ok": True, "name": "TopPostSharing", "version": VERSION,
                "host": HOST, "port": PORT, "shared": shared,
                # 共享模式下的同事入口；非共享模式只给本机地址
                "lanUrl": ("http://%s:%d/" % (lan_ip(), PORT)) if shared else "",
                "localUrl": "http://127.0.0.1:%d/" % PORT,
            })
        elif p == "/favicon.ico":
            self.send_response(204)
            self._cors()
            self.end_headers()
        elif p.startswith("/libs/"):
            fp = os.path.normpath(os.path.join(BUILD, p.lstrip("/")))
            if fp.startswith(os.path.abspath(BUILD) + os.sep) and os.path.isfile(fp):
                ext = fp.rsplit(".", 1)[-1].lower()
                self._file(fp, "application/javascript" if ext == "js" else "application/octet-stream")
            else:
                self._json(404, {"error": "not found"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p != "/api/fetch":
            self._json(404, {"error": "not found"})
            return
        # 关键：连 BaseException 一起兜住，保证线程不会静默死亡（否则前端只看到「网络错误」）
        try:
            ln = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(ln) if ln else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
            url = (body.get("url") or "").strip()
            if not url:
                self._json(400, {"error": "链接为空", "hint": "请先粘贴小红书笔记链接。"})
                return
            t0 = time.time()
            log("req url=%s" % url)          # 记录原始链接，便于事后复现排查
            data = scrape(url, log=log, with_playbook=body.get("playbook", True))
            log("ok %.1fs  %s  %s" % (time.time() - t0, data.get("user", {}).get("nickname", ""),
                                      (data.get("title") or "")[:40]))
            log("  type=%s imageCount=%s float=%s" % (
                data.get("type"), data.get("imageCount"), "yes" if data.get("float") else "no"))
            _snapshot(url, data)
            self._json(200, data)
        except ScrapeError as e:
            log("scrape-error: %s" % e)
            self._json(422, {"error": str(e), "hint": getattr(e, "hint", "")})
        except Exception as e:
            log("error: %s: %s\n%s" % (type(e).__name__, e, traceback.format_exc()[-600:]))
            self._json(500, {"error": "抓取时发生意外错误：%s: %s" % (type(e).__name__, e),
                             "hint": "可稍后重试；持续失败请把链接发我排查（详细日志见 app/server.log）。"})
        except BaseException as e:                      # noqa: BLE001 最后一道保险
            log("fatal: %s: %s" % (type(e).__name__, e))
            try:
                self._json(500, {"error": "服务内部错误：%s" % type(e).__name__,
                                 "hint": "请查看 app/server.log。"})
            except Exception:
                pass

    def log_message(self, fmt, *args):
        pass                                            # 静音默认 stderr 噪声


def already_running():
    import socket
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex(("127.0.0.1", PORT)) == 0
    finally:
        s.close()


def lan_ip():
    """取本机在局域网里的 IP（用于团队共享模式）"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _redirect_to_log():
    """把 stdout/stderr 重定向到 LOG_PATH，配套守护进程用"""
    try:
        sys.stdout = open(LOG_PATH, "a", buffering=1, encoding="utf-8")
        sys.stderr = sys.stdout
    except Exception:
        pass


def run():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    log("started on %s:%d  (pid %d)" % (HOST, PORT, os.getpid()))
    print("TopPostSharing 门户已启动 -> http://127.0.0.1:%d/" % PORT)
    if HOST == "0.0.0.0":
        print("团队共享模式已开启，同事可访问 -> http://%s:%d/" % (lan_ip(), PORT))
    srv.serve_forever()


if __name__ == "__main__":
    if os.environ.get("TPS_DAEMON") == "1":
        # 守护模式（启动器用）：脱离当前会话 + 崩溃自动重启
        # 跨平台：Unix 用 os.fork() + setsid；Windows 没有 fork，popen 出子进程即可
        # （Windows 的窗口关闭就退出，但启动器是用 pythonw 唤起的，能撑住）
        if already_running():
            print("已在运行 -> http://127.0.0.1:%d/" % PORT)
            raise SystemExit(0)
        if os.name == "nt":
            # Windows：把自己再启动一次（TPS_CHILD=1 表示「我是真正的子进程」），父进程立刻退出
            env = os.environ.copy()
            env["TPS_CHILD"] = "1"
            env.pop("TPS_DAEMON", None)              # 关键：不要让子进程再走 daemon 分支
            log("windows daemon parent (pid %d) -> child launch" % os.getpid())
            subprocess.Popen(
                [sys.executable, os.path.abspath(__file__)],
                env=env,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                close_fds=True,
            )
            time.sleep(0.4)
            print("launched daemon (windows)")
            raise SystemExit(0)
        # Unix：fork 后父进程退出，子进程 setsid 脱离会话
        pid = os.fork()
        if pid > 0:
            print("launched daemon pid", pid)
            raise SystemExit(0)
        os.setsid()
        _redirect_to_log()
        log("daemon boot (pid %d)" % os.getpid())
        while True:
            try:
                run()
            except Exception as e:
                log("crash: %s: %s（2 秒后重启）" % (type(e).__name__, e))
                time.sleep(2)
    elif os.environ.get("TPS_CHILD") == "1":
        # Windows 守护的子进程：把 stdout/stderr 重定向到日志，循环跑
        _redirect_to_log()
        log("windows daemon child (pid %d)" % os.getpid())
        while True:
            try:
                run()
            except Exception as e:
                log("crash: %s: %s（2 秒后重启）" % (type(e).__name__, e))
                time.sleep(2)
    else:
        # 前台模式（调试用）：Ctrl-C 停止
        if already_running():
            print("端口 %d 已被占用，服务应该已经在运行 -> http://127.0.0.1:%d/" % (PORT, PORT))
            raise SystemExit(0)
        run()
