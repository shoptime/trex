(function(window, $) {
    var Trex = function() {};
    window.Trex = new Trex();
    Trex = Trex.prototype;

    Trex.Templates = {};

    moment.fn.toJSON = function() {
        return { $ltime: this.format('YYYY-MM-DDTHH:mm:ss.SSS') };
    };
    Trex.parse_json = function(str) {
        return JSON.parse(str, Trex.parse_json.reviver);
    };

    Trex.parse_json.reviver = function(k, v) {
        if (v instanceof Object && '$ltime' in v) {
            return moment(v.$ltime);
        }
        return v;
    };

    Trex.Logger = function() { this.init.apply(this, arguments); };
    (function(cls) {
        cls.tag = '';
        cls.history = [];

        cls.init = function(tag, opt) {
            this.tag = typeof(tag) == 'string' ? tag : '';
            this.opt = _.extend({
                filter: null // Set to a function to filter log lines
            }, opt);
            if ( this.opt.filter !== null && typeof(this.opt.filter) !== 'function' ) {
                this.opt.filter = null;
                this.log.w("filter option was passed to logger but it isn't a function. Ignoring");
            }
        };

        cls.stringify_anything = function(obj) {
            if ( typeof(obj) === 'undefined' ) {
                return 'undefined';
            }
            if ( obj === null ) {
                return 'null';
            }
            if ( typeof(obj) === 'object' ) {
                var cls = obj._class;
                var result ;
                try {
                    result = JSON.stringify(obj);
                }
                catch(e){}
                if ( result && result.length < 512 ) {
                    if ( cls ) {
                        return '[' + cls + ' ' + result + ']';
                    }
                    return result;
                }
            }
            return String(obj);
        };

        cls.store_history = function(prefix, args) {
            args = [].slice.call(args);
            args.unshift(prefix);
            args.unshift(this.tag);
            args = _.map(args, this.stringify_anything);
            args.unshift((new Date()).getTime());
            cls.history.push(args);
        };

        cls.dump_history = function() {
            _.each(this.history, function(e) {
                var args = _.clone(e);
                args[0] = (new Date(args[0])).toLocaleTimeString();
                args[1] = '[' + args[1] + ']';
                var type = args.splice(2, 1)[0];
                switch (type) {
                    case 'window.onerror':
                    case 'log.error':
                        this.console_log('error', args, false);
                        break;
                    case 'log.warning':
                        this.console_log('warn', args, false);
                        break;
                    case 'log.info':
                        this.console_log('info', args, false);
                        break;
                    default:
                        this.console_log('log', args, false);
                }
            }, this);
        };

        cls.console_log = function(func, args, do_prep_args) {
            if ( do_prep_args !== false ) {
                args = this.prep_args(args);
            }
            if (typeof window.console != 'undefined' && window.console[func]) {
                if (window.console[func].apply ) {
                    window.console[func].apply(window.console, args);
                }
                else if (typeof(window.console[func]) == 'object') {
                    // Hello, IE
                    window.console[func](args.join(' '));
                }
            }
        };

        cls.prep_args = function(args) {
            args = Array.prototype.slice.call(args);
            if ( this.tag ) {
                args.unshift('[' + this.tag + ']');
            }
            // Special case for PhoneGap
            if ( window.cordova ) {
                return [args.join(' ')];
            }
            return args;
        };

        cls.s = function() {
            if ( this.opt.filter && this.opt.filter.call(this, 'log.stats', arguments) === false ) { return; }
            this.store_history('log.stats', arguments);
            this.console_log('debug', arguments);
        };
        cls.d = function() {
            if ( this.opt.filter && this.opt.filter.call(this, 'log.debug', arguments) === false ) { return; }
            this.store_history('log.debug', arguments);
            this.console_log('log', arguments);
        };
        cls.i = function() {
            if ( this.opt.filter && this.opt.filter.call(this, 'log.info', arguments) === false ) { return; }
            this.store_history('log.info', arguments);
            this.console_log('info', arguments);
        };
        cls.w = function() {
            if ( this.opt.filter && this.opt.filter.call(this, 'log.warning', arguments) === false ) { return; }
            this.store_history('log.warning', arguments);
            this.console_log('warn', arguments);
        };
        cls.e = function() {
            if ( this.opt.filter && this.opt.filter.call(this, 'log.error', arguments) === false ) { return; }
            this.store_history('log.error', arguments);
            this.console_log('error', arguments);
        };
    })(Trex.Logger.prototype);
    Trex.log = new Trex.Logger('app');

    Trex.ViewCollection = function() { Backbone.View.apply(this, arguments); };
    Trex.ViewCollection = Backbone.View.extend({
        constructor: Trex.ViewCollection,
        _class: 'Trex.ViewCollection',
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
})(window, jQuery);
