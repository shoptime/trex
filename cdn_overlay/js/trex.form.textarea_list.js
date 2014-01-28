(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.form.textarea_list", "trex.form");

    function bind(context) {
        var $elements = $('.trex-textarea-list.widget', context);
        $elements.on('click', '.item button', function(e) {
            e.preventDefault();
            $(e.currentTarget).closest('.item').remove();
        });
        $elements.on('click', '.add-item button', function(e) {
            e.preventDefault();
            var $container = $(e.currentTarget).closest('.add-item')
            var $new_item = $($container.data('template'));
            $container.before($new_item);
            $new_item.find('textarea').focus();
        });
    }

    Trex.form._bind_functions.push(bind);
    if (Trex.opt.auto_bind_form_elements) {
        bind();
    }
})(window, jQuery);
