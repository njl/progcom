from collections import namedtuple
import os 
import random
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
    q = '''SELECT id, email, display_name, approved_on IS NOT NULL AS approved
            FROM users WHERE id=%s'''
    return fetchone(q, id)

def list_users():
    q = '''SELECT id, email, display_name, created_on, approved_on
            FROM users'''
    return fetchall(q)

"""
Proposal Management
"""
def _get_proposal_authors(id):
    q = 'SELECT email, name FROM authors WHERE revision=%s'
    return [x._asdict() for x in fetchall(q, id)]

def get_proposal(id):
    q = 'SELECT * FROM proposals WHERE id=%s'
    result = _e.execute(q, id)
    raw = result.fetchone()
    if not raw:
        return None
    raw = dict(zip(result.keys(), raw))
    authorsT = build_tuple(('name', 'email'))
    raw['authors'] = tuple(authorsT(name, email) 
                            for name, email in zip(raw['author_names'],
                                                raw['author_emails']))
    del raw['author_names']
    del raw['author_emails']
    keys, values = zip(*raw.items())
    T = build_tuple(keys)
    return T(*values)

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
Voting
"""

def get_reasons():
    return [x.description for x in
                fetchall('SELECT description FROM vote_reasons')]

def add_reason(s):
    q = 'INSERT INTO vote_reasons (description) VALUES (%s) RETURNING id'
    return scalar(q, s)

def vote(voter, proposal, yea, reason=None):
    if not get_user(voter).approved:
        return None

    q = '''INSERT INTO votes (voter, proposal, yea, reason)
            VALUES (%s, %s, %s, %s)  RETURNING id'''
    try:
        return scalar(q, voter, proposal, yea, reason)
    except IntegrityError as e:
        pass
    q = '''UPDATE votes SET yea=%s, reason=%s
            WHERE voter=%s AND proposal=%s RETURNING id'''
    return scalar(q, yea, reason, voter, proposal)


def get_votes(proposal):
    return fetchall('SELECT * FROM votes WHERE proposal=%s', proposal)

def needs_votes(email, uid):
    q = '''SELECT id, vote_count FROM proposals
            WHERE NOT (lower(%s) = ANY(author_emails) )
            AND NOT (%s = ANY(voters))
            ORDER BY vote_count ASC'''
    results = fetchall(q, email, uid)
    if not results:
        return None
    min_vote = results[0].vote_count
    results = [x for x in results if x.vote_count == min_vote]
    return random.choice(results).id

def kitten_progress():
    q = 'SELECT vote_count, COUNT(vote_count) as quantity FROM proposals GROUP BY vote_count'
    return fetchall(q)

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
    q = 'SELECT * FROM discussion WHERE proposal=%s ORDER BY created ASC'
    return fetchall(q, proposal)

def add_to_discussion(userid, proposal, body, feedback=False):
    q = 'SELECT voter FROM votes WHERE proposal=%s'
    users = set(x.voter for x in fetchall(q, proposal))
    q = 'SELECT frm FROM discussion WHERE proposal=%s AND frm IS NOT NULL'
    users.update(x.frm for x in fetchall(q, proposal))

    if userid in users:
        users.remove(userid)
    q = 'INSERT INTO discussion(frm, proposal, body, feedback) VALUES (%s, %s,%s,%s)'
    execute(q, userid, proposal, body, feedback)
    if users:
        q = '''INSERT INTO unread (proposal, voter) SELECT %s, %s
                WHERE NOT EXISTS 
                    (SELECT 1 FROM unread WHERE proposal=%s AND voter=%s)'''
        execute(q, [(proposal, x, proposal, x) for x in users])

    if feedback:
        full_proposal = get_proposal(proposal)
        email = _JINJA.get_template('feedback_notice.txt')
        email = email.render(proposal=full_proposal, body=body, url='TODO',
                                edit_url='TODO') #TODO
        msg = {'text': email,
                'subject': 'Feedback on Your PyCon Talk Proposal',
                'from_email': _EMAIL_FROM,
                'from_name': 'PyCon Program Committee',
                'to': [{'email':'TODO'}],
                'auto_html':False,}
        _MANDRILL.messages.send(msg)


def mark_read(userid, proposal):
    q = 'DELETE FROM unread WHERE voter=%s AND proposal=%s'
    execute(q, userid, proposal)

def get_unread(userid):
    q = 'SELECT proposal FROM unread WHERE voter=%s'
    return [x.proposal for x in fetchall(q, userid)]

