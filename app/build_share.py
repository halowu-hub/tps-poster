# -*- coding: utf-8 -*-
"""
打包「分享版」——给同事用的零安装包。

产物（Mac + Windows 双系统）：
  分享版/TopPostSharing-分享版-Mac/
  分享版/TopPostSharing-分享版-Windows/
  分享版/TopPostSharing-分享版-Mac.zip
  分享版/TopPostSharing-分享版-Windows.zip

每个分享版只带运行必需文件（纯 Python 标准库，无需 pip install）：
  index.html     门户页（库已内联，离线也能渲染）
  serve.py       本地服务（已支持跨平台守护进程）
  scrape.py      抓取
  fetch_note.py  抓取底层
  ① 双击我启动.command    (Mac 启动器)
  ① 双击我启动.bat       (Windows 启动器；首启会自动选 python）
  离线备用·无需服务.html   (没装 Python 时的降级方案)
  使用说明（同事版）.md

用法：python3 build_share.py
"""
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # TopPostSharing/
BUILD = os.path.join(ROOT, "_build")
DIST_ROOT = os.path.join(ROOT, "分享版")

PKG_MAC = os.path.join(DIST_ROOT, "TopPostSharing-分享版-Mac")
PKG_WIN = os.path.join(DIST_ROOT, "TopPostSharing-分享版-Windows")
ZIP_MAC = os.path.join(DIST_ROOT, "TopPostSharing-分享版-Mac.zip")
ZIP_WIN = os.path.join(DIST_ROOT, "TopPostSharing-分享版-Windows.zip")

LAUNCHER_MAC = r'''#!/bin/bash
# Top Post Sharing · 每周海报生成器 —— 一键启动（双击即可，macOS 版）
cd "$(dirname "$0")" || exit 1
printf '\033]0;Top Post Sharing\033\\'

echo "=============================================="
echo "  Top Post Sharing · 每周海报生成器 (macOS)"
echo "=============================================="
echo

# ---- 1) 找一个可用的 python3（macOS 自带 / Homebrew 都行）----
PY=""
for c in /usr/bin/python3 "$(command -v python3 2>/dev/null)" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  [ -n "$c" ] || continue
  [ -x "$c" ] || continue
  if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 7) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done

if [ -z "$PY" ]; then
  echo "[X] 没找到可用的 Python 3。"
  echo
  echo "  这台 Mac 还没装「命令行开发者工具」。装上就能用全自动模式："
  echo "    打开「终端」→ 粘贴这行 → 回车，等它装完："
  echo "        xcode-select --install"
  echo
  echo "  不想装也没关系，现在给你打开「离线版」——"
  echo "  离线版同样能出海报，只是内容要自己填（不能自动抓链接）。"
  echo
  read -n 1 -s -r -p "  按任意键打开离线版…"
  echo
  open "离线备用·无需服务.html" 2>/dev/null
  exit 1
fi

echo "[OK] Python: $PY"
echo "  $("$PY" -V 2>&1)"

# ---- 2) 起服务（后台守护，关掉本窗口也能继续用）----
if nc -z 127.0.0.1 8731 2>/dev/null; then
  echo "[OK] 服务已在运行"
else
  echo "[..] 正在启动本地服务…"
  TPS_DAEMON=1 "$PY" serve.py >/dev/null 2>&1
  for i in $(seq 1 50); do
    nc -z 127.0.0.1 8731 2>/dev/null && break
    sleep 0.2
  done
fi

echo
if nc -z 127.0.0.1 8731 2>/dev/null; then
  echo "[OK] 就绪 → http://127.0.0.1:8731/"
  echo
  echo "  用法：把小红书笔记链接粘进去 → 回车 → 自动出图（内容可改）。"
  echo "  这个窗口可以直接关掉，服务在后台继续跑。"
  echo
  open "http://127.0.0.1:8731/"
else
  echo "[X] 服务启动失败。最近日志："
  echo "----------------------------------------------"
  tail -20 server.log 2>/dev/null
  echo "----------------------------------------------"
  echo "  可以把这些日志截图发给发起人排查。"
  echo
  read -n 1 -s -r -p "  按任意键退出…"
fi
'''

