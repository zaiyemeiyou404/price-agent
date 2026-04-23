"""
统一爬虫基类

提供:
- 浏览器单例管理
- 完整的反爬指纹伪装
- 智能选择器等待
- 重试机制
- Cookie持久化
- 验证码检测
"""
import asyncio
import json
import random
import hashlib
from pathlib import Path
from typing import Optional, List, Any, Callable
from functools import wraps
from loguru import logger

from playwright.async_api import async_playwright, Browser, Page, BrowserContext


def retry_with_backoff(max_attempts: int = 3, backoff: List[float] = None):
    """
    指数退避重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        backoff: 退避时间列表 (秒)
    """
    if backoff is None:
        backoff = [1, 2, 4]
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff[min(attempt, len(backoff) - 1)]
                        logger.warning(f"第 {attempt + 1} 次尝试失败: {e}, {wait_time}秒后重试")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"重试 {max_attempts} 次后仍然失败: {e}")
            raise last_error
        return wrapper
    return decorator


class BrowserManager:
    """
    浏览器单例管理器
    
    复用浏览器实例，减少资源消耗
    """
    _instance: Optional['BrowserManager'] = None
    _browser: Optional[Browser] = None
    _playwright = None
    _lock = asyncio.Lock()
    _ref_count = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_browser(self, proxy: str = None, headless: bool = True) -> Browser:
        """获取浏览器实例（单例）"""
        async with self._lock:
            if self._browser is None:
                self._playwright = await async_playwright().start()
                
                launch_options = {
                    "headless": headless,
                    "args": [
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                }
                
                if proxy and proxy.strip():
                    if proxy.startswith(('http://', 'https://', 'socks5://')):
                        launch_options["proxy"] = {"server": proxy}
                        logger.info(f"使用代理: {proxy}")
                
                self._browser = await self._playwright.chromium.launch(**launch_options)
                logger.info("浏览器实例已创建")
            
            self._ref_count += 1
            return self._browser
    
    async def release(self):
        """释放浏览器引用"""
        async with self._lock:
            self._ref_count -= 1
            if self._ref_count <= 0 and self._browser:
                await self._browser.close()
                self._browser = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                logger.info("浏览器实例已关闭")
    
    async def close_all(self):
        """强制关闭浏览器"""
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._ref_count = 0
            logger.info("浏览器已强制关闭")


class BaseCrawler:
    """
    爬虫基类
    
    提供完整的反爬措施和通用功能
    """
    
    # 平台名称（子类覆盖）
    platform_name: str = "base"
    
    # Cookie存储目录
    COOKIE_DIR = Path(__file__).parent.parent.parent / "cookies"
    
    # 用户代理列表
    USER_AGENTS = [
        # Chrome Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Chrome Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]
    
    # 移动端UA
    MOBILE_USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    ]
    
    def __init__(
        self,
        proxy: str = None,
        headless: bool = True,
        timeout: int = 30000,
        use_mobile: bool = False,
    ):
        self.proxy = proxy
        self.headless = headless
        self.timeout = timeout
        self.use_mobile = use_mobile
        self._browser_manager = BrowserManager()
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # 确保Cookie目录存在
        self.COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _get_random_ua(self) -> str:
        """获取随机UA"""
        ua_list = self.MOBILE_USER_AGENTS if self.use_mobile else self.USER_AGENTS
        return random.choice(ua_list)
    
    async def _create_context(self, browser: Browser) -> BrowserContext:
        """创建带完整指纹伪装的浏览器上下文"""
        context_options = {
            "viewport": {"width": 375, "height": 667} if self.use_mobile else {"width": 1920, "height": 1080},
            "user_agent": self._get_random_ua(),
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }

        # 优先复用完整会话状态（cookies + localStorage 等）
        state_file = self.COOKIE_DIR / f"{self.platform_name}_state.json"
        if state_file.exists():
            context_options["storage_state"] = str(state_file)
            logger.info(f"加载 storage_state: {state_file}")
        
        context = await browser.new_context(**context_options)
        
        # 注入完整的反检测脚本
        await context.add_init_script("""
            // 1. 覆盖 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 2. 覆盖 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ];
                    plugins.length = 3;
                    return plugins;
                }
            });
            
            // 3. 覆盖 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
            
            // 4. 覆盖 platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // 5. 覆盖 hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            // 6. 覆盖 deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
            
            // 7. 覆盖 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // 8. 添加 chrome 对象
            window.chrome = {
                app: {
                    isInstalled: false,
                    InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
                    RunningState: { CannotRun: 'cannot_run', ReadyToRun: 'ready_to_run', Running: 'running' }
                },
                runtime: {
                    OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
                    OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
                    PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
                    PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
                    PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
                    RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
                    connect: function() { return { onDisconnect: { addListener: function() {} }, onMessage: { addListener: function() {} }, postMessage: function() {} }; },
                    sendMessage: function() {}
                },
                csi: function() {},
                loadTimes: function() {},
                webstore: { onInstallStageChanged: { addListener: function() {} }, onInstallProgress: { addListener: function() {} } }
            };
            
            // 9. 覆盖 WebGL vendor 和 renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };
            
            // 10. 覆盖 iframe contentWindow
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    return window;
                }
            });
        """)
        
        return context
    
    async def _create_page(self) -> Page:
        """创建页面"""
        browser = await self._browser_manager.get_browser(self.proxy, self.headless)
        self._context = await self._create_context(browser)
        self._page = await self._context.new_page()
        
        # 设置默认超时
        self._page.set_default_timeout(self.timeout)
        
        return self._page
    
    async def _wait_for_selectors(
        self, 
        selectors: List[str], 
        timeout: int = 10000
    ) -> Optional[str]:
        """
        智能等待多个选择器，返回第一个匹配的选择器
        
        Args:
            selectors: 选择器列表（按优先级排序）
            timeout: 总超时时间
        
        Returns:
            匹配到的选择器，或 None
        """
        start_time = asyncio.get_event_loop().time()
        
        for selector in selectors:
            try:
                remaining_time = timeout - (asyncio.get_event_loop().time() - start_time) * 1000
                if remaining_time <= 0:
                    break
                
                await self._page.wait_for_selector(selector, timeout=min(3000, remaining_time))
                logger.debug(f"选择器匹配成功: {selector}")
                return selector
            except Exception:
                continue
        
        logger.warning(f"所有选择器均未匹配: {selectors}")
        return None
    
    async def _scroll_page(self, times: int = 3, delay: float = 1.0):
        """
        滚动页面以触发懒加载
        
        Args:
            times: 滚动次数
            delay: 滚动间隔
        """
        for i in range(times):
            await self._page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i + 1) / times})")
            await asyncio.sleep(delay + random.uniform(0, 0.5))
    
    async def _random_delay(self, min_delay: float = 0.5, max_delay: float = 2.0):
        """随机延迟"""
        await asyncio.sleep(random.uniform(min_delay, max_delay))
    
    async def _human_type(self, selector: str, text: str):
        """模拟人类输入"""
        await self._page.click(selector)
        await self._random_delay(0.1, 0.3)
        
        for char in text:
            await self._page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    
    async def _save_cookies(self, name: str = None):
        """保存Cookies"""
        if not self._context:
            return
        
        name = name or self.platform_name
        cookies = await self._context.cookies()
        cookie_file = self.COOKIE_DIR / f"{name}_cookies.json"
        
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
        
        logger.info(f"Cookies已保存: {cookie_file}")

        # 额外保存完整状态，提升登录态复用稳定性
        try:
            state_file = self.COOKIE_DIR / f"{name}_state.json"
            await self._context.storage_state(path=str(state_file))
            logger.info(f"storage_state已保存: {state_file}")
        except Exception as e:
            logger.warning(f"保存storage_state失败: {e}")
    
    async def _load_cookies(self, name: str = None) -> bool:
        """加载Cookies"""
        if not self._context:
            return False
        
        name = name or self.platform_name
        cookie_file = self.COOKIE_DIR / f"{name}_cookies.json"
        
        if not cookie_file.exists():
            logger.warning(f"⚠ 未找到Cookie文件: {cookie_file}")
            logger.warning(f"⚠ 请先运行登录脚本: python login.py {name} qr")
            return False
        
        try:
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            
            await self._context.add_cookies(cookies)
            logger.info(f"✓ Cookies已加载: {cookie_file} ({len(cookies)}条)")
            return True
        except Exception as e:
            logger.warning(f"加载Cookies失败: {e}")
            return False
    
    async def _check_login_required(self) -> bool:
        """
        检测是否需要登录
        
        Returns:
            True: 需要登录, False: 已登录或不确定
        """
        # 检查是否有登录按钮或登录提示
        login_indicators = [
            "text=登录",
            "text=请登录",
            "text=登录/注册",
            "[class*='login']",
            "a[href*='login']",
        ]
        
        for indicator in login_indicators:
            try:
                element = await self._page.query_selector(indicator)
                if element:
                    # 排除一些误判情况
                    text = await element.inner_text()
                    if text and "登录" in text and len(text) < 20:
                        return True
            except Exception:
                continue
        
        return False
    
    async def _detect_captcha(self) -> bool:
        """
        检测验证码
        
        Returns:
            是否检测到验证码
        """
        captcha_indicators = [
            "验证码",
            "滑动验证",
            "安全验证",
            "请完成安全验证",
            "#nc_1_wrapper",  # 淘宝滑块
            ".nc_wrapper",
            "#captcha",
            ".captcha",
            "iframe[src*='captcha']",
        ]
        
        for indicator in captcha_indicators:
            try:
                if indicator.startswith('#') or indicator.startswith('.'):
                    element = await self._page.query_selector(indicator)
                else:
                    element = await self._page.query_selector(f'text="{indicator}"')
                
                if element:
                    logger.warning(f"检测到验证码: {indicator}")
                    return True
            except Exception:
                continue
        
        return False
    
    async def _handle_captcha(self) -> bool:
        """
        处理验证码（需要人工介入）
        
        Returns:
            是否处理成功
        """
        logger.warning(f"[{self.platform_name}] 检测到验证码，需要人工处理")
        
        # 截图保存
        screenshot_path = self.COOKIE_DIR / f"{self.platform_name}_captcha.png"
        await self._page.screenshot(path=str(screenshot_path))
        logger.info(f"验证码截图已保存: {screenshot_path}")
        
        # 这里可以添加自动处理逻辑或通知
        return False
    
    async def _safe_extract_text(self, element, selector: str = None) -> str:
        """安全提取文本"""
        try:
            if selector:
                el = await element.query_selector(selector)
                return await el.inner_text() if el else ""
            return await element.inner_text()
        except Exception:
            return ""
    
    async def _safe_extract_attr(self, element, attr: str, selector: str = None) -> str:
        """安全提取属性"""
        try:
            if selector:
                el = await element.query_selector(selector)
                return await el.get_attribute(attr) if el else ""
            return await element.get_attribute(attr) or ""
        except Exception:
            return ""
    
    async def close(self):
        """关闭页面和上下文"""
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None
        
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        
        await self._browser_manager.release()


# 导出
__all__ = [
    "BaseCrawler",
    "BrowserManager",
    "retry_with_backoff",
]
