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
        return render_response('main.html', tunes=tunes)

class RegistRecordHandler(RequestHandler):
    def post(self):
        srfile = self.request.files.get('score_record_file')
        if srfile:
            records = simplejson.load(srfile)

            new_revision = models.ScoreRevision()
            new_revision.regist_new_revision(records)

            return redirect_to('main')
