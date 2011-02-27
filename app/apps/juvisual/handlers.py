# -*- coding: utf-8 -*-
"""
    handlers
    ~~~~~~~~

    Hello, World!: the simplest tipfy app.

    :copyright: 2009 by tipfy.org.
    :license: BSD, see LICENSE for more details.
"""
import simplejson

from tipfy import RequestHandler, Response, redirect_to
from tipfy.ext.jinja2 import render_response

from . import models

class MainHandler(RequestHandler):
    def get(self):
        tunes = models.Tune.all().order('tune_id')
        latest_revision = models.ScoreRevision.latest_revision()
        if latest_revision:
            q = latest_revision.query_score_records()
            scores = q.order('title').fetch(models.Tune.LIMIT*len(models.LEVEL_KINDS))
        else:
            scores = []
        return render_response('main.jinja', tunes=tunes, scores=scores)

class RegistRecordHandler(RequestHandler):
    def post(self):
        srfile = self.request.files.get('score_record_file')
        if srfile:
            records = simplejson.load(srfile)
            models.ScoreRevision.regist_new_revision(records)

            return redirect_to('main')
