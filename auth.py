# coding=utf-8

from __future__ import absolute_import
from app import app
from flask import g, request, url_for, redirect, abort
import urllib

login_url = app.settings.get('security', 'login_url')

def get_login_url(return_to):
    return '{}?{}'.format(login_url, urllib.urlencode(dict(return_to=return_to)))

def public(*args, **kwargs):
    pass

def login(*args, **kwargs):
    if not g.user:
        return redirect(get_login_url(request.url))

has_flag_cache = {}
def has_flag(flag):
    if flag in has_flag_cache:
        return has_flag_cache[flag]

    def check_flag(*args, **kwargs):
        if not g.user:
            return redirect(get_login_url(request.url))
        if not g.user.has_flag(flag):
            return abort(403)

    check_flag.__name__ = 'has_flag(%s)' % flag

    has_flag_cache[flag] = check_flag

    return check_flag

has_role_cache = {}
def has_role(role):
    if role in has_role_cache:
        return has_role_cache[role]

    def check_role(*args, **kwargs):
        if not g.user:
            return redirect(get_login_url(request.url))
        if not g.user.has_role(role):
            return abort(403)

    check_role.__name__ = 'has_role(%s)' % role

    has_role_cache[role] = check_role

    return check_role

def is_role(role):
    func = is_role_in(role)
    func.__name__ = 'is_role(%s)' % role
    return func

is_role_in_cache = {}
def is_role_in(*args):
    role_set = frozenset(args)
    if role_set in is_role_in_cache:
        return is_role_in_cache[role_set]

    def check_role(*args, **kwargs):
        if not g.user:
            return redirect(get_login_url(request.url))
        for role in role_set:
            if g.user.is_role(role):
                return
        return abort(403)

    check_role.__name__ = 'is_role_in(%s)' % (','.join(args))

    is_role_in_cache[role_set] = check_role

    return check_role
