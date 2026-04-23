#!/usr/bin/env python3
"""
简单比价爬虫 - 使用 requests + BeautifulSoup
"""
import requests
from bs4 import BeautifulSoup
import re
import sys

def search_hist_price(query: str):
    """
    从历史价格网搜索
    网站: http://www.lsjgc.com/
    """
    print(f"\n{'='*60}")
    print(f"[历史价格网] 搜索: {query}")
    print("="*60)
    
    try:
        url = f"http://www.lsjgc.com/search?keyword={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找商品
            items = soup.find_all(['div', 'li'], class_=re.compile(r'item|goods|product', re.I))
            
            if not items:
                # 尝试查找表格
                items = soup.find_all('tr')
            
            print(f"找到 {len(items)} 个元素")
            
            results = []
            for item in items[:10]:
                text = item.get_text(strip=True)
                if text and len(text) > 5:
                    # 提取价格
                    prices = re.findall(r'[¥￥]?\s*(\d+\.?\d*)', text)
                    
                    if prices:
                        results.append({
                            "text": text[:80],
                            "prices": prices
                        })
            
            if results:
                print("\n找到以下价格信息:")
                for i, r in enumerate(results[:5], 1):
                    print(f"  [{i}] {r['text'][:60]}")
                    print(f"      价格: {', '.join(r['prices'][:3])}")
            
            return results
            
    except Exception as e:
        print(f"错误: {e}")
        return []


def search_bi1bi(query: str):
    """
    从比一比价搜索
    网站: https://www.bi1bi.com/
    """
    print(f"\n{'='*60}")
    print(f"[比一比价] 搜索: {query}")
    print("="*60)
    
    try:
        url = f"https://www.bi1bi.com/search/{query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找价格信息
            text = soup.get_text()
            prices = re.findall(r'[¥￥]\s*(\d+\.?\d*)', text)
            
            print(f"页面中的价格: {prices[:10]}")
            
            # 查找商品列表
            items = soup.find_all(['div', 'li'], class_=re.compile(r'item|list|goods', re.I))
            print(f"找到 {len(items)} 个商品元素")
            
            return prices
            
    except Exception as e:
        print(f"错误: {e}")
        return []


def search_gwd(query: str):
    """
    从购物党搜索
    网站: https://www.gwdang.com/
    """
    print(f"\n{'='*60}")
    print(f"[购物党] 搜索: {query}")
    print("="*60)
    
    try:
        url = f"https://www.gwdang.com/search?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 保存HTML用于调试
            with open(r"G:\.openclaw\workspace\price-agent\gwdang.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("HTML已保存到 gwdang.html")
            
            # 查找商品
            items = soup.find_all(['div', 'li'], class_=re.compile(r'item|goods|product', re.I))
            print(f"找到 {len(items)} 个商品元素")
            
            results = []
            for item in items[:10]:
                text = item.get_text(strip=True)
                if text and len(text) > 5:
                    results.append(text[:100])
            
            if results:
                print("\n商品信息:")
                for i, r in enumerate(results[:5], 1):
                    print(f"  [{i}] {r}")
            
            return results
            
    except Exception as e:
        print(f"错误: {e}")
        return []


def main():
    print("\n" + "="*60)
    print("简单比价爬虫测试")
    print("="*60)
    
    query = "iPhone 15"
    
    # 测试多个网站
    search_hist_price(query)
    search_bi1bi(query)
    search_gwdang(query)
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    # 安装: pip install beautifulsoup4 requests
    main()
