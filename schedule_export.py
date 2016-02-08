#!/usr/bin/env python

import logic as l
import csv
import sys

def main(out):
    q = 'SELECT schedules.*, proposals.title from schedules JOIN proposals ON proposals.id=schedules.proposal'
    keys = ('proposal', 'day', 'room', 'time', 'duration', 'title')
    with open(out, 'wb') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(keys)
        for row in l.fetchall(q):
            writer.writerow(list(unicode(getattr(row, k)).encode('utf-8') for k in keys))

if __name__ == "__main__":
    main(sys.argv[1])
