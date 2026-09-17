#!/bin/bash
# 双击本文件：启动本地门户，并自动打开浏览器到 http://127.0.0.1:8731/
# 服务只监听本机 127.0.0.1，不上公网；这个终端窗口可以直接关掉，服务会继续在后台运行。
# 想停掉服务：终端执行  pkill -f "app/serve.py"

cd "$(dirname "$0")" || exit 1
PORT=8731
URL="http://127.0.0.1:$PORT/"

# 1) 选一个能用的 Python（优先独立运行环境，自带 Pillow，便于需要时重建页面）
PY="/Users/wutingxiang/.workbuddy/binaries/python/envs/default/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
if [ -z "$PY" ]; then
  echo "✗ 没找到 python3，请先安装（或用 WorkBuddy 环境里的 Python）"
  read -r -p "按回车关闭…" _; exit 1
fi

# 2) 门户页不存在就构建一次
if [ ! -f index.html ]; then
  echo "· 首次运行，正在构建页面…"
  "$PY" build_portal.py || { echo "✗ 构建失败"; read -r -p "按回车关闭…" _; exit 1; }
fi

# 3) 服务没在跑就以后台守护方式拉起
if ! nc -z 127.0.0.1 $PORT 2>/dev/null; then
  echo "· 正在启动本地抓取服务…"
  TPS_DAEMON=1 "$PY" serve.py
  for _ in $(seq 1 30); do
    nc -z 127.0.0.1 $PORT 2>/dev/null && break
    sleep 0.2
  done
fi

if nc -z 127.0.0.1 $PORT 2>/dev/null; then
  echo "✓ 服务已就绪：$URL"
  open "$URL" 2>/dev/null || echo "  请手动在浏览器打开：$URL"
  echo
  echo "用法：在页面顶部粘贴小红书笔记链接 → 自动生成整张海报 → 可直接导出 PNG。"
  echo "这个窗口可以关闭，服务会在后台继续运行。"
else
  echo "✗ 服务启动失败，请查看 server.log"
  tail -n 12 server.log 2>/dev/null
fi
sleep 2
