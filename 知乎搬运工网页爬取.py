#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/1/8 19:43
# @Author  : 修明
# @File    : __init__.py.py
# @Description :

import requests
from lxml import etree


def get_page(url):
    path = './知乎搬运工/'
    response = requests.get(url)
    if response.status_code == 200:
        page = etree.HTML(response.content)
        tittle = page.xpath('/html/body/div[2]/div/article/h1/text()')[0]
        # tittle = '沙雕搞笑小说'
        # print(tittle)
        page_all = page.xpath('/html/body/div[2]/div/article/div[2]/p//text()')
        description = page_all[2] + page_all[4] + page_all[5]
        github_url = "https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection"
        if tittle[-1] == '?' or tittle[-1] == '？' :
            tittle = tittle[:-1]

        if '/' in tittle:
            tittle = tittle.replace('/', ' ')

        with open(path + tittle + ' .md', 'w') as f:
            f.write("# " + tittle + "  \n")
            for i,duanluo in enumerate(page_all):
                if i == 0:
                    f.write("## " + duanluo + ": ")
                elif i == 1:
                    f.write(duanluo + '  \n')
                else:
                    f.write("&emsp;&emsp;" + duanluo + '  \n')
                    f.write("  \n")
            f.write(f"本文搬运来自：{url}  \n 收藏于：{github_url}")
            f.close()
        # print(page_all)
        with open("目录" + '.md', 'a') as f:
            f.write( "## " + f"[{tittle}](./知乎搬运工/{tittle}.md)  \n" + f"&emsp;[阅读原文]({url})  \n"  + "文章首段内容:  \n&emsp;&emsp;" + f"{description}" + "  \n" )
        with open("当前进度" + '.txt', 'w') as f:
            f.write(url[24:])
        print(f"{url}  爬取保存成功")
        return True
    else:
        print("网站还未更新")
        return False



# get_page('https://www.zhbyg.top/a/2516')
#

with open('./当前进度' + '.txt', 'r') as f:
    t = f.read()
    f.close()
while True:
    url = 'https://www.zhbyg.top/a/'
    t = str(int(t) + 1)
    urljindu = url + t
    state = get_page(urljindu)
    if state is True:
        pass
    else:
        continue
    # time.sleep(0.5)
