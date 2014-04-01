(function(window, $) {
    var Trex = window.Trex;
    Trex._register_module("trex.form.phonenumber", "trex.form.phonenumber-lib");

    Trex.form.phonenumber = new Trex._TrexModule();
    //var log = new Trex.Logger('trex.form.phonenumber');

    function bind(context) {
        $('.trex-phone-field', context).each(function() {
            var $this = $(this);

            var $hidden = $('<input type="hidden">').attr('name', $this.attr('name')).insertAfter($this);
            $this.attr('name', null);

            var $message = $('<span></span>')
                .css({
                    marginLeft: 10
                })
                .insertAfter($this)
            ;

            var phoneUtil = Trex.i18n.phonenumbers.PhoneNumberUtil.getInstance();
            var PNF = Trex.i18n.phonenumbers.PhoneNumberFormat;
            var PNT = Trex.i18n.phonenumbers.PhoneNumberType;
            var $country_field = $();
            if ($this.data('country')) {
                $country_field = $('<input type="hidden">').val($this.data('country'));
            }
            else if ($this.data('country-field')) {
                $country_field = $('#' + $this.data('country-field'));
            }
            var current_country = function() {
                return $country_field.val();
            };

            var value, phone, country;

            var update_value = function() {
                if (value == $this.val() && current_country() == country) {
                    return;
                }
                value = $this.val();
                country = current_country();
                if (country) {
                    $this.attr('placeholder', phoneUtil.format(phoneUtil.getExampleNumberForType(country, PNT.MOBILE), PNF.NATIONAL));
                }
                else {
                    $this.attr('placeholder', phoneUtil.format(phoneUtil.getExampleNumberForType('GB', PNT.MOBILE), PNF.INTERNATIONAL));
                }
                try {
                    phone = phoneUtil.parseAndKeepRawInput(value, country);
                }
                catch(e) {
                    phone = null;
                }
            };

            var do_validation = function() {
                var is_valid = false;
                var show_error = !$this.is(':focus');

                var message;
                var extra_info = [];
                update_value();

                if (!value.match(/\S/)) {
                    // Empty field, is valid
                    is_valid = true;
                    message = '';
                    $hidden.val('');
                }
                else if (phone && phoneUtil.isValidNumber(phone)) {
                    // Valid number
                    is_valid = true;
                    message = phoneUtil.format(phone, PNF.INTERNATIONAL);
                    if (phoneUtil.getRegionCodeForNumber(phone)) {
                        extra_info.push(phoneUtil.getRegionCodeForNumber(phone));
                    }
                    switch (phoneUtil.getNumberType(phone)) {
                        case 0:
                            extra_info.push('Fixed Line');
                            break;
                        case 1:
                            extra_info.push('Mobile');
                            break;
                    }
                    if (extra_info.length) {
                        message += ' (' + extra_info.join(' ') + ')';
                    }
                    $hidden.val(phoneUtil.format(phone, PNF.E164));
                }
                else {
                    // Couldn't parse a phone number or it was invalid
                    is_valid = false;
                    message = 'Invalid phone number';
                    $hidden.val('invalid:' + value);
                }

                // Remove any error put there by the server-side
                $this.closest('.form-group, .control-group').find('.help-inline-error, .help-block-error').remove()
                if (is_valid || show_error) {
                    $message
                        .toggleClass('text-danger text-error', !is_valid)
                        .toggleClass('text-success', is_valid)
                        .text(message)
                        .show()
                    ;
                    $this.closest('.form-group').toggleClass('has-error', !is_valid);
                    $this.closest('.control-group').toggleClass('error', !is_valid);
                }
                else {
                    $message.hide();
                    $this.closest('.form-group').removeClass('has-error');
                    $this.closest('.control-group').removeClass('error');
                }
            };

            $this.on('blur change keyup keydown keypress', do_validation);
            $country_field.on('change', do_validation);

            update_value();
            if (phone && !$this.data('keep-raw-value')) {
                $this.val(phoneUtil.format(phone, PNF.INTERNATIONAL));
            }
            do_validation();
            $this.attr('disabled', null).prop('disabled', false);
        });
    }

    Trex.form._bind_functions.push(bind);
    if (Trex.opt.auto_bind_form_elements) {
        bind();
    }
})(window, jQuery);
