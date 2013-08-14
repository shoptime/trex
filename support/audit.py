# coding=utf-8

from __future__ import absolute_import
from flask import g

def audit(description, tags, documents=None, user=None, system_action=False, moreinfo=None):
    import app.model as m  # We import this late so that the audit method can be loaded into the model

    if user is None and hasattr(g, 'user'):
        user = g.user

    if system_action:
        user = None

    if documents is None:
        documents = []

    audit = m.Audit(
        user        = user,
        tags        = tags,
        documents   = documents,
        description = description,
        moreinfo    = moreinfo,
    )
    audit.save()
