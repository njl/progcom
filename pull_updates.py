#!/usr/bin/env python
import os
from hashlib import sha1
from calendar import timegm
from datetime import datetime
import sys

import pytz
import requests
from raven import Client
from simplejson import JSONDecodeError
from requests.exceptions import RequestException

import logic as l

API_KEY = os.environ['PYCON_API_KEY']
API_SECRET = os.environ['PYCON_API_SECRET']
API_HOST = os.environ['PYCON_API_HOST']

def api_call(uri):
    method = 'GET'
    body = ''

    timestamp = timegm(datetime.now(tz=pytz.UTC).timetuple())
    base_string = unicode(''.join((
        API_SECRET,
        unicode(timestamp),
        method.upper(),
        uri,
        body,
        )))

    headers = {
            'X-API-Key': str(API_KEY),
            'X-API-Signature': str(sha1(base_string.encode('utf-8')).hexdigest()),
            'X-API-Timestamp': str(timestamp),
            }
    url = 'http://{}{}'.format(API_HOST, uri)
    try:
        return requests.get(url, headers=headers).json()
    except JSONDecodeError, RequestException:
        sys.exit(1)

"""
TALK_IDS_FORCE = [1553, 1554, 1555, 1556, 1557, 1559, 1560, 1561, 1562, 1565,
                  1566, 1568, 1569, 1570, 1571, 1572, 1573, 1576, 1577, 1579, 1580,
                  1581, 1582, 1583, 1584, 1585, 1586, 1587, 1590, 2057, 2134,
                  2135, 2136, 2143, 2144, 2145, 2210]
"""
TALK_IDS_FORCE = []

def fetch_ids():
    raw = api_call('/2017/pycon_api/proposals/?type=talk&limit=5000&status=undecided')
    #print len(raw['data'])
    rv = [x['id'] for x in raw['data']]
    return list(set(TALK_IDS_FORCE + rv + l.get_all_proposal_ids()))

def fetch_talk(id):
    rv = api_call('/2017/pycon_api/proposals/{}/'.format(id))
    if not rv or 'data' not in rv:
        return {}
    rv = rv['data']
    rv['authors'] = rv['speakers']
    del rv['speakers']
    rv.update(rv['details'])
    del rv['details']
    return rv

def main():
    for id in fetch_ids():
        #print 'FETCHING {}'.format(id)
        proposal = fetch_talk(id)
        if proposal:
            l.add_proposal(proposal)


raven_client = Client(os.environ['SENTRY_DSN'])
if __name__ == '__main__':
    try:
        main()
    except:
        raven_client.captureException()
        sys.exit(1)

