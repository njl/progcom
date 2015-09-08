#!/usr/bin/env python
import os
import json
from flask import (Flask, render_template, request, session, url_for, redirect,
                    flash)

import logic as l

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']

"""
Account Silliness
"""

@app.before_request
def login_check():
    uid = session.get('userid', None)
    if uid:
        request.user = l.get_user(uid)
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
    votes = l.get_votes(id)
    discussion = l.get_discussion(id)
    reasons = l.get_reasons()

    return render_template('kitten_proposal.html', proposal=proposal,
                            votes=votes, discussion=discussion,
                            reasons=reasons)

@app.route('/')
def pick():
    id = l.needs_votes(request.user.email)
    return redirect(url_for('kitten', id=id))

if __name__ == '__main__':
    app.run(port=4000, debug=True)
