(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.ux.modal_form", "trex", "trex.form");

    $(document).on('click', 'button.trex-modal-form, .dropdown-menu a.trex-modal-form', function(e) {
        e.preventDefault();

        var $button = $(e.currentTarget);

        var button_id = $button.attr('id');
        var modal_id  = button_id + '-modal';
        var title_id  = button_id + '-modal-title';
        var $modal;
        if (Trex.opt.bs_version === 3) {
            $modal = $('<div class="modal fade trex-modal-form-modal" tabindex="-1" role="dialog" aria-hidden="true"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button><h4 class="modal-title"></h4></div><div class="modal-body"><span class="loading"></span> Loading...</div><div class="modal-footer"><span class="loading"></span><span class="label label-danger failed">Failed</span><span class="label label-success success">Success</span><button type="button" class="btn btn-primary">Save changes</button></div></div></div></div>');
        }
        else if (Trex.opt.bs_version === 2) {
            $modal = $('<div class="modal hide fade trex-modal-form-modal"><div class="modal-header"><button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button><h3 class="modal-title"></h3></div><div class="modal-body"><span class="loading"></span> Loading...</div><div class="modal-footer"><span class="loading"></span><span class="label label-danger failed">Failed</span><span class="label label-success success">Success</span><button type="button" class="btn btn-primary">Save changes</button></div></div></div></div>');
        }
        else {
            throw Error('Unknown bootstrap version in Trex.opt.bs_version');
        }

        $modal.attr('id', modal_id);
        $modal.attr('aria-labelledby', title_id);
        $modal.find('.modal-header .modal-title')
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
        var modal_visible = $.Deferred();
        $modal.on('shown.bs.modal', function() {
            modal_visible.resolve();
        });

        function handle_render(data) {
            if ( data.state != 'render' ) {
                $modal.find('.modal-body').text('Sorry, this form is currently unavailable');
                Trex.log.e("Did not receive a 'render' response from server");
                return;
            }
            var $content = $('<div>' + data.content + '</div>');
            var $form = $content.find('form');
            $modal.find('.modal-body').html($content.children());
            modal_visible.then(function() {
                Trex.form.bind_widgets($form);
                $form.find('.form-control').first().focus();
            });
            $form.on('submit', function(e) {
                e.preventDefault();
                $modal.find('.modal-footer .loading').show();
                $modal.find('.modal-footer .failed').hide();
                $modal.find('.modal-body').append('<div class="overlay"></div>');
                $.ajax({
                    type: 'POST',
                    url: $button.data('href') || $button.attr('href'),
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
                            var action = data.action || $button.data('action');
                            switch (action) {
                                case 'reload':
                                    window.location.reload();
                                    break;
                                case 'redirect':
                                    window.location = data.url || $button.data('url');
                                    break;
                                case 'close-modal':
                                    $modal.modal('hide');
                                    break;
                                default:
                                    throw Error("Unknown action '" + action + "' returned by server");
                            }
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
            url: $button.data('href') || $button.attr('href'),
            cache: false,
            success: handle_render,
            error: function() {
                $modal.find('.modal-body').text('Sorry, this form is currently unavailable');
            }
        });

        $('body').append($modal);
        $('#' + modal_id).modal();
    });
})(window, jQuery);
