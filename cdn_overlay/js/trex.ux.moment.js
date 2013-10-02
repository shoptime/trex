(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.ux.moment", "trex");

    $.fn.trex_moment = function() {
        this.each(function() {
            var $this = $(this);
            var m = moment($this.data('moment'));
            $this
                .text(m.from())
                .attr('title', m.format('dddd, MMMM Do YYYY, h:mm:ss a'))
            ;
        });
    };

    $('.trex-moment').trex_moment();
})(window, jQuery);
