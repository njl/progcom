function show_proposal_tabs(ev){
    ev.preventDefault();
    $(this).tab('show');
}

function batch_add(ev){
    var $accept = $('#accept');
    if ($accept.find('li').length >= 2){
        return;
    }
    var $this = $(this);
    var id = $this.data().id;
    $this.hide();
    $('#notalks').hide();
    $accept.append(TEMPLATES.ordered_row({id:id, title:TALKS[id]}));
}

function batch_rem(ev){
    var $accept = $('#accept'),
        $this=$(this),
        id = $this.find('input').val();
    $('#unranked-prop-'+id).show();
    $this.remove();
    if ($accept.find('li').length <= 0){
        $('#notalks').show();
    }
}

function nominate_status(){
    var enabled = false;
    $('#vote-form .btn-group input[type=hidden]').each(function(){
        var val = $(this).val();
        if(val == "1" || val == "0"){
            enabled = true;
        }
    });
    $("#nominate").attr("disabled", !enabled);
    if(!enabled && $('input[name=nominate]').val() == '1'){
        $('#nominate').click();
    }
}

function vote_click(){
    var $this = $(this);
    $this.siblings('input').val($this.data().val);
    $this.siblings().addClass('btn-default').removeClass('btn-success btn-warning btn-danger');
    $this.addClass({'0':'btn-danger', '1':'btn-warning', '2': 'btn-success'}[$this.data().val])
    $this.removeClass('btn-default');
    $('#save').attr('disabled', $('#vote-form input[value=-1]').length > 0);
    nominate_status()
}

function nominate_click(){
    var $this=$(this),
        $inp = $(this).siblings('input');
    if($inp.val() == 0){
        $this.text("Nominated for Special Consideration!")
        $inp.val(1);
        $this.addClass("btn-success").removeClass("btn-default");
    }else{
        $this.text("Nominate for Special Consideration");
        $inp.val(0);
        $this.addClass("btn-default").removeClass("btn-success")
    }
}

function save_vote(ev){
    ev.preventDefault();
    $.post('vote/', $('#vote-form').serialize(), null, 'html').then(function(data){
        $('#existing-votes-block').remove();
        $('#user-vote-block').replaceWith(data);
    });
}

function mark_read(ev){
    ev.preventDefault();
    $.post('mark_read/').then(function(text){
        $('#discussion-panel').replaceWith(text);
    });
}

function give_feedback(ev){
    ev.preventDefault();
    $.post('feedback/', $('#feedback-form').serialize()).then(function(text){
        $('#discussion-panel').replaceWith(text);
        $('#feedback-form textarea').val('');
    });
}

function leave_comment(ev){
    ev.preventDefault();
    $.post('comment/', $('#comment-form').serialize()).then(function(text){
        $('#discussion-panel').replaceWith(text);
    });
}

function toggle_bookmark(ev){
    ev.preventDefault();
    $.post($(this).attr('action')).then(function(data){
        $('#left-column').empty().html(data);
    });
}

TEMPLATES = {};

$(document).ready(function(){
    $('script[type="underscore/template"]').each(function(){
        var $this = $(this);
        TEMPLATES[$this.attr("id")] = _.template($this.text());
    });

    //Batch
    $('#proposal-tabs a').click(show_proposal_tabs);
    $('#unranked li').on('click', batch_add);
    $('#accept').on('click', 'li', batch_rem);
    $('#proposal-tabs a').first().tab("show");

    //
    $('#right-column').on('click', '.voting-stripe button', vote_click);
    $('#right-column').on('click', '#nominate', nominate_click);
    $('#right-column').on('click', '#save', save_vote);
    $('#right-column').on('click', '#mark-read', mark_read);
    $('#right-column').on('submit', '#feedback-form', give_feedback);
    $('#right-column').on('submit', '#comment-form', leave_comment);
    $('#left-column').on('submit', '#bookmark-form', toggle_bookmark);

    if($("#vote-form").length > 0){
        nominate_status();
    }
});
