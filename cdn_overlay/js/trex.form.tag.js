(function(window, $, Backbone, _) {
    var Trex = window.Trex;
    Trex._register_module("trex.form.tag", "trex.form");

    var module = Trex.form.tag = new Trex._TrexModule();
    var log = new Trex.Logger('trex.form.tag');

    module.opt_for = {};

    Trex.form.tag.tag = function() { Backbone.Model.apply(this, arguments); };
    module.tag = Backbone.Model.extend({
        constructor: module.tag,
        _class: 'Trex.form.tag.tag',
        matches: function(query) {
            var query = query.toLowerCase();
            var name = this.get('name');
            var id = this.id;

            var match_regex = new RegExp('\\b' + query.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&"), 'i');
            if (name && match_regex.test(name)) { 
                return true;
            } 
            if (id && match_regex.test(id)) { 
                return true;
            } 
            return false;
        }
    });

    Trex.form.tag.tags = function() { Backbone.Collection.apply(this, arguments); };
    module.tags = Backbone.Collection.extend({
        constructor: module.tags,
        model: module.tag,
        _class: 'Trex.form.tag.tags',
        _prepareModel: function(model, options) {
            if (_.isArray(model)) {
                model = {
                    id: model[0],
                    name: model[1]
                };
            }
            return Backbone.Collection.prototype._prepareModel.call(this, model, options);
        }
    });

    Trex.form.tag.main = function() { Backbone.View.apply(this, arguments); };
    module.main = Backbone.View.extend({
        constructor: module.main,
        _class: 'Trex.form.tag.main',
        className: 'trex-tag-field form-control',

        events: {
            'click': function() { this.$('textarea').focus(); },
            'keypress textarea': 'keypress',
            'keydown textarea': 'keydown',
            'keyup textarea': 'keyup',
            'click .tag a': 'remove_handler',
            'paste textarea': 'paste_handler',
            'mousedown .autocomplete div': function(e) {
                this.select_current_autocomplete();
                this.render();
            },
            'mouseover .autocomplete div': function(e) {
                var $target = this.$(e.currentTarget);
                $target.siblings().removeClass('selected');
                $target.addClass('selected');
            },
        },

        format_text: function(model) {
            if (this.opt.format_text) {
                return this.opt.format_text(model);
            }
            return model.id;
        },

        initialize: function(opt) {
            this.opt = _.extend({
                format_text: null, // function that converts a model to string
                collection_class: module.tags,
                collection: null, // instance of this.opt.collection_class
                name: null
            }, opt);

            if (!this.opt.name) {
                throw new Error("name is a required option for the tag widget");
            }

            this.key_repeat_tracking = {};

            _.bindAll(this, 'blur_handler');
            $(document).on('focus blur', '.trex-tag-field', this.blur_handler);

            this.collection = this.opt.collection || (new this.opt.collection_class());
            this.tags = [];
            this.el_for_tag = {};

            this.$el.append('<div class="mark"></div><textarea autocomplete="false" spellcheck="false" autocapitalize="off" autocorrect="off" rows="1"></textarea>');
            this.$el.append('<div class="textarea-mirror"></div>');
            this.$el.append('<div class="autocomplete"></div>');
            this.$el.append($('<input type="hidden">').attr('name', this.opt.name).val(Trex.json_encode([])));
        },

        remove_handler: function(e) {
            this.remove_tag($(e.currentTarget).closest('.tag').data('model').id);
        },

        update_source_data: function(data) {
            this.collection.set(data);
        },

        add_tag: function(tag) {
            var model = this.collection.get(tag);
            if (!model) {
                this.add_tag_from_text(tag);
                return;
            }
            if (model.id in this.el_for_tag) {
                log.w("Trying to add duplicate tag: ", model.id);
                return;
            }
            this.tags.push(model.id);
            this.el_for_tag[model.id] = $('<span class="tag"></span>')
                .text(this.format_text(model))
                .append('<a></a>')
                .data('model', model)
                .insertBefore(this.$('.mark'))
            ;
            this.$('input').val(Trex.json_encode(this.tags));
            this.render();
        },

        remove_tag: function(tag) {
            if (!(tag in this.el_for_tag)) {
                log.e("Tried to remove tag that isn't selected: ", tag);
            }
            var model = this.el_for_tag[tag].remove().data('model');
            delete this.el_for_tag[tag];
            this.tags = _.filter(this.tags, function(t) { return t != tag; });
            this.$('input').val(Trex.json_encode(this.tags));
            this.render();
        },

        calculate_state: function() {
            if (this.$('.autocomplete').is(':visible')) {
                return 'autocomplete';
            }
            if (this.$('textarea').val() != '') {
                return 'text';
            }

            return 'empty';
        },

        select_current_autocomplete: function() {
            var $selected = this.$('.autocomplete .selected');
            if ($selected.length) {
                this.add_tag($selected.data('model').id);
            }
            this.$('textarea').val('');
            _.defer(_.bind(function() { this.$('textarea').focus(); }))
        },

        add_tag_from_text: function(text) {
            if (text === undefined) {
                text = this.$('textarea').val();
            }
            text = text.replace(/^\s+|\s+$/g, '');
            var model = new this.collection.model({id: text});
            this.collection.add(model);
            this.add_tag(model.id);
            this.$('textarea').val('');
            return model;
        },

        move_autocomplete_selection: function(direction) {
            var $selected = this.$('.autocomplete .selected');
            var $target = $selected[direction>0?'next':'prev']();
            if ($target.length) {
                $selected.removeClass('selected');
                $target.addClass('selected');
            }
        },

        blur_handler: function(e) {
            if (e.currentTarget != this.$el[0]) {
                return;
            }

            if (e.type == 'focusout') {
                this.$el.removeClass('focus');
                _.defer(_.bind(function() {
                    this.event_handler(e, 'blur');
                }, this));
            }
            else {
                this.$el.addClass('focus');
            }
        },

        paste_handler: function(e) {
            var paste_parser = function(input) {
                var list = [];
                var regexp = /(.+?)\s*(,|$)/g;
                var m;
                while (m = regexp.exec(input)) {
                    list.push([m[1]]);
                }
                return list;
            };
            if (this.opt.paste_parser) {
                paste_parser = this.opt.paste_parser;
            }
            _.defer(_.bind(function() {
                var $textarea = this.$('textarea');
                var list = paste_parser($textarea.val());
                log.d("paste parsed: ", list);
                if (list.length>1) {
                    this.collection.add(list);
                    _.each(list, function(item) {
                        if (_.isArray(item)) {
                            this.add_tag_from_text(item[0]);
                        }
                    }, this);
                    if (!_.isArray(list[list.length-1])) {
                        $textarea.val(list[list.length-1].replace(/\r?\n/g, ' ').replace(/^\s+|\s+$/g, ''));
                    }
                }
                else {
                    $textarea.val($textarea.val().replace(/\r?\n/g, ' ').replace(/^\s+|\s+$/g, ''));
                }
            }, this));
        },

        event_handler: function(e, evt) {
            var state = this.calculate_state();
            switch (state) {
                case 'autocomplete':
                    switch (evt) {
                        case 'enter':
                        case 'comma':
                        case 'tab':
                            e.preventDefault();
                            this.select_current_autocomplete();
                            break;
                        case 'blur':
                            e.preventDefault();
                            this.add_tag_from_text();
                            break;
                        case 'escape':
                            e.preventDefault();
                            this.$('.autocomplete').hide().empty();
                            break;
                        case 'arrow_up':
                        case 'arrow_down':
                            e.preventDefault();
                            this.move_autocomplete_selection(evt == 'arrow_up' ? -1 : 1);
                            break;
                    }
                    break;
                case 'text':
                    switch (evt) {
                        case 'enter':
                        case 'comma':
                        case 'tab':
                        case 'blur':
                            e.preventDefault();
                            this.add_tag_from_text();
                            break;
                    }
                    break;
                case 'empty':
                    switch(evt) {
                        case 'enter':
                        case 'comma':
                            e.preventDefault();
                            break;
                        case 'backspace':
                            if (!this.key_repeat_tracking[e.which] && this.tags.length) {
                                this.remove_tag(this.tags[this.tags.length-1]);
                            }
                            break;
                        case 'space':
                            e.preventDefault();
                            break;
                    }
                    break;
                default:
                    throw new Error("Unknown state: " + state);
            }
            this.render();
        },

        keypress: function(e) {
            switch (e.which) {
                case 13:
                    this.event_handler(e, 'enter');
                    break;
                case 44:
                    this.event_handler(e, 'comma');
                    break;
                case 32:
                    this.event_handler(e, 'space');
                    break;
            }
        },

        keydown: function(e) {
            switch (e.which) {
                case 8:
                    this.event_handler(e, 'backspace');
                    break;
                case 9:
                    this.event_handler(e, 'tab');
                    break;
                case 27:
                    this.event_handler(e, 'escape');
                    break;
                case 37:
                    this.event_handler(e, 'arrow_left');
                    break;
                case 38:
                    this.event_handler(e, 'arrow_up');
                    break;
                case 39:
                    this.event_handler(e, 'arrow_right');
                    break;
                case 40:
                    this.event_handler(e, 'arrow_down');
                    break;
            }
            this.key_repeat_tracking[e.which] = true;
        },

        keyup: function(e) {
            this.key_repeat_tracking[e.which] = false;
            this.render();
        },

        render: function() {
            var $textarea = this.$('textarea');
            var $mirror = this.$('.textarea-mirror');
            var $autocomplete = this.$('.autocomplete');
            var line_height = $mirror.text(' ').height();
            $mirror.text($textarea.val());

            // The fun-times width calculation
            var element_width = this.$el.width();
            var textarea_pos = this.$('.mark').position().left;
            var target_width = element_width - textarea_pos;
            $mirror.width(target_width);
            if ($mirror.height() > line_height) {
                target_width = '100%';
                $mirror.width(target_width);
            }
            $textarea.width(target_width);
            if ($mirror.height() > 0) {
                $textarea.height($mirror.height());
            }
            else {
                $textarea.height(line_height);
            }

            // Autocomplete calculation
            var text = $textarea.val();
            if (text != this.previous_text) {
                if (!text) {
                    $autocomplete.hide().empty();
                }
                else {
                    matches = this.collection.filter(function(t) {
                        return !(t.id in this.el_for_tag) && t.matches(text);
                    }, this).slice(0, 8);
                    if (matches.length) {
                        $autocomplete.empty()
                        $autocomplete.append.apply($autocomplete, _.map(matches, function(t, i) {
                            return $('<div></div>')
                                .text(this.format_text(t))
                                .data('model', t)
                                .toggleClass('selected', i == 0)
                            ;
                        }, this));
                        $autocomplete.show();
                    }
                    else {
                        $autocomplete.hide().empty();
                    }
                }
                this.previous_text = text;
            }
        },
    });

    function bind(context) {
        $('.trex-tag-field', context).each(function() {
            var name = $(this).attr('name');
            var behaviour = $(this).data('behaviour') || name;
            log.d("Initialising tag field:", name, '- behaviour:', behaviour);
            var main = new module.main(_.extend(
                {},
                module.opt_for[behaviour],
                {name: name}
            ));
            main.$el.css('min-height', $(this).outerHeight()).insertAfter(this);
            if ($(this).data('source-data')) {
                main.update_source_data($(this).data('source-data'));
            }
            if ($(this).data('existing')) {
                _.each($(this).data('existing'), function(tag) { main.add_tag(tag); });
            }
            main.render();
            $(this).remove();
        });
    }

    Trex.form._bind_functions.push(bind);
    if (Trex.opt.auto_bind_form_elements) {
        bind();
    }
})(window, jQuery, Backbone, _);
