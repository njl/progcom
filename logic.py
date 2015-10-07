from collections import namedtuple, defaultdict, Counter
import os 
import random
import json

import itsdangerous
import mandrill

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from jinja2 import Environment, FileSystemLoader

"""
Some DB wrapper stuff
"""
_e = create_engine(os.environ['PSQL_CONNECTION_STRING'])

__TUPLE_CACHE = {}
def build_tuple(keys):
    keys = tuple(keys)
    if keys not in __TUPLE_CACHE:
        name = 'T{}'.format(len(__TUPLE_CACHE))
        __TUPLE_CACHE[keys] = namedtuple(name, keys)
    return __TUPLE_CACHE[keys]

def execute(*args, **kwargs):
    _e.execute(*args, **kwargs)

def fetchone(*args, **kwargs):
    result = _e.execute(*args, **kwargs)
    T = build_tuple(result.keys())
    result = result.fetchone()
    if not result:
        return None
    return T(*result)

def fetchall(*args, **kwargs):
    result = _e.execute(*args, **kwargs)
    T = build_tuple(result.keys())
    rv = []
    for row in result.fetchall():
        rv.append(T(*row))
    return rv

def scalar(*args, **kwargs):
    return _e.scalar(*args, **kwargs)

"""
User management
"""
_SALT_ROUNDS=12
def _mangle_pw(pw, salt=None):
    if not salt:
        salt = bcrypt.gensalt(rounds=_SALT_ROUNDS)
    else:
        salt = salt.encode('utf-8')
    return bcrypt.hashpw(pw.encode('utf-8'), salt)

def add_user(email, display_name, pw):
    q = '''INSERT INTO users (email, display_name, pw)
                VALUES (%s, %s, %s) RETURNING id'''
    return scalar(q, email, display_name, _mangle_pw(pw))

def approve_user(id):
    q = 'UPDATE users SET approved_on=now() WHERE id=%s'
    return execute(q, id)

def check_pw(email_address, pw):
    q = 'SELECT id, pw from users WHERE lower(email) = lower(%s)'
    result = fetchone(q, email_address)
    if not result:
        return None
    if _mangle_pw(pw, result.pw) == result.pw:
        return result.id
    return None

def change_pw(id, pw):
    q = 'UPDATE users SET pw=%s WHERE id=%s RETURNING id'
    return bool(scalar(q, _mangle_pw(pw), id))

def get_user(id):
    if not id:
        return None
    q = '''SELECT id, email, display_name, approved_on IS NOT NULL AS approved,
            EXISTS (SELECT 1 FROM unread WHERE voter=%s limit 1) as unread
            FROM users WHERE id=%s'''
    return fetchone(q, id, id)

def list_users():
    q = '''SELECT id, email, display_name, created_on, approved_on
            FROM users'''
    return fetchall(q)

"""
Proposal Management
"""
def _clean_proposal(raw):
    authorsT = build_tuple(('name', 'email'))
    raw['authors'] = tuple(authorsT(name, email) 
                            for name, email in zip(raw['author_names'],
                                                raw['author_emails']))
    del raw['author_names']
    del raw['author_emails']
    keys, values = zip(*raw.items())
    T = build_tuple(keys)
    return T(*values)

def get_proposal(id):
    q = 'SELECT * FROM proposals WHERE id=%s'
    raw = fetchone(q, id)
    if not raw:
        return None
    return _clean_proposal(raw._asdict())

def add_proposal(data):
    data = data.copy()
    emails, names = zip(*((x['email'], x['name']) for x in data['authors']))
    data['author_emails'] = list(emails)
    data['author_names'] = list(names)
    del data['authors']

    keys = ('id', 'author_emails', 'author_names', 'title',
            'category', 'duration', 'description', 'audience',
            'python_level', 'objectives', 'abstract', 'outline',
            'additional_notes', 'additional_requirements')


    q = 'SELECT {} FROM proposals WHERE id=%s'.format(', '.join(keys))
    proposal = fetchone(q, data['id'])

    if proposal:
        proposal = proposal._asdict()
        for k in set(proposal.keys()) - set(keys):
            del proposal[k]

    for k in set(data.keys()) - set(keys):
        del data[k]


    if proposal == data:
        return None

    if not proposal:
        q = 'INSERT INTO proposals ({}) VALUES ({})'
        q = q.format(', '.join(keys), ', '.join('%({})s'.format(x) for x in keys))
    else:
        q = 'UPDATE proposals SET {}, updated=now() WHERE id=%(id)s'
        q = q.format(', '.join('{0}=%({0})s'.format(x) for x in keys))

    execute(q, **data)
    return data['id']

