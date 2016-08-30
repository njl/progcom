#!/usr/bin/env python
import os
import json
import random
import time
from collections import defaultdict

from flask import (Flask, render_template, request, session, url_for, redirect,
                    flash, abort, jsonify)
from jinja2 import Markup
import bleach
import markdown2 as markdown
from raven.contrib.flask import Sentry


import logic as l

from bp.admin import bp as bp_admin

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']

app.register_blueprint(bp_admin, url_prefix='/admin')

if 'SENTRY_DSN' in os.environ:
    sentry = Sentry(app)
    print 'Sentry'

THIS_IS_BATCH = 'THIS_IS_BATCH' in os.environ
app.config.THIS_IS_BATCH = THIS_IS_BATCH

CUTOFF_FEEDBACK = 'CUTOFF_FEEDBACK' in os.environ
app.config.CUTOFF_FEEDBACK = CUTOFF_FEEDBACK

_ADMIN_EMAILS = set(json.loads(os.environ['ADMIN_EMAILS']))
app.config.ADMIN_EMAILS = _ADMIN_EMAILS

_OBSERVER_EMAILS = set(json.loads(os.environ['OBSERVER_EMAILS']))
app.config.OBSERVER_EMAILS = _OBSERVER_EMAILS

if THIS_IS_BATCH:
    print 'THIS IS BATCH'
else:
    print 'This is Screening!'

@app.template_filter('date')
def date_filter(d):
    if not d:
        return ''
    return d.strftime('%B %-d, %-I:%M %p')

@app.template_filter('minutes')
def time_to_minutes(d):
    return d.hour*60+d.minute

def set_nofollow(attrs, new=False):
    attrs['target'] = '_blank'
    return attrs


