function show_proposal_tabs(ev){
    ev.preventDefault();
    $(this).tab('show');
}

function thunder_add(ev){
    var $accept = $('#accept');
    if ($accept.find('li').length >= 2){
        return;
    }
    var $this = $(this);
    var id = $this.data().id;
    $this.hide();
    $accept.append(TEMPLATES.ordered_row({id:id, title:TALKS[id]}));
}

function thunder_rem(ev){
    var $this=$(this),
        id = $this.find('input').val();
    $('#unranked-prop-'+id).show();
    $this.remove();
}

function star_click(){
    var $this = $(this);
    $this.prevAll().removeClass('glyphicon-star-empty').addClass('glyphicon-star');
    $this.nextAll().removeClass('glyphicon-star').addClass('glyphicon-star-empty');
    $this.removeClass('glyphicon-star-empty').addClass('glyphicon-star');
    score_stars();
}

function score_stars(){
    var rv = {},
        complete = true;
    $('.voting-stripe').each(function(){
        var $this = $(this),
            stars = $this.find('.glyphicon-star').length;
        if(stars){
            rv[$this.data().standard] = stars-1;
        }else{
            complete = false;
        }
    });
    $('#scores').val(JSON.stringify(rv));
    $('#save').attr('disabled', !complete)
}

TEMPLATES = {};

$(document).ready(function(){
    $('script[type="underscore/template"]').each(function(){
        var $this = $(this);
        TEMPLATES[$this.attr("id")] = _.template($this.text());
    });

    //Thunderdome
    $('#proposal-tabs a').click(show_proposal_tabs);
    $('#unranked li').on('click', thunder_add);
    $('#accept').on('click', 'li', thunder_rem);
    $('.voting-stripe span').on('click', star_click);
    $('#proposal-tabs a').first().tab("show");
});
