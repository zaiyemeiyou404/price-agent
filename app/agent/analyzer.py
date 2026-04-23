"""
失败分析器

基于调试产物（HTML/截图）对爬虫空结果进行原因诊断，
用于在 Agent 无结果时输出可执行的排查建议。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger

from app.models import Platform


class FailureAnalyzer:
    """爬虫失败分析器"""

    DEBUG_ROOT = Path(__file__).resolve().parents[2] / "debug_output"

    KEYWORDS = {
        "captcha": [
            "验证码",
            "滑动验证",
            "安全验证",
            "请完成安全验证",
            "nc_1_wrapper",
            "captcha",
            "action=captcha",
            "_____tmd_____",
            "punish?",
        ],
        "login_required": [
            "login.taobao.com",
            "member/login",
            "tb-login",
            "请先登录",
            "账户登录",
        ],
        "anti_bot": [
            "访问受限",
            "访问异常",
            "系统检测到异常",
            "非常抱歉，您的访问出现异常",
            "稍后再试",
        ],
        "empty_result": [
            "没有找到相关宝贝",
            "没有找到相关商品",
            "抱歉，没有找到",
            "未找到相关",
        ],
    }

    LABELS = {
        "login_required": "登录态失效",
        "captcha": "触发验证码",
        "anti_bot": "触发风控/反爬",
        "empty_result": "页面返回空结果",
        "unknown": "未识别原因",
    }

    def analyze(self, platforms: List[Platform], query: str) -> Dict[str, object]:
        """分析各平台失败原因"""
        details = []

        for platform in platforms:
            reason, evidence = self._analyze_platform(platform, query)
            details.append(
                {
                    "platform": platform.value,
                    "reason": reason,
                    "reason_label": self.LABELS.get(reason, self.LABELS["unknown"]),
                    "evidence": evidence,
                }
            )

        summary = self._build_summary(details)
        return {"details": details, "summary": summary}

    def _analyze_platform(self, platform: Platform, query: str) -> Tuple[str, str]:
        platform_dir = self.DEBUG_ROOT / platform.value
        if not platform_dir.exists():
            return "unknown", "未找到调试目录"

        # 先看最近调试文件名中的阶段标记，避免仅靠正文关键词误判
        stage_reason = self._detect_reason_from_stage_name(platform_dir, query)
        if stage_reason:
            return stage_reason, "命中最近调试阶段标记"

        html_path = self._find_latest_html(platform_dir, query)
        if not html_path:
            return "unknown", "未找到对应查询的调试HTML"

        try:
            content = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"读取调试HTML失败: {html_path}, {e}")
            return "unknown", f"读取调试HTML失败: {html_path.name}"

        reason = self._detect_reason(content)
        return reason, f"命中文件: {html_path.name}"

    def _detect_reason_from_stage_name(self, platform_dir: Path, query: str) -> str | None:
        safe_query = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", query)[:30]
        recent_files = sorted(
            platform_dir.glob(f"*_{safe_query}_*.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:8]
        if not recent_files:
            recent_files = sorted(platform_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]

        names = [p.name.lower() for p in recent_files]
        if any("_captcha" in n for n in names):
            return "captcha"
        if any("_login_required" in n for n in names):
            return "login_required"
        if any("_empty" in n for n in names):
            return "empty_result"
        return None

    def _find_latest_html(self, platform_dir: Path, query: str) -> Path | None:
        safe_query = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", query)[:30]
        candidates = list(platform_dir.glob(f"*_{safe_query}_*.html"))
        if not candidates:
            candidates = list(platform_dir.glob("*.html"))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def _detect_reason(self, content: str) -> str:
        lowered = content.lower()
        # 按优先级判定，避免“登录”关键词误伤验证码页面
        priority = ["captcha", "anti_bot", "login_required", "empty_result"]
        for reason in priority:
            words = self.KEYWORDS.get(reason, [])
            for word in words:
                if word.lower() in lowered:
                    return reason
        return "unknown"

    def _build_summary(self, details: List[Dict[str, str]]) -> str:
        if not details:
            return "未找到相关商品"

        labels = "；".join([f"{d['platform']}: {d['reason_label']}" for d in details])

        has_login = any(d["reason"] == "login_required" for d in details)
        has_captcha = any(d["reason"] == "captcha" for d in details)
        has_antibot = any(d["reason"] == "anti_bot" for d in details)
        has_empty = any(d["reason"] == "empty_result" for d in details)

        if has_login:
            return f"未找到相关商品。诊断结果：{labels}。建议先重新登录并更新 Cookie 后重试。"
        if has_captcha:
            return f"未找到相关商品。诊断结果：{labels}。建议人工完成验证码后再次搜索。"
        if has_antibot:
            return f"未找到相关商品。诊断结果：{labels}。建议切换有头模式、放慢请求频率并重试。"
        if has_empty:
            return f"未找到相关商品。诊断结果：{labels}。建议更换关键词或检查页面选择器。"

        return f"未找到相关商品。诊断结果：{labels}。请查看 debug_output 中的最新截图和 HTML。"
