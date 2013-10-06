(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.ux", "trex", "trex.util");
    Trex.ux = new Trex._TrexModule();

    $(function() {
        Trex.util.check_element_deps('.trex-moment', 'trex.ux.moment');
        Trex.util.check_element_deps('button.trex-post, .dropdown-menu a.trex-post, button.trex-post-confirm, .dropdown-menu a.trex-post-confirm, button.trex-post-simple-confirm', 'trex.ux.confirm');
        Trex.util.check_element_deps('button.trex-modal-form', 'trex.ux.modal_form');
    });
})(window, jQuery);
