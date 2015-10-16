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
    $accept.append(TEMPLATES.ordered_row({id:id, title:TALKS[id]}));
}

function batch_rem(ev){
    var $this=$(this),
        id = $this.find('input').val();
    $('#unranked-prop-'+id).show();
    $this.remove();
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
    $('#save').attr('disabled', $('#vote-form input[value=-1]').length > 0);
    nominate_status()
}

function nominate_click(){
    var $this=$(this),
        $inp = $(this).siblings('input');
    if($inp.val() == 0){
        $this.text("Nominated for Special Consideration")
        $inp.val(1);
        $this.addClass("btn-success").removeClass("btn-default");
    }else{
        $this.text("Nominate for Special Consideration");
        $inp.val(0);
        $this.addClass("btn-default").removeClass("btn-success")
    }
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
    $('.voting-stripe button').on('click', vote_click);
    $('#proposal-tabs a').first().tab("show");
    $('#nominate').on('click', nominate_click);
    if($("#vote-form").length > 0){
        nominate_status();
    }
});
