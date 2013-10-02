(function(window, $) {
    var Trex = window.Trex;
    Trex._module_check_deps("trex.form.star_rating", "trex.form");

    function bind(context) {
        $('.trex-star-rating-field', context).each(function() {
            var $input = $(this);
            var high_label = $input.data('high-label');
            var low_label = $input.data('low-label');
            var star_count = parseInt($input.data('star-count'), 10);
            var $stars = {};
            var value = parseInt($input.val(), 10);
            var hover_value = null;
            var $el = $('<table><tbody><tr></td></tbody><tfoot><tr><td></td><td class="text-right"></td></tr></tfoot></table>');
            $el
                .find('tfoot td:eq(0)').text(low_label).attr('colspan', Math.floor(star_count/2)).end()
                .find('tfoot td:eq(1)').text(high_label).attr('colspan', Math.ceil(star_count/2)).end()
            ;

            var render = function() {
                _.each($stars, function($star, v) {
                    v = parseInt(v, 10);
                    if (hover_value) {
                        $star.toggleClass('hover', v<=hover_value);
                    }
                    else {
                        $star.removeClass('hover');
                    }
                    $star.toggleClass('selected', v<=value);
                });
            };

            var i;
            for (i=1; i<=star_count; i++) {
                $stars[i] = $('<td><div></div></td>')
                    .data('value', i)
                    .on('click', function() {
                        value = $(this).data('value');
                        $input.val(value);
                        render();
                    })
                    .hover(
                        function() {
                            hover_value = $(this).data('value');
                            render();
                        },
                        function() {
                            hover_value = null;
                            render();
                        }
                    )
                ;
                $el.find('tbody tr').append($stars[i]);
            }
            $el.insertAfter($input);
            render();
        });
    }

    Trex.form._bind_functions.push(bind);
    bind();
})(window, jQuery);
