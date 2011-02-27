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
    for l in ('bas', 'adv', 'ext'):
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

    score_bas = db.IntegerProperty()
    score_adv = db.IntegerProperty()
    score_ext = db.IntegerProperty()
    score_all = db.IntegerProperty()

    score_diff_bas = db.IntegerProperty()
    score_diff_adv = db.IntegerProperty()
    score_diff_ext = db.IntegerProperty()
    score_diff_all = db.IntegerProperty()

    @staticmethod
    def latest_revision(keys_only=False):
        # TODO: hold on memcache
        return ScoreRevision.all(keys_only=keys_only).filter('is_valid', True).order('-created_at').get()

    @staticmethod
    def regist_new_revision(scores):
        current_revision_key = ScoreRevision.latest_revision(keys_only=True)
        if current_revision_key:
            current_scores = ScoreRecord.all().ancestor(current_revision_key).fetch(Tune.LIMIT)
            current_scores_dict = dict([(v.tune_id, v) for v in current_scores])
        else:
            current_scores_dict = {}

        tunes = Tune.tunes_dict()

        new_revision = ScoreRevision()
        new_revision.put()
        try:
            new_entities = [new_revision]

            for s in scores:
                t = tunes.get(s['tune_id'])
                if not t:
                    continue
                sr = ScoreRecord(parent=new_revision, tune_id=t.tune_id)
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
    tune_id = db.IntegerProperty(required=True)
    title = db.StringProperty()
    artist = db.StringProperty()
    level_bas = db.IntegerProperty()
    level_adv = db.IntegerProperty()
    level_ext = db.IntegerProperty()

    score_bas = db.IntegerProperty()
    score_adv = db.IntegerProperty()
    score_ext = db.IntegerProperty()

    fc_bas = db.BooleanProperty()
    fc_adv = db.BooleanProperty()
    fc_ext = db.BooleanProperty()

    rating_bas = db.StringProperty(choices=RATINGS)
    rating_adv = db.StringProperty(choices=RATINGS)
    rating_ext = db.StringProperty(choices=RATINGS)

    mb_bas = db.ListProperty(int, indexed=False)
    mb_adv = db.ListProperty(int, indexed=False)
    mb_ext = db.ListProperty(int, indexed=False)

    score_diff_bas = db.IntegerProperty()
    score_diff_adv = db.IntegerProperty()
    score_diff_ext = db.IntegerProperty()

    last_play_date = db.DateTimeProperty()
    last_update_date = db.DateTimeProperty()

    # def __init__(self, tune, **kwargs):
    #     db.Model.__init__(self, **kwargs)
    #     self.dup_tune(tune)

    # dup_tune = functools.partial(dup_property_values,
    #                              props='tune_id title artist level_bas level_adv level_ext')
    def dup_tune(self, tune):
        self.tune_id = tune.tune_id
        self.title = tune.title
        self.artist = tune.artist
        self.level_bas = tune.level_bas
        self.level_adv = tune.level_adv
        self.level_ext = tune.level_ext

    def update_new_score(self, cur, new_js):
        # @run_by_level('score_%s', 'fc_%s', 'score_diff_%s')
        # def a(score_attr, fc_attr, score_diff_attr):
        #     setattr(self, score_attr, new_js[score_attr])
        #     setattr(self, fc_attr, new_js[fc_attr])
        #     setattr(self, score_diff_attr,
        #             getattr(self, score_attr) - (getattr(cur, score_attr) if cur else 0))
        # run_by_level(a)
        self.score_bas = new_js['score_bas']
        self.score_adv = new_js['score_adv']
        self.score_ext = new_js['score_ext']
        self.fc_bas = new_js['fc_bas']
        self.fc_adv = new_js['fc_adv']
        self.fc_ext = new_js['fc_ext']
        self.rating_bas = rating_by_score(self.score_bas)
        self.rating_adv = rating_by_score(self.score_adv)
        self.rating_ext = rating_by_score(self.score_ext)
        
        self.last_play_date = datetime.datetime.strptime(new_js['last_play_date'], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=pytz.utc)

        self.score_diff_bas = self.score_bas - (cur.score_bas if cur else 0)
        self.score_diff_adv = self.score_adv - (cur.score_adv if cur else 0)
        self.score_diff_ext = self.score_ext - (cur.score_ext if cur else 0)
        if self.score_diff_bas or self.score_diff_adv or self.score_diff_ext:
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

        self.mb_bas = convert_mb(new_js['mb_bas'])
        self.mb_adv = convert_mb(new_js['mb_adv'])
        self.mb_ext = convert_mb(new_js['mb_ext'])
