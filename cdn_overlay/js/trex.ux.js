(function(window, $) {
    var Trex = window.Trex;
    Trex._module_check_deps("trex.ux", "trex");
    Trex.ux = new Trex._TrexModule();

    Trex.ux.check_element_deps = function(selector, deps) {
        var $el = $(selector);
        var args = Array.prototype.slice.apply(arguments);
        args.shift();
        args.unshift("$("+selector+")");
        if ($el.length) { Trex._check_deps.apply(Trex, args); }
    };

    $(function() {
        Trex.ux.check_element_deps('.trex-moment', 'trex.ux.moment');
        Trex.ux.check_element_deps('button.trex-post, .dropdown-menu a.trex-post, button.trex-post-confirm, .dropdown-menu a.trex-post-confirm, button.trex-post-simple-confirm', 'trex.ux.confirm');
        Trex.ux.check_element_deps('button.trex-modal-form', 'trex.ux.modal_form');
    });
})(window, jQuery);
