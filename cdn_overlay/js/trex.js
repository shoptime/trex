(function(window, $) {
    var Trex = function() {};
    Trex = window.Trex = new Trex();

    Trex.opt = {
        auto_bind_form_elements: true,
        bs_version: 3
    };

    Trex._loaded_modules = ['trex'];

    Trex._register_module = function(this_module) {
        this._check_deps.apply(this, arguments);
        Trex._loaded_modules.push(this_module);
    };

    Trex._check_deps = function(deps_for) {
        var deps = Array.prototype.slice.apply(arguments);
        deps.shift(); // Pop off deps_for
        var missing_deps = [];
        _.each(deps, function(dep) {
            if (_.indexOf(Trex._loaded_modules, dep) === -1) {
                missing_deps.push(dep);
            }
        });
        if (missing_deps.length) {
            throw new Error("Missing deps for " + deps_for + " (" + missing_deps.join(', ') + ")");
        }
    };

    var TrexModule = function() {};
    Trex._TrexModule = TrexModule;

    Trex.Templates = new TrexModule();

    Trex.json_decode = function(str) {
        return JSON.parse(str, Trex.json_decode.reviver);
    };

    Trex.json_decode.reviver = function(k, v) {
        if (v instanceof Object && '$ltime' in v) {
            return moment(v.$ltime);
        }
        return v;
    };

    Trex.json_encode = function(obj) {
        return JSON.stringify(obj, Trex.json_encode.replacer);
    };

    Trex.json_encode.replacer = function(k, v) {
        if (k === '') {
            return v;
        }
        var original_v = this[k];

        if (moment.isMoment(original_v)) {
            return { $ltime: original_v.format('YYYY-MM-DDTHH:mm:ss.SSS') };
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

    $.ajaxPrefilter(function(options, originalOptions, jqXHR) {
        if ( options.type.toLowerCase() == 'post' ) {
            jqXHR.setRequestHeader('X-CSRFToken', $('html').data('csrf-token'));
        }
    });
})(window, jQuery);
