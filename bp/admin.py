from flask import (Blueprint, render_template, jsonify, request,
                    redirect, url_for, flash)

import logic as l

bp = Blueprint('admin', __name__)

@bp.route('/')
def admin_menu():
    return render_template('admin/admin_page.html')

@bp.route('/batchgroups/<int:id>/lock/', methods=['POST'])
def lock_batch_group(id):
    lock = request.values.get('lock', None) == 't'
    l.l('lock_batch_group', user=request.user.id, lock=lock, id=id)
    l.toggle_lock_batch(id, lock)
    return jsonify(result='ok', status=lock)

@bp.route('/batchgroups/')
def list_batchgroups():
    l.l('list_batchgroups', user=request.user.id)
    return render_template('admin/batchgroups.html',
                            groups=l.raw_list_groups())

@bp.route('/batchgroups/', methods=['POST'])
def add_batchgroup():
    name = request.values.get('name')
    id = l.create_group(request.values.get('name'), None)
    l.l('add_batchgroup', uid=request.user.id, name = name, id=id)
    if request.is_xhr:
        return jsonify(groups=l.raw_list_groups())
    return redirect(url_for('admin.list_batchgroups'))

@bp.route('/batchgroups/<int:id>/', methods=['POST'])
def rename_batch_group(id):
    name = request.values.get('name')
    l.l('rename_batch_group', uid=request.user.id, name=name, gid=id)
    l.rename_batch_group(id,name)
    if request.is_xhr:
        return jsonify(groups=l.raw_list_groups())
    return redirect(url_for('admin.list_batchgroups'))

@bp.route('/assign/', methods=['POST'])
def assign_proposal():
    gid = request.values.get('gid', None)
    pid = request.values.get('pid')
    l.l('assign_proposal', uid=request.user.id, gid=gid, pid=pid)
    l.assign_proposal(gid, pid)
    return jsonify(status='ok')

@bp.route('/users/')
def list_users():
    return render_template('admin/user_list.html', users=l.list_users())

@bp.route('/users/<int:uid>/approve/', methods=['POST'])
def approve_user(uid):
    l.approve_user(uid)
    user = l.get_user(uid)
    flash('Approved user {}'.format(user.email))
    l.email_approved(uid)
    return redirect(url_for('admin.list_users'))

@bp.route('/standards/')
def list_standards():
    return render_template('admin/standards.html', standards=l.get_standards())

@bp.route('/standards/', methods=['POST'])
def add_reason():
    text = request.values.get('text')
    l.add_standard(text)
    flash('Added standard "{}"'.format(text))
    return redirect(url_for('admin.list_standards'))

@bp.route('/rough_scores/auto_grouping/')
def get_auto_grouping():
    return jsonify(data=l.get_proposals_auto_grouped())

@bp.route('/rough_scores/')
def rough_scores():
    proposals = l.scored_proposals()
    consensus = l.get_batch_coverage()
    for x in proposals:
        x['auto_group'] = ''
        if x['batchgroup']:
            x['consensus'] = consensus[x['batch_id']][x['id']]
        else:
            x['consensus'] = -1
    return render_template('admin/rough_scores.html',
                            proposals=proposals,
                            groups=l.raw_list_groups())
