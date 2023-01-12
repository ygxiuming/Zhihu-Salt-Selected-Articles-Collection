#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/1/12 16:35
# @Author  : 修明
# @File    : 我不是盐神.py
# @Description :  我不是盐神网页爬取
import json
import time

import requests
from lxml import etree


class yanshen(object):
    def __init__(self):
        self.catalogueurl = 'https://onehu.xyz/archives/'
        self.headers = {
            'user - agent': 'Mozilla / 5.0(Windows NT 10.0;Win64;x64) AppleWebKit / 537.36(KHTML, likeGecko) Chrome / 108.0.0.0Safari / 537.36'
        }
        self.speed = ''
        self.catalogue = []

    def get_catalogue(self,):
        try:
            with open('盐神进度.txt', 'r') as f:
                self.speed = f.read()
                f.close()
            nextpage = [1]
            nexturl = self.catalogueurl
            while len(nextpage):
                response = requests.get(nexturl, headers=self.headers)
                while response.status_code != 200:
                    response = requests.get(nexturl, headers=self.headers)
                    time.sleep(1)
                response = etree.HTML(response.content)
                # 目录父节点
                responsefu = response.xpath('/html/body/main/div[1]/div/div/div/div/div')[0]
                nextpage = response.xpath('//*[@rel="next"]/@href')

                for item in responsefu.xpath('./a'):
                    # 日期
                    date = item.xpath('./time/text()')[0]
                    # 标题
                    tittle = item.xpath('./div/text()')[0]
                    # url
                    url = 'https://onehu.xyz' + item.xpath('./@href')[0]

                    if url != self.speed:
                        data = {
                            "tittle": tittle,
                            "time" : date,
                            "url" : url
                            }
                        self.catalogue.append(data)
                    else:
                        break

                print(nexturl + " 爬取成功")
                if len(nextpage) > 0 :
                    nexturl = 'https://onehu.xyz' + nextpage[0]
            print(self.catalogue)
            with open("temp.json","w", encoding='UTF-8') as f:
                json.dump(self.catalogue, f, ensure_ascii=False)
                f.close()
            print("保存任务进度成功！")
            self.get_page()
        except Exception as e :
            print(e)


    def get_page(self, ):
        github_url = "https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection"
        path = './盐神/'
        with open("temp.json","r", encoding='UTF-8') as f:
            self.catalogue = json.load(f)
        print(len(self.catalogue))
        for index,item in enumerate(self.catalogue):
            if index>=0:
                # print(item)
                url = item["url"]
                tittle = item["tittle"]
                response = requests.get(url,self.headers)
                response = etree.HTML(response.content)
                data = response.xpath("//*[@id='board']/article/div[1]/p//text()")
                description = data[0] + data[1] + data[2]

                with open("盐神目录.md", "a") as f:
                    f.write( "## " + f"[{tittle}](./我不是盐神/{tittle}.md)  \n" + f"&emsp;[阅读原文]({url})  \n"  + "文章首段内容:  \n&emsp;&emsp;" + f"{description}" + "  \n  \n" )
                    f.write("<br>   \n")
                    f.write("  \n")
                    f.close()

                with open(path + tittle + '.md', 'w') as f:
                    f.write("# " + tittle + "  \n")
                    f.write(f"[原文地址]({url})" + "  \n")
                    f.write("<br>   \n")
                    for row in data :
                        f.write("&emsp;&emsp;" + row + '  \n')
                        f.write("<br>   \n")
                    f.write(f"本文搬运来自：{url}  \n收藏于：{github_url}")
                    f.close()
                    print(f"{index+1}/{len(self.catalogue)}   {tittle}  保存成功")
            else:
                continue
        print("所有文章爬取成功！")
        with open("盐神进度.txt", "w") as f:
            f.write(self.catalogue[0]["url"])
            f.close()








# yanshen().get_catalogue()
yanshen().get_page()



