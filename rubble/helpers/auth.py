# coding: utf8

from __future__ import absolute_import
from flask import url_for
from .browser import *
from .assertions import *

def login(email, password='password'):
    message("Logging in as %s" % email)

    get(url_for('trex.auth.logout'))
    get(url_for('trex.auth.login'))
    find('#email').type(email)
    find('#password').type(password)
    find('.form-actions .btn-primary').filter_by_text('Log in').click()

def logout():
    get(url_for('trex.auth.logout'))
