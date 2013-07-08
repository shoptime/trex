(function(document, window, Backbone, jQuery, _) {
    function now() {
        return moment();
    }

    Trex.Scheduler = function() { Backbone.View.apply(this, arguments); };
    Trex.Scheduler = Backbone.View.extend({
        default_options: function() {
            return {
                firstDayOfWeek: 1, // 0 = Sunday, 1 = Monday, ...
                startWeek: now(), // A moment that is in the week we want to display
                startHour: now().startOf('hour').hour(7), // A moment representing how far to pre-scroll the display
                minimumEventLength: 30, // What is the shortest an event can be?
                hourHeight: 40, // How high is an hour in pixels
                minuteResolution: 30, // When dragging, what should be snapped to
                canDragEvents: true, // Can you move/resize events?
                defaultColor: '#d96666', // Any valid CSS color (used as background)
                // Formats for various parts of the UI (all in moment.js format strings)
                dateFormat: 'ddd Do',
                timeFormat: 'ha',
                infoFormat: 'Do MMM YYYY',
                spanFormat: 'h:mma',
                // Handlers for various UI interactions
                newEventHandler: null,
                openEventView: Trex.Scheduler.SampleEventView,
            }
        },
        className: 'trex-scheduler',
        log: new Trex.Logger('scheduler'),
        events: {
            'click .btn-toolbar button[data-action]': 'toolbar_handler',
            'mousedown .trex-scheduler-event-row td:not(.trex-scheduler-time)>div': 'start_drag',
            'selectstart': function(e) { e.preventDefault(); }, // Stop IE from selecting text while dragging
        },
        toolbar_handler: function(e) {
            var $button = $(e.currentTarget);
            switch ($button.data('action')) {
                case 'next-week':
                    this.opt.startWeek.add('weeks', 1)
                    this.render();
                    break;
                case 'prev-week':
                    this.opt.startWeek = this.opt.startWeek.subtract('weeks', 1)
                    this.render();
                    break;
                case 'today':
                    this.opt.startWeek = this.startOfWeek(now());
                    this.render();
                    break;
            }
        },
        open_event: function(evt, e) {
            if (typeof(this.opt.openEventView) === 'function') {
                if (this.current_open_event) {
                    this.current_open_event.remove();
                }
                var view = this.event_views[evt.cid];
                var x = e ? (e.pageX||e.originalEvent.pageX) : view.$el.position().left + view.$el.width()/2;
                var y = e ? (e.pageY||e.originalEvent.pageY) : view.$el.position().top + view.$el.height()/2;
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
                color: self.opt.defaultColor
            });
            var view = this.event_views[new_event.cid] = new Trex.Scheduler.SpanView({
                model: new_event,
                scheduler: self,
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
                view.remove();
                if (do_save) {
                    new_event.set('dragging', false);
                    self.model.add(new_event);
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

            if (!this.model) {
                this.model = new Trex.Scheduler.Events();
            }
            // TODO, ensure this.model is what we expect
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
            this.$el.toggleClass('trex-scheduler-draggable', this.opt.canDragEvents);
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
            };
            this.rendered_week = this.opt.startWeek.clone();
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
                scheduler: this,
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
        },
    });

    Trex.Scheduler.SpanView = function() { Backbone.View.apply(this, arguments); };
    Trex.Scheduler.SpanView = Backbone.View.extend({
        constructor: Trex.Scheduler.SpanView,
        log: new Trex.Logger('scheduler-span'),
        className: 'trex-scheduler-span',
        events: {
            'mousedown': 'start_drag',
            'mousedown .trex-scheduler-handle': 'start_drag',
        },
        open_event: function(e) {
            e.preventDefault();
            this.scheduler.open_event(this.model, e);
        },
        start_drag: function(e) {
            if (!this.scheduler.opt.canDragEvents) {
                return;
            }
            if (e.which!=1) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();

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
                    self.open_event(e);
                    return;
                }
                var do_save = e.type == 'mouseup';
                var new_attrs = {
                    dragging: false,
                    start_dm: 0,
                    end_dm: 0,
                    day_delta: 0,
                }
                if (do_save) {
                    new_attrs.start = self.model.start();
                    new_attrs.end = self.model.end();
                }
                self.model.set(new_attrs);
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
            this.$el.toggleClass('trex-scheduler-dragging', this.model.get('dragging'));
            var width = this.slot_count == 1 ? 97 : (97 / this.slot_count)*1.5;
            var left = this.slot_number == 0 ? 0 : (97 - width) * (this.slot_number / (this.slot_count-1));
            var zindex = this.slot_number + 5;
            if (this.model.get('dragging')) {
                zindex = 100;
            }
            this.$el.attr('data-s', this.slot_number);
            this.$el.attr('data-c', this.slot_count);
            this.$el.css({
                top: start_hours * this.scheduler.opt.hourHeight,
                height: duration_hours * this.scheduler.opt.hourHeight,
                backgroundColor: (this.model.get('color') || this.scheduler.opt.defaultColor),
                zIndex: zindex,
                width: width + '%',
                left: left + '%',
            });
            this.$('.time').text(start.format(this.scheduler.opt.spanFormat) + '-' + end.format(this.scheduler.opt.spanFormat));
        },
    });

    Trex.Scheduler.Event = function() { Backbone.Model.apply(this, arguments); };
    Trex.Scheduler.Event = Backbone.Model.extend({
        constructor: Trex.Scheduler.Event,
        defaults: {
            dragging: false,
            // Deltas for minutes/days used while dragging
            start_dm: 0,
            end_dm: 0,
            day_delta: 0,
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
        },
    });

    Trex.Scheduler.Events = function() { Backbone.Collection.apply(this, arguments); };
    Trex.Scheduler.Events = Backbone.Collection.extend({
        constructor: Trex.Scheduler.Events,
        model: Trex.Scheduler.Event,
    });

    Trex.Scheduler.SampleEventView = function() { Backbone.View.apply(this, arguments); };
    Trex.Scheduler.SampleEventView = Backbone.View.extend({
        constructor: Trex.Scheduler.SampleEventView,
        log: new Trex.Logger('scheduler-sample-event-view'),
        events: {
            'click button': function(e) {
                e.preventDefault();
                this.log.d("Removing event");
                this.model.collection.remove(this.model);
            },
        },
        initialize: function(opt) {
            this.log.d('initialized: ', opt);
            var $content = $('<div><button class="btn">delete</button></div>');
            var title = this.model.start().format('h:mma') + '-' + this.model.end().format('h:mma');
            this.$el
                .css({
                    position: 'absolute',
                    top: opt.y,
                    left: opt.x,
                    width: '300px',
                    marginLeft: '-150px',
                })
                .appendTo('body')
                    .popover({
                        title: title,
                        content: $content,
                        trigger: 'manual',
                        html: true,
                        placement: 'top',
                        container: this.$el,
                    })
                .popover('show')
            ;
        },
        remove: function(opt) {
            this.log.d('view destroy');
            this.$el.popover('destroy');
            Backbone.View.prototype.remove.apply(this, arguments);
        },
    })

})(document, window, Backbone, jQuery, _);
