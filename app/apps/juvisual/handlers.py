# -*- coding: utf-8 -*-
"""
    handlers
    ~~~~~~~~

    Hello, World!: the simplest tipfy app.

    :copyright: 2009 by tipfy.org.
    :license: BSD, see LICENSE for more details.
"""
from tipfy import RequestHandler, Response
from tipfy.ext.jinja2 import render_response

from . import models

class MainHandler(RequestHandler):
    def get(self):
        tunes = models.Tune.all().order('tune_id')

        return render_response('main.html', tunes=tunes)
