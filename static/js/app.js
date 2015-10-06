function vote_comment_reason_handler(ev){
    $('#reason').val($('#comment-reason').val()).change();
}

var character_count = $('#character-count');
function reason_length_counter(ev){
    var content = $(ev.target).val();
    character_count.text(63-content.length);
}
var reason = "";
function vote_radio_click(ev){
    var v = $('.vote-radio input:checked').val();
    if(v == 'nay'){
        $('#reason').val(reason);
        $('#reasons-panel').show()
    }else{
        console.log($('#reason'), $('#reason').val());
        $('#reasons-panel').hide()
        reason = $('#reason').val();
        console.log('hiding reasons', reason);
        $('#reason').val('').change();
    }
}

function show_proposal_tabs(ev){
    ev.preventDefault();
    $(this).tab('show');
}

function thunder_unranked(ev){
    var $this = $(this);
    var id = $this.data().id;
    $this.remove();
    $('#ranked').append(TEMPLATES.ordered_row({id:id, title:TALKS[id]}));
    thunder_quantity_change();
    $('#save').attr('disabled', !!$('#unranked tr').length);
}

function thunder_down(ev){
    var $this = $(this).parents('.ordered');
    if(!$this.next().length){
        return;
    }
    $this.next().after($this);
    thunder_quantity_change();
}
function thunder_up(ev){
    var $this = $(this).parents('.ordered');
    if(!$this.prev().length){
        return;
    }
    $this.after($this.prev());
    thunder_quantity_change();
}

function thunder_quantity_change(){
    var $this = $('#quantity-selector'),
        quantity = parseInt($this.val());
    $('#ranked tr').removeClass('success').slice(0, quantity).addClass('success');
    var ranked = [];
    $('#ranked tr').each(function(){
        ranked.push($(this).data().id);
    });
    $('#hidden-ranked').val(JSON.stringify(ranked));
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
    $('#comment-reason').on('change', vote_comment_reason_handler);
    $('#reason').on('keyup change', reason_length_counter);
    $('.vote-radio input').on('change', vote_radio_click);

    //Thunderdome
    $('#proposal-tabs a').click(show_proposal_tabs);
    $('#unranked tr').on('click', thunder_unranked);
    $('#ranked').on('click', 'button.thunder-down', thunder_down);
    $('#ranked').on('click', 'button.thunder-up', thunder_up);
    $('#quantity-selector').on('change', thunder_quantity_change);
    $('.voting-stripe span').on('click', star_click);
    if($('#proposal-tabs').length){
        //It's Thunderdome
        $('#proposal-tabs a').first().tab("show");
        if(VOTE){
            $('#quantity-selector').val(VOTE.accept);
            _.each(VOTE.ranked, function(id){
                $('#unranked-prop-'+id).click();
            });
        }
    }
});