__ALLOWED_TAGS =['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'hr', 'pre']
@app.template_filter('markdown')
def markdown_filter(s):
    raw = bleach.clean(markdown.markdown(s), 
                    tags=bleach.ALLOWED_TAGS+__ALLOWED_TAGS)
    raw = bleach.linkify(raw, callbacks=[set_nofollow])
    return Markup(raw)

"""
Account Silliness
""" 
@app.before_request
def security_check():
    request.user = l.get_user(session.get('userid'))

    if request.user and not request.user.approved:
        session.clear()
        return redirect(url_for('login'))

    path = request.path
    if (request.user and path.startswith('/admin') 
            and request.user.email not in _ADMIN_EMAILS):
        abort(403)

    if path.startswith('/screening') and THIS_IS_BATCH:
        abort(403)

    if path.startswith('/batch') and not THIS_IS_BATCH:
        if request.user and request.user.email not in _ADMIN_EMAILS:
            abort(403)

    if request.user:
        return

    safe_prefixes = ('/static', '/user', '/feedback', '/confirmation')
    for prefix in safe_prefixes:
        if path.startswith(prefix):
            return

    return redirect(url_for('login'))

@app.route('/user/login/')
def login():
    return render_template('user/login.html')

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
    return render_template('user/new_user.html')

@app.route('/user/new/', methods=['POST'])
def new_user_post():
    email = request.values.get('email')
    name = request.values.get('name')
    pw = request.values.get('pw')
    if not pw or not pw.strip():
        flash('No empty passwords, please!')
        return redirect(url_for('new_user'))
    uid = l.add_user(email, name, pw)
    if uid == -1:
        flash('An account with that email address already exists')
        return redirect(url_for('login'))
    l.email_new_user_pending(email, name)
    flash('You will be able to log in after your account is approved!')
    return redirect(url_for('login'))

@app.route('/user/logout/')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/user/email_login/')
def request_reset():
    return render_template('user/request_reset.html')

@app.route('/user/email_login/', methods=['POST'])
def request_reset_post():
    if l.send_login_email(request.values.get('email')):
        flash('Reset sent')
    else:
        flash('Reset failed; perhaps a bad email address?')
    return redirect(url_for('request_reset'))

@app.route('/user/login/<key>/')
def view_reset_key(key):
    uid = l.test_login_string(key)
    if not uid:
        flash('Bad key; has it expired?')
        return redirect(url_for('request_reset'))
    session['userid'] = uid
    flash('Logged in!')
    return redirect(url_for('reset_password'))

@app.route('/me/change_password/')
def reset_password():
    return render_template('user/reset_password.html')


@app.route('/me/change_password/', methods=['POST'])
def reset_password_post():
    l.change_pw(request.user.id, request.values.get('pw'))
    flash('Password changed')
    return redirect('/')

"""
User State
"""
@app.route('/votes/')
def show_votes():
    votes = l.get_my_votes(request.user.id)
    votes = [x._replace(updated_on=l._js_time(x.updated_on)) for x in votes]
    percent = l.get_vote_percentage(request.user.email, request.user.id)
    return render_template('my_votes.html', votes=votes, percent=percent,
                            standards = l.get_standards())

@app.route('/bookmarks/')
def show_bookmarks():
    return render_template('bookmarks.html',
                            bookmarks=l.get_bookmarks(request.user.id))

@app.route('/unread/')
def show_unread():
    return render_template('unread.html', unread=l.get_unread(request.user.id)) 

"""
Batch Actions
"""
@app.route('/batch/')
def batch_splash_page():
    groups = [x._asdict() for x in l.list_groups(request.user.id)]
    unread = l.get_unread_batches(request.user.id)
    stats = l.get_batch_stats()
    for group in groups:
        group['unread'] = group['id'] in unread
        group.update(stats[group['id']])
    percent = int( 100.0*sum(1.0 for x in groups if x['voted']) / len(groups))
    return render_template('batch/batch.html', groups=groups, percent=percent)

@app.route('/batch/full/<int:id>/')
def view_single_proposals(id):
    proposal = l.get_proposal(id)
    if request.user.email in [x.email for x in proposal.authors]:
        abort(404)
    return render_template('batch/single_proposal.html', proposal=proposal,
                            discussion=l.get_discussion(id))

@app.route('/batch/full/')
def full_list():
    return render_template('batch/full_list.html',
            proposals=l.full_proposal_list(request.user.email))

@app.route('/batch/<int:id>/')
def batch_view(id):
    l.l('batch_view', uid=request.user.id, gid=id)
    group = l.get_group(id)
    if not group:
        abort(404)
    if request.user.email in group.author_emails:
        abort(404)
    raw_proposals = l.get_group_proposals(id)
    votes  = l.get_group_votes(id)
    proposals = []
    for rp in raw_proposals:
        clean_prop = {'proposal': rp, 'discussion': l.get_discussion(rp.id)}
        voters = [v.display_name for v in votes if rp.id in v.accept]
        clean_prop['voters'] = ', '.join(voters)
        clean_prop['voters_count'] = len(voters)
        proposals.append(clean_prop)
    proposal_map = {x.id:x for x in raw_proposals}
    if group.locked:
        proposals.sort(key=lambda x:-x['voters_count'])
    else:
        random.shuffle(proposals)
    basics = {x['proposal'].id:x['proposal'].title for x in proposals}
    vote = l.get_batch_vote(id, request.user.id)
    msgs = l.get_batch_messages(id)
    l.mark_batch_read(id, request.user.id)
    return render_template('batch/batchgroup.html', group=group,
                            proposals=proposals, proposal_map=proposal_map,
                            basics=basics, msgs=msgs,
                            all_votes=votes,
                            vote = vote._asdict() if vote else None)

@app.route('/batch/<int:id>/vote/', methods=['POST'])
def batch_vote(id):
    group = l.get_group(id)
    if request.user.email in group.author_emails or group.locked:
        abort(404)

    accept = request.values.getlist('accept', int)

    l.vote_group(id, request.user.id, accept)
    return redirect(url_for('batch_view', id=id))

@app.route('/batch/<int:id>/comment/', methods=['POST'])
def batch_discussion(id):
    group = l.get_group(id)
    if request.user.email in group.author_emails or group.locked:
        abort(404)
    l.add_batch_message(request.user.id, id, request.values.get('comment'))
    return render_template('batch/batch_discussion_snippet.html',
                            msgs=l.get_batch_messages(id))

@app.route('/batch/nominations/')
def my_nominations():
    return render_template('batch/my_pycon.html',
                            proposals=l.get_my_pycon(request.user.id))

"""
Screening Actions
"""
@app.route('/activity_buttons/')
def activity_buttons():
    return render_template('activity_button_fragment.html')


@app.route('/screening/stats/')
def screening_stats():
    users = [x for x in l.list_users() if x.votes]
    users.sort(key=lambda x:-x.votes)
    progress = l.screening_progress()
    votes_when = l.get_votes_by_day()
    coverage_by_age = l.coverage_by_age()
    active_discussions = l.active_discussions()
    nomination_density = l.nomination_density()
    return render_template('screening_stats.html',
                            users=users, progress=progress,
                            nomination_density=nomination_density,
                            coverage_by_age=coverage_by_age,
                            total_votes=sum(u.votes for u in users),
                            total_proposals=sum(p.quantity for p in progress),
                            active_discussions=active_discussions,
                            votes_when=votes_when)

@app.route('/screening/<int:id>/')
def screening(id):
    l.l('screening_view', uid=request.user.id, id=id)
    proposal = l.get_proposal(id)
    if not proposal or proposal.withdrawn:
        abort(404)

    if request.user.email in (x.email.lower() for x in proposal.authors):
        abort(404)

    unread = l.is_unread(request.user.id, id)
    discussion = l.get_discussion(id)

    standards = l.get_standards()
    bookmarked = l.has_bookmark(request.user.id, id)

    existing_vote = l.get_user_vote(request.user.id, id)
    votes = l.get_votes(id)

    my_votes = l.get_my_votes(request.user.id)
    percent = l.get_vote_percentage(request.user.email, request.user.id)

    return render_template('screening_proposal.html', proposal=proposal,
                            votes=votes, discussion=discussion,
                            standards=standards,
                            bookmarked=bookmarked,
                            existing_vote=existing_vote,
                            unread=unread,
                            percent=percent)

@app.route('/screening/<int:id>/vote/', methods=['POST'])
def vote(id):
    standards = l.get_standards()
    scores = {}
    for s in standards:
        scores[s.id] = int(request.values['standard-{}'.format(s.id)])
    nominate = request.values.get('nominate', '0') == '1'
    l.vote(request.user.id, id, scores, nominate)
    return render_template('user_vote_snippet.html', 
                            standards=l.get_standards(),
                            votes = l.get_votes(id),
                            existing_vote=l.get_user_vote(request.user.id, id))

@app.route('/screening/<int:id>/comment/', methods=['POST'])
def comment(id):
    comment = request.values.get('comment').strip()
    if comment:
        l.add_to_discussion(request.user.id, id, comment, feedback=False)
    return render_template('discussion_snippet.html', 
            unread = l.is_unread(request.user.id, id),
            discussion = l.get_discussion(id))

@app.route('/screening/<int:id>/feedback/', methods=['POST'])
def feedback(id):
    if CUTOFF_FEEDBACK:
        abort(404)
    comment = request.values.get('feedback').strip()
    if comment:
        l.add_to_discussion(request.user.id, id, comment, feedback=True)
    return render_template('discussion_snippet.html', 
            unread = l.is_unread(request.user.id, id),
            discussion = l.get_discussion(id))

@app.route('/screening/<int:id>/bookmark/add/', methods=['POST'])
def add_bookmark(id):
    l.add_bookmark(request.user.id, id)
    return render_template('proposal_snippet.html', proposal=l.get_proposal(id),
                            bookmarked=l.has_bookmark(request.user.id, id))

@app.route('/screening/<int:id>/bookmark/remove/', methods=['POST'])
def remove_bookmark(id):
    l.remove_bookmark(request.user.id, id)
    return render_template('proposal_snippet.html', proposal=l.get_proposal(id),
                            bookmarked=l.has_bookmark(request.user.id, id))

@app.route('/screening/<int:id>/mark_read/', methods=['POST'])
def mark_read(id):
    l.mark_read(request.user.id, id)
    return render_template('discussion_snippet.html', 
            unread = l.is_unread(request.user.id, id),
            discussion = l.get_discussion(id))

@app.route('/screening/<int:id>/mark_read/next/', methods=['POST'])
def mark_read_read_next(id):
    l.mark_read(request.user.id, id)
    unread = l.get_unread(request.user.id)
    if not unread:
        flash('All unread messages marked as read')
        return redirect(url_for('screening_stats'))
    target = random.choice(unread)
    return redirect(url_for('screening', id=random.choice(unread).id))

"""
Author Feedback
"""

@app.route('/feedback/<key>')
def author_feedback(key):
    name, id = l.check_author_key(key)
    if not name:
        return render_template('bad_feedback_key.html')
    proposal = l.get_proposal(id)
    return render_template('author_feedback.html', name=name, 
                            proposal=proposal, messages=l.get_discussion(id))


@app.route('/feedback/<key>', methods=['POST'])
def author_post_feedback(key):
    if CUTOFF_FEEDBACK:
        abort(404)
    name, id = l.check_author_key(key)
    if not name:
        return render_template('bad_feedback_key.html')
    message = request.values.get('message', '').strip()
    redir = redirect(url_for('author_feedback', key=key)) 
    if not message:
        flash('Empty message')
        return redir
    l.add_to_discussion(None, id, request.values.get('message'), name=name)
    flash('Your message has been saved!')
    return redir
"""
Observer View
"""

@app.route('/schedule/')
def view_schedule():
    return render_template('admin/schedule.html', schedule=l.get_schedule(),
                                talks=l.get_accepted(), read_only=True)

"""
Confirmation
"""
@app.route('/confirmation/<key>/')
def confirmation(key):
    id = l.acknowledge_confirmation(key)
    if not id:
        return render_template('bad_feedback_key.html')
    return render_template('confirmation.html', proposal=l.get_proposal(id))


"""
Default Action
"""
@app.route('/')
def pick():
    if THIS_IS_BATCH:
        return redirect(url_for('batch_splash_page'))


    if request.user.revisit:
        data = [x for x in l.get_my_votes(request.user.id) if x.updated]
        if data:
            msg = """This proposal has been updated since your last vote.
                    Please reconsider and save your vote!"""
            flash(msg)
            return redirect(url_for('screening', id=data[0].proposal))

    id = l.needs_votes(request.user.email, request.user.id)
    if not id:
        flash("You have voted on every proposal!")
        return redirect(url_for('screening_stats'))
    return redirect(url_for('screening', id=id))

if __name__ == '__main__':
    app.run(port=4000, debug=True)
