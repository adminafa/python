# coding:utf-8

'''
@author = super_fazai
@File    : my_requests.py
@Time    : 2017/3/22 10:13
@connect : superonesfazai@gmail.com
'''

import requests
from random import randint
from my_ip_pools import MyIpPools
import re, gc, json, time
from pprint import pprint
from json import dumps, loads

__all__ = [
    'MyRequests',
]

class MyRequests(object):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_url_body(cls, url, headers:dict,
                     params=None, data=None, cookies=None,
                     had_referer=False, encoding='utf-8',
                     method='get', timeout=12, num_retries=1):
        '''
        根据url得到body
        :param url:
        :param headers:
        :param params:
        :param data:
        :param cookies:
        :param had_referer:
        :param encoding:
        :param method:
        :param timeout:
        :param num_retries:
        :return: '' 表示error | str 表示success
        '''
        # 设置代理ip
        tmp_proxies = cls._get_proxies()
        # print('------>>>| 正在使用代理ip: {} 进行爬取... |<<<------'.format(tmp_proxies.get('http')))

        tmp_headers = headers
        tmp_headers['Host'] = re.compile(r'://(.*?)/').findall(url)[0]
        if had_referer:
            if re.compile(r'https').findall(url) != []:
                tmp_headers['Referer'] = 'https://' + tmp_headers['Host'] + '/'
            else:
                tmp_headers['Referer'] = 'http://' + tmp_headers['Host'] + '/'

        with requests.session() as s:
            try:
                response = s.request(method=method, url=url, headers=tmp_headers, params=params, data=data, cookies=cookies, proxies=tmp_proxies, timeout=timeout)  # 在requests里面传数据，在构造头时，注意在url外头的&xxx=也得先构造
                # print(response.url)
                body = cls._wash_html(response.content.decode(encoding))

                # print(body)
            except Exception:
                if num_retries > 1:
                    return cls.get_url_body(method=method, url=url, headers=tmp_headers, params=params, data=data, cookies=cookies, had_referer=had_referer, encoding=encoding, timeout=timeout, num_retries=num_retries-1)
                else:
                    print('requests.get()请求超时....')
                    print('data为空!')
                    body = ''

        return body

    @classmethod
    def _wash_html(cls, body):
        body = re.compile('\t').sub('', body)
        body = re.compile('  ').sub('', body)
        body = re.compile('\r\n').sub('', body)
        body = re.compile('\n').sub('', body)

        return body

    @classmethod
    def _get_proxies(cls):
        '''
        得到单个代理ip
        :return: 格式: {'http': ip+port}
        '''
        ip_object = MyIpPools()
        proxies = ip_object.get_proxy_ip_from_ip_pool()  # {'http': ['xx', 'yy', ...]}
        proxy = proxies['http'][randint(0, len(proxies) - 1)]

        tmp_proxies = {
            'http': proxy,
        }

        return tmp_proxies

    def __del__(self):
        gc.collect()

