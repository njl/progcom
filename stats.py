#!/usr/bin/env python
import sys
import json
import collections
import logic as l

def parse_log(f):

    prefix = 'INFO:logic:'
    seen = collections.Counter()
    for row in open(f):
        if not row.startswith(prefix):
            continue
        seen[json.loads(row[len(prefix):])['key']] += 1
    return seen

def avg(v):
    v = list(v)
    return sum(float(x) for x in v)/len(v)

def main():
    actions = parse_log(sys.argv[1])

    print '\nScreening'

    q = 'SELECT count(*) FROM proposals'
    proposal_count = l.scalar(q)
    print 'There were {} proposals.'.format(proposal_count)

    q = 'SELECT count(*), voter FROM votes group by voter'
    print '{} voters did '.format(len(l.fetchall(q)))

    q = 'SELECT count(*) FROM votes'
    print '{:,} reviews'.format(actions['vote'])

    q = 'SELECT COUNT(*) FROM votes WHERE nominate'
    print 'and gave {} nominations.'.format(l.scalar(q))

    q = 'SELECT id from discussion'
    print '{:,} messages were written,'.format(len(l.fetchall(q)))

    q = 'SELECT id from discussion WHERE feedback'
    print '{:,} of them feedback to proposal authors.'.format(len(l.fetchall(q)))

    q = 'SELECT count(*), proposal from VOTES group by proposal order by count'
    votes = l.fetchall(q)
    print 'Every proposal received at least {} reviews,'.format(votes[0].count)

    full_coverage = sum(1 for x in l.list_users() 
                        if (x.votes + x.proposals_made) == proposal_count)
    print 'and {} voters performed the incredible task of reviewing all of the proposals.'.format(full_coverage)



    print '\n\n'

    q = 'SELECT COUNT(*) FROM proposals WHERE batchgroup is not null'
    print '{} talks made it into the second round,'.format(l.scalar(q))

    q = '''SELECT COUNT(*), batchgroup FROM proposals WHERE batchgroup is not null
                group by batchgroup'''
    print 'where they were grouped into {} batches.'.format(len(l.fetchall(q)))

    q = 'SELECT count(*) FROM batchvotes'
    batch_vote_count = l.scalar(q)
    print '{:,} reviews happened,'.format(actions['vote_group'],
                                                    batch_vote_count)

    q= 'SELECT id from batchmessages'
    print '{} more messages were sent, and'.format(len(l.fetchall(q)))

    q = 'SELECT count(*), voter from batchvotes group by voter'
    print '{} voters participated.'.format(len(l.fetchall(q)))


    q = '''SELECT count(*), batchgroup from batchvotes group by batchgroup
            order by count'''
    batch_count = l.fetchall(q)
    print 'Every batch got at least {} reviews'.format(batch_count[0].count)

    print 'to arrive at our final 95 accepted talks!'


if __name__ == '__main__':
    main()
