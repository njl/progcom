#!/usr/bin/env python
from jinja2.utils import generate_lorem_ipsum
import logic as l
import logic_test as lt
import random

def words(mn, mx):
    return generate_lorem_ipsum(n=1, min=mn, max=mx, html=False)[:-1]

def ipsum(n, **kwargs):
    kwargs['html'] = False

def main():
    lt.transact()
    emails = ['user{}@example.com'.format(n) for n in range(50)]
    for e in emails[:25]:
        uid = l.add_user(e, e.split('{} Person'.format(e.split('@')[0])), 'abc123')
        l.approve_user(uid)

    proposal_ids = []
    for n in range(200):
        data = {'id': n*2, 'authors': [{'email': random.choice(emails),
                                        'name': 'Speaker Name Here'}],
                'title': words(3,8),
                'category': words(1,2),
                'duration': '30 minutes',
                'description': ipsum(4),
                'audience': ipsum(1),
                'python_level': 'Novice',
                'objectives': ipsum(1),
                'abstract': ipsum(1),
                'outline': ipsum(5),
                'additional_notes': ipsum(1),
                'additional_requirements': ipsum(1)}
        l.add_proposal(data)
        proposal_ids.append(n*2)

    random.shuffle(proposal_ids)
    proposal_ids = proposal_ids[:70]
    for n in range(0, len(proposal_ids), 5):
        l.create_group(words(2,4),
                proposal_ids[n:n+5])


if __name__ == '__main__':
    main()