"""
Bookmarks
"""

def add_bookmark(uid, proposal):
    q = 'INSERT INTO bookmarks (voter, proposal) VALUES (%s, %s)'
    try:
        execute(q, uid, proposal)
    except IntegrityError as e:
        pass

def remove_bookmark(uid, proposal):
    q = 'DELETE FROM bookmarks WHERE voter=%s AND proposal=%s'
    execute(q, uid, proposal)

def has_bookmark(uid, proposal):
    q = 'SELECT 1 FROM bookmarks WHERE voter=%s and proposal=%s'
    return scalar(q, uid, proposal)

def get_bookmarks(uid):
    q = '''SELECT proposals.id as id, proposals.title as title
            FROM bookmarks INNER JOIN proposals 
                            ON (bookmarks.proposal = proposals.id)
            WHERE voter=%s'''
    return fetchall(q, uid)


"""
Kittendome Voting
"""

def get_standards():
    return fetchall('SELECT * FROM standards ORDER BY id')

def add_standard(s):
    q = 'INSERT INTO standards (description) VALUES (%s) RETURNING id'
    return scalar(q, s)

def _clean_vote(vote):
    return vote._replace(scores={int(k):v for k,v in vote.scores.items()}) 

def vote(voter, proposal, scores):
    if not get_user(voter).approved:
        return None

    if set(scores.keys()) != set(x.id for x in get_standards()):
        return None
    for v in scores.values():
        if not 0 <= v <= 3:
            return None

    q = '''INSERT INTO votes (voter, proposal, scores)
            VALUES (%s, %s, %s) RETURNING id'''
    try:
        return scalar(q, voter, proposal, json.dumps(scores))
    except IntegrityError as e:
        pass

    q = '''UPDATE votes SET scores=%s, added_on=now()
            WHERE voter=%s AND proposal=%s RETURNING id'''
    return scalar(q, [[json.dumps(scores), voter, proposal]])

def get_user_vote(userid, proposal):
    q = '''SELECT * FROM votes WHERE
            voter=%s AND proposal=%s'''
    rv = fetchone(q, userid, proposal)
    if not rv:
        return None

    return _clean_vote(rv)

def get_votes(proposal):
    q = '''SELECT * FROM votes
            WHERE proposal=%s'''
    rv = defaultdict(Counter)
    for r in fetchall(q, proposal):
        for k,v in r.scores.items():
            rv[int(k)][int(v)] += 1
    return rv

def needs_votes(email, uid):
    q = '''SELECT id, vote_count FROM proposals
            WHERE NOT (lower(%s) = ANY(author_emails) )
            AND NOT (%s = ANY(voters))
            AND NOT withdrawn 
            ORDER BY vote_count ASC'''
    results = fetchall(q, email, uid)
    if not results:
        return None
    min_vote = results[0].vote_count
    results = [x for x in results if x.vote_count == min_vote]
    return random.choice(results).id

def kitten_progress():
    q = '''SELECT vote_count, COUNT(vote_count) as quantity
            FROM proposals GROUP BY vote_count'''
    return fetchall(q)

def get_my_votes(uid):
    q = '''SELECT votes.*, proposals.updated AS updated,
            proposals.title AS title
            FROM votes INNER JOIN proposals ON (votes.proposal = proposals.id)
            WHERE votes.voter = %s'''
    return [_clean_vote(v) for v in fetchall(q, uid)]

"""
Thunderdome
"""
def create_group(name, proposals):
    q = 'INSERT INTO thundergroups (name) VALUES (%s) RETURNING id'
    id = scalar(q, name)
    q = 'UPDATE proposals SET thundergroup=%s WHERE id = ANY(%s)'
    execute(q, id, proposals)
    return id

def vote_group(thundergroup, voter, accept):
    try:
        q = '''INSERT INTO thundervotes (thundergroup, voter, accept)
                VALUES (%s, %s, %s)'''
        execute(q, thundergroup, voter, accept)
        return
    except IntegrityError as e:
        pass
    q = '''UPDATE thundervotes SET accept=%s
            WHERE thundergroup=%s AND voter=%s'''
    execute(q, [[accept, thundergroup, voter]])


