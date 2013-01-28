# -*- coding: utf-8 -*-

import urllib2
import json
from decimal import Decimal

def getJSON(url):
    u = urllib2.urlopen(url)
    data = u.read()
    feed = json.loads(data)
    return feed

def MtGox(currency):
    j = getJSON("https://mtgox.com/api/1/BTC%s/ticker" % (currency))
    data = {}
    for i in ["last", "avg", "high", "low"]:
        data[i] = Decimal(j['return'][i]['value'])

    data["volume"] = Decimal(j['return']["vol"]['value'])
    data["bid"] = Decimal(j['return']["buy"]['value'])
    data["ask"] = Decimal(j['return']["sell"]['value'])
    data["spread"] = data["ask"]-data["bid"]
    return data

def getRate(exchange, currency):
    if exchange not in exchanges or currency not in exchanges[exchange]['currencies']:
        return None
    data = exchanges[exchange]['function'](currency)
    return data

def getExchanges():
    exchange_list = []
    for exchange in exchanges:
        exchange_list.append(exchange)
    return exchange_list

def getCurrencies(exchange):
    return exchanges[exchange]['currencies']

exchanges = {
                'MtGox' : 
                {
                    'currencies' : ['USD', 'EUR', 'JPY', 'CAD', 'GBP', 'CHF', 'RUB', 'AUD', 'SEK', 'DKK', 'HKD', 'PLN', 'CNY', 'SGD', 'THB', 'NZD', 'NOK'],
                    'function' : MtGox
                },
            }
