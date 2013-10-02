(function(window, $) {
    var Trex = window.Trex;
    Trex._module_check_deps("trex.form", "trex", "trex.ux");
    Trex.form = new Trex._TrexModule();

    Trex.form._bind_functions = [];

    Trex.form.bind_widgets = function(context) {
        _.each(this._bind_functions, function(func) {
            func.call(this, context);
        }, this);
    };

    $(function() {
        Trex.ux.check_element_deps('.trex-date-field, .trex-time-field', 'trex.form.datetime');
        Trex.ux.check_element_deps('.trex-chosen-select-field', 'trex.form.chosen_select');
        Trex.ux.check_element_deps('.trex-invite-field', 'trex.form.invites');
        Trex.ux.check_element_deps('.trex-dependent-select-field', 'trex.form.dependent_select');

        Trex.ux.check_element_deps('.trex-file-list-widget', 'trex.form.files');
        Trex.ux.check_element_deps('.trex-image-widget', 'trex.form.files');
        Trex.ux.check_element_deps('.trex-star-rating-field', 'trex.form.star_rating');
    });
})(window, jQuery);
