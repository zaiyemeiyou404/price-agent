# Price Agent

一个基于 FastAPI + Playwright 的本地比价工具。

当前版本以爬虫模式为主，前端输入关键词后，后端会调用淘宝等平台抓取结果并返回比价数据。项目内还带了登录、调试、测试脚本，方便处理验证码、登录态和页面结构变化。

## 功能概览

- 提供 HTTP API：`/api/v1/compare`
- 提供本地前端页面：`index.html`
- 支持平台能力查询：`/api/v1/platforms`、`/api/v1/capabilities`
- 支持淘宝登录态持久化
- 支持调试脚本、登录脚本、Postman 集合

## 目录结构

```text
price-agent/
├─ app/                    # 主服务代码
│  ├─ api/                 # FastAPI 路由
│  ├─ agent/               # Agent / 分析逻辑
│  ├─ models/              # Pydantic 数据模型
│  ├─ services/            # 比价服务、缓存服务
│  └─ tools/               # 各平台抓取工具
├─ scripts/
│  ├─ debug/               # 调试脚本
│  ├─ login/               # 登录脚本
│  └─ tests/               # 手工测试脚本
├─ postman/                # Postman collection / environment
├─ cookies/                # 登录态、storage_state
├─ debug_output/           # 调试产物
├─ index.html              # 本地前端页面
├─ start.bat               # 生产式本地启动
└─ run.bat                 # 带 reload 的开发启动
```

## 环境要求

- Windows
- Python 3.10+
- Chromium（由 Playwright 安装）

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/zaiyemeiyou404/price-agent.git
cd price-agent
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. 配置环境变量

```bash
copy .env.example .env
```

默认情况下可以先不改 `.env`。

## 启动方式

### 方式一：推荐

```bash
start.bat
```

适合日常使用。不会因为运行过程中写入 `cookies/`、`debug_output/` 而触发热重载。

### 方式二：开发模式

```bash
run.bat
```

适合调试代码。当前已经排除了 `cookies/`、`debug_output/` 等目录，避免运行时文件改动导致服务误重启。

### 方式三：直接命令启动

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动成功后访问：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

## 前端使用

1. 先启动后端服务。
2. 直接打开项目根目录的 `index.html`。
3. 输入商品关键词，比如 `iPhone 15`。
4. 选择平台后点击“开始比价”。

## API 使用

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 获取平台列表

```bash
curl http://127.0.0.1:8000/api/v1/platforms
```

### 获取前端能力元数据

```bash
curl http://127.0.0.1:8000/api/v1/capabilities
```

### 发起比价

```bash
curl -X POST http://127.0.0.1:8000/api/v1/compare ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"iPhone 15\",\"type\":\"shopping\",\"platforms\":[\"taobao\"]}"
```

请求体字段：

- `query`: 搜索关键词
- `type`: `shopping` 或 `food`
- `platforms`: 可选，指定平台列表
- `location`: 可选，外卖场景使用

## 淘宝登录态使用说明

淘宝抓取经常会遇到登录和验证码，所以项目提供了单独的登录脚本。

### 刷新淘宝登录态

```bash
python scripts/login/login.py taobao qr
```

执行后会弹出浏览器，使用手机淘宝扫码登录。登录成功后会把状态保存到：

- `cookies/taobao_cookies.json`
- `cookies/taobao_state.json`

注意：

- 现在登录脚本和主程序已经统一使用项目根目录的 `cookies/`
- 不需要再手动从 `scripts/login/cookies/` 复制文件
- 比价过程中如果弹出验证码页，不要手动关闭页面，先让程序继续处理

## 调试脚本

### 淘宝调试

```bash
python scripts/debug/debug_crawler.py taobao "iPhone 15"
```

### 京东调试

```bash
python scripts/debug/debug_crawler.py jd "华为手机"
```

### 仅测试淘宝登录

```bash
python scripts/login/login.py taobao qr
```

### 手工运行测试脚本

```bash
python scripts/tests/test_crawler.py
python scripts/tests/test_search.py
python scripts/tests/test_playwright.py
```

## Postman

仓库自带 Postman 文件：

- `postman/price-agent.postman_collection.json`
- `postman/price-agent.local.postman_environment.json`

导入后建议按下面顺序测试：

1. `Health`
2. `Capabilities`
3. `Compare - Shopping (Taobao)`

## 常见问题

### 1. 服务运行中突然退出

优先使用 `start.bat`。

如果使用 `run.bat`，当前版本已经排除了 `cookies/` 和 `debug_output/`，避免运行时写文件触发 `uvicorn --reload` 重启。

### 2. 淘宝弹登录框或验证码

先执行：

```bash
python scripts/login/login.py taobao qr
```

拿到新的登录态后再发起比价。

### 3. 验证码处理后页面被关闭

当前淘宝工具已经增加了恢复逻辑：验证码通过后，如果原搜索页被关闭，会尝试切换到存活页面，或者重开搜索页继续抓取。

### 4. Redis 超时警告

当前缓存服务即使 Redis 不可用，也会退回到内存缓存。出现超时警告不一定会影响本地调试。

## 不要提交这些文件

以下内容已经在 `.gitignore` 中忽略：

- `.env`
- `cookies/`
- `debug_output/`
- `__pycache__/`
- 调试截图和导出的 HTML

## 当前状态说明

当前仓库仍以本地调试为主，淘宝链路经过了几轮修正：

- 统一了登录脚本和主程序的 `cookies` 目录
- 修复了 `run.bat` 热重载误伤运行时文件的问题
- 补了淘宝验证码后的搜索页恢复逻辑

如果你准备继续扩平台，建议优先把淘宝链路跑稳，再扩京东、拼多多和外卖平台。
