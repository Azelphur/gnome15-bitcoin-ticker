# -*- coding: utf-8 -*-

import urllib
import json

exchanges = {'MtGox' :
                { 'fields' : ['ticker', 'last'],
                  'url' : 'https://mtgox.com/api/0/data/ticker.php',
                  'symbol' : '$'
                },
             'Intersango' :
                { 'fields' : ['last'],
                  'url' : 'https://intersango.com/api/ticker.php?currency_pair_id=1',
                  'symbol' : '£'
                },
             'BTCe' :
                { 'fields' : ['ticker', 'last'],
                  'url' : 'https://btc-e.com/api/2/1/ticker',
                  'symbol' : '$',
                }
             }

def getRate(exchange):
    if not exchange in exchanges:
        raise BaseException('Exchange does not exist')
    u = urllib.urlopen(exchanges[exchange]['url'])
    data = u.read()
    feed = json.loads(data)
    rate = feed
    for field in exchanges[exchange]['fields']:
        rate = rate[field]
    rate = float(rate)
    return "%s%.2f" % (exchanges[exchange]['symbol'], rate)

def getExchanges():
    exchange_list = []
    for exchange in exchanges:
        exchange_list.append(exchange)
    return exchange_list
