from collections import namedtuple, defaultdict, Counter
import os 
import random
import json
import logging
import datetime
import time
import re

import pandas as pd
import itsdangerous
import mandrill
import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from jinja2 import Environment, FileSystemLoader

from gensim import corpora, models, similarities
from gensim.similarities.docsim import MatrixSimilarity

"""
Log It
"""
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig()

def l(key, **data):
    data['key'] = key
    data['when'] = datetime.datetime.now().isoformat()+'Z'
    logger.info(json.dumps(data))
    

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
    try:
        id = scalar(q, email, display_name, _mangle_pw(pw))
        l('add_user', email=email, display_name=display_name, uid=id)
    except IntegrityError:
        l('add_user_dupe', email=email, display_name=display_name)
        return -1
    return id 

def approve_user(id):
    q = 'UPDATE users SET approved_on=now() WHERE id=%s'
    l('approve_user', uid=id)
    return execute(q, id)

def check_pw(email_address, pw):
    q = 'SELECT id, pw from users WHERE lower(email) = lower(%s)'
    result = fetchone(q, email_address)
    if not result:
        l('check_pw_bad_email', email=email_address)
        return None
    if _mangle_pw(pw, result.pw) == result.pw:
        l('check_pw_ok', email=email_address)
        return result.id
    l('check_pw_bad', email=email_address)
    return None

def change_pw(id, pw):
    q = 'UPDATE users SET pw=%s WHERE id=%s RETURNING id'
    l('change_pw', uid=id)
    return bool(scalar(q, _mangle_pw(pw), id))

def get_user(id):
    if not id:
        return None
    q = '''SELECT id, email, display_name, approved_on IS NOT NULL AS approved,
            EXISTS (SELECT 1 FROM unread WHERE voter=%s limit 1) 
                AS unread,
            EXISTS (SELECT 1 FROM votes 
                        INNER JOIN proposals ON (votes.proposal = proposals.id)
                        WHERE votes.voter=%s
                                AND proposals.updated > votes.updated_on) 
                AS revisit
            FROM users WHERE id=%s'''
    return fetchone(q, id, id, id)

def list_users():
    q = '''SELECT id, email, display_name, created_on, approved_on,
            (SELECT COUNT(*) FROM votes WHERE users.id=votes.voter)
            AS votes,
            (SELECT MAX(updated_on) FROM votes WHERE users.id=votes.voter)
            AS last_voted,
            (SELECT COUNT(*) FROM proposals WHERE lower(users.email) = ANY(author_emails))
            AS proposals_made
            FROM users
            ORDER BY id'''
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
            'audience_level', 'objective', 'abstract', 'outline',
            'notes', 'additional_requirements', 'recording_release')

    """
    print 'Missing:', set(keys) - set(data.keys())
    print 'Extra:', set(data.keys()) - set(keys)
    """


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

def get_vote_percentage(email, id):
    q = '''SELECT COUNT(*) FROM proposals WHERE NOT withdrawn
            AND NOT (lower(%s) = ANY(author_emails) )'''
    total = scalar(q, email)
    q = 'SELECT COUNT(*) FROM votes WHERE voter=%s'
    votes = scalar(q, id)
    return "%0.2f" % (100.0*votes/total)

def get_all_proposal_ids():
    q = 'SELECT id FROM proposals'
    return [x.id for x in fetchall(q)]

"""
Bookmarks
"""

def add_bookmark(uid, proposal):
    l('bookmark', uid=uid, id=proposal)
    q = 'INSERT INTO bookmarks (voter, proposal) VALUES (%s, %s)'
    try:
        execute(q, uid, proposal)
    except IntegrityError as e:
        pass

