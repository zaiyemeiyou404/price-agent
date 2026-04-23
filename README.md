# Price Agent - 纯爬虫比价系统

当前版本仅使用 Playwright 爬虫，不依赖任何第三方商品 API（不需要淘宝客、京东联盟、折淘客等密钥）。

## 🚀 快速开始

### 方式一：一键启动

```bash
# Windows 双击运行
start.bat

# 或命令行运行
python -m uvicorn app.main:app --reload
```

然后打开 `index.html` 文件即可使用。

### 方式二：手动启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装浏览器
playwright install chromium

# 3. 启动服务
uvicorn app.main:app --reload

# 4. 打开前端页面
# 直接双击打开 index.html 文件
# 或访问 http://localhost:8000/docs 查看 API 文档
```

## 接口联调

```bash
# 健康检查
curl http://localhost:8000/health

# 获取当前可用平台和模式
curl http://localhost:8000/api/v1/capabilities

# 发起比价（当前默认仅 taobao）
curl -X POST http://localhost:8000/api/v1/compare \
  -H "Content-Type: application/json" \
  -d '{"query":"iPhone 15","type":"shopping","platforms":["taobao"]}'
```

## Postman 联调

- Collection: `postman/price-agent.postman_collection.json`
- Environment: `postman/price-agent.local.postman_environment.json`
- 导入后先执行 `Health`、`Capabilities`，再执行 `Compare - Shopping (Taobao)`。

## 调试爬虫

```bash
# 测试单个爬虫
python scripts/debug/debug_crawler.py taobao "iPhone 15"
python scripts/debug/debug_crawler.py jd "华为手机"
python scripts/debug/debug_crawler.py pdd "耳机"
python scripts/debug/debug_crawler.py meituan "肯德基套餐" --lat 39.9042 --lng 116.4074

# 非无头模式（可看到浏览器操作）
python scripts/debug/debug_crawler.py taobao "iPhone 15" --no-headless

# 截图模式（调试页面结构）
python scripts/debug/debug_crawler.py taobao "iPhone 15" --screenshot
```

## 说明

- 代码路径中的 `api/` 目录是 FastAPI 路由层，不是第三方商品 API。
- 当前配置已强制 `api_mode=false`，即使 `.env` 中有同名项也不会启用外部 API。
