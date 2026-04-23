"""
项目分析 Agent

用于输出当前项目运行状态、调试产物状态和可执行建议。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from app.config import settings
from app.models import Platform


class ProjectAnalyzerAgent:
    """项目诊断分析器"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.debug_root = self.project_root / "debug_output"

    def analyze(self) -> Dict[str, Any]:
        debug_summary = self._collect_debug_summary()
        recommendations = self._build_recommendations(debug_summary)

        return {
            "generated_at": datetime.now().isoformat(),
            "mode": {
                "api_mode": settings.api_mode,
                "taobao_only_mode": settings.taobao_only_mode,
                "llm_provider": settings.llm_provider,
            },
            "paths": {
                "project_root": str(self.project_root),
                "debug_output": str(self.debug_root),
                "cookies_dir": settings.crawler_cookies_dir,
            },
            "debug_summary": debug_summary,
            "recommendations": recommendations,
        }

    def _collect_debug_summary(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "exists": self.debug_root.exists(),
            "platforms": [],
            "total_html": 0,
            "total_png": 0,
        }
        if not self.debug_root.exists():
            return result

        for platform in Platform:
            pdir = self.debug_root / platform.value
            html_files = sorted(pdir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True) if pdir.exists() else []
            png_files = sorted(pdir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True) if pdir.exists() else []

            latest_html = html_files[0].name if html_files else None
            latest_png = png_files[0].name if png_files else None

            result["platforms"].append(
                {
                    "platform": platform.value,
                    "dir_exists": pdir.exists(),
                    "html_count": len(html_files),
                    "png_count": len(png_files),
                    "latest_html": latest_html,
                    "latest_png": latest_png,
                }
            )
            result["total_html"] += len(html_files)
            result["total_png"] += len(png_files)

        return result

    def _build_recommendations(self, debug_summary: Dict[str, Any]) -> List[str]:
        recs: List[str] = []
        if settings.taobao_only_mode:
            recs.append("当前为淘宝单平台模式；如需多平台比价，请先关闭 taobao_only_mode 并逐平台回归。")
        if not settings.api_mode:
            recs.append("当前为纯爬虫模式；建议优先保证 Cookie 有效并定期人工登录续期。")

        total_html = debug_summary.get("total_html", 0)
        total_png = debug_summary.get("total_png", 0)
        if total_html == 0 and total_png == 0:
            recs.append("尚未发现调试产物；建议先执行一次 compare 请求并检查 debug_output。")
        else:
            recs.append("已检测到调试产物；可优先查看最新 HTML/截图定位登录态、验证码或反爬问题。")

        return recs

