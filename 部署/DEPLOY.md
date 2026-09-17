# 部署到云端（任何能跑 Docker 的 VPS 都可以）

## 你需要准备的
- 一台 VPS（推荐 1 核 1GB，几十块/月，**必须是境外 IP**——国内 IP 抓小红书会撞风控）
  - 便宜选项：AWS Lightsail / DigitalOcean / Vultr / Bandwagon
- 一个域名（解析到 VPS 的公网 IP）
- 在 VPS 上装好 Docker（一行 `curl -fsSL https://get.docker.com | sh`）

## 部署（3 步，约 5 分钟）

### 1) 在你 Mac 上构建并打包镜像
```bash
cd TopPostSharing

# 构建镜像（约 50MB）
docker build -t top-post-sharing:1.0 .

# 导出成文件，方便传到 VPS（也可以走 docker hub 拉，省一步）
docker save top-post-sharing:1.0 | gzip > tps-1.0.tar.gz
scp tps-1.0.tar.gz user@your-vps-ip:~/
```

### 2) 在 VPS 上加载并跑起来
```bash
ssh user@your-vps-ip

# 加载镜像
docker load < tps-1.0.tar.gz

# 起服务（-p 8731:8731 把容器端口暴露给宿主；--restart always 崩溃自动重启）
docker run -d \
  --name top-post-sharing \
  --restart always \
  -p 8731:8731 \
  top-post-sharing:1.0

# 检查状态
docker ps
docker logs -f top-post-sharing
```

### 3) 配域名 + HTTPS（强烈建议）
- 域名解析到 VPS IP
- 用 certbot 申请证书：
  ```bash
  sudo apt install -y certbot
  sudo certbot certonly --standalone -d tps.example.com   # 改成你的真实域名
  ```
- 把 `部署/nginx.conf.example` 复制到 `/etc/nginx/sites-available/tps`，改两处域名（占位 `tps.example.com` → 你的域名），然后：
  ```bash
  sudo ln -s /etc/nginx/sites-available/tps /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx
  ```

之后任何人浏览器打开 `https://tps.example.com/` 就能用（**记得把这里替换成你的真实域名**）。

## 升级
```bash
# 在 Mac 上
docker build -t top-post-sharing:1.1 .
docker save top-post-sharing:1.1 | gzip > tps-1.1.tar.gz
scp tps-1.1.tar.gz user@your-vps-ip:~/

# 在 VPS 上
ssh user@your-vps-ip
docker stop top-post-sharing && docker rm top-post-sharing
docker load < tps-1.1.tar.gz
docker run -d --name top-post-sharing --restart always -p 8731:8731 top-post-sharing:1.1
```

## 注意事项
1. **IP 风控**：小红书对频繁抓取的 IP 会限速。云端若被封，可加 VPS 出口代理、或换 IP、或降低抓取频率。
2. **抓取频率**：单实例够 5–10 人同时用。100+ 人请加 nginx 限流 + 多实例 + 共享 Redis 缓存。
3. **持久化日志**：`docker logs` 默认不留盘。要保留抓取日志，run 时加 `-v /var/log/tps:/app`。
4. **HTTPS 必须**：浏览器对 private network 跨源请求越来越严，HTTPS 是最稳的部署形态。
