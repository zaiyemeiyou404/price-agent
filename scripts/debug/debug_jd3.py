import requests
import re
from bs4 import BeautifulSoup

url = 'https://search.jd.com/Search?keyword=iPhone%2015'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
resp = requests.get(url, headers=headers)
print('Status:', resp.status_code)
print('Length:', len(resp.text))
# 查找商品列表
soup = BeautifulSoup(resp.text, 'html.parser')
# 查找所有script标签
scripts = soup.find_all('script')
for script in scripts:
    if script.string and 'gl-item' in script.string:
        print('Found gl-item in script')
        # 提取JSON数据
        pass
# 查找商品列表容器
goods_list = soup.find(id='J_goodsList')
if goods_list:
    print('Found J_goodsList')
    items = goods_list.find_all(class_='gl-item')
    print('gl-item count:', len(items))
else:
    print('J_goodsList not found')
# 查找其他可能的选择器
for cls in ['gl-i-wrap', 'p-img', 'p-name']:
    elems = soup.find_all(class_=cls)
    print(f'{cls}: {len(elems)}')
# 输出前5000字符
print(resp.text[:5000])