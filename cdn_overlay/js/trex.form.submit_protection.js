(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.form.submit_protection", "trex.form");

    function bind(context) {
        $('.wtform', context).on('submit', function() {
            var $form = $(this);
            $form.find('.form-actions button').prop('disabled', 'disabled');
        });
        $('.wtform .form-actions button', context).on('click', function() {
            var $btn = $(this);
            $btn
                .text('Processing...')
                .addClass('processing');
        });
    }

    Trex.form._bind_functions.push(bind);
    bind();
})(window, jQuery);
