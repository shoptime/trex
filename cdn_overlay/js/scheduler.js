(function(document, window, Backbone, $, _) {
    function now() {
        return moment();
    }

    Trex.Scheduler = function() { Backbone.View.apply(this, arguments); };
    Trex.Scheduler = Backbone.View.extend({
        default_options: function() {
            return {
                firstDayOfWeek: 1, // 0 = Sunday, 1 = Monday, ...
                startWeek: now(), // A moment that is in the week we want to display
                minWeek: null, // A moment that is in the earliest week navigatable by the user
                maxWeek: null, // A moment that is in the latest week navigatable by the user
                startHour: now().startOf('hour').hour(7), // A moment representing how far to pre-scroll the display
                minimumEventLength: 30, // What is the shortest an event can be?
                hourHeight: 40, // How high is an hour in pixels
                minuteResolution: 30, // When dragging, what should be snapped to
                canDragEvents: true, // Can you move/resize events?
                defaultType: 'default', // Becomes the "type" of all new events
                // Formats for various parts of the UI (all in moment.js format strings)
                dateFormat: 'ddd Do',
                timeFormat: 'ha',
                infoFormat: 'Do MMM YYYY',
                spanFormat: 'h:mma',
                // Handlers for various UI interactions
                newEventHandler: null,
                // This is used in place of openEventView (takes exactly the
                // same args) but is responsible for creating the appropriate
                // view.
                openEventHandler: null,
                openEventView: Trex.Scheduler.SampleEventView,
                // This allows you to have events mashed together if they
                // overlap. If you name a type in this list, all events of that
                // type will be merged. Note: events of DIFFERENT types are
                // NEVER merged together. Also note that this option is merely
                // passed through to the model; if you specify your own model,
                // then set this option on that instead.
                mergeTypes: []
            };
        },
        className: 'trex-scheduler',
        log: new Trex.Logger('scheduler'),
        events: {
            'click .btn-toolbar button[data-action]': 'toolbar_handler',
            'mousedown .trex-scheduler-event-row td:not(.trex-scheduler-time)>div': 'start_drag',
            'selectstart': function(e) { e.preventDefault(); } // Stop IE from selecting text while dragging
        },
        toolbar_handler: function(e) {
            var $button = $(e.currentTarget);
            switch ($button.data('action')) {
                case 'next-week':
                    this.opt.startWeek.add('weeks', 1);
                    this.render();
                    this.trigger('change_week', this.opt.startWeek);
                    break;
                case 'prev-week':
                    this.opt.startWeek.subtract('weeks', 1);
                    this.render();
                    this.trigger('change_week', this.opt.startWeek);
                    break;
                case 'today':
                    this.opt.startWeek = this.startOfWeek(now());
                    this.render();
                    this.trigger('change_week', this.opt.startWeek);
                    break;
            }
        },
        open_event: function(evt, e) {
            if (this.current_open_event) {
                this.current_open_event.remove();
            }
            var view = this.event_views[evt.cid];
            var x = e ? (e.pageX||e.originalEvent.pageX) : view.$el.position().left + view.$el.width()/2;
            var y = e ? (e.pageY||e.originalEvent.pageY) : view.$el.position().top + view.$el.height()/2;
            if (typeof(this.opt.openEventHandler) === 'function') {
                this.current_open_event = this.opt.openEventHandler({model:evt, x:x, y:y});
            }
            else if (typeof(this.opt.openEventView) === 'function') {
                this.current_open_event = new this.opt.openEventView({model:evt, x:x, y:y});
            }
        },
        start_drag: function(e) {
            if (e.which!=1) {
                return;
            }
            e.preventDefault();

            if (this.current_open_event) {
                this.current_open_event.remove();
                delete this.current_open_event;
                return;
            }

            if (typeof(this.opt.newEventHandler) !== 'function') {
                // Can't create new events without a handler
                return;
            }

            var self = this;

            var $scrollable = this.$('.trex-scheduler-scrollable');
            var initialMinute = ($scrollable.scrollTop() - $scrollable.offset().top + (e.pageY||e.originalEvent.pageY)) / self.opt.hourHeight * 60;
            var x = (e.pageX||e.originalEvent.pageX);
            var column = 6;
            self.$event_columns.each(function(i) {
                if (x < $(this).offset().left + $(this).width()) {
                    column = i;
                    return false;
                }
            });

            initialMinute = Math.round(initialMinute/self.opt.minuteResolution)*self.opt.minuteResolution;
            var start = self.opt.startWeek.clone().add(column, 'days').add(initialMinute, 'minutes');
            var end = start.clone().add(self.opt.minimumEventLength, 'minutes');
            var min_minute = end.diff(end.clone().startOf('day'), 'minutes', true);
            var new_event = new Trex.Scheduler.Event({
                start: start,
                end: end,
                dragging: true,
                type: self.opt.defaultType
            });
            var view = this.event_views[new_event.cid] = new Trex.Scheduler.SpanView({
                model: new_event,
                scheduler: self
            });
            self.$event_columns.eq(column).append(view.$el);

            var mousemove = function(e) {
                var y = $scrollable.scrollTop() - $scrollable.offset().top + (e.pageY||e.originalEvent.pageY);
                var minute = y / self.opt.hourHeight * 60;
                minute = Math.round((minute < min_minute ? min_minute : minute)/self.opt.minuteResolution)*self.opt.minuteResolution;
                new_event.set('end', end.clone().startOf('day').add(minute, 'minutes'));
            };

            var done = function(e) {
                if (e.type == 'keydown' && e.which != 27) {
                    // Only interested in the escape key
                    return;
                }
                $(document)
                    .off('mousemove', mousemove)
                    .off('mouseup keydown', done)
                ;
                var do_save = e.type == 'mouseup';
                if (do_save) {
                    var new_event_ready = $.Deferred();

                    $.when(new_event_ready).then(
                        function() {
                            // resolved (saving the new event)
                            view.remove();
                            new_event.set('dragging', false);
                            self.model.add(new_event);
                        },
                        function() {
                            // rejected (discarding the new event)
                            view.remove();
                        }
                    );

                    self.opt.newEventHandler(new_event_ready, new_event);
                }
                else {
                    view.remove();
                }
            };

            $(document).on('mousemove', mousemove);
            $(document).on('mouseup keydown', done);

            e.preventDefault();
            e.stopPropagation();
        },
        initialize: function(opt) {
            this.opt = _.extend({}, this.default_options(), opt);
            this.opt.startWeek = this.startOfWeek(this.opt.startWeek);
            if (this.opt.minWeek) {
                this.opt.minWeek = this.startOfWeek(this.opt.minWeek);
            }
            if (this.opt.maxWeek) {
                this.opt.maxWeek = this.startOfWeek(this.opt.maxWeek);
            }

            if (!this.model) {
                this.model = new Trex.Scheduler.Events([], {mergeTypes: this.opt.mergeTypes});
            }
            if (!(this.model instanceof Trex.Scheduler.Events)) {
                throw new Error("Model must be an instance of Trex.Scheduler.Events");
            }
            this.$el.addClass(this.className).html(Trex.Templates.scheduler);
            this.$event_columns = this.$('.trex-scheduler-event-row td:not(.trex-scheduler-time) div');
            this.event_views = {};
            this.$('.trex-scheduler-scrollable')[0].scrollTop = this.opt.startHour.diff(this.opt.startHour.clone().startOf('day'), 'hours', true) * this.opt.hourHeight;

            this.listenTo(this.model, 'reset', this.reset);
            this.listenTo(this.model, 'add', this.add);
            this.listenTo(this.model, 'remove', this.remove);
            this.listenTo(this.model, 'change', this.change);

            this.render();
        },
        startOfWeek: function(m) {
            if (m.day() < this.opt.firstDayOfWeek) {
                return m.clone().startOf('day').subtract('days', 7 - this.opt.firstDayOfWeek + m.day());
            }
            if (m.day() > this.opt.firstDayOfWeek) {
                return m.clone().startOf('day').subtract('days', m.day() - this.opt.firstDayOfWeek);
            }
            return m.clone().startOf('day');
        },
        render: function() {
            if (!this.rendered_week || !this.rendered_week.isSame(this.opt.startWeek)) {
                this.render_frame();
            }
            this.$el.toggleClass('trex-scheduler-notdraggable', !this.opt.canDragEvents);
            this.reset();
        },
        render_frame: function() {
            var self = this;
            var todayIndex = null;

            this.$('.trex-scheduler-info').text('Week starting ' + self.opt.startWeek.format(this.opt.infoFormat));
            this.$('.trex-scheduler-today').removeClass('trex-scheduler-today');

            var day = self.opt.startWeek.clone();
            this.$('thead tr th').not('.trex-scheduler-time, .trex-scheduler-pad').each(function() {
                $(this).text(day.format(self.opt.dateFormat));
                if (day.isSame(now().startOf('day'))) {
                    $(this).addClass('trex-scheduler-today');
                    todayIndex = $(this).index();
                }
                day.add('days', 1);
            });
            if (todayIndex !== null) {
                this.$('tbody .trex-scheduler-event-row td').eq(todayIndex).addClass('trex-scheduler-today');
            }
            var $timeContainer = this.$('tbody .trex-scheduler-event-row .trex-scheduler-time').empty();
            var hour = now().startOf('day');
            var stop = hour.clone().endOf('day');
            while (hour.isBefore(stop)) {
                $timeContainer.append($('<div></div>').text(hour.format(self.opt.timeFormat)));
                hour.add('hours', 1);
            }
            this.rendered_week = this.opt.startWeek.clone();

            var enable_prev = !this.opt.minWeek || this.opt.minWeek.isBefore(this.opt.startWeek);
            var enable_next = !this.opt.maxWeek || this.opt.maxWeek.isAfter(this.opt.startWeek);
            this.$('.btn-toolbar button[data-action="prev-week"]').prop('disabled', !enable_prev);
            this.$('.btn-toolbar button[data-action="next-week"]').prop('disabled', !enable_next);
            if (enable_prev || enable_next) {
                this.$('.btn-toolbar button[data-action]').show();
            }
            if (!enable_prev && !enable_next) {
                this.$('.btn-toolbar button[data-action]').hide();
            }
        },
        event_column_for: function(date) {
            var diff = date.diff(this.opt.startWeek, 'days');
            if (diff >= 0 && diff < 7) {
                return this.$event_columns.eq(diff);
            }
        },
        reset: function() {
            _.each(this.event_views, function(view) {
                this.remove(view.model);
            }, this);
            this.model.each(function(model) {
                this.add(model);
            }, this);
        },
        add: function(evt) {
            var $column = this.event_column_for(evt.date());
            if (!$column) { return; }
            var view = this.event_views[evt.cid] = new Trex.Scheduler.SpanView({
                model: evt,
                scheduler: this
            });
            $column.append(view.$el);
            this.balance_date(evt.date());
        },
        remove: function(evt) {
            if (this.current_open_event && this.current_open_event.model == evt) {
                this.current_open_event.remove();
                delete this.current_open_event;
            }
            var view = this.event_views[evt.cid];
            if (view) {
                delete this.event_views[evt.cid].scheduler;
                delete this.event_views[evt.cid];
                view.remove();
                this.balance_date(evt.date());
            }
        },
        change: function(evt, options) {
            var $column = this.event_column_for(evt.date());
            var view = this.event_views[evt.cid];
            if (view && $column) {
                // A view exists and it should
                if (view.$el.parent()[0] !== $column[0]) {
                    // It's moved column, move the span and rebalance the columns
                    $column.append(view.$el);
                }
                else if (evt.hasChanged('start') || evt.hasChanged('end')) {
                    this.balance_date(evt.date());
                    if (!evt.old_date().isSame(evt.date())) {
                        this.balance_date(evt.old_date());
                    }
                }
            }
            else if (view && !$column) {
                // A view exists and it should not
                this.remove(evt);
            }
            else if (!view && $column) {
                // No view exists, but it should
                this.add(evt);
            }
        },
        // TODO - debounce this?
        balance_date: function(date) {
            var events = this.model.filter(function(evt) { return evt.cid in this.event_views && date.isSame(evt.date(), 'day'); }, this);
            var $column = this.event_column_for(date);
            var timelist = _.flatten(_.map(events, function(evt) {
                return [
                    [evt.start().format(), 'start', evt],
                    [evt.end().format(), 'end', evt]
                ];
            }, this), true).sort(function(a, b) {
                // Sort by time first
                if (a[0] < b[0]) { return -1; }
                if (a[0] > b[0]) { return 1; }
                // Sort "end" before "start"
                if (a[1] < b[1]) { return -1; }
                if (a[1] > b[1]) { return 1; }
                // Sort longer events earlier
                if (a[2].duration() > b[2].duration()) { return -1; }
                if (a[2].duration() < b[2].duration()) { return 1; }
                return 0;
            });
            var depth = 0;
            var slots = {};
            var slot_index_for = {};
            _.each(timelist, function(item) {
                var type = item[1];
                var evt = item[2];
                var view = this.event_views[evt.cid];
                if (!view) {
                    return;
                }
                if (type == 'start') {
                    depth++;
                    view.slot_count = 0;
                    var n = 0;
                    while (slots[n]) { n++; }
                    slots[n] = view;
                    view.slot_number = n;
                    slot_index_for[evt.cid] = n;
                    _.each(slots, function(v) { v.slot_count = depth > v.slot_count ? depth : v.slot_count; });
                }
                else {
                    depth--;
                    delete slots[slot_index_for[evt.cid]];
                    view.render();
                }
            }, this);
        }
    });

    Trex.Scheduler.SpanView = function() { Backbone.View.apply(this, arguments); };
    Trex.Scheduler.SpanView = Backbone.View.extend({
        constructor: Trex.Scheduler.SpanView,
        log: new Trex.Logger('scheduler-span'),
        className: 'trex-scheduler-span',
        events: {
            'mousedown': 'start_drag',
            'mousedown .trex-scheduler-handle': 'start_drag',
            'click': 'open_event'
        },
        open_event: function(e) {
            e.preventDefault();
            if (this.temporary_no_open) {
                this.temporary_no_open = false;
                return;
            }
            this.scheduler.open_event(this.model, e);
        },
        start_drag: function(e) {
            if (e.which!=1) {
                return;
            }
            if (!this.scheduler.opt.canDragEvents) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();
            if (!this.model.get('canDrag')) {
                return;
            }

            if (this.scheduler.current_open_event) {
                this.scheduler.current_open_event.remove();
                delete this.scheduler.current_open_event;
            }

            var self = this;
            // Are we moving it, or altering the end-time
            var moving_event = !$(e.currentTarget).hasClass('trex-scheduler-handle');

            var $scrollable = this.scheduler.$('.trex-scheduler-scrollable');
            var initialMinute = ($scrollable.scrollTop() - $scrollable.offset().top + (e.pageY||e.originalEvent.pageY)) / self.scheduler.opt.hourHeight * 60;

            var min_dm, max_dm;
            if (moving_event) {
                // Can't move the event past the top of the day
                min_dm = -self.model.start().diff(self.model.start().startOf('day'), 'minutes', true);
            }
            else {
                // Can't shrink the event smaller than minimumEventLength
                min_dm = self.scheduler.opt.minimumEventLength - self.model.end().diff(self.model.start(), 'minutes', true);
            }
            // Event can't go past midnight
            max_dm = self.model.start().add(1, 'day').startOf('day').diff(self.model.end(), 'minutes', true);

            var mouse_has_moved = false;

            var mousemove = function(e) {
                var y = $scrollable.scrollTop() - $scrollable.offset().top + (e.pageY||e.originalEvent.pageY);
                var x = (e.pageX||e.originalEvent.pageX);

                // Probably want this to have a threshold
                mouse_has_moved = true;

                var minute = y / self.scheduler.opt.hourHeight * 60;
                var dm = Math.round((minute-initialMinute)/self.scheduler.opt.minuteResolution)*self.scheduler.opt.minuteResolution;
                self.model.set('dragging', true);
                if (moving_event) {
                    self.model.set('start_dm', dm < min_dm ? min_dm : dm > max_dm ? max_dm : dm);
                    self.model.set('end_dm', dm < min_dm ? min_dm : dm > max_dm ? max_dm : dm);
                    var column = 6;
                    self.scheduler.$event_columns.each(function(i) {
                        if (x < $(this).offset().left + $(this).width()) {
                            column = i;
                            return false;
                        }
                    });
                    var day_delta = self.scheduler.opt.startWeek.clone().add(column, 'days').diff(self.model.get('start').clone().startOf('day'), 'days');
                    self.model.set('day_delta', day_delta);
                }
                else {
                    self.model.set('end_dm', dm < min_dm ? min_dm : dm > max_dm ? max_dm : dm);
                }
            };

            var done = function(e) {
                if (e.type == 'keydown' && e.which != 27) {
                    // Only interested in the escape key
                    return;
                }
                $(document)
                    .off('mousemove', mousemove)
                    .off('mouseup keydown', done)
                ;
                if (e.type == 'mouseup' && !mouse_has_moved) {
                    return;
                }
                // Don't open the event after a drag
                self.temporary_no_open = true;
                var do_save = e.type == 'mouseup';
                var new_attrs = {
                    dragging: false,
                    start_dm: 0,
                    end_dm: 0,
                    day_delta: 0
                };
                if (do_save) {
                    new_attrs.start = self.model.start();
                    new_attrs.end = self.model.end();
                }
                self.model.set(new_attrs);
                self.model.trigger('altered'); // Moved or resized
            };

            $(document).on('mousemove', mousemove);
            $(document).on('mouseup keydown', done);
        },
        initialize: function(opt) {
            this.scheduler = opt.scheduler;
            this.$el.addClass(this.className);
            this.listenTo(this.model, 'change', this.render);
            this.$el.html('<div class="time"></div><div class="trex-scheduler-handle">=</div>');
            this.slot_number = 0;
            this.slot_count = 1;
            this.render();
        },
        render: function() {
            var start = this.model.start();
            var end = this.model.end();
            var start_hours = start.diff(start.clone().startOf('day'), 'hours', true);
            var duration_hours = end.diff(start, 'hours', true);
            this.$el.toggleClass('trex-scheduler-notdraggable', !this.model.get('canDrag'));
            this.$el.toggleClass('trex-scheduler-dragging', this.model.get('dragging'));
            var width = this.slot_count == 1 ? 97 : (97 / this.slot_count)*1.5;
            var left = this.slot_number === 0 ? 0 : (97 - width) * (this.slot_number / (this.slot_count-1));
            var zindex = this.slot_number + 5;
            if (this.model.get('dragging')) {
                zindex = 100;
            }
            this.$el
                .removeClass(_.filter((this.$el.attr('class')||'').split(/\s+/), function(cls) { return cls.match(/^trex-scheduler-eventtype-/); }).join(' '))
                .addClass('trex-scheduler-eventtype-' + this.model.get('type'))
                .css({
                    top: start_hours * this.scheduler.opt.hourHeight,
                    height: duration_hours * this.scheduler.opt.hourHeight,
                    zIndex: zindex,
                    width: width + '%',
                    left: left + '%'
                })
            ;
            this.$('.time').text(start.format(this.scheduler.opt.spanFormat) + '-' + end.format(this.scheduler.opt.spanFormat));
        }
    });

    Trex.Scheduler.Event = function() { Backbone.Model.apply(this, arguments); };
    Trex.Scheduler.Event = Backbone.Model.extend({
        constructor: Trex.Scheduler.Event,
        defaults: {
            canDrag: true,
            canOpen: true,
            dragging: false,
            // Deltas for minutes/days used while dragging
            start_dm: 0,
            end_dm: 0,
            day_delta: 0
        },
        start: function() {
            var start = this.get('start').clone();
            if (this.get('start_dm')) {
                start.add(this.get('start_dm'), 'minutes');
            }
            if (this.get('day_delta')) {
                start.add(this.get('day_delta'), 'days');
            }
            return start;
        },
        end: function() {
            var end = this.get('end').clone();
            if (this.get('end_dm')) {
                end.add(this.get('end_dm'), 'minutes');
            }
            if (this.get('day_delta')) {
                end.add(this.get('day_delta'), 'days');
            }
            return end;
        },
        date: function() {
            return this.start().startOf('day');
        },
        old_date: function() {
            return this.previous('start').clone().startOf('day');
        },
        duration: function() {
            return this.end() - this.start();
        },
        toJSON: function() {
            var data = Backbone.Model.prototype.toJSON.apply(this, arguments);
            delete data.start_dm;
            delete data.end_dm;
            delete data.day_delta;
            delete data.dragging;
            return data;
        }
    });

    Trex.Scheduler.Events = function(models, options) {
        options || (options = {});
        this.mergeTypes = options.mergeTypes || [];
        Backbone.Collection.apply(this, arguments);
    };
    Trex.Scheduler.Events = Backbone.Collection.extend({
        constructor: Trex.Scheduler.Events,
        model: Trex.Scheduler.Event,
        merge: function(evt, options) {
            if (!(evt instanceof Trex.Scheduler.Event)) {
                evt = this._prepareModel(evt, options);
            }

            var evtStartDate = evt.start();
            var evtEndDate = evt.end();

            // Create a list of the events we need to check against
            var date = evt.date();
            var events = this.filter(function(e) { return  e != evt && date.isSame(e.date(), 'day') && e.get('type') === evt.get('type'); }, this);

            var merged = false;
            while (events.length) {
                var existingEvent = events.pop();

                if (
                    evtStartDate >= existingEvent.start() && evtStartDate <= existingEvent.end() // new event start in range
                    ||
                    evtEndDate >= existingEvent.start() && evtEndDate <= existingEvent.end() // new event end in range
                    ||
                    existingEvent.start() >= evtStartDate && existingEvent.start() <= evtEndDate // existing event start
                    ||
                    existingEvent.end() >= evtStartDate && existingEvent.end() <= evtEndDate // existing event end
                    ) {
                    // Make the existing event incorporate the new start/end
                    existingEvent.set({
                        start: moment(Math.min(existingEvent.start(), evtStartDate)),
                        end: moment(Math.max(existingEvent.end(), evtEndDate))
                    });

                    // And baleet the event we were checking against. This
                    // might seem strange, but we can be checking against an
                    // event that's already in the model (see next block of
                    // code)
                    this.remove(evt);

                    // Now start checking against the event that we modified
                    evt = existingEvent;
                    evtStartDate = evt.start();
                    evtEndDate = evt.end();
                    merged = true;
                }
            }

            if (!merged) {
                // Not merged. Add new event as a distinct model.
                var r = Backbone.Collection.prototype.add.apply(this, [evt, options]);
                var self = this;
                this.listenTo(evt, 'altered', function() { self.merge(evt, options); });
            }
        },
        add: function(models, options) {
            if (models instanceof Trex.Scheduler.Event) {
                models = [models];
            }

            _.forEach(models, function(evt) {
                evt = this._prepareModel(evt);
                // Work out if this model actually needs to result in a merge with an existing model
                if (_.contains(this.mergeTypes, evt.get('type'))) {
                    this.merge(evt, options);
                }
                else {
                    // Not merging. Add new event as a distinct model.
                    Backbone.Collection.prototype.add.apply(this, [evt, options]);
                }
            }, this);
        }
    });

    Trex.Scheduler.EventViewBase = function() { Backbone.View.apply(this, arguments); };
    Trex.Scheduler.EventViewBase = Backbone.View.extend({
        constructor: Trex.Scheduler.EventViewBase,
        log: new Trex.Logger('scheduler-event-view'),
        width: 300,
        initialize: function(opt) {
            this.$content = $('<div></div>');
            this.$el
                .css({
                    position: 'absolute',
                    top: opt.y,
                    left: opt.x,
                    width: this.width + 'px',
                    marginLeft: -(this.width/2) + 'px'
                })
                .appendTo('body')
                .popover({
                    content: this.$content,
                    trigger: 'manual',
                    html: true,
                    placement: 'top',
                    container: this.$el,
                    // This is a dirty hack for IE8 (which doesn't support the
                    // :empty pseudo-selector). It's basically the normal
                    // template without the <h3 class="popover-title"> element
                    template: '<div class="popover"><div class="arrow"></div><div class="popover-content"></div></div>'
                })
            ;
            this.render();
        },
        render: function() {
            this.$el.popover('show');
            if ($.browser.msie && $.browser.version <= 8) {
                // Really dirty hack to make sure the arrow-tip on the popup
                // isn't munted
                var popover = this.$el.data('popover');
                popover.$tip.find('.arrow').hide();
                setTimeout(function() {
                    popover.$tip.find('.arrow').show();
                }, 0);
            }
        },
        remove: function(opt) {
            this.$el.popover('destroy');
            Backbone.View.prototype.remove.apply(this, arguments);
        }
    });

    Trex.Scheduler.SampleEventView = function() { Trex.Scheduler.EventViewBase.apply(this, arguments); };
    Trex.Scheduler.SampleEventView = Trex.Scheduler.EventViewBase.extend({
        constructor: Trex.Scheduler.SampleEventView,
        log: new Trex.Logger('scheduler-sample-event-view'),
        events: {
            'click button': function(e) {
                e.preventDefault();
                this.log.d("Removing event");
                this.model.collection.remove(this.model);
            }
        },
        initialize: function(opt) {
            Trex.Scheduler.EventViewBase.prototype.initialize.apply(this, arguments);
            this.render();
        },
        render: function() {
            this.$content.html('<button class="btn btn-default">remove</button>');
            Trex.Scheduler.EventViewBase.prototype.render.apply(this, arguments);
        }
    });
})(document, window, Backbone, jQuery, _);