LAUNCHER_WIN = r'''@echo off
chcp 65001 >nul
title Top Post Sharing · 每周海报生成器
cd /d "%~dp0"

echo ==============================================
echo   Top Post Sharing · 每周海报生成器 (Windows)
echo ==============================================
echo.

REM ---- 1) 找一个可用的 python（py launcher / 系统 python / 常见安装位置都试）----
set "PY="
for %%P in (py -3 python) do (
  call :try_python "%%P"
  if not errorlevel 1 goto :py_ok
)
for %%F in (C:\Python311\python.exe C:\Python310\python.exe C:\Python312\python.exe) do (
  if exist "%%F" (
    set "PY=%%F"
    goto :py_ok
  )
)
for %%F in ("%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe") do (
  if exist %%F (
    set "PY=%%F"
    goto :py_ok
  )
)
echo [X] 没找到可用的 Python 3。
echo.
echo   1) 去 https://www.python.org/downloads/ 下载安装（务必勾选「Add Python to PATH」）
echo   2) 或者用 winget 一行装好：winget install Python.Python.3.11
echo.
echo   不想装 Python？现在给你打开「离线版」—— 同样能出海报，只是内容要自己填。
echo.
pause
start "" "离线备用·无需服务.html"
exit /b 1

:try_python
  %1 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,7) else 1)" 1>nul 2>nul
  if errorlevel 1 exit /b 1
  set "PY=%1"
  exit /b 0

:py_ok
echo [OK] Python: %PY%
%PY% -V 2>nul
echo.

REM ---- 2) 起服务（如果已在跑就跳过）----
set "PORT=8731"
netstat -ano | findstr /R ":%PORT%.*LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  echo [OK] 服务已在运行
  goto :open_browser
)
echo [..] 正在启动本地服务…

REM 用 PowerShell 在后台启动，最小化窗口（PowerShell 几乎所有 Win10/11 都有）
set "TPS_DAEMON=1"
powershell -NoProfile -WindowStyle Hidden -Command ^
  "$env:TPS_DAEMON='1'; Start-Process -FilePath '%PY%' -ArgumentList 'serve.py' -WorkingDirectory '%CD%' -WindowStyle Hidden | Out-Null"

REM 等端口起来
set /a count=0
:wait_port
  set /a count+=1
  if !count! GTR 50 goto :open_browser
  netstat -ano | findstr /R ":%PORT%.*LISTENING" >nul 2>&1
  if %ERRORLEVEL% EQU 0 goto :open_browser
  ping -n 1 127.0.0.1 >nul
  goto :wait_port

:open_browser
echo.
echo [OK] 就绪 → http://127.0.0.1:%PORT%/
echo.
echo   用法：把小红书笔记链接粘进去 → 回车 → 自动出图（内容可改）。
echo   这个窗口可以直接关掉，服务在后台继续跑。
echo.
start "" "http://127.0.0.1:%PORT%/"
exit /b 0
'''

README = r'''# Top Post Sharing · 每周海报生成器（同事版）

一句话：**把小红书笔记链接粘进去，自动生成一张 1080px 的分享海报。**

支持 macOS 和 Windows，开箱即用。

---

## 怎么用（3 步）

1. **双击启动器**
   - macOS：双击 `① 双击我启动.command`
   - Windows：双击 `① 双击我启动.bat`
   - 会自动启动本地服务并打开浏览器（页面地址 `http://127.0.0.1:8731/`）
   - 浏览器打开后，**启动器窗口可以直接关掉**，服务在后台继续跑
2. 在小红书 App 里打开要分享的笔记 → **分享 → 复制链接** → 粘到页面顶部的输入框
3. 生成后：左边改文字、右边实时看效果 → 点右上角 **下载 PNG (2x)** 得到成品图

想关掉服务：
- macOS：「活动监视器」里结束 `Python` 进程
- Windows：任务管理器里结束 `python.exe` 进程

---

## 会自动帮你填好的

| 项目 | 说明 |
|---|---|
| 账号名 / 头像 | 笔记作者，自动裁圆 |
| 三个数据 | 点赞 / 收藏 / 分享 |
| 手机屏封面 | 笔记封面，按手机屏比例顶对齐裁切 |
| 悬浮小图 | 笔记的**第 2 张图**（图文笔记才有；视频/单图会自动跳过） |
| 二维码 | 指向这条笔记，扫码直达 |
| 分析文案 | 封面 / 文案 / 关键词 / 可复用打法（**可以直接改**） |

分析文案是自动起草的「有据可依的草稿」，数字和标签都来自真实抓取，
但**判断请以你自己为准**——哪里不对直接在页面上改。

---

## 常见问题

**Q：提示「这条链接缺少访问凭证（xsec_token）」**
说明链接是从网页版复制的。请**在手机 App 里**点「分享 → 复制链接」，用带 `xsec_token` 的完整链接。

**Q：提示「小红书返回 404」**
链接被截断了，或这条笔记已删除、被设为仅粉丝可见。换一条公开笔记再试。

**Q：macOS 双击 .command 没反应 / 提示「无法打开，因为它来自身份不明的开发者」**
右键点这个文件 → **打开** → 在弹窗里再点「打开」。
如果还是不行，打开「终端」，输入 `chmod +x `（注意末尾有个空格），
把 `① 双击我启动.command` 拖进终端窗口，回车，然后双击它。

**Q：Windows 双击 .bat 闪退 / 提示没找到 Python**
去 https://www.python.org/downloads/ 下载 Python 3.10 或更高版本，
**安装时务必勾选「Add Python to PATH」**。装完再双击启动器。

**Q：不想要 Python，能不能直接用？**
可以：双击 `离线备用·无需服务.html`。它是完整功能的单文件工具（改字、加行、导出 PNG 都有），
只是不会自动抓链接。

**Q：能不能多人共用、只有一个人装？**
可以。让装了的人用团队共享模式启动，其他人浏览器打开就行：

- macOS：在「终端」cd 到这个文件夹，运行 `TPS_HOST=0.0.0.0 python3 serve.py`
- Windows：在该文件夹按住 Shift 右键 → 在此处打开 PowerShell，运行 `$env:TPS_HOST="0.0.0.0"; python serve.py`

然后同事访问 `http://<你的局域网IP>:8731/`。适合办公室同一 WiFi 下用。
**注意：Windows 首次启动会弹防火墙窗口，必须点「允许访问」。**

---

## 隐私

服务只跑在**本机 127.0.0.1**（团队共享模式除外），不上传任何数据到第三方服务器，
生成的图也只保存在你自己电脑上。
'''


