# -*- coding: utf-8; -*-

import functools
import datetime

from google.appengine.ext import db
import pytz

# group by user
# - play count
# - last play date

# group by level + total
# - average score
# - total best score
# - rating EXC
# - rating SSS
# - rating SS
# - rating S
# - rating A
# - rating B
# - rating C
# - rating PLAY (below C)

# group by tune, level
# - score
# - last play date
# - last update date
# - rating
# - full combo

MB_GREY = 1
MB_BLUE = 2
MB_YELLOW = 3

LEVEL_KINDS = [ 'bas', 'adv', 'ext' ]

RATINGS = ['exc', 'sss', 'ss', 's', 'a', 'b', 'c', 'd', 'e', '']

def rating_by_score(score):
    if score >= 1000000:
        return 'exc'
    elif score >= 980000:
        return 'sss'
    elif score >= 950000:
        return 'ss'
    elif score >= 900000:
        return 's'
    elif score >= 850000:
        return 'a'
    elif score >= 800000:
        return 'b'
    elif score >= 700000:
        return 'c'
    elif score >= 500000:
        return 'd'
    elif score > 0:
        return 'e'
    return ''

def dup_property_values(dst, src, props):
    for p in props.split(' '):
        setattr(dst, p, getattr(src, p))

def run_by_level(func, with_all=False):
    for l in LEVEL_KINDS:
        func(l)
    if with_all:
        func('all')

class Tune(db.Model):
    tune_id = db.IntegerProperty(required=True)
    title = db.StringProperty(required=True)
    artist = db.StringProperty()
    level_bas = db.IntegerProperty()
    level_adv = db.IntegerProperty()
    level_ext = db.IntegerProperty()

    LIMIT = 1000
    TUNES_DICT_CACHE = {}

    @classmethod
    def tunes_dict(cls):
        if cls.TUNES_DICT_CACHE:
            return cls.TUNES_DICT_CACHE
        d = {}
        for t in Tune.all().fetch(Tune.LIMIT):
            d[t.tune_id] = t
        cls.TUNES_DICT_CACHE = d
        return d

class ScoreRevision(db.Model):
    is_valid = db.BooleanProperty(required=True, default=False)
    created_at = db.DateTimeProperty(auto_now_add=True)

    @staticmethod
    def latest_revision(keys_only=False):
        # TODO: hold on memcache
        return ScoreRevision.all(keys_only=keys_only).filter('is_valid', True).order('-created_at').get()

    @staticmethod
    def regist_new_revision(scores):
        tunes = Tune.tunes_dict()

        current_revision_key = ScoreRevision.latest_revision(keys_only=True)

        new_revision = ScoreRevision()
        new_revision.put()
        try:
            new_entities = [new_revision]

            for lk in LEVEL_KINDS:
                if current_revision_key:
                    current_scores = ScoreRecord.all().ancestor(current_revision_key).filter('level_kind', lk).fetch(Tune.LIMIT)
                    current_scores_dict = dict([(v.tune_id, v) for v in current_scores])
                else:
                    current_scores_dict = {}

                # TODO: Tune を基点に scorerecord を引くようにする
                for s in scores:
                    t = tunes.get(s['tune_id'])
                    if not t:
                        continue
                    sr = ScoreRecord(parent=new_revision,
                                     tune_id=t.tune_id,
                                     level_kind=lk)
                    sr.dup_tune(t)
                    cur = current_scores_dict.get(s['tune_id'])
                    sr.update_new_score(cur, s)
                    new_entities.append(sr)

            new_revision.is_valid = True

            def txn():
                db.put(new_entities)
            db.run_in_transaction(txn)

        except Exception:
            new_revision.delete()
            raise

    def query_score_records(self):
        return ScoreRecord.all().ancestor(self)


class ScoreRecord(db.Model):
    level_kind = db.StringProperty(required=True, choices=LEVEL_KINDS)
    tune_id = db.IntegerProperty(required=True)
    title = db.StringProperty()
    artist = db.StringProperty()

    level = db.IntegerProperty()

    score = db.IntegerProperty()
    fc = db.BooleanProperty()
    rating = db.StringProperty(choices=RATINGS)
    mb = db.ListProperty(int, indexed=False)
    ng = db.BooleanProperty()   # NO GRAY
    ay = db.BooleanProperty()   # ALL YELLOW
    score_diff = db.IntegerProperty()

    last_play_date = db.DateTimeProperty()
    last_update_date = db.DateTimeProperty()

    # def __init__(self, tune, **kwargs):
    #     db.Model.__init__(self, **kwargs)
    #     self.dup_tune(tune)

    def dup_tune(self, tune):
        self.tune_id = tune.tune_id
        self.title = tune.title
        self.artist = tune.artist
        self.level = getattr(tune, 'level_'+self.level_kind)

    def update_new_score(self, cur, new_js):
        lk = self.level_kind

        self.score = new_js['score_'+lk]
        self.fc = new_js['fc_'+lk]
        self.rating = rating_by_score(self.score)

        self.last_play_date = datetime.datetime.strptime(new_js['last_play_date'], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=pytz.utc)

        self.score_diff = self.score - (cur.score if cur else 0)
        if self.score_diff:
            self.last_update_date = self.last_play_date
        else:
            self.last_update_date = cur.last_update_date

        def convert_mb(mb):
            l = []
            for b in [ord(c) for c in mb.decode('base64')]:
                l.append(b & 3)
                l.append((b >> 2) & 3)
                l.append((b >> 4) & 3)
                l.append((b >> 6) & 3)
            return l

        self.mb = convert_mb(new_js['mb_'+lk])

        self.ng = MB_GREY not in self.mb
        self.ay = (MB_GREY not in self.mb) and (MB_BLUE not in self.mb)
