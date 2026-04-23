#!/usr/bin/env python3
"""分析HTML结构"""
import re
from pathlib import Path

# 淘宝HTML
html_file = Path(__file__).parent / "cookies" / "debug_taobao_20260420_201156.html"
if html_file.exists():
    html = html_file.read_text(encoding='utf-8')
    print(f"文件大小: {len(html)} 字符")
    
    # 搜索商品相关的class
    patterns = [
        r'class="[^"]*Item[^"]*"',
        r'class="[^"]*Card[^"]*"',
        r'class="[^"]*price[^"]*"',
        r'class="[^"]*title[^"]*"',
        r'data-index',
        r'data-nid',
    ]
    
    for p in patterns:
        matches = re.findall(p, html, re.IGNORECASE)
        unique = list(set(matches))[:5]
        if unique:
            print(f"\n{p[:30]}:")
            for m in unique:
                print(f"  {m}")
    
    # 检查是否有验证码或登录
    if '验证' in html or 'login' in html.lower():
        print("\n--- 可能需要验证/登录 ---")
else:
    print(f"文件不存在: {html_file}")
