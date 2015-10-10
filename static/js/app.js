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

function vote_click(){
    var $this = $(this);
    $this.siblings('input').val($this.data().val);
    $this.siblings().addClass('btn-default').removeClass('btn-primary');
    $this.addClass('btn-primary');
    var ready = true;
    $('.voting-stripe').each(function(){
        if($(this).find('.btn-primary').length <= 0){
            ready = false;
        }
    });
    $('#save').attr('disabled', !ready);
}

function nominate_click(){
    var $this=$(this),
        $inp = $(this).siblings('input');
    if($inp.val() == 0){
        $this.text("Nominated")
        $inp.val(1);
        $this.addClass("btn-success").removeClass("btn-primary");
    }else{
        $this.text("Nominate");
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
});
