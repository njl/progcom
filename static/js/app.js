function vote_comment_reason_handler(ev){
    $('#reason').val($('#comment-reason').val()).change();
}

var character_count = $('#character-count');
function reason_length_counter(ev){
    var content = $(ev.target).val();
    character_count.text(63-content.length);
}

function vote_radio_click(ev){
    var v = $('.vote-radio input:checked').val();
    if(v == 'nay'){
        $('#reasons-panel').show()
    }else{
        $('#reasons-panel').hide()
        $('#reason').val('').change();
    }
}

$(document).ready(function(){
    $('#comment-reason').on('change', vote_comment_reason_handler);
    $('#reason').on('keyup change', reason_length_counter);
    $('.vote-radio').on('click', vote_radio_click);
});
