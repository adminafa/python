# coding = utf-8

'''
@author = super_fazai
@File    : urllib_parse_quote.py
@Time    : 2017/8/17 11:03
@connect : superonesfazai@gmail.com
'''

"""
通过urlencode()进行编码时,可能在查询参数时导致解析问题
可以使用quote()或quote_plus()功能作为一个安全的方式
来直接引用它们来避免服务器的解析错误
"""

from urllib.parse import quote, quote_plus, urlencode

url = 'http://localhost:8080/~hellmann/'
print('urlencode() :', urlencode({'url': url}))
print('quote()     :', quote(url))
print('quote_plus():', quote_plus(url))     # 这个方法引用与原url更为相似的

print('分割线'.center(40, '-'))

# 对应通过unquote()或者unquote_plus来还原url
from urllib.parse import unquote, unquote_plus

print(unquote('http%3A//localhost%3A8080/%7Ehellmann/'))
print(unquote_plus(
    'http%3A%2F%2Flocalhost%3A8080%2F%7Ehellmann%2F'
))

'''
测试结果:
urlencode() : url=http%3A%2F%2Flocalhost%3A8080%2F%7Ehellmann%2F
quote()     : http%3A//localhost%3A8080/%7Ehellmann/
quote_plus(): http%3A%2F%2Flocalhost%3A8080%2F%7Ehellmann%2F
------------------分割线-------------------
http://localhost:8080/~hellmann/
http://localhost:8080/~hellmann/
'''