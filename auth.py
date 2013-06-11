# coding=utf-8

from __future__ import absolute_import
from flask import g, request, url_for, redirect

def public(*args, **kwargs):
    pass

def login(*args, **kwargs):
    if not g.user:
        return redirect(url_for('auth.login', return_to = request.url))
