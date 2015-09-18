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

$(document).ready(function(){
    $('#comment-reason').on('change', vote_comment_reason_handler);
    $('#reason').on('keyup change', reason_length_counter);
    $('.vote-radio input').on('change', vote_radio_click);
});
