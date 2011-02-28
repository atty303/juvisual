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

MB_NULL = '0'
MB_GRAY = '1'
MB_BLUE = '2'
MB_YELLOW = '3'

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
        q = ScoreRevision.all(keys_only=keys_only).filter('is_valid', True)
        q = q.order('-created_at')
        return q.get()

    @staticmethod
    def regist_new_revision(scores):
        tunes = Tune.tunes_dict()

        cur_rev_key = ScoreRevision.latest_revision(keys_only=True)

        new_rev = ScoreRevision()
        new_rev.put()
        try:
            new_entities = [new_rev]

            for lk in LEVEL_KINDS:
                if cur_rev_key:
                    q = ScoreRecord.all().ancestor(cur_rev_key).filter('level_kind', lk)
                    cur_scores = q.fetch(Tune.LIMIT)
                    cur_scores_dict = dict([(v.tune_id, v) for v in cur_scores])
                else:
                    cur_scores_dict = {}

                # TODO: Tune を基点に scorerecord を引くようにする
                for s in scores:
                    t = tunes.get(s['tune_id'])
                    if not t:
                        continue
                    sr = ScoreRecord(parent=new_rev,
                                     tune_id=t.tune_id,
                                     level_kind=lk)
                    sr.dup_tune(t)
                    cur = cur_scores_dict.get(s['tune_id'])
                    sr.update_new_score(cur, s)
                    new_entities.append(sr)

            new_rev.is_valid = True

            def txn():
                db.put(new_entities)
            db.run_in_transaction(txn)

        except Exception:
            new_rev.delete()
            raise

    def query_score_records(self):
        return ScoreRecord.all().ancestor(self)


class ScoreRecord(db.Model):
    level_kind = db.StringProperty(required=True, choices=LEVEL_KINDS)
    tune_id = db.IntegerProperty(required=True)
    title = db.StringProperty()
    artist = db.StringProperty()

    level = db.IntegerProperty()

    is_played = db.BooleanProperty()
    score = db.IntegerProperty()
    is_full_combo = db.BooleanProperty()
    rating = db.StringProperty(choices=RATINGS)
    musicbar = db.StringProperty(indexed=False)
    is_no_gray = db.BooleanProperty()
    is_all_yellow = db.BooleanProperty()
    score_diff = db.IntegerProperty()

    last_play_date = db.DateTimeProperty()
    last_update_date = db.DateTimeProperty()

    def dup_tune(self, tune):
        self.tune_id = tune.tune_id
        self.title = tune.title
        self.artist = tune.artist
        self.level = getattr(tune, 'level_'+self.level_kind)

    def update_new_score(self, cur, new_js):
        lk = self.level_kind

        self.score = new_js['score_'+lk]
        if self.score < 0:
            self.score = 0
            self.is_played = False
        else:
            self.is_played = True

        self.is_full_combo = new_js['fc_'+lk]
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
                l.append(str(b & 3))
                l.append(str((b >> 2) & 3))
                l.append(str((b >> 4) & 3))
                l.append(str((b >> 6) & 3))
            if MB_NULL in l:
                return ''
            else:
                return ''.join(l)

        self.musicbar = convert_mb(new_js['mb_'+lk])
        if self.musicbar:
            self.is_no_gray = MB_GRAY not in self.musicbar
            self.is_all_yellow = (MB_GRAY not in self.musicbar) and (MB_BLUE not in self.musicbar)
