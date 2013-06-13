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

    $('.trex-file-list-widget').each(function() {
        var $widget = $(this);
        var files = new (Backbone.Collection.extend({ model: Trex.FileListWidgetModel }))();
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
        files.on('add remove change', function() {
            // Keep the javascript up to date
            $widget.find('input:hidden').val(JSON.stringify(files));
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
                        .html('<a class="close">&times</a> <span class="filename"></span> <span class="size"></span><div class="progress progress-striped active"><div class="bar"></div></div><div class="label label-important">Upload failed</div>')
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
                    this.$('.size').text('('+this.model.pretty_size()+')');
                    this.$('.bar').css('width', this.model.get('progress')+'%');
                    this.$('.progress').toggle(this.model.get('progress')<100);
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
                console.error("Only support XHR for now");
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
                            console.log('XHR file upload complete');
                            var data = JSON.parse(this.response);
                            console.log('Response data: ', data);
                            model.set(data);
                        }
                        else {
                            model.set('error', true);
                        }
                    }
                };
                xhr.onabort = xhr.onerror = function() {
                    console.error('XHR failed: ', this, arguments);
                    model.set('error', true);
                };
                xhr.upload.onprogress = function(e) {
                    model.set('progress', e.loaded / e.total * 100);
                };
                xhr.send(file);
            });
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
})(jQuery);
