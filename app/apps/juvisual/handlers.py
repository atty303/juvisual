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
#        self.response.headers['Content-Type'] = 'text/html; charset=UTF-8'
        res = ''
        res += '<html><body><ul>'

        tunes = models.Tune.all().order('tune_id')

        for tune in tunes:
            res += '<li>'
            if tune.title:
                res += '<b>%s</b>' % tune.title
            if tune.artist:
                res += '/ %s' % tune.artist
            res += '</li>'

        # Write the submission form and the footer of the page
        res += '</ul></body></html>'

        return Response(res)

        tvars = dict(tunes=tunes)
        # path = os.path.join(os.path.dirname(__file__), 'main.html')
        # self.response.out.write(template.render(path, tvars))


class HelloWorldHandler(RequestHandler):
    def get(self):
        """Simply returns a Response object with an enigmatic salutation."""
        return Response('Hello, World!')


class PrettyHelloWorldHandler(RequestHandler):
    def get(self):
        """Simply returns a rendered template with an enigmatic salutation."""
        return render_response('hello_world.html', message='Hello, World!')
