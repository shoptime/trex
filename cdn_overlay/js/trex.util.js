(function(window, Backbone) {
    var Trex = window.Trex;
    Trex._register_module("trex.util", "trex");

    Trex.util = new Trex._TrexModule();

    Trex.util.check_element_deps = function(selector) {
        var $el = $(selector);
        var args = Array.prototype.slice.apply(arguments);
        args.shift();
        args.unshift("$("+selector+")");
        if ($el.length) { Trex._check_deps.apply(Trex, args); }
    };

    if ( !Backbone ) {
        return;
    }

    Trex.util.ViewCollection = function() { Backbone.View.apply(this, arguments); };
    Trex.util.ViewCollection = Backbone.View.extend({
        constructor: Trex.util.ViewCollection,
        _class: 'Trex.util.ViewCollection',
        className: 'trex-collection',

        initialize: function(opt) {
            this.subviews = {};
            this.opt = _.extend({
                monitorChanges: false
            }, opt);

            Backbone.View.prototype.initialize.apply(this, arguments);

            this.$el.addClass(this.className);
            this.view  = this.opt.view;
            this.view_options = this.opt.view_options || {};
            this.container = this.opt.container || this.$el;
            this.filter = this.opt.filter;

            if (!this.view) {
                throw new Error("<view> must be a Backbone view class");
            }

            if (!(this.container instanceof jQuery)) {
                throw new Error("<container> must be a jQuery object");
            }

            this.model.on('reset', this.reset, this);
            this.model.on('add', this.add_model, this);
            this.model.on('remove', this.remove_model, this);
            if ( this.opt.monitorChanges ) {
                this.model.on('change', this.change_model, this);
            }

            this.reset();
        },

        reset: function() {
            _.each(this.subviews, function(view) {
                this.remove_model(view.model);
            }, this);
            this.model.each(function(model) {
                this.add_model(model);
            }, this);
        },

        find_model: function(index, delta) {
            var model;
            index += delta;
            while ( index >= 0 && index < this.model.length ) {
                model = this.model.at(index);
                if ( typeof(this.filter) === 'function' ) {
                    if ( this.filter(model) ) {
                        return model;
                    }
                }
                else {
                    return model;
                }
                index += delta;
            }
            return;
        },

        add_model: function(model, collection, options) {
            options = _.extend({}, options);
            if ( typeof(this.filter) === 'function' ) {
                if ( ! this.filter(model) ) {
                    return;
                }
            }
            if ( model.id in this.subviews ) {
                throw new Error("Can't add the same model twice");
            }
            var view = this.subviews[model.id] = new this.view(_.extend({}, this.view_options, { model: model }));
            view.view_collection = this;

            var model_before, model_after;

            if ( 'index' in options ) {
                model_before = this.find_model(options.index, -1);
                model_after = this.find_model(options.index, 1);
            }
            if ( model_before ) {
                view.$el.insertAfter(this.subviews[model_before.id].$el);
            }
            else if ( model_after ) {
                view.$el.insertBefore(this.subviews[model_after.id].$el);
            }
            else {
                this.container.append(view.$el);
            }
            this.trigger('add', view);
        },

        change_model: function(model) {
            if ( typeof(this.filter) !== 'function' ) {
                return;
            }
            var passed_filter = this.filter(model);
            if ( passed_filter && !(model.id in this.subviews) ) {
                this.add_model(model);
            }
            if ( !passed_filter && (model.id in this.subviews) ) {
                this.remove_model(model);
            }
        },

        remove_model: function(model) {
            var view = this.subviews[model.id];
            if ( view ) {
                delete this.subviews[model.id].view_collection;
                delete this.subviews[model.id];
                this.trigger('remove', view);
                view.remove();
            }
        },

        remove: function() {
            this.model.off(null, null, this);
            _.each(this.subviews, function(view) {
                this.remove_model(view.model);
            }, this);
            Backbone.View.prototype.remove.apply(this, arguments);
        }
    });
})(window, typeof(Backbone) === 'undefined' ? null : Backbone);
