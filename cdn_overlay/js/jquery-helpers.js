// Provides simple ways to make buttons that actually do POST requests
//
// e.g.:
// <button
//     data-href="{{ url_for('.dangerous', id=library.id, item_id=item.id) }}"
//     class="post-confirm btn"
//     data-title="{{_("Confirm dangerous action")}}"
//     data-body="{{_("Are you sure you want to end the world?")}}"
//     data-confirm-label="{{_("End world")}}"
//     data-cancel-label="{{ _("Cancel") }}"
// >{{ _('End world') }}</button>

(function($) {
    $.ajaxPrefilter(function(options, originalOptions, jqXHR) {
        if ( options.type.toLowerCase() == 'post' ) {
            jqXHR.setRequestHeader('X-CSRFToken', $('html').data('csrf-token'));
        }
    });

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

        var modal = $('<div class="modal fade"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><a href="" class="close">&times</a><h3></h3></div><div class="modal-body"><p></p><p><a class="cancel btn btn-default">Cancel</a> <a class="confirm btn btn-primary">Confirm</a></p></div></div></div></div>');
        modal
            .find('.modal-header h3').text($(this).data('title')).end()
            .find('.modal-body p:first-child').text($(this).data('body')).end()
            .find('.modal-body .cancel, .modal-header .close').click(function() {
                modal.modal('hide');
                return false;
            }).end()
            .find('.modal-body .confirm').click(function() {
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
            modal.find('.modal-body .confirm').text($(this).data('confirm-label'));
        }
        if ( $(this).data('confirm-label-class') ) {
            modal.find('.modal-body .confirm').removeClass('btn-primary').addClass($(this).data('confirm-label-class'));
        }
        if ( $(this).data('cancel-label') ) {
            modal.find('.modal-body .cancel').text($(this).data('cancel-label'));
        }
        modal
            .appendTo('body')
            .modal('show')
            .on('hidden', function() {
                modal.remove();
            })
        ;
    });

    $(document).on('click', 'button.trex-post-simple-confirm', function(e) {
        e.preventDefault();
        var cleaned_up = false;
        var $button = $(e.currentTarget);
        var href = $button.data('href');
        var $confirm = $('<ul class="dropdown-menu"><li><a></a></li></ul>')
            .css({
                marginRight: '-2px',
                marginLeft: '-2px',
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
            .css('position', 'relative')
            .append($confirm.show())
        ;

        var cleanup;
        cleanup = function() {
            if (cleaned_up) { return; }
            cleaned_up = true;
            $(document).off('click', cleanup);
            $button.css('position', '');
            $confirm.remove();
        };
        $(document).on('click', cleanup);
    });
})(jQuery);