def remove_bookmark(uid, proposal):
    l('remove_bookmark', uid=uid, id=proposal)
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
Screening Voting
"""

def get_standards():
    return fetchall('SELECT * FROM standards ORDER BY id')

def add_standard(s):
    l('add_standard', s=s)
    q = 'INSERT INTO standards (description) VALUES (%s) RETURNING id'
    return scalar(q, s)

def _clean_vote(vote):
    return vote._replace(scores={int(k):v for k,v in vote.scores.items()}) 

def vote(voter, proposal, scores, nominate=False):
    l('vote', uid=voter, id=proposal, scores=scores, nominate=nominate)
    if not get_user(voter).approved:
        return None

    if set(scores.keys()) != set(x.id for x in get_standards()):
        return None
    for v in scores.values():
        if not 0 <= v <= 2:
            return None

    q = '''INSERT INTO votes (voter, proposal, scores, nominate)
            VALUES (%s, %s, %s, %s) RETURNING id'''
    try:
        return scalar(q, voter, proposal, json.dumps(scores), nominate)
    except IntegrityError as e:
        pass

    q = '''UPDATE votes SET scores=%s, updated_on=now(), nominate=%s
            WHERE voter=%s AND proposal=%s RETURNING id'''
    return scalar(q, [[json.dumps(scores), nominate, voter, proposal]])

def get_user_vote(userid, proposal):
    q = '''SELECT * FROM votes WHERE
            voter=%s AND proposal=%s'''
    rv = fetchone(q, userid, proposal)
    if not rv:
        return None

    return _clean_vote(rv)

def get_votes(proposal):
    q = '''SELECT votes.*, users.display_name
            FROM votes LEFT JOIN users ON (votes.voter=users.id)
            WHERE proposal=%s'''
    return [_clean_vote(v) for v in fetchall(q, proposal)]

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
    rv = random.choice(results).id
    l('needs_votes', uid=uid, id=rv)
    return rv

def get_my_votes(uid):
    q = '''SELECT votes.*, proposals.updated > votes.updated_on AS updated,
            proposals.title AS title, proposals.updated AS proposal_updated
            FROM votes INNER JOIN proposals ON (votes.proposal = proposals.id)
            WHERE votes.voter=%s ORDER BY updated DESC'''
    return [_clean_vote(v) for v in fetchall(q, uid)]


def get_reconsider(id):
    q = '''SELECT proposal as id, proposals.title AS title 
            FROM votes INNER JOIN proposals ON (votes.proposal = proposals.id)
            WHERE voter=%s AND
            json_extract_path(scores, '4')::text = ANY('{0,1}'::text[])
            AND updated_on < timestamp '2015-11-17 16:00-05' '''
    return fetchall(q, id)

"""
Screening stats
"""

def get_reconsider_left():
    q = '''SELECT voter, count(id) FROM votes
            WHERE json_extract_path(scores, '4')::text = ANY('{0,1}'::text[])
            AND updated_on < timestamp '2015-11-17 16:00-05'
            GROUP BY voter'''
    results = fetchall(q)
    return {'votes_left': sum(x.count for x in results),
            'voters_left': len(results)}

def _score_weight_average(v):
    return int(100*sum(v)/(2.0*len(v)))

def scored_proposals():
    q = '''SELECT scores, nominate, proposal, proposals.title,
                    batchgroups.name as batchgroup
            FROM votes
            INNER JOIN proposals ON (votes.proposal = proposals.id)
            LEFT JOIN batchgroups ON (proposals.batchgroup = batchgroups.id)'''
    votes = fetchall(q)
    scores = defaultdict(list)
    nom_green = defaultdict(list)
    greenness = defaultdict(list)
    nominations = Counter()
    titles = {v.proposal:v.title for v in votes}
    batchgroups = {v.proposal:v.batchgroup for v in votes}
    for v in votes:
        scores[v.proposal].extend(v.scores.values())
        if v.nominate:
            nom_green[v.proposal].extend(2 for _ in v.scores.values())
            greenness[v.proposal].append(1.0)
        else:
            nom_green[v.proposal].extend(v.scores.values())
            greenness[v.proposal].append(sum(1.0 for x in v.scores.values() if x == 2)/(1.0*len(v.scores.values())))
        nominations[v.proposal] += 1 if v.nominate else 0
    rv = [{'id':k, 'score':_score_weight_average(v),
            'nom_is_green':_score_weight_average(nom_green[k]),
            'greenness':int(100*sum(greenness[k])/len(greenness[k])),
        'nominations': nominations[k], 'title':titles[k],
        'batchgroup':batchgroups[k]}
                    for k,v in scores.items()]
    rv.sort(key=lambda x:-x['nom_is_green'])
    for n, v in enumerate(rv):
        v['delta'] = abs(v['score'] - v['nom_is_green'])
        v['rank'] = n
    return rv

def screening_progress():
    q = '''SELECT vote_count, COUNT(vote_count) as quantity
            FROM proposals GROUP BY vote_count
            ORDER BY vote_count ASC'''
    return fetchall(q)

def _js_time(d):
    return int(time.mktime(d.timetuple()))*1000;

def get_votes_by_day():
    q = '''SELECT COUNT(*) as count, 
            date_trunc('day', updated_on) AS day
            FROM votes GROUP BY day'''
    results = {x.day.date().isoformat():x.count for x in fetchall(q)}
    full = pd.Series(results)
    full.index = pd.DatetimeIndex(full.index)
    full = full.reindex(pd.date_range(min(full.index),
                                        max(full.index)), fill_value=0)
    return [{'count':v, 'day':_js_time(k)} for k,v in full.iteritems()]

def coverage_by_age():
    q = '''SELECT COUNT(*) as total,
            date_trunc('week', added_on) AS week,
            vote_count FROM proposals GROUP BY week, vote_count
            ORDER BY vote_count ASC'''
    result = defaultdict(dict)
    for r in fetchall(q):
        result[r.vote_count][r.week.date().isoformat()] = r.total
    
    df = pd.DataFrame(result).fillna(0)
    df.index = pd.DatetimeIndex(df.index)

    result = {votes:series for votes, series in df.iteritems()}
    rv = []
    for key, series in result.iteritems():
        rv.append({'key':key, 
            'values': [{'week':_js_time(k), 'votes':v}
                        for k,v in series.iteritems()]})
    return rv

def added_last_week():
    q = '''SELECT COUNT(*) AS total FROM proposals 
            WHERE added_on > current_date - interval '7 days' '''
    return scalar(q)

def updated_last_week():
    q = '''SELECT COUNT(*) AS total FROM proposals
            WHERE added_on < current_date - interval '7 days'
                    AND updated > current_date - interval '7 days' '''
    return scalar(q)

def votes_last_week():
    q = '''SELECT COUNT(*) AS total FROM votes 
            WHERE updated_on > current_date - interval '7 days' '''
    return scalar(q)

def active_discussions():
    q = '''SELECT COUNT(d.id) as count, p.title as title, p.id as id
            FROM discussion as d INNER JOIN proposals AS p ON (d.proposal=p.id)
            WHERE d.created > current_date - interval '7 days'
            GROUP BY p.title, p.id
            ORDER BY count DESC'''
    return [x for x in fetchall(q) if x.count > 2]

def nomination_density():
    q = '''SELECT count(proposal) FROM votes 
            WHERE nominate=TRUE GROUP BY proposal'''
    rv = [x for x in Counter([x.count for x in fetchall(q)]).items() ]
    rv.sort(key=lambda x:-x[0])
    return rv

"""
Batch
"""

def full_proposal_list(email):
    q = '''SELECT p.id, p.title, bg.id as batch_id,
            array_to_string(p.author_names, ', ') AS author_names,
            COALESCE(bg.name, '') AS batchgroup,
            EXISTS (SELECT 1 FROM users
                    WHERE users.email = ANY(p.author_emails)) as progcom_member
            FROM proposals AS p 
            LEFT JOIN batchgroups AS bg ON (p.batchgroup = bg.id)
            WHERE NOT (%s = ANY(p.author_emails))'''
    return fetchall(q, email)

def create_group(name, proposals):
    q = 'INSERT INTO batchgroups (name) VALUES (%s) RETURNING id'
    id = scalar(q, name)
    if proposals:
        q = 'UPDATE proposals SET batchgroup=%s WHERE id = ANY(%s)'
        execute(q, id, proposals)
    l('create_group', name=name, proposals=proposals, gid=id)
    return id

def rename_batch_group(id, name):
    q = 'UPDATE batchgroups SET name=%s WHERE id=%s'
    execute(q, name, id)

def assign_proposal(gid, pid):
    q = 'UPDATE proposals SET batchgroup=%s WHERE id = %s'
    execute(q, gid, pid)
    l('assign_proposal', gid=gid, pid=pid)

def vote_group(batchgroup, voter, accept):
    l('vote_group', gid=batchgroup, uid=voter, accept=accept)
    try:
        q = '''INSERT INTO batchvotes (batchgroup, voter, accept)
                VALUES (%s, %s, %s)'''
        execute(q, batchgroup, voter, accept)
        return
    except IntegrityError as e:
        pass
    q = '''UPDATE batchvotes SET accept=%s, updated_on=now()
            WHERE batchgroup=%s AND voter=%s'''
    execute(q, [[accept, batchgroup, voter]])

def raw_list_groups():
    return fetchall('''SELECT batchgroups.*, 
        (SELECT COUNT(*) FROM proposals
            WHERE proposals.batchgroup = batchgroups.id) AS talk_count
            FROM batchgroups
            ORDER BY lower(name)''')

def get_batch_stats():
    q = 'SELECT batch, COUNT(id) FROM batchmessages GROUP BY batch'
    message_count = {x.batch:x.count for x in fetchall(q)}
    q = 'SELECT batchgroup, accept FROM batchvotes'
    batchmap = defaultdict(Counter)
    batch_voters = defaultdict(int)
    no_forward = defaultdict(int)
    for vote in fetchall(q):
        batch_voters[vote.batchgroup] += 1
        if not vote.accept:
            no_forward[vote.batchgroup] +=1
        for selection in vote.accept:
            batchmap[vote.batchgroup][selection] += 1

    q = '''SELECT batchgroup as id, COUNT(id) as proposals FROM proposals
            WHERE batchgroup IS NOT NULL GROUP BY batchgroup'''
    rv = [x._asdict() for x in fetchall(q)]
    for group in rv:
        id = group['id']
        group['voters'] = batch_voters.get(id, 0)
        group['msgs'] = message_count.get(id, 0)
        nominated_talks = batchmap.get(id, defaultdict(int))
        group['nominated_talks'] = len(nominated_talks)
        group['nominations'] = sum(nominated_talks.values())
        max_nominations = max(nominated_talks.values()) if nominated_talks else 0
        max_nominations = max(max_nominations, no_forward.get(id, 0))
        if group['voters']:
            consensus = int((float(max_nominations)/group['voters'])*100)
        else:
            consensus = 0
        group['consensus'] = consensus
    return {x['id']:x for x in rv}

def list_groups(userid):
    user = get_user(userid)
    q = '''SELECT tg.*, tv.batchgroup IS NOT NULL AS voted,
            (SELECT COUNT(*) FROM proposals
                WHERE proposals.batchgroup = tg.id) as count
            FROM batchgroups as tg
            LEFT JOIN batchvotes as tv 
            ON (tg.id=tv.batchgroup AND tv.voter = %s)
            WHERE NOT (%s = ANY(author_emails))
            ORDER BY tg.name'''
    return [x for x in fetchall(q, userid, user.email) if x.count]

def get_group(batchgroup):
    return fetchone('''SELECT *,
            ARRAY(SELECT display_name FROM users WHERE users.email = ANY (batchgroups.author_emails)) as progcom_members
            FROM batchgroups WHERE id=%s''', batchgroup)

def get_group_proposals(batchgroup):
    q = '''SELECT proposals.*, count(batchvotes.voter)
            FROM proposals LEFT JOIN batchvotes ON (proposals.id = ANY(batchvotes.accept))
            WHERE proposals.batchgroup=%s GROUP BY proposals.id'''
    rv = fetchall(q, batchgroup)
    rv = [_clean_proposal(x._asdict()) for x in rv]
    return rv

def get_group_votes(batchgroup):
    q = '''SELECT batchvotes.accept, users.display_name
            FROM batchvotes LEFT JOIN users ON (batchvotes.voter = users.id)
            WHERE batchvotes.batchgroup=%s'''

    return fetchall(q, batchgroup)

def get_batch_vote(batchgroup, voter):
    q = 'SELECT * FROM batchvotes WHERE batchgroup=%s AND voter=%s'
    return fetchone(q, batchgroup, voter)

"""
Batch Discussion (this is just easier)
"""

def add_batch_message(frm, batch, body):
    l('add_batch_message', uid=frm, gid=batch, body=body)
    q = '''INSERT INTO batchmessages (frm, batch, body)
            VALUES (%s, %s, %s) RETURNING id'''
    id = fetchone(q, frm, batch, body)
    q = 'SELECT voter FROM batchvotes WHERE batchgroup=%s AND voter <> %s'
    users = set(x.voter for x in fetchall(q, batch, frm))

    if users:
        q = 'INSERT INTO batchunread (batch, voter) VALUES (%s, %s)'
        try:
            execute(q, [(batch, u) for u in users])
        except IntegrityError:
            pass #Already exists
    return id

def get_batch_messages(batch):
    q = '''SELECT batchmessages.*, users.display_name 
            FROM batchmessages LEFT JOIN users ON (users.id=batchmessages.frm)
            WHERE batchmessages.batch=%s ORDER BY batchmessages.created ASC'''
    return fetchall(q, batch)

def get_unread_batches(userid):
    q = 'SELECT batch from batchunread where voter=%s'
    return set(x.batch for x in fetchall(q, userid))

def mark_batch_read(batch, user):
    l('mark_batch_read', gid=batch, uid=user)
    q = 'DELETE FROM batchunread WHERE batch=%s AND voter=%s'
    execute(q, batch, user)

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
    l('add_to_discussion', uid=userid, id=proposal, body=body,
                            feedback=feedback, name=name)
    q = 'SELECT voter FROM votes WHERE proposal=%s'
    users = set(x.voter for x in fetchall(q, proposal))
    q = 'SELECT frm FROM discussion WHERE proposal=%s AND frm IS NOT NULL'
    users.update(x.frm for x in fetchall(q, proposal))

    if userid in users:
        users.remove(userid)

    if userid:
        q = '''INSERT INTO discussion(frm, proposal, body, feedback)
                VALUES (%s, %s,%s,%s)'''
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
        email = _JINJA.get_template('email/feedback_notice.txt')
        for to, key in generate_author_keys(proposal).items():
            url = 'http://{}/feedback/{}'.format(_WEB_HOST, key)
            edit_url = 'https://us.pycon.org/2016/proposals/{}/'.format(proposal)
            rendered = email.render(proposal=full_proposal, body=body, 
                                url=url, edit_url=edit_url) 
            msg = {'text': rendered,
                    'subject': 'Feedback on Your PyCon Talk Proposal',
                    'from_email': _EMAIL_FROM,
                    'from_name': 'PyCon Program Committee',
                    'to': [{'email':to}],
                    'auto_html':False,}
            l('filter_email_sent', api_result=_MANDRILL.messages.send(msg),
                    to=to)


def mark_read(userid, proposal):
    l('mark_read', uid=userid, id=proposal)
    q = 'DELETE FROM unread WHERE voter=%s AND proposal=%s'
    execute(q, userid, proposal)

def get_unread(userid):
    q = '''SELECT unread.proposal as id, proposals.title as title
                FROM unread
                LEFT JOIN proposals ON (unread.proposal = proposals.id)
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

"""
Emails
"""
_ADMIN_EMAILS = set(json.loads(os.environ['ADMIN_EMAILS']))
_LOGIN_EMAIL_ITSD = itsdangerous.URLSafeTimedSerializer(os.environ['ITSD_KEY'],
                                                salt='loginemail')

def send_login_email(email):
    q = 'SELECT id, email FROM users WHERE lower(email) = lower(%s)'
    user = fetchone(q, email)
    if not user:
        l('failed_pw_reset_request', email=email)
        return False

    body = _JINJA.get_template('email/login_email.txt')
    key = _LOGIN_EMAIL_ITSD.dumps(user.id)
    url = 'http://{}/user/login/{}/'.format(_WEB_HOST, key)
    body = body.render(url=url)

    msg = {'text':body,
            'subject': 'PyCon Program Committee Password Reset',
            'from_email':'njl@njl.us',
            'from_name':'Ned Jackson Lovely',
            'to':[{'email':user.email}]}
    _MANDRILL.messages.send(msg)
    l('successful_pw_reset_request', email=email, id=user.id)
    return True

def test_login_string(s):
    try:
        id = _LOGIN_EMAIL_ITSD.loads(s, max_age=60*20)
    except Exception as e:
        l('bad_pw_reset_key', e=str(e), s=s)
        return False
    return id

def email_approved(id):
    user = get_user(id)
    msg = {'text': _JINJA.get_template('email/welcome_user.txt').render(),
            'subject': 'Welcome to the Program Committee Web App!',
            'from_email': 'njl@njl.us',
            'from_name':'Ned Jackson Lovely',
            'to':[{'email':user.email}] 
                + [{'email':x, 'type':'cc'} for x in _ADMIN_EMAILS]}
    _MANDRILL.messages.send(msg)

def email_new_user_pending(email, name):
    body = _JINJA.get_template('email/new_user_pending.txt').render(name=name,
                                                            email=email)
    msg = {'text': body,
            'subject': 'New Progcom User',
            'from_email': 'njl@njl.us',
            'from_name':'PyCon Program Committee Robot',
            'to':[{'email':x} for x in _ADMIN_EMAILS]}
    _MANDRILL.messages.send(msg)
 
def send_weekly_update():
    body = _JINJA.get_template('email/weekly_email.txt')
    body = body.render(new_proposal_count=added_last_week(),
                        updated_proposal_count=updated_last_week(),
                        votes_last_week=votes_last_week(),
                        active_discussions=active_discussions(),
                        screening_progress=screening_progress())
    msg = {'text':body,
            'subject':'Weekly Program Committee Status',
            'from_email': 'njl@njl.us',
            'from_name': 'PyCon Program Committee Robot',
            'to':[{'email':'pycon-pc@python.org'}]}
    _MANDRILL.messages.send(msg)

"""
Experimental Topic Grouping
"""


#Installing NLTK and downloading everything is a trial.
_NLTK_ENGLISH_STOPWORDS = set([u'i', u'me', u'my', u'myself', u'we', u'our',
u'ours', u'ourselves', u'you', u'your', u'yours', u'yourself', u'yourselves',
u'he', u'him', u'his', u'himself', u'she', u'her', u'hers', u'herself', u'it',
u'its', u'itself', u'they', u'them', u'their', u'theirs', u'themselves',
u'what', u'which', u'who', u'whom', u'this', u'that', u'these', u'those',
u'am', u'is', u'are', u'was', u'were', u'be', u'been', u'being', u'have',
u'has', u'had', u'having', u'do', u'does', u'did', u'doing', u'a', u'an',
u'the', u'and', u'but', u'if', u'or', u'because', u'as', u'until', u'while',
u'of', u'at', u'by', u'for', u'with', u'about', u'against', u'between',
u'into', u'through', u'during', u'before', u'after', u'above', u'below', u'to',
u'from', u'up', u'down', u'in', u'out', u'on', u'off', u'over', u'under',
u'again', u'further', u'then', u'once', u'here', u'there', u'when', u'where',
u'why', u'how', u'all', u'any', u'both', u'each', u'few', u'more', u'most',
u'other', u'some', u'such', u'no', u'nor', u'not', u'only', u'own', u'same',
u'so', u'than', u'too', u'very', u's', u't', u'can', u'will', u'just', u'don',
u'should', u'now'] + ['www', 'youtube', 'com', 'google', 'python', 'http',
'talk', 'https', 'programming', 'markdown', 'mins', 'min'])

def _get_words(s):
    s = s.lower()
    s = re.sub("[^a-z]", " ", s)
    return [x for x in s.lower().split() if x and x not in _NLTK_ENGLISH_STOPWORDS]

def _get_raw_docs():
    fields = ('title', 'category', 'description', 'audience', 'objective',
                'abstract', 'outline', 'notes')
    q = 'SELECT id, {} FROM proposals'.format(', '.join(fields))
    raw_documents = fetchall(q)
    rv = {}
    all_words = Counter()
    for row in raw_documents:
        rv[row.id] = _get_words(' '.join(getattr(row, k) for k in fields))
        all_words.update(set(rv[row.id]))

    useful_words = set(k for k,v in all_words.items() if v > 1)

    ids, words = zip(*{k:[x for x in v if x in useful_words] for k,v in rv.iteritems()}.items())
    return ids, words

def get_proposals_auto_grouped(topics_count=100, threshold=.5):
    ids, words = _get_raw_docs()

    dictionary = corpora.Dictionary(words)
    corpus = [dictionary.doc2bow(x) for x in words]
    tfidf = models.TfidfModel(corpus)
    corpus_tfidf = tfidf[corpus]
    lsi = models.LsiModel(corpus_tfidf, id2word=dictionary, num_topics=topics_count)
    lsi_corpus = lsi[corpus_tfidf]

    ms = MatrixSimilarity(lsi_corpus)

    neighbors = {}
    for frm, row in zip(ids, lsi_corpus):
        neighbors[frm] = [ids[n] for n, match in enumerate(ms[row]) if match > threshold and ids[n] != frm]

    results = []
    groups = {}
    for root, children in neighbors.items():
        target = groups.get(root, None)
        if not target:
            target = set()
            results.append(target)
        target.add(root)
        target.update(children)
        for c in children:
            groups[c] = target

    rv = {}
    for n, row in enumerate(results):
        for x in row:
            rv[x] = n

    return rv
