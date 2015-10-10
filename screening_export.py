#!/usr/bin/env python
import sys
import json

import logic as l



def main(target):
    data = [x._asdict()
                for x in l.fetchall('SELECT yea, proposal, reason FROM votes')]
    with open(target, 'w') as out:
        json.dump(data, out)

if __name__ == '__main__':
    main(sys.argv[1])
