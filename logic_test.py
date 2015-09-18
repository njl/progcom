import os.path
import random

import pytest
import mock

import logic as l

l._M_OLD = l._MANDRILL
l._MANDRILL = mock.Mock()


@pytest.fixture(autouse=True)
def transact():
    """Since the whole point of bcrypt is to be slow, it helps to dial the knob
        down while testing."""
    l._SALT_ROUNDS=4
    e = l._e
    q = "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    for table in e.execute(q).fetchall():
        table = table[0]
        e.execute('DROP TABLE IF EXISTS %s CASCADE' % table)
    sql = open(os.path.join(os.path.dirname(__file__), 'tables.sql')).read()
    e.execute(sql)   

def test_pw():
    pw = [u'blah blah blah', 'blah blah blah',
            u"\u2603", 'Blah Blah Blah']
    for p in pw:
        s = l._mangle_pw(p)
        assert s
        assert s == l._mangle_pw(p, s)

def test_user_basics():
    for n in range(20):
        assert l.add_user(u'{}@example.com'.format(n), u'Name {}'.format(n),
                            u'pw{}'.format(n))


    email = u'ned@example.com'
    name = u'Ned Jackson Lovely'
    pw = u'password'

    assert not l.check_pw(email, pw)

    uid = l.add_user(email, name, pw)
    
    assert len(l.list_users()) == 21

    for user in l.list_users():
        assert not user.approved_on 

    l.approve_user(uid)

    for user in l.list_users():
        assert not user.approved_on if user.id != uid else user.approved_on


    assert l.get_user(uid).display_name == name

    assert l.check_pw(email, pw)
    assert l.check_pw(email.upper(), pw)
    assert not l.check_pw(email, pw.upper())

    pw2 = u'\u2603'
    l.change_pw(uid, pw2)

    assert not l.check_pw(email, pw)
    assert l.check_pw(email, pw2)


data = {'id': 123, 'title': 'Title Here', 'category': 'Python',
        'duration': '30', 'description':'the description goes here.',
        'audience': 'People who want to learn about python',
        'python_level': 'Intermediate', 'objectives': 'Talk about Python',
        'abstract':'This is an abstract', 
        'outline':"First I'll talk about one thing, then another",
        'additional_notes': 'Additional stuff',
        'additional_requirements':'I need a fishtank',
        'authors': [{'name':'Person Personson','email':'person@example.com'}]}

def test_proposal_basics():
    assert l.add_proposal(data)
    assert not l.add_proposal(data)
    assert l.get_proposal(data['id']).outline == data['outline']

    changed = data.copy()
    changed['abstract'] = 'This is a longer abstract.'

    assert l.add_proposal(changed)

def test_voting_basics():
    l.add_proposal(data)
    uid = l.add_user('bob@example.com', 'Bob', 'bob')
    assert not l.get_votes(123)
    assert not l.vote(uid, 123, True)
    assert not l.get_votes(123)

    assert l.get_proposal(123).vote_count == 0

    l.approve_user(uid)

    assert l.vote(uid, 123, True)
    assert l.get_votes(123)[0].yea
    assert l.get_proposal(123).vote_count == 1

    assert l.vote(uid, 123, False)
    assert len(l.get_votes(123)) == 1
    assert not l.get_votes(123)[0].yea
    assert l.get_proposal(123).vote_count == 1


def test_needs_votes():
    proposals = []
    users = {}
    for n in range(1,10):
        prop = data.copy()
        prop['id'] = n*2
        prop['abstract'] = 'Proposal {}'.format(n)
        email = '{}@example.com'.format(n)
        uid = l.add_user(email, email, email)
        l.approve_user(uid)
        users[email] = uid
        prop['authors'] = [{'email':email, 'name':'foo'}]
        l.add_proposal(prop)
        proposals.append(n*2)

    non_author_email = 'none@example.com'
    non_author_id = l.add_user(non_author_email, non_author_email, non_author_email)
    l.approve_user(non_author_id)

    random.seed(0)
    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes(non_author_email, non_author_id))
    assert seen_ids == set(proposals)

    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes('2@example.com', users['2@example.com']))
    not_2_proposals = set(proposals)
    not_2_proposals.remove(4)
    assert seen_ids == not_2_proposals

    for n in range(1, 9):
        l.vote(users['8@example.com'], n*2, True)

    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes(non_author_email, non_author_id))
    assert seen_ids == set([18])

    l.vote(users['8@example.com'], 18, True)

    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes(non_author_email, non_author_id))
    assert seen_ids == set(proposals)

def test_reasons():
    assert l.get_reasons() == []
    l.add_reason('Bob')
    assert l.get_reasons() == ['Bob']


def test_discussion():
    l.add_proposal(data)
    proposal = data['id']

    users = []
    for n in range(10):
        uid = l.add_user('{}@example.com'.format(n), 'name {}'.format(n), 'blah')
        l.approve_user(uid)
        users.append(uid)

    l.add_to_discussion(users[0], proposal, 'Lorem ipsum')

    for u in users:
        assert len(l.get_unread(u)) == 0

    assert len(l.get_discussion(proposal)) == 1
    assert l.get_discussion(proposal)[0].body == 'Lorem ipsum'

    l.add_to_discussion(users[-1], proposal, 'dolor sit')
    assert [x.id for x in l.get_unread(users[0])] == [proposal]
    l.add_to_discussion(users[-1], proposal, 'amet, consectetur')
    assert [x.id for x in l.get_unread(users[0])] == [proposal]

    l.mark_read(users[0], proposal)
    for u in users:
        assert len(l.get_unread(u)) == 0

    l.add_to_discussion(users[0], proposal, 'LOREM IPSUM')
    assert l.get_discussion(proposal)[-1].body == 'LOREM IPSUM'
    assert l.get_discussion(proposal)[0].body == 'Lorem ipsum'
