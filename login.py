#!/usr/bin/env python3
"""
多平台登录工具

支持淘宝、京东的扫码登录和账号密码登录。
登录成功后自动保存 Cookie 到 cookies/ 目录。

用法:
    python login.py taobao qr        # 淘宝扫码登录
    python login.py taobao password  # 淘宝账号密码登录
    python login.py jd qr            # 京东扫码登录
    python login.py all qr           # 全部平台扫码登录
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright, Page, Browser
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

# Cookie 存储目录
COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


class LoginManager:
    """登录管理器"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context = None
        self._page: Optional[Page] = None
    
    async def init_browser(self):
        """初始化浏览器"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        
        # 注入反检测脚本
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        self._page = await self._context.new_page()
        logger.info("浏览器已启动")
    
    async def close(self):
        """关闭浏览器"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("浏览器已关闭")
    
    async def save_cookies(self, platform: str) -> bool:
        """保存 Cookie"""
        try:
            cookies = await self._context.cookies()
            cookie_file = COOKIE_DIR / f"{platform}_cookies.json"
            
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)

            # 保存完整会话状态（cookies + localStorage）
            state_file = COOKIE_DIR / f"{platform}_state.json"
            await self._context.storage_state(path=str(state_file))
            
            logger.info(f"✓ Cookie 已保存: {cookie_file}")
            logger.info(f"✓ storage_state 已保存: {state_file}")
            logger.info(f"  共 {len(cookies)} 条 Cookie")
            return True
        except Exception as e:
            logger.error(f"保存 Cookie 失败: {e}")
            return False
    
    async def _check_taobao_login(self) -> bool:
        """检查淘宝登录状态"""
        try:
            await self._page.goto("https://www.taobao.com", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            selectors = [
                ".site-nav-user a",
                ".member-nick",
                ".J_MemberNick",
                "[class*='member-nick']",
            ]
            
            for selector in selectors:
                element = await self._page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip() and "登录" not in text:
                        logger.info(f"✓ 淘宝已登录: {text.strip()}")
                        return True
            
            current_url = self._page.url
            if "login" in current_url:
                return False
            
            return False
        except Exception as e:
            logger.debug(f"检查淘宝登录状态失败: {e}")
            return False
    
    async def _check_jd_login(self) -> bool:
        """检查京东登录状态"""
        try:
            await self._page.goto("https://www.jd.com", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            selectors = [
                ".nickname",
                ".user-name",
                "[class*='nickname']",
            ]
            
            for selector in selectors:
                element = await self._page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip() and "登录" not in text:
                        logger.info(f"✓ 京东已登录: {text.strip()}")
                        return True
            
            return False
        except Exception as e:
            logger.debug(f"检查京东登录状态失败: {e}")
            return False


class TaobaoLogin(LoginManager):
    """淘宝登录"""
    
    platform = "taobao"
    
    async def qr_login(self, timeout: int = 600) -> bool:
        """扫码登录"""
        logger.info("=" * 50)
        logger.info("淘宝扫码登录")
        logger.info("=" * 50)
        
        try:
            # 登录页经常出现 networkidle 超时，改为多入口 + domcontentloaded
            entry_urls = [
                "https://login.taobao.com/",
                "https://www.taobao.com/",
                "https://www.tmall.com/",
            ]
            opened = False
            for entry in entry_urls:
                try:
                    logger.info(f"尝试打开登录入口: {entry}")
                    await self._page.goto(entry, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(2)
                    opened = True
                    break
                except Exception as e:
                    logger.warning(f"打开入口失败: {entry}, {e}")
            
            if not opened:
                logger.error("无法打开淘宝登录入口，请检查网络后重试")
                return False
            
            # 强制切换到扫码登录（多策略，避免“点不动”）
            await self._switch_to_qr_mode()
            
            logger.info("请使用淘宝 APP 扫描二维码登录...")
            logger.info(f"等待扫码中... (超时: {timeout} 秒)")
            
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    logger.error("登录超时")
                    return False
                
                if await self._check_taobao_login():
                    logger.info("✓ 扫码登录成功!")
                    await self.save_cookies("taobao")
                    return True
                
                current_url = self._page.url
                if "taobao.com" in current_url and "login" not in current_url:
                    logger.info("✓ 扫码登录成功!")
                    await self.save_cookies("taobao")
                    return True

                # 二维码可能过期，自动尝试刷新
                await self._refresh_taobao_qr_if_needed()
                
                await asyncio.sleep(1)
                remaining = int(timeout - elapsed)
                if remaining % 10 == 0:
                    logger.info(f"继续等待扫码... (剩余 {remaining} 秒)")
        
        except Exception as e:
            logger.error(f"扫码登录失败: {e}")
            return False

    async def _switch_to_qr_mode(self):
        """尽量把页面切到扫码登录模式"""
        selectors = [
            "text=扫码登录",
            "text=二维码登录",
            "text=扫码",
            "[class*='qrcode']",
            "[class*='qr']",
            "[class*='quick']",
            "[class*='login-switch']",
            ".iconfont.quick",
        ]

        # 尝试主页面点击
        for selector in selectors:
            try:
                btn = await self._page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1.2)
                    if await self._has_qr_code():
                        logger.info("已切换到扫码登录模式")
                        return
            except Exception:
                continue

        # 尝试 iframe 内点击（淘宝登录常见）
        for frame in self._page.frames:
            for selector in selectors:
                try:
                    btn = await frame.query_selector(selector)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(1.2)
                        if await self._has_qr_code():
                            logger.info("已在 iframe 内切换到扫码登录模式")
                            return
                except Exception:
                    continue

        logger.warning("未能自动切换扫码模式，请在页面中手动切换后扫码")

    async def _has_qr_code(self) -> bool:
        """检查是否出现二维码登录元素"""
        qr_selectors = [
            "img[src*='qrcode']",
            "img[class*='qrcode']",
            "canvas",
            "text=请使用手机淘宝扫码登录",
            "text=扫码登录更安全",
        ]
        try:
            for selector in qr_selectors:
                el = await self._page.query_selector(selector)
                if el:
                    return True
        except Exception:
            return False
        return False

    async def _refresh_taobao_qr_if_needed(self):
        """二维码过期时自动刷新"""
        try:
            refresh_selectors = [
                "text=二维码已失效",
                "text=二维码过期",
                "text=点击刷新",
                "text=刷新二维码",
                ".refresh",
                "[class*='refresh']",
            ]
            refresh_trigger = None
            for selector in refresh_selectors:
                el = await self._page.query_selector(selector)
                if el:
                    refresh_trigger = el
                    break

            if refresh_trigger:
                await refresh_trigger.click()
                logger.info("检测到二维码过期，已自动刷新")
                await asyncio.sleep(1.5)
        except Exception:
            pass
    
    async def password_login(self, username: str, password: str, timeout: int = 120) -> bool:
        """账号密码登录"""
        logger.info("=" * 50)
        logger.info("淘宝账号密码登录")
        logger.info("=" * 50)
        
        try:
            await self._page.goto("https://login.taobao.com/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 切换到账号密码登录
            password_tab = await self._page.query_selector("[class*='static'], text=密码登录, text=账号登录")
            if password_tab:
                await password_tab.click()
                await asyncio.sleep(1)
            
            # 填写账号
            username_input = await self._page.query_selector("#fm-login-id, input[name='username'], input[placeholder*='手机号']")
            if username_input:
                await username_input.fill(username)
                logger.info("已填写账号")
            else:
                logger.warning("未找到账号输入框，请手动填写")
            
            # 填写密码
            password_input = await self._page.query_selector("#fm-login-password, input[name='password'], input[type='password']")
            if password_input:
                await password_input.fill(password)
                logger.info("已填写密码")
            else:
                logger.warning("未找到密码输入框，请手动填写")
            
            logger.info("")
            logger.info("⚠ 请在浏览器中完成以下操作:")
            logger.info("  1. 检查账号密码是否正确")
            logger.info("  2. 点击登录按钮")
            logger.info("  3. 完成滑块验证/短信验证（如果有）")
            logger.info("")
            logger.info(f"等待登录完成... (超时: {timeout} 秒)")
            
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    logger.error("登录超时")
                    return False
                
                if await self._check_taobao_login():
                    logger.info("✓ 登录成功!")
                    await self.save_cookies("taobao")
                    return True
                
                current_url = self._page.url
                if "taobao.com" in current_url and "login" not in current_url:
                    logger.info("✓ 登录成功!")
                    await self.save_cookies("taobao")
                    return True
                
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"账号密码登录失败: {e}")
            return False


class JDLogin(LoginManager):
    """京东登录"""
    
    platform = "jd"
    
    async def qr_login(self, timeout: int = 120) -> bool:
        """扫码登录"""
        logger.info("=" * 50)
        logger.info("京东扫码登录")
        logger.info("=" * 50)
        
        try:
            await self._page.goto("https://passport.jd.com/new/login.aspx", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            logger.info("请使用京东 APP 扫描二维码登录...")
            logger.info(f"等待扫码中... (超时: {timeout} 秒)")
            
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    logger.error("登录超时")
                    return False
                
                if await self._check_jd_login():
                    logger.info("✓ 扫码登录成功!")
                    await self.save_cookies("jd")
                    return True
                
                current_url = self._page.url
                if "jd.com" in current_url and "passport" not in current_url and "login" not in current_url:
                    logger.info("✓ 扫码登录成功!")
                    await self.save_cookies("jd")
                    return True
                
                await asyncio.sleep(1)
                remaining = int(timeout - elapsed)
                if remaining % 10 == 0:
                    logger.info(f"继续等待扫码... (剩余 {remaining} 秒)")
        
        except Exception as e:
            logger.error(f"扫码登录失败: {e}")
            return False
    
    async def password_login(self, username: str, password: str, timeout: int = 120) -> bool:
        """账号密码登录"""
        logger.info("=" * 50)
        logger.info("京东账号密码登录")
        logger.info("=" * 50)
        
        try:
            await self._page.goto("https://passport.jd.com/new/login.aspx", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 切换到账号密码登录
            account_tab = await self._page.query_selector(".login-tab-r, text=账户登录")
            if account_tab:
                await account_tab.click()
                await asyncio.sleep(1)
            
            # 填写账号
            username_input = await self._page.query_selector("#loginname, input[name='username'], input[placeholder*='账户']")
            if username_input:
                await username_input.fill(username)
                logger.info("已填写账号")
            else:
                logger.warning("未找到账号输入框，请手动填写")
            
            # 填写密码
            password_input = await self._page.query_selector("#nloginpwd, input[name='password'], input[type='password']")
            if password_input:
                await password_input.fill(password)
                logger.info("已填写密码")
            else:
                logger.warning("未找到密码输入框，请手动填写")
            
            logger.info("")
            logger.info("⚠ 请在浏览器中完成以下操作:")
            logger.info("  1. 检查账号密码是否正确")
            logger.info("  2. 点击登录按钮")
            logger.info("  3. 完成滑块验证/短信验证（如果有）")
            logger.info("")
            logger.info(f"等待登录完成... (超时: {timeout} 秒)")
            
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    logger.error("登录超时")
                    return False
                
                if await self._check_jd_login():
                    logger.info("✓ 登录成功!")
                    await self.save_cookies("jd")
                    return True
                
                current_url = self._page.url
                if "jd.com" in current_url and "passport" not in current_url and "login" not in current_url:
                    logger.info("✓ 登录成功!")
                    await self.save_cookies("jd")
                    return True
                
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"账号密码登录失败: {e}")
            return False


def print_usage():
    """打印使用说明"""
    print("""
淘宝/京东登录工具

用法:
    python login.py <平台> <模式> [选项]

平台:
    taobao     淘宝
    jd         京东
    all        全部平台

模式:
    qr         扫码登录（推荐）
    password   账号密码登录

账号密码登录选项:
    --username, -u    用户名/手机号
    --password, -p    密码

示例:
    python login.py taobao qr                    # 淘宝扫码登录
    python login.py jd qr                        # 京东扫码登录
    python login.py all qr                       # 全部平台扫码登录
    python login.py taobao password -u 手机号 -p 密码   # 淘宝账号密码登录
    python login.py jd password -u 用户名 -p 密码       # 京东账号密码登录

注意:
    - 扫码登录更稳定，推荐使用
    - 账号密码登录可能触发验证码，需要手动处理
    - 登录成功后 Cookie 保存在 cookies/ 目录
""")


async def login_taobao(mode: str, username: str = None, password: str = None):
    """淘宝登录"""
    login = TaobaoLogin(headless=False)
    try:
        await login.init_browser()
        
        if mode == "qr":
            success = await login.qr_login()
        else:
            if not username or not password:
                logger.error("账号密码登录需要提供 -u 用户名 -p 密码")
                return False
            success = await login.password_login(username, password)
        
        return success
    finally:
        await login.close()


async def login_jd(mode: str, username: str = None, password: str = None):
    """京东登录"""
    login = JDLogin(headless=False)
    try:
        await login.init_browser()
        
        if mode == "qr":
            success = await login.qr_login()
        else:
            if not username or not password:
                logger.error("账号密码登录需要提供 -u 用户名 -p 密码")
                return False
            success = await login.password_login(username, password)
        
        return success
    finally:
        await login.close()


async def main():
    """主函数"""
    args = sys.argv[1:]
    
    if not args or args[0] in ["-h", "--help", "help"]:
        print_usage()
        return
    
    platform = args[0].lower()
    mode = args[1].lower() if len(args) > 1 else "qr"
    
    # 解析账号密码
    username = None
    password = None
    
    i = 2
    while i < len(args):
        if args[i] in ["-u", "--username"]:
            username = args[i + 1] if i + 1 < len(args) else None
            i += 2
        elif args[i] in ["-p", "--password"]:
            password = args[i + 1] if i + 1 < len(args) else None
            i += 2
        else:
            i += 1
    
    # 执行登录
    if platform == "taobao":
        success = await login_taobao(mode, username, password)
    elif platform == "jd":
        success = await login_jd(mode, username, password)
    elif platform == "all":
        logger.info("开始登录全部平台...")
        success_taobao = await login_taobao(mode, username, password)
        success_jd = await login_jd(mode, username, password)
        success = success_taobao and success_jd
    else:
        logger.error(f"未知平台: {platform}")
        print_usage()
        return
    
    logger.info("")
    if success:
        logger.info("=" * 50)
        logger.info("✓ 登录完成!")
        logger.info("=" * 50)
        logger.info(f"Cookie 已保存到: {COOKIE_DIR}")
        logger.info("现在可以运行爬虫抓取商品数据了")
    else:
        logger.error("登录失败，请重试")


if __name__ == "__main__":
    asyncio.run(main())
