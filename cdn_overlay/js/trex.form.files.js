(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.form.files", "trex.form");
    Trex.form.files = new Trex._TrexModule();

    Trex.form.files.can_do_xhr_upload = !!(window.File && window.FileList && window.FileReader && (new XMLHttpRequest()).upload);
    var log = new Trex.Logger('trex.form.files');

    Trex.form.files.UploadModel = function() { Backbone.Model.apply(this, arguments); }; // {{{
    Trex.form.files.UploadModel = Backbone.Model.extend({
        constructor: Trex.form.files.UploadModel,
        defaults: {
            progress: 0,
            error: false
        },
        has_progress: function() {
            var progress = this.get('progress');
            return !isNaN(parseFloat(progress)) && isFinite(progress);
        },
        pretty_size: function() {
            var kilobyte = 1024;
            var megabyte = kilobyte * 1024;
            var gigabyte = megabyte * 1024;
            var terabyte = gigabyte * 1024;
            var bytes = this.get('size');
            var precision = 2;

            if ((bytes >= 0) && (bytes < kilobyte)) {
                return bytes + ' B';
            } else if ((bytes >= kilobyte) && (bytes < megabyte)) {
                return (bytes / kilobyte).toFixed(precision) + ' KB';
            } else if ((bytes >= megabyte) && (bytes < gigabyte)) {
                return (bytes / megabyte).toFixed(precision) + ' MB';
            } else if ((bytes >= gigabyte) && (bytes < terabyte)) {
                return (bytes / gigabyte).toFixed(precision) + ' GB';
            } else if (bytes >= terabyte) {
                return (bytes / terabyte).toFixed(precision) + ' TB';
            } else {
                return bytes + ' B';
            }
        },
        toJSON: function() {
            var data = Backbone.Model.prototype.toJSON.apply(this, arguments);
            // we leave: filename, size, mime, url, oid
            delete data.progress;
            delete data.error;
            delete data.id;
            return data;
        }
    }); // }}}

    Trex.form.files.do_xhr_upload = function(url, file_input, collection, options) { // {{{
        var models = [];
        _.each(file_input.files, function(file) {
            var model = new Trex.form.files.UploadModel();
            model.set({
                id: model.cid,
                filename: file.name,
                size: file.size,
                mime: file.type
            });
            models.push(model);
            if (collection) {
                collection.add(model);
            }
            if (options.type_validators) {
                var valid = false;
                var segments = file.name.split('.');
                var extension = segments[segments.length-1].toLowerCase();
                _.each(options.type_validators.rules, function(rule) {
                    if (
                        (rule[0] === null || rule[0] == file.type)
                        &&
                        (rule[1] === null || rule[1] == extension)
                    ) {
                        valid = true;
                    }
                });
                if (!valid) {
                    model.set({
                        error: true,
                        error_message: options.type_validators.message,
                    });
                    return;
                }
            }

            var xhr = new XMLHttpRequest();
            xhr.open('POST', url, true);
            xhr.setRequestHeader('X-CSRFToken', $('html').data('csrf-token'));
            xhr.setRequestHeader('X-FileName', model.get('filename')),
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.setRequestHeader('Content-Type', model.get('mime'));
            xhr.onreadystatechange = function() {
                if (this.readyState == this.DONE) {
                    if (this.status == 200) {
                        log.d('XHR file upload complete');
                        var data = JSON.parse(this.response);
                        model.set(data);
                    }
                    else {
                        model.set('error', true);
                    }
                }
            };
            xhr.onabort = xhr.onerror = function() {
                log.e('XHR failed: ', this, arguments);
                model.set('error', true);
            };
            xhr.upload.onprogress = function(e) {
                model.set('progress', e.loaded / e.total * 100);
            };
            xhr.send(file);
        });
        return models;
    }; // }}}

    Trex.form.files.do_iframe_upload = function(url, file_input, collection) { // {{{
        log.d("Doing iframe upload");
        var $file = $(file_input);
        var filename = $file.val().replace(/^.*\\/, '');
        var model = new Trex.form.files.UploadModel({
            filename: filename,
            progress: 'unknown'
        });
        model.set('id', model.cid);
        var upload_id = 'trex-file-upload-' + model.cid;
        var $form = $file.closest('form');
        var $field_name = $('<input type="hidden" name="_trex_file_field_name">').val($file.attr('name')).appendTo($form);
        var old_form_action = $form.attr('action');
        var old_form_target = $form.attr('target');
        $form
            .attr('action', url)
            .attr('target', upload_id)
        ;
        var upload_complete = false;
        var $iframe = $('<iframe></iframe>')
            .hide()
            .attr('id', upload_id)
            .attr('name', upload_id)
            .on('load', function() {
                $iframe.remove();
                $field_name.remove();
                if (!upload_complete) {
                    model.set('error', true);
                }
            })
            .on('upload', function(e, file_info) {
                upload_complete = true;
                log.d("iframe upload complete");
                model.set(file_info);
            })
        ;
        $('body').append($iframe);
        $form.submit();
        if (collection) {
            collection.add(model);
        }
        $form
            .attr('action', old_form_action)
            .attr('target', old_form_target)
        ;
        if (!old_form_target) {
            $form.removeAttr('target');
        }
        return [model];
    }; // }}}

    $.fn.trex_delayed_submit = function(message, cb) { // {{{
        if (!(this.length === 1 && this.filter('form').length === 1)) {
            throw new Error("This method only works on single form elements");
        }
        var $form = this;
        var first_bind = false;
        if (!$form.data('trex_delayed_submit')) {
            $form.data('trex_delayed_submit', {
                message: message,
                callbacks: []
            });
            first_bind = true;
        }
        var form_data = $form.data('trex_delayed_submit');
        if (typeof(cb) === 'function') {
            form_data.callbacks.push(cb);
        }

        if (first_bind) {
            var pass = false;
            $form.on('submit', function(e) {
                if (pass) { return; }
                e.preventDefault();

                var $to_disable = $form.find('input:not(:disabled), select:not(:disabled), textarea:not(:disabled), button:not(.disabled), a:not(.disabled)');
                var $primary_button = $form.find('.form-actions .btn:eq(0)');
                $to_disable.prop('disabled', true).toggleClass('disabled');

                var old_text = $primary_button.text();
                $primary_button.text(form_data.message);

                var list = _.map(form_data.callbacks, function(cb) { return cb(); });
                $.when.apply($, list).then(
                    function() {
                        $to_disable.prop('disabled', false).toggleClass('disabled');
                        $primary_button.text(old_text);
                        pass = true;
                        $form.submit();
                    },
                    function() {
                        $to_disable.prop('disabled', false).toggleClass('disabled');
                        $primary_button.text(old_text);
                    }
                );
            });
        }
    }; // }}}


    function bind(context) {
        $('.trex-file-list-widget', context).each(function() {
            var $widget = $(this);
            var files = new (Backbone.Collection.extend({
                model: Trex.form.files.UploadModel,
                uploads_complete: function() {
                    return this.length == this.filter(function(m) { return m.get('progress') == 100 && m.get('oid'); }).length;
                }
            }))();
            if ($widget.find('input[type=hidden]').val()) {
                _.each(JSON.parse($widget.find('input[type=hidden]').val()), function(data) {
                    var model = new Trex.form.files.UploadModel(data);
                    model.set({
                        id: model.cid,
                        progress: 100
                    });
                    files.add(model);
                });
            }
            var finished_uploads;
            $widget.closest('form').trex_delayed_submit('Waiting for file uploads to finish ...', function() {
                finished_uploads = $.Deferred();
                if (files.uploads_complete()) {
                    finished_uploads.resolve();
                }
                return finished_uploads;
            });
            files.on('add remove change', function(model) {
                // Keep the javascript up to date
                $widget.find('input[type=hidden]').val(JSON.stringify(files.where({error:false})));
                if (finished_uploads && files.uploads_complete()) {
                    if (model.get('error')) {
                        finished_uploads.reject();
                    }
                    else {
                        finished_uploads.resolve();
                    }
                }
            });
            var files_view = new Trex.util.ViewCollection({
                view: Backbone.View.extend({
                    className: "file",
                    events: {
                        'click .close': 'remove_file',
                        'click .filename.linkable': 'open_link'
                    },
                    initialize: function() {
                        this.$el
                            .addClass(this.className)
                            .html('<a class="close">&times</a> <span class="filename"></span> <span class="size"></span><div class="progress progress-striped active"><div class="bar"></div></div><div class="uploading"></div><div class="label label-important">Upload failed</div>')
                        ;
                        this.listenTo(this.model, 'change', this.render);
                        this.render();
                    },
                    render: function() {
                        this.$('.filename')
                            .text(this.model.get('filename'))
                            .data('url', this.model.get('url'))
                            .toggleClass('linkable', !!this.model.get('url'))
                        ;
                        this.$('.size').toggle(!!this.model.get('size')).text('('+this.model.pretty_size()+')');
                        if (this.model.get('progress') === 'unknown') {
                            this.$('.progress').hide();
                            this.$('.uploading').show();
                        }
                        else {
                            this.$('.uploading').hide();
                            this.$('.bar').css('width', this.model.get('progress')+'%');
                            this.$('.progress').toggle(this.model.get('progress')<100);
                        }
                        this.$('.label').toggle(!!this.model.get('error'));
                    },
                    remove_file: function(e) {
                        e.preventDefault();
                        this.model.collection.remove(this.model);
                    },
                    open_link: function(e) {
                        e.preventDefault();
                        window.open(this.model.get('url'), '_blank');
                    }
                }),
                model: files,
                el: $widget.find('.files')
            });

            $widget.on('change.trexFileListWidget', 'input[type=file]', function(e) {
                if (Trex.form.files.can_do_xhr_upload) {
                    Trex.form.files.do_xhr_upload($widget.data('xhr-url'), e.target, files);
                }
                else {
                    Trex.form.files.do_iframe_upload($widget.data('iframe-url'), e.target, files);
                }
                $(this).val('');
            });
        });

        var FileView = Backbone.View.extend({
            initialize: function(opt) {
                this.opt = _.extend({}, opt);
                if (this.model) {
                    this.listenTo(this.model, 'change', this.render);
                }
            },
            change_model: function(new_model) {
                if (this.model) {
                    this.stopListening(this.model);
                }
                this.model = new_model;
                if (this.model) {
                    this.listenTo(this.model, 'change', this.render);
                }
                this.render();
            },
            state: function() {
                if (!this.model) { return 'empty'; }
                if (this.model.get('error')) { return 'error'; }
                if (this.model.get('url')) { return 'valid'; }
                return 'uploading';
            },
            render: function(initial_render) {
                var state = this.state();

                // Ensure correct "Clear" button visibility
                this.$('button').toggle(state == 'valid' && this.opt.allow_clear);

                // Ensure correct uploading spinner visibility
                this.$('.uploading').css('display', state == 'uploading' ? 'inline-block' : 'none');

                // Ensure correct error visibility
                this.$el.closest('.form-group').toggleClass('has-error', state == 'error');
                this.$el.closest('.form-group').find('.help-block-error').remove();
                if (state == 'error') {
                    $('<span class="help-block help-block-error"></span>').text(this.model.get('error_message') || 'An error occured uploading.').appendTo(this.$el);
                }

                switch (state) {
                    case 'valid':
                        this.render_file_display();
                        break;
                    case 'uploading':
                        this.render_progress();
                        break;
                    case 'empty':
                        this.render_empty();
                        break;
                    default:
                        this.$('.file-display').hide();
                }
            },
            render_empty: function() {
                this.$('.file-display').hide();
            },
            render_file_display: function() {
                this.$('.file-display').text(this.model.get('filename')).show();
            },
            render_progress: function() {
                if (!this.model.has_progress()) {
                    // Browser isn't indicating progress, we'll just make-do with the upload spinner
                    this.$('.file-display').hide();
                    return;
                }
                var progressbar = this.$('.file-display .progress');
                if (progressbar.length === 0) {
                    this.$('.file-display').html('<div class="progress"><div class="progress-bar"></div></div>').show();
                    progressbar = this.$('.progress').css({margin: 0, width: 300});
                }
                progressbar.find('.progress-bar').css('width', this.model.get('progress') + '%');
            }
        });
        var ImageView = FileView.extend({
            render_empty: function() {
                this.$('.file-display').html('<div class="thumbnail"><span class="no-image">No image</span></div>').show();
            },
            render_file_display: function() {
                this.$('.file-display').html('<div class="thumbnail"><img></div>').show().find('img').attr('src', this.model.get('url'));
            }
        });

        $('.trex-image-widget, .trex-file-widget', context).each(function() {
            var $widget = $(this);
            var options = _.extend({}, $widget.data('options'));
            var files = new (Backbone.Collection.extend({
                model: Trex.form.files.UploadModel,
                uploads_complete: function() {
                    return this.length == this.filter(function(m) { return m.get('progress') == 100 && m.get('oid') || m.get('error'); }).length;
                }
            }))();
            if ($widget.find('input[type=hidden]').val()) {
                var model = new Trex.form.files.UploadModel(JSON.parse($widget.find('input[type=hidden]').val()));
                model.set({
                    id: model.cid,
                    progress: 100
                });
                files.add(model);
            }
            var finished_uploads;
            $widget.closest('form').trex_delayed_submit('Waiting for file uploads to finish ...', function() {
                finished_uploads = $.Deferred();
                if (files.uploads_complete()) {
                    finished_uploads.resolve();
                }
                return finished_uploads;
            });
            files.on('add remove change reset', function() {
                // Keep the javascript up to date
                var model = files.where({error:false})[0];
                $widget.find('input[type=hidden]').val(model ? JSON.stringify(model) : '');

                if (finished_uploads && files.uploads_complete()) {
                    if (model.get('error')) {
                        finished_uploads.reject();
                    }
                    else {
                        finished_uploads.resolve();
                    }
                }
            });

            var view;
            if ($widget.hasClass('trex-image-widget')) {
                view = new ImageView(_.extend({
                    el: $widget,
                    model: files.first(),
                }, options));
            }
            else {
                view = new FileView(_.extend({
                    el: $widget,
                    model: files.first(),
                }, options));
            }
            window.f = files;
            window.v = view;

            $widget.on('change.trexImageWidget', 'input[type=file]', function(e) {
                var model;
                if (Trex.form.files.can_do_xhr_upload) {
                    model = Trex.form.files.do_xhr_upload($widget.data('xhr-url'), e.target, null, options)[0];
                }
                else {
                    model = Trex.form.files.do_iframe_upload($widget.data('iframe-url'), e.target, null, options)[0];
                }
                files.reset(model);
                view.change_model(model);
                $(this).val('');
            });
            $widget.find('button').on('click', function() {
                files.reset([]);
                view.change_model();
            });
        });
    }

    Trex.form._bind_functions.push(bind);
    if (Trex.opt.auto_bind_form_elements) {
        bind();
    }
})(window, jQuery);
