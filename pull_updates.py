#!/usr/bin/env python
import os
from hashlib import sha1
from calendar import timegm
from datetime import datetime

import pytz
import requests

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
            'X-API-Key': API_KEY,
            'X-API-Signature': sha1(base_string.encode('utf-8')).hexdigest(),
            'X-API-Timestamp': timestamp,
            }
    url = 'http://{}{}'.format(API_HOST, uri)
    return requests.get(url, headers=headers).json()

def fetch_ids():
    raw = api_call('/2016/pycon_api/proposals/?type=talk')
    #print len(raw['data'])
    return [x['id'] for x in raw['data']]

def fetch_talk(id):
    rv = api_call('/2016/pycon_api/proposals/{}/'.format(id))['data']
    rv['authors'] = rv['speakers']
    del rv['speakers']
    rv.update(rv['details'])
    del rv['details']
    return rv

def main():
    for id in fetch_ids():
        #print 'FETCHING {}'.format(id)
        proposal = fetch_talk(id)
        l.add_proposal(proposal)


if __name__ == '__main__':
    main()
