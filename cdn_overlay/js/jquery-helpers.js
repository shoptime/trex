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

    $(document).on('click', 'button.trex-modal-form', function(e) {
        e.preventDefault();

        var $button = $(e.currentTarget);

        var button_id = $button.attr('id');
        var modal_id  = button_id + '-modal';
        var title_id  = button_id + '-modal-title';
        var $modal    = $('<div class="modal fade trex-modal-form-modal" tabindex="-1" role="dialog" aria-hidden="true"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button><h4 class="modal-title"></h4></div><div class="modal-body"><span class="loading"></span> Loading...</div><div class="modal-footer"><span class="loading"></span><span class="label label-danger failed">Failed</span><span class="label label-success success">Success</span><button type="button" class="btn btn-primary">Save changes</button></div></div></div></div>');

        $modal.attr('id', modal_id);
        $modal.attr('aria-labelledby', title_id);
        $modal.find('.modal-header h4')
            .attr('id', title_id)
            .text($button.data('title'));
        $modal.find('.modal-footer .btn-primary')
            .prop('disabled', true)
            .text($button.data('button-title'));
        $modal.find('.modal-footer .loading').hide();
        $modal.on('hidden.bs.modal', function() {
            _.defer(function() {
                $modal.remove();
            });
        });

        function handle_render(data) {
            if ( data.state != 'render' ) {
                $modal.find('.modal-body').text('Sorry, this form is currently unavailable');
                throw Error("Did not receive a 'render' response from server");
            }
            var $content = $('<div>' + data.content + '</div>');
            var $form = $content.find('form');
            $modal.find('.modal-body').html($content.children());
            Trex.bind_form_widgets($form);
            $modal.on('shown.bs.modal', function() {
                $form.find('.form-control').first().focus();
            });
            // Make pressing enter in fields do a form submit, like most forms usually do.
            $form.find('input').on('keyup', function(e) {
                if ( e.keyCode === 13 ) {
                    $form.submit();
                }
            });
            $form.on('submit', function(e) {
                e.preventDefault();
                $modal.find('.modal-footer .loading').show();
                $modal.find('.modal-footer .failed').hide();
                $modal.find('.modal-body').append('<div class="overlay"></div>');
                $.ajax({
                    type: 'POST',
                    url: $button.data('href'),
                    data: $form.serialize(),
                    success: function(data) {
                        if ( data.state == 'render' ) {
                            // This is generally because form submission failed
                            $form.off('submit');
                            _.defer(function() { handle_render(data); });
                            return;
                        }
                        else if ( data.state == 'ok' ) {
                            $modal.find('.modal-footer .success').show();
                            if ( data.action === 'reload' ) {
                                window.location.reload();
                                return;
                            }
                            throw Error("Unknown action '" + data.action + "' returned by server");
                        }
                        else {
                            throw Error('Unknown state returned from server');
                        }
                    },
                    error: function() {
                        $modal.find('.modal-footer .failed').show();
                        $modal.find('.modal-body .overlay').remove();
                    }
                }).always(function() {
                    $modal.find('.modal-footer .loading').hide();
                });
            });
            $modal.find('.modal-footer .btn-primary')
                .prop('disabled', false)
                .off('click')
                .click(function() {
                    $form.submit();
                    return false;
                });
        }

        // Load content
        $.ajax({
            type: 'GET',
            url: $button.data('href'),
            cache: false,
            success: handle_render,
            error: function() {
                $modal.find('.modal-body').text('Sorry, this form is currently unavailable');
            },
        });

        $('body').append($modal);
        $('#' + modal_id).modal();
    });
})(jQuery);