FILES = [
    ("index.html", "index.html"),
    ("serve.py", "serve.py"),
    ("scrape.py", "scrape.py"),
]


def _collect_files():
    """收集分享版里要打的全部文件，返回 [(src_path, pkg_name), ...]"""
    files = []
    for src_name, dst_name in FILES:
        src = os.path.join(HERE, src_name)
        if not os.path.isfile(src):
            raise SystemExit("缺少源文件：%s" % src)
        files.append((src, dst_name))
    # fetch_note.py
    fn = os.path.join(BUILD, "fetch_note.py")
    if not os.path.isfile(fn):
        raise SystemExit("缺少源文件：%s" % fn)
    files.append((fn, "fetch_note.py"))
    # 离线兜底
    offline = os.path.join(ROOT, "每周海报生成器.html")
    if not os.path.isfile(offline):
        raise SystemExit("缺少源文件：%s" % offline)
    files.append((offline, "离线备用·无需服务.html"))
    return files


def _build_pkg(pkg_dir, zip_path, arch_name, launcher_name, launcher_text, launcher_mode):
    """打一个包：拷贝文件 + 写启动器 + 写说明 + 压 zip"""
    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)
    os.makedirs(pkg_dir, exist_ok=True)

    for src, dst in _collect_files():
        shutil.copy2(src, os.path.join(pkg_dir, dst))

    lp = os.path.join(pkg_dir, launcher_name)
    with open(lp, "w", encoding="utf-8", newline="\n") as f:
        f.write(launcher_text)
    if launcher_mode is not None:
        os.chmod(lp, launcher_mode)

    with open(os.path.join(pkg_dir, "使用说明（同事版）.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(README)

    # 打包
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(pkg_dir)):
            full = os.path.join(pkg_dir, name)
            z.write(full, arch_name + "/" + name)

    return pkg_dir, zip_path


def main():
    os.makedirs(DIST_ROOT, exist_ok=True)
    print("===  macOS 版  ===")
    pkg, zp = _build_pkg(PKG_MAC, ZIP_MAC, "TopPostSharing-分享版-Mac",
                         "① 双击我启动.command", LAUNCHER_MAC, 0o755)
    for n in sorted(os.listdir(pkg)):
        print("   %-30s %7.0f KB" % (n, os.path.getsize(os.path.join(pkg, n)) / 1024))
    print("   -> %s  (%.0f KB)" % (zp, os.path.getsize(zp) / 1024))

    print()
    print("===  Windows 版  ===")
    pkg, zp = _build_pkg(PKG_WIN, ZIP_WIN, "TopPostSharing-分享版-Windows",
                         "① 双击我启动.bat", LAUNCHER_WIN, None)
    for n in sorted(os.listdir(pkg)):
        print("   %-30s %7.0f KB" % (n, os.path.getsize(os.path.join(pkg, n)) / 1024))
    print("   -> %s  (%.0f KB)" % (zp, os.path.getsize(zp) / 1024))


if __name__ == "__main__":
    main()
