# coding: utf8


from flask import url_for
from .browser import *
from .assertions import *
import app.model as m

def login(user, password='password'):
    if isinstance(user, m.User):
        email = user.email
    else:
        email = user

    message("Logging in as %s" % email)

    get(url_for('trex.auth.logout'))
    get(url_for('trex.auth.login'))
    find('#email').type(email)
    find('#password').type(password)
    find('.form-actions .btn-primary').filter_by_text('Log in').click()

def logout():
    get(url_for('trex.auth.logout'))
