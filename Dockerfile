# Top Post Sharing · 云端部署（任何 VPS / Render / Railway 容器平台都适用）
#
# 选 alpine + python 3.12 镜像（约 50MB）。镜像里只放运行时必需文件。
# 运行期纯标准库，无需 pip install。
FROM python:3.12-alpine

# 容器内服务以 0.0.0.0 监听（云端必须如此）
# 注意：PORT 由平台注入（Render/Railway/Heroku 都用这个名），不要在这里固定
ENV TPS_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

# 把运行时需要的服务和页面打进去
WORKDIR /app
COPY app/serve.py        ./serve.py
COPY app/scrape.py       ./scrape.py
COPY app/index.html      ./index.html
COPY _build/fetch_note.py ./fetch_note.py

EXPOSE 10000

# 健康检查：前端用它判断「服务已连接」
HEALTHCHECK --interval=20s --timeout=4s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
p=int(__import__('os').environ.get('PORT','10000')); \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%d/api/ping'%p, timeout=3).status==200 else 1)"

CMD ["python", "serve.py"]
