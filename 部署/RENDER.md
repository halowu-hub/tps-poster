# 部署到 Render（永久免费固定域名）

## 一句话
把整个项目推到 GitHub，Render 自动构建并分配 `https://tps-poster.onrender.com/` 永久免费域名。**你电脑不需要开机**，任何浏览器打开这个链接就能用。

## 你需要准备的
- GitHub 账号（注册 1 分钟）
- Render 账号（用 GitHub 登录，**不要绑卡**——免费档不要求）

## 部署步骤（约 5 分钟）

### 1) 推代码到 GitHub

打开终端，到项目根目录：

```bash
cd TopPostSharing
git init
git add Dockerfile render.yaml app/ serve.py scrape.py index.html _build/fetch_note.py 使用说明.md
git commit -m "Top Post Sharing · 部署就绪"

# 去 github.com/new 建一个空仓库（名字随意，比如 tps-poster）
# 然后照页面提示 push 上去：
git remote add origin git@github.com:<你的用户名>/tps-poster.git
git branch -M main
git push -u origin main
```

> 我故意排除了 `输出/` `分享版/` `__pycache__/` `.workbuddy/` 等本地文件，仓库干净。

### 2) 在 Render 创建服务

1. 去 https://dashboard.render.com/connect ，点 GitHub 授权
2. 选 `New +` → `Blueprint`
3. 选你刚推上去的 `tps-poster` 仓库
4. Render 自动识别 `render.yaml`，点 `Apply`
5. 等约 2 分钟，看到状态 `Live` 即可

### 3) 拿你的永久链接

服务上线后，Render 会给你一个默认域名：
**`https://tps-poster.onrender.com/`**（可改成你想要的名字）

把这个链接发到群里，谁都能打开用。**这个链接永久有效**，不会因为你不续费或电脑关机而消失。

## 免费档限制

| 项 | 值 | 影响 |
|---|---|---|
| 域名 | `*.onrender.com` 永久 | ✅ 够用 |
| 运行 | 24/7 不停 | ✅ 比本机版省心 |
| 休眠 | 15 分钟无访问会休眠，下次访问自动唤醒（30 秒左右） | 可接受 |
| CPU | 750 小时/月 | 完全够用 |
| 出站 | **无限制**（已验证可以访问小红书） | ✅ 抓取类工具能用 |
| 数据 | 容器实例**重启会丢**（无持久化） | ⚠️ 见下 |

## ⚠️ 唯一要注意的：抓取快照不持久

之前我加的 `_snapshot` 落盘到 `输出/缓存/` 目录——Render 免费档**没有持久磁盘**，**实例重启后快照就丢**。
两种解法选一个：

**A 接受现状**：调试、临时分析够用，反正只为了"事后能复现"。生产场景对每个用户不痛不痒。

**B 改用 Render 持久化（推荐）**：免费档不支持 Persistent Disk，要升级到 Starter $7/月才有。
或者用 Render 自带的免费 PostgreSQL，10MB 够存几百条快照的 meta（不带图）。

默认走 A。你要 B 我再动。

## 升级方案

| 平台 | 限制 | 适合场景 |
|---|---|---|
| **Render 免费** | 15 分钟休眠、磁盘非持久 | 调试 + 小团队 + 偶尔使用 |
| **Render Starter ($7/月)** | 持久化磁盘、永不休眠 | 真正生产 |
| **Railway 免费** | 每月 $5 额度 | 同 Render，但休眠策略不同 |
| **VPS 自建 (~$10/月)** | 自己运维 | 大流量、需要控 IP |

## 故障排查

**Q：服务起来了但 502/Application Error**
看 Render Dashboard → Logs。最常见是 Dockerfile 路径写错。检查 `app/index.html` 是否被拷到 `/app/index.html`。

**Q：服务起得来但 `/api/fetch` 报 422（链接打不开）**
不是代码问题，是 Render 数据中心 IP 被小红书风控了。免费档不能换 IP，要么升级 Starter 用固定 IP，要么自建 VPS。
**这种情况下本机版（Mac 启动器）反而更稳**——用你家的宽带 IP，小红书不风控个人宽带。

**Q：QR 码还是指向 127.0.0.1**
如果想让海报二维码指向 Render 域名而非原笔记链接，需要在 `scrape.py` 里加一行：`d["qrText"] = d.get("url") or f"https://{os.environ.get('RENDER_EXTERNAL_URL','')}/{d.get('noteId','')}"`。**暂不动**，等你说要。
