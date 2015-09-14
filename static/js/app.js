function vote_comment_reason_handler(ev){
    $('#reason').val($('#comment-reason').val()).change();
}

var character_count = $('#character-count');
function reason_length_counter(ev){
    var content = $(ev.target).val();
    character_count.text(63-content.length);
}

$(document).ready(function(){
    $('#comment-reason').on('change', vote_comment_reason_handler);
    $('#reason').on('keyup change', reason_length_counter);
});
