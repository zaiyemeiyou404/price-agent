#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析京东HTML"""
import re
from pathlib import Path

html_file = Path(r"G:\.openclaw\workspace\price-agent\cookies\jd_page.html")
html = html_file.read_text(encoding='utf-8')

print(f"HTML大小: {len(html)} 字符\n")

# 搜索商品相关关键词
keywords = ['gl-item', 'data-sku', 'p-name', 'p-price', 'J_goodsList', 'skuId', 'wareId']
for kw in keywords:
    count = html.count(kw)
    print(f"{kw}: {count}")

# 搜索script标签
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"\nscript标签数: {len(scripts)}")

# 查找大数据块
sizes = [(len(s), i) for i, s in enumerate(scripts)]
sizes.sort(reverse=True)

print("\n最大的script块:")
for size, i in sizes[:5]:
    if size > 1000:
        print(f"\nscript[{i}]: {size} 字符")
        # 打印开头
        preview = scripts[i][:200].replace('\n', ' ')
        print(f"  开头: {preview}...")
        
        # 搜索JSON关键词
        if 'sku' in scripts[i].lower() or 'price' in scripts[i].lower():
            print("  [包含sku或price!]")

# 搜索window变量
window_vars = re.findall(r'window\.(\w+)\s*=', html)
if window_vars:
    print(f"\nwindow变量: {list(set(window_vars))[:10]}")
