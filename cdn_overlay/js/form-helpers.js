(function($) {
    var can_do_xhr_upload = window.File && window.FileList && window.FileReader && (new XMLHttpRequest()).upload;

    Trex.FileListWidgetModel = function() {};
    Trex.FileListWidgetModel = Backbone.Model.extend({
        defaults: {
            progress: 0,
            error: false
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
    });

    $.fn.trex_delayed_submit = function(message, cb) {
        if (!this.length === 1 && this.filter('form').length === 1) {
            throw new Error("This method only works on single form elements");
        }
        var $form = this;
        var first_bind = false;
        if (!$form.data('trex_delayed_submit')) {
            $form.data('trex_delayed_submit', {
                message: message,
                callbacks: [],
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
    };

    $('.trex-file-list-widget').each(function() {
        var log = new Trex.Logger('file-upload');
        var $widget = $(this);
        var files = new (Backbone.Collection.extend({
            model: Trex.FileListWidgetModel,
            uploads_complete: function() {
                return this.length == this.filter(function(m) { return m.get('progress') == 100 && m.get('oid'); }).length;
            },
        }))();
        window.f = files;
        if ($widget.find('input:hidden').val()) {
            _.each(JSON.parse($widget.find('input:hidden').val()), function(data) {
                var model = new Trex.FileListWidgetModel(data);
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
            $widget.find('input:hidden').val(JSON.stringify(files.where({error:false})));
            if (finished_uploads && files.uploads_complete()) {
                if (model.get('error')) {
                    finished_uploads.reject();
                }
                else {
                    finished_uploads.resolve();
                }
            }
        });
        var files_view = new Trex.ViewCollection({
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
            if (can_do_xhr_upload) {
                do_xhr_upload(e.target);
            }
            else {
                do_iframe_upload(e.target);
            }
            $(this).val('');
        });

        function do_xhr_upload(file_input) {
            _.each(file_input.files, function(file) {
                var model = new Trex.FileListWidgetModel();
                model.set({
                    id: model.cid,
                    filename: file.name,
                    size: file.size,
                    mime: file.type
                });
                files.add(model);
                var xhr = new XMLHttpRequest();
                xhr.open('POST', $widget.data('xhr-url'), true);
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
        }

        function do_iframe_upload(file_input) {
            log.d("Doing iframe upload");
            var $file = $(file_input);
            var filename = $file.val().replace(/^.*\\/, '');
            var model = new Trex.FileListWidgetModel({
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
                .attr('action', $widget.data('iframe-url'))
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
            files.add(model);
            $form
                .attr('action', old_form_action)
                .attr('target', old_form_target)
            ;
            if (!old_form_target) {
                $form.removeAttr('target');
            }
        }
    });

    $('.trex-dependent-select-field').each(function() {
        var $select = $(this);
        var $parent = $('#'+$select.data('parent'));
        var choices = $select.data('choices');
        var select_text = $select.data('select-text');

        function render_options() {
            var old_value = $select.val();
            $select.empty();
            if (choices[$parent.val()]) {
                $select.prop('disabled', false);
                if (select_text) {
                    $('<option></option>')
                        .attr('value', '')
                        .text(select_text)
                        .appendTo($select)
                    ;
                }
                _.each(choices[$parent.val()], function(choice) {
                    $('<option></option>')
                        .attr('value', choice[0])
                        .attr('selected', choice[0] === old_value)
                        .text(choice[1])
                        .appendTo($select)
                    ;
                });
            }
            else {
                $select.prop('disabled', true);
            }
        }

        $parent.on('change', render_options);
        render_options();
    });

    $('.trex-date-field').each(function() {
        $(this).datepicker({format: "yyyy-mm-dd"});
    });

    $('.trex-chosen-select-field').chosen();
})(jQuery);
