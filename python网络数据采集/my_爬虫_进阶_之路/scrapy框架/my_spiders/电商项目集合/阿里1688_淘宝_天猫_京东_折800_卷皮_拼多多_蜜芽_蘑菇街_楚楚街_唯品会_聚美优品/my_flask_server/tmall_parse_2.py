# coding:utf-8

'''
@author = super_fazai
@File    : tmall_parse_2.py
@Time    : 2018/4/14 20:59
@connect : superonesfazai@gmail.com
'''

import time, requests
from random import randint
import json
import re, execjs
from pprint import pprint
from decimal import Decimal
from selenium import webdriver
from time import sleep
import gc
from scrapy.selector import Selector

from settings import PHANTOMJS_DRIVER_PATH, HEADERS, MY_SPIDER_LOGS_PATH
from settings import TAOBAO_USERNAME, TAOBAO_PASSWD, _tmall_cookies
import pytz, datetime
from scrapy.selector import Selector
from logging import INFO, ERROR
from requests.exceptions import ProxyError

from taobao_parse import TaoBaoLoginAndParse
from my_requests import MyRequests
from my_logging import set_logger
from my_utils import tuple_or_list_params_2_dict_params, get_shanghai_time

class TmallParse(object):
    def __init__(self, logger=None):
        self._set_headers()
        self.result_data = {}
        self._set_logger(logger)
        self.msg = ''

    def _set_headers(self):
        self.headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'User-Agent': HEADERS[randint(0, len(HEADERS) - 1)],  # 随机一个请求头
            'Accept': '*/*',
            'Referer': 'https://detail.m.tmall.com/item.htm?id=541107920538',
            'Connection': 'keep-alive',
        }

    def _set_logger(self, logger):
        if logger is None:
            self.my_lg = set_logger(
                log_file_name=MY_SPIDER_LOGS_PATH + '/天猫/_/' + str(get_shanghai_time())[0:10] + '.txt',
                console_log_level=INFO,
                file_log_level=ERROR
            )
        else:
            self.my_lg = logger

    def get_goods_data(self, goods_id):
        '''
        得到data
        :param goods_id:
        :return: data 类型dict
        '''
        if goods_id == []:
            self.result_data = {}
            return {}

        type = goods_id[0]  # 天猫类型
        # self.my_lg.info(str(type))
        goods_id = goods_id[1]  # 天猫goods_id
        tmp_url = 'https://detail.m.tmall.com/item.htm?id=' + str(goods_id)
        self.my_lg.info('------>>>| 得到的移动端地址为: %s' % tmp_url)

        params = self._set_params(goods_id=goods_id)
        # pprint(params)
        self.headers.update({'Referer': tmp_url})
        _url = 'https://h5api.m.taobao.com/h5/mtop.taobao.detail.getdetail/6.0/'

        # body = MyRequests.get_url_body(url=_url, headers=self.headers, params=params)
        # self.my_lg.info(str(body))

        # 设置代理ip
        tmp_proxies = MyRequests._get_proxies()
        self.proxy = tmp_proxies['http']
        # self.my_lg.info(tmp_proxies)

        s = requests.session()
        try:
            response = s.get(_url, headers=self.headers, params=params, proxies=tmp_proxies, timeout=13)  # 在requests里面传数据，在构造头时，注意在url外头的&xxx=也得先构造
            last_url = re.compile(r'\+').sub('', response.url)  # 转换后得到正确的url请求地址
            # self.my_lg.info(last_url)
            response = s.get(last_url, headers=self.headers, proxies=tmp_proxies, timeout=13)  # 在requests里面传数据，在构造头时，注意在url外头的&xxx=也得先构造
            body = response.content.decode('utf-8')
            # self.my_lg.info(str(body))
        except Exception:
            self.my_lg.error('requests.get()请求超时... 出错type: %s, goods_id: %s' % (str(type), str(goods_id)))
            self.my_lg.error('data为空!')
            self.result_data = {}  # 重置下，避免存入时影响下面爬取的赋值
            return {}

        try:
            assert body != '', '获取到的body为空值, 此处跳过! 出错type %s: , goods_id: %s' % (str(type), goods_id)
            data = re.compile('mtopjsonp3\((.*)\)').findall(body)[0]  # 贪婪匹配匹配所有
        except AssertionError or IndexError as e:
            self.my_lg.exception(e)
            self.result_data = {}
            return {}

        if data != '':
            try:
                data = json.loads(data)
            except Exception:
                self.my_lg.error('json.loads转换data时出错, 请检查! 出错type: %s, goods_id: %s' % (str(type), str(goods_id)))
                self.result_data = {}  # 重置下，避免存入时影响下面爬取的赋值
                return {}
            # pprint(data)

            if data.get('data', {}).get('trade', {}).get('redirectUrl', '') != '' and data.get('data', {}).get('seller', {}).get('evaluates') is None:
                '''
                ## 表示该商品已经下架, 原地址被重定向到新页面
                '''
                self.my_lg.info('@@@@@@ 该商品已经下架...')
                tmp_data_s = self.init_pull_off_shelves_goods(type)
                self.result_data = {}
                return tmp_data_s

            # 处理商品被转移或者下架导致页面不存在的商品
            if data.get('data').get('seller', {}).get('evaluates') is None:
                self.my_lg.error('data为空, 地址被重定向, 该商品可能已经被转移或下架, 出错type: %s, goods_id: %s' % (str(type), str(goods_id)))
                self.result_data = {}  # 重置下，避免存入时影响下面爬取的赋值
                return {}

            data['data']['rate'] = ''  # 这是宝贝评价
            data['data']['resource'] = ''  # 买家询问别人
            data['data']['vertical'] = ''  # 也是问和回答
            data['data']['seller']['evaluates'] = ''  # 宝贝描述, 卖家服务, 物流服务的评价值...
            result_data = data['data']

            # 处理result_data['apiStack'][0]['value']
            # self.my_lg.info(result_data.get('apiStack', [])[0].get('value', ''))
            result_data_apiStack_value = result_data.get('apiStack', [])[0].get('value', {})

            # 将处理后的result_data['apiStack'][0]['value']重新赋值给result_data['apiStack'][0]['value']
            result_data['apiStack'][0]['value'] = self._wash_result_data_apiStack_value(
                goods_id=goods_id,
                result_data_apiStack_value=result_data_apiStack_value
            )

            # 处理mockData
            mock_data = result_data['mockData']
            try:
                mock_data = json.loads(mock_data)
            except Exception:
                self.my_lg.error('json.loads转化mock_data时出错, 跳出 出错type: %s, goods_id: %s' % (str(type), str(goods_id)))
                self.result_data = {}  # 重置下，避免存入时影响下面爬取的赋值
                return {}
            mock_data['feature'] = ''
            # pprint(mock_data)
            result_data['mockData'] = mock_data

            # self.my_lg.info(str(result_data.get('apiStack', [])[0]))   # 可能会有{'name': 'esi', 'value': ''}的情况
            if result_data.get('apiStack', [])[0].get('value', '') == '':
                self.my_lg.error("result_data.get('apiStack', [])[0].get('value', '')的值为空....出错type: %s, goods_id: %s" % (str(type), goods_id))
                result_data['trade'] = {}
                self.result_data = {}  # 重置下，避免存入时影响下面爬取的赋值
                return {}
            else:
                result_data['trade'] = result_data.get('apiStack', [])[0].get('value', {}).get('trade', {})     # 用于判断该商品是否已经下架的参数
                # pprint(result_data['trade'])

            result_data['type'] = type
            result_data['goods_id'] = goods_id
            self.result_data = result_data
            # pprint(self.result_data)
            return result_data

        else:
            self.my_lg.error('data为空! 出错type: %s, goods_id: %s' % (str(type), str(goods_id)))
            self.result_data = {}  # 重置下，避免存入时影响下面爬取的赋值
            return {}

    def deal_with_data(self):
        '''
        得到需求数据
        :return:
        '''
        data = self.result_data
        # pprint(data)
        if data != {}:
            taobao = TaoBaoLoginAndParse(logger=self.my_lg)
            goods_id = data['goods_id']
            # 天猫类型
            tmall_type = data.get('type', 33)  # 33用于表示无法正确获取
            # self.my_lg.info(str(tmall_type))

            # 店铺名称
            shop_name = data['seller'].get('shopName', '')      # 可能不存在shopName这个字段

            # 掌柜
            account = data['seller'].get('sellerNick', '')

            # 商品名称
            title = data['item']['title']
            # 子标题
            sub_title = data['item'].get('subtitle', '')
            sub_title = re.compile(r'\n').sub('', sub_title)
            # 店铺主页地址
            # shop_name_url = 'https:' + data['seller']['taoShopUrl']
            # shop_name_url = re.compile(r'.m.').sub('.', shop_name_url)  # 手机版转换为pc版

            # 商品价格
            # price = data['apiStack'][0]['value']['price']['extraPrices'][0]['priceText']
            tmp_taobao_price = data['apiStack'][0].get('value', '').get('price').get('price').get('priceText', '')
            tmp_taobao_price = tmp_taobao_price.split('-')  # 如果是区间的话，分割成两个，单个价格就是一个
            # self.my_lg.info(str(tmp_taobao_price))
            if len(tmp_taobao_price) == 1:
                # 商品最高价
                # price = Decimal(tmp_taobao_price[0]).__round__(2)     # json不能处理decimal所以后期存的时候再处理
                price = tmp_taobao_price[0]
                # 商品最低价
                taobao_price = price
                # self.my_lg.info(str(price))
                # self.my_lg.info(str(taobao_price))
            else:
                # price = Decimal(tmp_taobao_price[1]).__round__(2)
                # taobao_price = Decimal(tmp_taobao_price[0]).__round__(2)
                price = tmp_taobao_price[1]
                taobao_price = tmp_taobao_price[0]
                # self.my_lg.info(str(price))
                # self.my_lg.info(str(taobao_price))

            # 商品库存
            goods_stock = data['apiStack'][0]['value'].get('skuCore', {}).get('sku2info', {}).get('0', {}).get('quantity', '')

            # 商品标签属性名称,及其对应id值
            detail_name_list, detail_value_list = taobao._get_detail_name_and_value_list(data=data)

            '''
            每个标签对应值的价格及其库存
            '''
            price_info_list = taobao._get_price_info_list(data=data, detail_value_list=detail_value_list)

            # 所有示例图片地址
            all_img_url = taobao._get_all_img_url(tmp_all_img_url=data['item']['images'])
            # self.my_lg.info(str(all_img_url))

            # 详细信息p_info
            p_info = taobao._get_p_info(tmp_p_info=data.get('props').get('groupProps'))  # tmp_p_info 一个list [{'内存容量': '32GB'}, ...]
            if p_info != []:
                p_info = [{
                    'id': 0,
                    'name': _i.get('p_name', ''),
                    'value': _i.get('p_value', ''),
                } for _i in p_info]

            '''
            div_desc
            '''
            # 手机端描述地址
            if data.get('item').get('taobaoDescUrl') is not None:
                phone_div_url = 'https:' + data['item']['taobaoDescUrl']
            else:
                phone_div_url = ''

            # pc端描述地址
            if data.get('item').get('taobaoPcDescUrl') is not None:
                pc_div_url = 'https:' + data['item']['taobaoPcDescUrl']
                # self.my_lg.info(phone_div_url)
                # self.my_lg.info(pc_div_url)

                div_desc = taobao.get_div_from_pc_div_url(pc_div_url, goods_id)
                # self.my_lg.info(div_desc)
                if div_desc == '':
                    self.my_lg.error('该商品的div_desc为空! 出错goods_id: %s' % str(goods_id))
                    self.result_data = {}
                    return {}

                # self.driver.quit()
                gc.collect()
            else:
                pc_div_url = ''
                div_desc = ''

            '''
            后期处理
            '''
            # 后期处理detail_name_list, detail_value_list
            detail_name_list = [{'spec_name': i[0]} for i in detail_name_list]

            # 商品标签属性对应的值, 及其对应id值
            if data.get('skuBase').get('props') is None:
                pass
            else:
                tmp_detail_value_list = [item['values'] for item in data.get('skuBase', '').get('props', '')]
                # self.my_lg.info(str(tmp_detail_value_list))
                detail_value_list = []
                for item in tmp_detail_value_list:
                    tmp = [i['name'] for i in item]
                    # self.my_lg.info(str(tmp))
                    detail_value_list.append(tmp)  # 商品标签属性对应的值
                    # pprint(detail_value_list)

            is_delete = 0
            # 2017-10-16 1. 先通过buyEnable字段来判断商品是否已经下架
            if data.get('trade', {}) != {}:
                is_buy_enable = data.get('trade', {}).get('buyEnable')
                # self.my_lg.info(str(is_buy_enable))
                if is_buy_enable == 'false':
                    is_delete = 1

            # * 2018-4-17 新增再加一个判断是否下架
            _r = data.get('mockData', {}).get('trade', {}).get('buyEnable')     # bool类型 True or False
            # self.my_lg.info(type(_r))
            if _r is not None:
                if _r:
                    is_delete = 0

            # 2017-10-16 2. 此处再考虑名字中显示下架的商品
            if re.compile(r'下架').findall(title) != []:
                if re.compile(r'待下架').findall(title) != []:
                    is_delete = 0
                elif re.compile(r'自动下架').findall(title) != []:
                    is_delete = 0
                else:
                    is_delete = 1
            # self.my_lg.info('is_delete = %s' % str(is_delete))

            # 月销量
            try:
                sell_count = str(data.get('apiStack', [])[0].get('value', {}).get('item', {}).get('sellCount', ''))
            except:
                sell_count = '0'
                # self.my_lg.info(sell_count)

            try: del taobao
            except: pass
            result = {
                'shop_name': shop_name,                 # 店铺名称
                'account': account,                     # 掌柜
                'title': title,                         # 商品名称
                'sub_title': sub_title,                 # 子标题
                'price': price,                         # 商品价格
                'taobao_price': taobao_price,           # 淘宝价
                'goods_stock': goods_stock,             # 商品库存
                'detail_name_list': detail_name_list,   # 商品标签属性名称
                'detail_value_list': detail_value_list, # 商品标签属性对应的值
                'price_info_list': price_info_list,     # 要存储的每个标签对应规格的价格及其库存
                'all_img_url': all_img_url,             # 所有示例图片地址
                'p_info': p_info,                       # 详细信息标签名对应属性
                'pc_div_url': pc_div_url,               # pc端描述地址
                'div_desc': div_desc,                   # div_desc
                'sell_count': sell_count,               # 月销量
                'is_delete': is_delete,                 # 是否下架判断
                'type': tmall_type,                     # 天猫类型
            }
            # pprint(result)
            # self.my_lg.info(str(result))
            # wait_to_send_data = {
            #     'reason': 'success',
            #     'data': result,
            #     'code': 1
            # }
            # json_data = json.dumps(wait_to_send_data, ensure_ascii=False)
            # print(json_data)
            gc.collect()
            return result

        else:
            self.my_lg.info('待处理的data为空的dict, 该商品可能已经转移或者下架')
            # return {
            #     'is_delete': 1,
            # }
            return {}

    def to_right_and_update_data(self, data, pipeline):
        '''
        实时更新数据
        :param data:
        :param pipeline:
        :return:
        '''
        data_list = data
        tmp = {}
        tmp['goods_id'] = data_list['goods_id']  # 官方商品id
        '''
        时区处理，时间处理到上海时间
        '''
        tz = pytz.timezone('Asia/Shanghai')  # 创建时区对象
        now_time = datetime.datetime.now(tz)
        # 处理为精确到秒位，删除时区信息
        now_time = re.compile(r'\..*').sub('', str(now_time))
        # 将字符串类型转换为datetime类型
        now_time = datetime.datetime.strptime(now_time, '%Y-%m-%d %H:%M:%S')

        tmp['modfiy_time'] = now_time  # 修改时间

        tmp['shop_name'] = data_list['shop_name']  # 公司名称
        tmp['title'] = data_list['title']  # 商品名称
        tmp['sub_title'] = data_list['sub_title']  # 商品子标题
        tmp['link_name'] = ''  # 卖家姓名
        tmp['account'] = data_list['account']  # 掌柜名称
        tmp['month_sell_count'] = data_list['sell_count']  # 月销量

        # 设置最高价price， 最低价taobao_price
        tmp['price'] = Decimal(data_list['price']).__round__(2)
        tmp['taobao_price'] = Decimal(data_list['taobao_price']).__round__(2)
        tmp['price_info'] = []  # 价格信息

        tmp['detail_name_list'] = data_list['detail_name_list']  # 标签属性名称

        """
        得到sku_map
        """
        tmp['price_info_list'] = data_list.get('price_info_list')  # 每个规格对应价格及其库存

        tmp['all_img_url'] = data_list.get('all_img_url')  # 所有示例图片地址

        tmp['p_info'] = data_list.get('p_info')  # 详细信息
        tmp['div_desc'] = data_list.get('div_desc')  # 下方div

        # # 采集的来源地
        # if data_list.get('type') == 0:
        #     tmp['site_id'] = 3  # 采集来源地(天猫)
        # elif data_list.get('type') == 1:
        #     tmp['site_id'] = 4  # 采集来源地(天猫超市)
        # elif data_list.get('type') == 2:
        #     tmp['site_id'] = 6  # 采集来源地(天猫国际)
        tmp['is_delete'] = data_list.get('is_delete')  # 逻辑删除, 未删除为0, 删除为1

        tmp['my_shelf_and_down_time'] = data_list.get('my_shelf_and_down_time')
        tmp['delete_time'] = data_list.get('delete_time')

        tmp['_is_price_change'] = data_list.get('_is_price_change')
        tmp['_price_change_info'] = data_list.get('_price_change_info')

        pipeline.update_tmall_table(tmp, logger=self.my_lg)

    def old_tmall_goods_insert_into_new_table(self, data, pipeline):
        '''
        老库数据规范，然后存入
        :param data:
        :param pipeline:
        :return:
        '''
        data_list = data
        tmp = {}
        tmp['username'] = data_list['username']
        tmp['spider_url'] = data_list['goods_url']
        tmp['main_goods_id'] = data_list['main_goods_id']
        tmp['goods_id'] = data_list['goods_id']  # 官方商品id

        '''
        时区处理，时间处理到上海时间
        '''
        tz = pytz.timezone('Asia/Shanghai')  # 创建时区对象
        now_time = datetime.datetime.now(tz)
        # 处理为精确到秒位，删除时区信息
        now_time = re.compile(r'\..*').sub('', str(now_time))
        # 将字符串类型转换为datetime类型
        now_time = datetime.datetime.strptime(now_time, '%Y-%m-%d %H:%M:%S')

        tmp['deal_with_time'] = now_time  # 操作时间
        tmp['modfiy_time'] = now_time  # 修改时间

        tmp['shop_name'] = data_list['shop_name']  # 公司名称
        tmp['title'] = data_list['title']  # 商品名称
        tmp['sub_title'] = data_list['sub_title']  # 商品子标题
        tmp['link_name'] = ''  # 卖家姓名
        tmp['account'] = data_list['account']  # 掌柜名称
        tmp['month_sell_count'] = data_list['sell_count']  # 月销量

        # 设置最高价price， 最低价taobao_price
        tmp['price'] = Decimal(data_list['price']).__round__(2)
        tmp['taobao_price'] = Decimal(data_list['taobao_price']).__round__(2)
        tmp['price_info'] = []  # 价格信息

        tmp['detail_name_list'] = data_list['detail_name_list']  # 标签属性名称

        """
        得到sku_map
        """
        tmp['price_info_list'] = data_list.get('price_info_list')  # 每个规格对应价格及其库存

        tmp['all_img_url'] = data_list.get('all_img_url')  # 所有示例图片地址

        tmp['p_info'] = data_list.get('p_info')  # 详细信息
        tmp['div_desc'] = data_list.get('div_desc')  # 下方div

        # # 采集的来源地
        if data_list.get('type') == 0:
            tmp['site_id'] = 3  # 采集来源地(天猫)
        elif data_list.get('type') == 1:
            tmp['site_id'] = 4  # 采集来源地(天猫超市)
        elif data_list.get('type') == 2:
            tmp['site_id'] = 6  # 采集来源地(天猫国际)
        else:
            print('type为未知值, 导致site_id设置失败, 此处跳过!')
            return False

        tmp['is_delete'] = data_list.get('is_delete')  # 逻辑删除, 未删除为0, 删除为1

        # tmp['my_shelf_and_down_time'] = data_list.get('my_shelf_and_down_time')
        # tmp['delete_time'] = data_list.get('delete_time')

        pipeline.old_tmall_goods_insert_into_new_table(tmp)
        return True

    def init_pull_off_shelves_goods(self, type):
        '''
        初始化下架商品的数据
        :return:
        '''
        is_delete = 1
        result = {
            'shop_name': '',  # 店铺名称
            'account': '',  # 掌柜
            'title': '',  # 商品名称
            'sub_title': '',  # 子标题
            'price': 0,  # 商品价格
            'taobao_price': 0,  # 淘宝价
            'goods_stock': '',  # 商品库存
            'detail_name_list': [],  # 商品标签属性名称
            'detail_value_list': [],  # 商品标签属性对应的值
            'price_info_list': [],  # 要存储的每个标签对应规格的价格及其库存
            'all_img_url': [],  # 所有示例图片地址
            'p_info': [],  # 详细信息标签名对应属性
            'pc_div_url': '',  # pc端描述地址
            'div_desc': '',  # div_desc
            'sell_count': '0',  # 月销量
            'is_delete': is_delete,  # 是否下架判断
            'type': type,  # 天猫类型
        }
        return result

    def _wash_result_data_apiStack_value(self, goods_id, result_data_apiStack_value):
        '''
        清洗result_data_apiStack_value
        :param goods_id:
        :param result_data_apiStack_value:
        :return:
        '''
        try:
            result_data_apiStack_value = json.loads(result_data_apiStack_value)

            result_data_apiStack_value['vertical'] = ''
            result_data_apiStack_value['consumerProtection'] = ''  # 7天无理由退货
            result_data_apiStack_value['feature'] = ''
            result_data_apiStack_value['layout'] = ''
            result_data_apiStack_value['delivery'] = ''  # 发货地到收到地
            result_data_apiStack_value['resource'] = ''  # 优惠券
            # result_data_apiStack_value['item'] = ''       # 不能注释否则得不到月销量
            # pprint(result_data_apiStack_value)
        except Exception:
            self.my_lg.error("json.loads转换出错，得到result_data['apiStack'][0]['value']值可能为空，此处跳过 出错goods_id: %s" % str(goods_id))
            result_data_apiStack_value = ''
            pass

        return result_data_apiStack_value

    def _set_params(self, goods_id):
        '''
        设置params
        :param goods_id:
        :return:
        '''
        params = (
            ('jsv', '2.4.8'),
            ('appKey', '12574478'),
            ('t', str(time.time().__round__()) + str(randint(100, 999))),
            # ('sign', 'de765f1adf3bdc4a07687d45fd10a6b3'),
            ('api', 'mtop.taobao.detail.getdetail'),
            ('v', '6.0'),
            ('dataType', 'jsonp'),
            ('ttid', '2017@taobao_h5_6.6.0'),
            ('AntiCreep', 'true'),
            ('type', 'jsonp'),
            ('callback', 'mtopjsonp3'),
            ('data', json.dumps({'itemNumId': goods_id})),
        )

        return params

    def get_goods_id_from_url(self, tmall_url):
        '''
        得到合法url的goods_id
        :param tmall_url:
        :return: a list [0, '1111111'] [2, '1111111', 'https://ssss'] 0:表示天猫常规商品, 1:表示天猫超市, 2:表示天猫国际, 返回为[]表示解析错误
        '''
        is_tmall_url = re.compile(r'https://detail.tmall.com/item.htm.*?').findall(tmall_url)
        if is_tmall_url != []:                  # 天猫常规商品
            tmp_tmall_url = re.compile(r'https://detail.tmall.com/item.htm.*?id=(\d+)&{0,20}.*?').findall(tmall_url)
            if tmp_tmall_url != []:
                is_tmp_tmp_tmall_url = re.compile(r'https://detail.tmall.com/item.htm.*?&id=(\d+)&{0,20}.*?').findall(tmall_url)
                if is_tmp_tmp_tmall_url != []:
                    goods_id = is_tmp_tmp_tmall_url[0]
                else:
                    goods_id = tmp_tmall_url[0]
            else:
                tmall_url = re.compile(r';').sub('', tmall_url)
                goods_id = re.compile(r'https://detail.tmall.com/item.htm.*?id=(\d+)').findall(tmall_url)[0]
            self.my_lg.info('------>>>| 得到的天猫商品id为:%s' % goods_id)
            return [0, goods_id]
        else:
            is_tmall_supermarket = re.compile(r'https://chaoshi.detail.tmall.com/item.htm.*?').findall(tmall_url)
            if is_tmall_supermarket != []:      # 天猫超市
                tmp_tmall_url = re.compile(r'https://chaoshi.detail.tmall.com/item.htm.*?id=(\d+)&.*?').findall(tmall_url)
                if tmp_tmall_url != []:
                    goods_id = tmp_tmall_url[0]
                else:
                    tmall_url = re.compile(r';').sub('', tmall_url)
                    goods_id = re.compile(r'https://chaoshi.detail.tmall.com/item.htm.*?id=(\d+)').findall(tmall_url)[0]
                self.my_lg.info('------>>>| 得到的天猫商品id为:%s' % goods_id)
                return [1, goods_id]
            else:
                is_tmall_hk = re.compile(r'https://detail.tmall.hk/.*?item.htm.*?').findall(tmall_url)      # 因为中间可能有国家的地址 如https://detail.tmall.hk/hk/item.htm?
                if is_tmall_hk != []:           # 天猫国际， 地址中有地域的也能正确解析, 嘿嘿 -_-!!!
                    tmp_tmall_url = re.compile(r'https://detail.tmall.hk/.*?item.htm.*?id=(\d+)&.*?').findall(tmall_url)
                    if tmp_tmall_url != []:
                        goods_id = tmp_tmall_url[0]
                    else:
                        tmall_url = re.compile(r';').sub('', tmall_url)
                        goods_id = re.compile(r'https://detail.tmall.hk/.*?item.htm.*?id=(\d+)').findall(tmall_url)[0]
                    before_url = re.compile(r'https://detail.tmall.hk/.*?item.htm').findall(tmall_url)[0]
                    self.my_lg.info('------>>>| 得到的天猫商品id为:%s' % goods_id)
                    return [2, goods_id, before_url]
                else:
                    self.my_lg.info('天猫商品url错误, 非正规的url, 请参照格式(https://detail.tmall.com/item.htm)开头的...')
                    return []

    def __del__(self):
        try:
            del self.my_lg
            del self.msg
        except:
            pass
        gc.collect()

if __name__ == '__main__':
    tmall = TmallParse()
    while True:
        tmall_url = input('请输入待爬取的天猫商品地址: ')
        tmall_url = tmall_url.strip('\n').strip(';')
        goods_id = tmall.get_goods_id_from_url(tmall_url)   # 返回一个dict类型
        # print(goods_id)
        if goods_id != []:
            data = tmall.get_goods_data(goods_id=goods_id)
            result = tmall.deal_with_data()
            # pprint(result)
            # print(result)
            gc.collect()
        else:
            print('获取到的天猫商品地址无法解析，地址错误')

