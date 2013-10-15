(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.form.dependent_select", "trex.form");

    function bind(context) {
        $('.trex-dependent-select-field', context).each(function() {
            var $select = $(this);
            var $parent = $('#'+$select.data('parent'));
            var choices = $select.data('choices');
            var select_text = $select.data('select-text');

            function render_options() {
                var old_value = $select.val();
                $select.empty();
                if (choices[$parent.val()]) {
                    $select.prop('disabled', false);
                    if (select_text) {
                        $('<option></option>')
                            .attr('value', '')
                            .text(select_text)
                            .appendTo($select)
                        ;
                    }
                    _.each(choices[$parent.val()], function(choice) {
                        $('<option></option>')
                            .attr('value', choice[0])
                            .attr('selected', choice[0] === old_value)
                            .text(choice[1])
                            .appendTo($select)
                        ;
                    });
                }
                else {
                    $select.prop('disabled', true);
                }
            }

            $parent.on('change', render_options);
            render_options();
        });
    }

    Trex.form._bind_functions.push(bind);
    if (Trex.opt.auto_bind_form_elements) {
        bind();
    }
})(window, jQuery);
