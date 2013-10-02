(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.ux.confirm", "trex");

    $('body').on('click', 'button.trex-post, .dropdown-menu a.trex-post', function(e) {
        e.preventDefault();
        $('<form method="post"></form>')
            .append($('<input type="hidden" name="_csrf_token">').val($('html').data('csrf-token')))
            .attr('action', $(this).data('href') || $(this).attr('href'))
            .appendTo('body')
            .submit()
        ;
    });

    $('body').on('click', 'button.trex-post-confirm, .dropdown-menu a.trex-post-confirm', function(e) {
        e.preventDefault();
        var href = $(this).data('href');

        var modal = $('<div class="modal fade"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><a href="" class="close">&times</a><h3 class="modal-title"></h3></div><div class="modal-body"><p></p></div><div class="modal-footer"><a class="cancel btn btn-default">Cancel</a> <a class="confirm btn btn-primary">Confirm</a></div></div></div></div>');
        modal
            .find('.modal-header h3').text($(this).data('title')).end()
            .find('.modal-body p').text($(this).data('body')).end()
            .find('.modal-footer .cancel, .modal-header .close').click(function() {
                modal.modal('hide');
                return false;
            }).end()
            .find('.modal-footer .confirm').click(function() {
                modal.modal('hide');
                $('<form method="post"></form>')
                    .append($('<input type="hidden" name="_csrf_token">').val($('html').data('csrf-token')))
                    .attr('action', href)
                    .appendTo('body')
                    .submit()
                ;
                return false;
            }).end()
        ;
        if ( $(this).data('confirm-label') ) {
            modal.find('.modal-footer .confirm').text($(this).data('confirm-label'));
        }
        if ( $(this).data('confirm-label-class') ) {
            modal.find('.modal-footer .confirm').removeClass('btn-primary').addClass($(this).data('confirm-label-class'));
        }
        if ( $(this).data('cancel-label') ) {
            modal.find('.modal-footer .cancel').text($(this).data('cancel-label'));
        }
        modal
            .appendTo('body')
            .modal('show')
            .on('hidden', function() {
                modal.remove();
            })
        ;
    });

    $('button.trex-post-simple-confirm').each(function() {
        var $button = $(this);
        $(this).wrap('<span class="trex-post-simple-confirm-wrapper" style="display: inline-block; position: relative" />');
    });
    $(document).on('click', 'button.trex-post-simple-confirm', function(e) {
        e.preventDefault();
        var cleaned_up = false;
        var $button = $(e.currentTarget);
        if ($button.hasClass('opened')) {
            $button.removeClass('opened');
            return;
        }
        else {
            $button.addClass('opened');
        }

        var href = $button.data('href');
        var $confirm = $('<ul class="dropdown-menu"><li><a></a></li></ul>')
            .css({
                marginRight: '-2px',
                marginLeft: '-2px'
            })
            .find('a')
                .attr('href', href)
                .text('Confirm ' + $button.text())
                .on('click', function(e) {
                    e.preventDefault();
                    $('<form method="post"></form>')
                        .append($('<input type="hidden" name="_csrf_token">').val($('html').data('csrf-token')))
                        .attr('action', href)
                        .appendTo('body')
                        .submit()
                    ;
                })
            .end()
            .on('click', function(e) { e.stopPropagation(); cleanup(); })
        ;

        if ($button.offset().left >= $(document).width()/2) {
            $confirm.addClass('pull-right');
        }

        $button
            .closest('.trex-post-simple-confirm-wrapper')
            .append($confirm.show())
        ;

        var cleanup;
        cleanup = function() {
            if (cleaned_up) { return; }
            cleaned_up = true;
            $(document).off('click', cleanup);
            $button.removeClass('opened');
            $confirm.remove();
        };
        $(document).on('click', cleanup);
    });

})(window, jQuery);
