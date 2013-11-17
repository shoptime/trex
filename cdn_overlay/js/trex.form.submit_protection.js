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
                .data('current-text', $btn.text())
                .text('Processing...')
                .addClass('processing');
        });
    }

    Trex.form._bind_functions.push(bind);
    if (Trex.opt.auto_bind_form_elements) {
        bind();
    }

    Trex.form.submit_protection = {
        undo: function() {
            $('.wtform .form-actions button')
                .prop('disabled', false)
                .each(function(i, elem) {
                    var $elem = $(elem);
                    var old_text = $elem.data('current-text');
                    if ( old_text ) {
                        $elem.text(old_text);
                    }
                });
        }
    };
})(window, jQuery);
