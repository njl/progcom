#!/usr/bin/env python
import os
import json
from flask import (Flask, render_template, request, session, url_for, redirect,
                    flash)

import logic as l

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']

@app.template_filter('date')
def date_filter(d):
    return d.strftime('%b-%-d %I:%M')

"""
Account Silliness
"""

@app.before_request
def login_check():
    uid = session.get('userid', None)
    if uid:
        request.user = l.get_user(uid)
        if not request.user:
            session.clear()
            return redirect(url_for('login'))
        return
    if request.path.startswith('/static'):
        return
    if request.path.startswith('/user'):
        return
    return redirect(url_for('login'))

@app.route('/user/login/')
def login():
    return render_template('login.html')

@app.route('/user/login/', methods=['POST'])
def login_post():
    uid = l.check_pw(request.values.get('email'),
                        request.values.get('pw'))
    if not uid:
        flash('Bad email or password.')
        return redirect(url_for('login'))
    user = l.get_user(uid)
    if not user.approved:
        flash('You have not yet been approved.')
        return redirect(url_for('login'))
    session['userid'] = uid
    return redirect('/')

@app.route('/user/new/')
def new_user():
    return render_template('new_user.html')

@app.route('/user/new/', methods=['POST'])
def new_user_post():
    uid = l.add_user(request.values.get('email'),
                       request.values.get('name'),
                         request.values.get('pw'))
    flash('You will be able to log in after your account is approved!')
    return redirect(url_for('login'))

@app.route('/user/logout/')
def logout():
    session.clear()
    return redirect(url_for('login'))

"""
Admin
"""

_ADMIN_EMAILS = set(json.loads(os.environ['ADMIN_EMAILS']))

@app.route('/admin/users/')
def list_users():
    if request.user.email not in _ADMIN_EMAILS:
        return redirect('/')
    return render_template('user_list.html', users=l.list_users())

@app.route('/admin/users/<int:uid>/approve/', methods=['POST'])
def approve_user(uid):
    if request.user.email not in _ADMIN_EMAILS:
        return redirect('/')
    l.approve_user(uid)
    user = l.get_user(uid)
    flash('Approved user {}'.format(user.email))
    return redirect(url_for('list_users'))

@app.route('/admin/reasons/')
def list_reasons():
    if request.user.email not in _ADMIN_EMAILS:
        return redirect('/')
    return render_template('reasons.html', reasons=l.get_reasons())

@app.route('/admin/reasons/', methods=['POST'])
def add_reason():
    if request.user.email not in _ADMIN_EMAILS:
        return redirect('/')
    text = request.values.get('text')
    l.add_reason(text)
    flash('Added reason "{}"'.format(text))
    return redirect(url_for('list_reasons'))


"""
Kittendome
"""

@app.route('/kitten/<int:id>/')
def kitten(id):
    proposal = l.get_proposal(id)
    raw_votes = l.get_votes(id)
    raw_discussion = l.get_discussion(id)
    reasons = l.get_reasons()
    progress = l.kitten_progress()
    users = set(x.frm for x in raw_discussion if x.frm)
    users.update(x.voter for x in raw_votes)
    users = {x:l.get_user(x) for x in users}
    discussion = []
    for x in raw_discussion:
        x = x._asdict()
        x['frm'] = users[x['frm']] if x['frm'] else None
        discussion.append(x)

    votes = []
    for x in raw_votes:
        x = x._asdict()
        x['voter'] = users[x['voter']]
        votes.append(x)
    return render_template('kitten_proposal.html', proposal=proposal,
                            votes=votes, discussion=discussion,
                            reasons=reasons, progress=progress)

@app.route('/kitten/<int:id>/vote/', methods=['POST'])
def vote(id):
    v = request.values.get('vote', None)
    redir = redirect(url_for('kitten', id=id))
    if v not in ('+1', '+0', '-0', '-1'):
        return redir
    magnitude = int(v[-1])
    sign = -1 if v[0] == '-' else 1
    reason = request.values.get('reason', None)
    if not reason or not reason.strip():
        reason = None
    if l.vote(request.user.id, id, magnitude, sign, reason):
        proposal = l.get_proposal(id)
        flash('You voted "{}" for "{}" #{}'.format(v, proposal.title, proposal.id))
        return redirect(url_for('pick'))
    return redir

@app.route('/kitten/<int:id>/comment/', methods=['POST'])
def comment(id):
    comment = request.values.get('comment').strip()
    redir = redirect(url_for('kitten', id=id))
    if not comment:
        flash("Empty comment")
        return redir
    l.add_to_discussion(request.user.id, id, comment, feedback=False)
    return redir

@app.route('/kitten/<int:id>/feedback/', methods=['POST'])
def feedback(id):
    comment = request.values.get('feedback').strip()
    redir = redirect(url_for('kitten', id=id))
    if not comment:
        flash('Empty comment')
        return redir
    l.add_to_discussion(request.user.id, id, comment, feedback=True)
    return redir

@app.route('/')
def pick():
    id = l.needs_votes(request.user.email)
    return redirect(url_for('kitten', id=id))

if __name__ == '__main__':
    app.run(port=4000, debug=True)