def list_groups(userid):
    q = '''SELECT tg.*, tv.thundergroup IS NOT NULL AS voted
            FROM thundergroups as tg
            LEFT JOIN thundervotes as tv 
            ON tg.id=tv.thundergroup AND tv.voter = %s'''
    return fetchall(q, userid)

def get_group(thundergroup):
    return fetchone('SELECT * FROM thundergroups WHERE id=%s', thundergroup)

def get_group_proposals(thundergroup):
    q = 'SELECT * FROM proposals WHERE thundergroup=%s'
    rv = fetchall(q, thundergroup)
    return [_clean_proposal(x._asdict()) for x in rv]

def get_thunder_vote(thundergroup, voter):
    q = 'SELECT * FROM thundervotes WHERE thundergroup=%s AND voter=%s'
    return fetchone(q, thundergroup, voter)

"""
Discussion
"""
_USER_FB_ITSD = itsdangerous.URLSafeSerializer(os.environ['ITSD_KEY'])
_MANDRILL = mandrill.Mandrill(os.environ['MANDRILL_API_KEY'])
_EMAIL_FROM = os.environ['EMAIL_FROM']
_WEB_HOST = os.environ['WEB_HOST']

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates')
_JINJA = Environment(loader=FileSystemLoader(_TEMPLATE_PATH))

def get_discussion(proposal):
    q = '''SELECT discussion.*, users.display_name
           FROM discussion LEFT JOIN users ON (users.id=discussion.frm)
            WHERE proposal=%s ORDER BY created ASC'''
    return fetchall(q, proposal)

def add_to_discussion(userid, proposal, body, feedback=False, name=None):
    q = 'SELECT voter FROM votes WHERE proposal=%s'
    users = set(x.voter for x in fetchall(q, proposal))
    q = 'SELECT frm FROM discussion WHERE proposal=%s AND frm IS NOT NULL'
    users.update(x.frm for x in fetchall(q, proposal))

    if userid in users:
        users.remove(userid)

    if userid:
        q = 'INSERT INTO discussion(frm, proposal, body, feedback) VALUES (%s, %s,%s,%s)'
        execute(q, userid, proposal, body, feedback)
    else:
        q = 'INSERT INTO discussion(proposal, body, name) VALUES (%s, %s, %s)'
        execute(q, proposal, body, name)

    if users:
        q = '''INSERT INTO unread (proposal, voter) SELECT %s, %s
                WHERE NOT EXISTS 
                    (SELECT 1 FROM unread WHERE proposal=%s AND voter=%s)'''
        execute(q, [(proposal, x, proposal, x) for x in users])

    if feedback:
        full_proposal = get_proposal(proposal)
        email = _JINJA.get_template('feedback_notice.txt')
        for to, key in generate_author_keys(proposal).items():
            url = 'http://{}/feedback/{}'.format(_WEB_HOST, key)
            email = email.render(proposal=full_proposal, body=body, 
                                url=url, edit_url='TODO') #TODO
            msg = {'text': email,
                    'subject': 'Feedback on Your PyCon Talk Proposal',
                    'from_email': _EMAIL_FROM,
                    'from_name': 'PyCon Program Committee',
                    'to': [{'email':email}],
                    'auto_html':False,}
            print msg
            print msg['text']
            #TODO: Turn emailing back on
            #_MANDRILL.messages.send(msg)


def mark_read(userid, proposal):
    q = 'DELETE FROM unread WHERE voter=%s AND proposal=%s'
    execute(q, userid, proposal)

def get_unread(userid):
    q = '''SELECT unread.proposal as id, proposals.title as title
                FROM unread LEFT JOIN proposals ON (unread.proposal = proposals.id)
                WHERE voter=%s'''
    return fetchall(q, userid)

def is_unread(userid, proposal):
    q = 'SELECT 1 FROM unread WHERE voter=%s AND proposal=%s'
    return bool(scalar(q, userid, proposal))

def generate_author_keys(id):
    q = 'SELECT author_names, author_emails FROM proposals WHERE id=%s'
    authors = fetchone(q, id)
    rv = {}
    for e, name in zip(authors.author_emails, authors.author_names):
        rv[e] = _USER_FB_ITSD.dumps([name, id])
    return rv

def check_author_key(key):
    try:
        return _USER_FB_ITSD.loads(key)
    except Exception as e:
        return None, None
