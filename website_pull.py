import os
from hashlib import sha1
import pytz
from calendar import timegm
from datetime import datetime

import requests

def get(uri):
    api_key = os.environ['PYCON_AUTH_KEY']
    api_secret = os.environ['PYCON_SECRET']
    method = 'GET'
    body = ''


    timestamp = timegm(datetime.now(tz=pytz.UTC).timetuple())
    base_string = unicode(''.join((
        api_secret,
        unicode(timestamp),
        method.upper(),
        uri,
        body,
        )))

    headers = {
            'X-API-Key': api_key,
            'X-API-Signature': sha1(base_string.encode('utf-8')).hexdigest(),
            'X-API-Timestamp': timestamp,
            }
    return requests.get('http://us.pycon.org'+uri, headers=headers)
