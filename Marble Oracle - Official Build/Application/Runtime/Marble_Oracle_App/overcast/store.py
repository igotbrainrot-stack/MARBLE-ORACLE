"""Persistent, local-only SQLite evidence and prediction ledger."""
from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone, date, timedelta
from urllib.parse import urlsplit


def _latest_per_question(rows):
    latest={}
    for r in rows:
        key=' '.join(r['question'].casefold().split())
        if key not in latest or r['id']>latest[key]['id']:
            latest[key]=r
    return sorted(latest.values(),key=lambda r:r['id'])


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def default_state_dir() -> Path:
    """User data location. Deliberately still named `news_oracle` after the OVERCAST
    rename so every existing forecast, outcome and snapshot is found on upgrade."""
    override = os.getenv('MARBLE_ORACLE_STATE') or os.getenv('Marble_Oracle_STATE')
    if override:
        return Path(override).expanduser() / 'news_oracle'
    if sys.platform == 'win32':
        return Path(os.getenv('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Marble_Oracle' / 'news_oracle'
    return Path(os.getenv('XDG_STATE_HOME') or Path.home() / '.local' / 'state') / 'Marble_Oracle' / 'news_oracle'


class Store:
    def __init__(self, state_dir=None):
        self.state_dir = Path(state_dir).expanduser() if state_dir else default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.state_dir / 'news_oracle.sqlite3'), timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=15000')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self._init_db()

    def _init_db(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,
            published TEXT NOT NULL DEFAULT '',
            collected TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general'
        );
        CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published DESC);
        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            probability REAL NOT NULL CHECK(probability>=0 AND probability<=1),
            target_date TEXT NOT NULL,
            resolution_criteria TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            counterargument TEXT NOT NULL,
            change_mind TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            created TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS resolutions (
            forecast_id INTEGER PRIMARY KEY REFERENCES forecasts(id),
            outcome INTEGER NOT NULL CHECK(outcome IN (0,1)),
            evidence_url TEXT NOT NULL,
            note TEXT NOT NULL,
            resolved_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS forecast_audits (
            forecast_id INTEGER PRIMARY KEY REFERENCES forecasts(id),
            audit_json TEXT NOT NULL,
            created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS calendar_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_note TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS forecast_packets (
            forecast_id INTEGER PRIMARY KEY REFERENCES forecasts(id),
            as_of_utc TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            packet_json TEXT NOT NULL,
            saved_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS event_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_article_id INTEGER NOT NULL REFERENCES articles(id),
            actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL,
            location TEXT NOT NULL, event_date TEXT,
            kind TEXT NOT NULL, evidence_quote TEXT NOT NULL,
            claim_text TEXT NOT NULL, status TEXT NOT NULL,
            model_id TEXT NOT NULL, as_of_utc TEXT NOT NULL, recorded_at TEXT NOT NULL,
            UNIQUE(source_article_id, evidence_quote, actor, action)
        );
        CREATE INDEX IF NOT EXISTS idx_claims_actor ON event_claims(actor);
        CREATE TABLE IF NOT EXISTS reference_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL, focus TEXT NOT NULL,
            observations INTEGER NOT NULL CHECK(observations>=1),
            positive INTEGER NOT NULL CHECK(positive>=0 AND positive<=observations),
            period_start TEXT NOT NULL, period_end TEXT NOT NULL,
            source_url TEXT NOT NULL, notes TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outlooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL, query TEXT NOT NULL DEFAULT '',
            horizon_days INTEGER NOT NULL, deadline TEXT NOT NULL,
            strategic_question TEXT NOT NULL, adverse_direction TEXT NOT NULL,
            stress_index REAL NOT NULL CHECK(stress_index>=-100 AND stress_index<=100),
            scenarios_json TEXT NOT NULL, drivers_json TEXT NOT NULL, audit_json TEXT NOT NULL,
            model_id TEXT NOT NULL, method TEXT NOT NULL, prompt_version TEXT NOT NULL,
            created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outlook_signposts (
            outlook_id INTEGER NOT NULL REFERENCES outlooks(id),
            forecast_id INTEGER NOT NULL UNIQUE REFERENCES forecasts(id),
            position INTEGER NOT NULL, signpost_key TEXT NOT NULL, driver TEXT NOT NULL,
            adverse_if_yes INTEGER NOT NULL CHECK(adverse_if_yes IN (0,1)),
            weight INTEGER NOT NULL CHECK(weight BETWEEN 1 AND 3),
            PRIMARY KEY(outlook_id, forecast_id)
        );
        CREATE TABLE IF NOT EXISTS outlook_resolutions (
            outlook_id INTEGER PRIMARY KEY REFERENCES outlooks(id),
            scenario_id TEXT NOT NULL, evidence_url TEXT NOT NULL,
            note TEXT NOT NULL, resolved_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS forecast_orientation (
            forecast_id INTEGER PRIMARY KEY REFERENCES forecasts(id),
            adverse_if_yes INTEGER NOT NULL CHECK(adverse_if_yes IN (0,1)),
            severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 5),
            set_by TEXT NOT NULL, set_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            briefing TEXT NOT NULL,
            uncertainties TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            created TEXT NOT NULL
        );
        ''')
        # Additive column migrations (never drop or rewrite existing data).
        self._add_column('outlooks','revision_of','INTEGER REFERENCES outlooks(id)')
        self._add_column('outlook_signposts','severity','INTEGER NOT NULL DEFAULT 3')
        self.db.commit()

    def _add_column(self, table, column, decl):
        existing={r['name'] for r in self.db.execute(f'PRAGMA table_info({table})')}
        if column not in existing:
            self.db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {decl}')

    def save_articles(self, items):
        added = 0
        with self.db:
            for item in items:
                cursor = self.db.execute('''
                  INSERT OR IGNORE INTO articles(url,title,summary,source,published,collected,category)
                  VALUES(:url,:title,:summary,:source,:published,:collected,:category)''', item)
                added += cursor.rowcount
        return added

    def articles(self, limit=500, query=''):
        limit = min(max(1, int(limit)), 2000)
        if query:
            # Escape LIKE wildcards so "%" or "_" in a search are matched literally.
            needle = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            rows = self.db.execute('''SELECT * FROM articles
              WHERE title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\' OR source LIKE ? ESCAPE '\\'
              ORDER BY COALESCE(NULLIF(published,''), collected) DESC, id DESC LIMIT ?''',
              (needle,)*3 + (limit,)).fetchall()
        else:
            rows = self.db.execute('''SELECT * FROM articles
              ORDER BY COALESCE(NULLIF(published,''),collected) DESC, id DESC LIMIT ?''', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def recent_articles(self, days=15, limit=4000):
        """Everything published (or, if undated, first seen) in the last `days`, newest first.

        Retrieval works on this whole window rather than a fixed newest-N slice, so a busy
        refresh cannot push relevant stories from earlier in the fortnight out of view.
        Timestamps are stored as UTC ISO-8601 strings, so string comparison is chronological.
        """
        cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat(timespec='seconds')
        rows=self.db.execute('''SELECT * FROM articles WHERE COALESCE(NULLIF(published,''),collected) >= ?
              ORDER BY COALESCE(NULLIF(published,''),collected) DESC, id DESC LIMIT ?''',
              (cutoff,min(max(1,int(limit)),10000))).fetchall()
        return [dict(r) for r in rows]

    def article_ids(self, ids):
        ids = sorted({int(i) for i in ids})
        if not ids or len(ids) > 30:
            raise ValueError('Select 1 to 30 news items.')
        placeholders = ','.join('?' for _ in ids)
        rows = self.db.execute(f'SELECT * FROM articles WHERE id IN ({placeholders})', ids).fetchall()
        if len(rows) != len(ids):
            raise ValueError('One or more selected article IDs no longer exist.')
        return [dict(r) for r in rows]

    def add_schedule(self, title, start_date, end_date, source_url, source_note=''):
        from .calendar import iso_day
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError('A scheduled event needs a short title.')
        a, b = iso_day(start_date), iso_day(end_date)
        if b < a:
            raise ValueError('Scheduled end date must be on/after the start date.')
        if not isinstance(source_url, str) or not source_url.startswith('https://') or len(source_url)>2000:
            raise ValueError('Provide a HTTPS source URL documenting the scheduled date.')
        from urllib.parse import urlsplit
        if not urlsplit(source_url).hostname:
            raise ValueError('The source URL must contain a hostname.')
        if not isinstance(source_note, str) or len(source_note) > 1000:
            raise ValueError('Source note must be shorter than 1,000 characters.')
        with self.db:
            cur=self.db.execute('INSERT INTO calendar_schedules(title,start_date,end_date,source_url,source_note,created) '
                                'VALUES(?,?,?,?,?,?)',
                                (title.strip(), start_date, end_date, source_url, source_note.strip(), utc_now()))
            return cur.lastrowid

    def schedules(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM calendar_schedules ORDER BY start_date,id')]

    def add_forecast(self, data, evidence, model_id, prompt_version, raw, audit=None, snapshot=None):
        with self.db:
            return self._insert_forecast(data, evidence, model_id, prompt_version, raw, audit, snapshot)

    def _insert_forecast(self, data, evidence, model_id, prompt_version, raw, audit=None, snapshot=None):
        """Insert inside the caller's transaction (no commit here)."""
        cur = self.db.execute('''
          INSERT INTO forecasts(question,probability,target_date,resolution_criteria,reasoning,
            counterargument,change_mind,evidence_json,model_id,prompt_version,created,raw_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
          (data['question'],data['probability'],data['target_date'],data['resolution_criteria'],
           data['reasoning'],data['counterargument'],data['change_mind'],json.dumps(evidence),
           model_id,prompt_version,utc_now(),json.dumps(raw,ensure_ascii=False)))
        if audit is not None:
            self.db.execute('INSERT INTO forecast_audits(forecast_id,audit_json,created) VALUES(?,?,?)',
                            (cur.lastrowid,json.dumps(audit,ensure_ascii=False),utc_now()))
        if snapshot is not None:
            raw_packet=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            fingerprint=hashlib.sha256(raw_packet.encode('utf-8')).hexdigest()
            self.db.execute('''INSERT INTO forecast_packets(forecast_id,as_of_utc,sha256,packet_json,saved_at)
                               VALUES(?,?,?,?,?)''',(cur.lastrowid,snapshot['as_of_utc'],fingerprint,
                                                   raw_packet,utc_now()))
        return cur.lastrowid

    def add_outlook(self, outlook, signposts):
        """Atomically store an outlook and every signpost as a normal ledger forecast.

        signposts: list of dicts with keys data, evidence, raw, audit, snapshot,
        key, driver, adverse_if_yes, weight. Either everything is saved or nothing.
        """
        with self.db:
            cur=self.db.execute('''INSERT INTO outlooks(scope,query,horizon_days,deadline,strategic_question,
                adverse_direction,stress_index,scenarios_json,drivers_json,audit_json,model_id,method,
                prompt_version,created,revision_of) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (outlook['scope'],outlook.get('query',''),int(outlook['horizon_days']),outlook['deadline'],
                 outlook['strategic_question'],outlook['adverse_direction'],float(outlook['stress_index']),
                 json.dumps(outlook['scenarios'],ensure_ascii=False),json.dumps(outlook['drivers'],ensure_ascii=False),
                 json.dumps(outlook['audit'],ensure_ascii=False),outlook['model_id'],outlook['method'],
                 outlook['prompt_version'],utc_now(),outlook.get('revision_of')))
            outlook_id=cur.lastrowid
            ids=[]
            for position,item in enumerate(signposts,1):
                audit=dict(item['audit'],outlook_id=outlook_id)
                fid=self._insert_forecast(item['data'],item['evidence'],outlook['model_id'],
                                          item['prompt_version'],item['raw'],audit,item['snapshot'])
                self.db.execute('''INSERT INTO outlook_signposts(outlook_id,forecast_id,position,signpost_key,
                    driver,adverse_if_yes,weight,severity) VALUES(?,?,?,?,?,?,?,?)''',
                    (outlook_id,fid,position,item['key'],item['driver'],int(bool(item['adverse_if_yes'])),
                     int(item['weight']),int(item.get('severity',3))))
                ids.append(fid)
            return outlook_id,ids

    _OUTLOOK_SELECT='''SELECT o.*, r.scenario_id AS resolved_scenario, r.evidence_url AS resolution_url,
            r.note AS resolution_note, r.resolved_at FROM outlooks o LEFT JOIN outlook_resolutions r
            ON r.outlook_id=o.id'''

    @staticmethod
    def _outlook_row(row):
        item=dict(row)
        item['scenarios']=json.loads(item.pop('scenarios_json'))
        item['drivers']=json.loads(item.pop('drivers_json'))
        item['audit']=json.loads(item.pop('audit_json'))
        return item

    def outlooks(self, limit=200):
        rows=self.db.execute(self._OUTLOOK_SELECT+' ORDER BY o.id DESC LIMIT ?',(min(max(1,int(limit)),2000),)).fetchall()
        return [self._outlook_row(r) for r in rows]

    def outlook(self, outlook_id):
        row=self.db.execute(self._OUTLOOK_SELECT+' WHERE o.id=?',(int(outlook_id),)).fetchone()
        if not row:return None
        item=self._outlook_row(row)
        item['signposts']=[dict(r) for r in self.db.execute('''SELECT s.*, f.question, f.probability,
            f.target_date, f.resolution_criteria, res.outcome FROM outlook_signposts s
            JOIN forecasts f ON f.id=s.forecast_id LEFT JOIN resolutions res ON res.forecast_id=f.id
            WHERE s.outlook_id=? ORDER BY s.position''',(int(outlook_id),))]
        for x in item['signposts']:
            x['adverse_if_yes']=bool(x['adverse_if_yes'])
            x['p_adverse']=x['probability'] if x['adverse_if_yes'] else 1-x['probability']
            x['risk_score']=round(x['p_adverse']*(x.get('severity') or 3),3)
        resolved=[x for x in item['signposts'] if x['outcome'] is not None]
        item['signposts_resolved']=len(resolved)
        item['realised_index']=None
        if item['signposts'] and len(resolved)==len(item['signposts']):
            total=sum(x['weight'] for x in resolved)
            item['realised_index']=round(100*sum(x['weight']*(1 if x['adverse_if_yes'] else -1)*(2*x['outcome']-1)
                                                 for x in resolved)/total,1)
        return item

    def outlook_lineage(self, outlook_id):
        """All outlook IDs in the same revision chain (root and every revision)."""
        rows={r['id']:r['revision_of'] for r in self.db.execute('SELECT id, revision_of FROM outlooks')}
        def root(i):
            seen=set()
            while rows.get(i) and i not in seen:
                seen.add(i); i=rows[i]
            return i
        target=root(int(outlook_id))
        return sorted(i for i in rows if root(i)==target)

    def signpost_twins(self, forecast_id):
        row=self.db.execute('SELECT outlook_id, signpost_key, question FROM outlook_signposts s JOIN forecasts f '
                            'ON f.id=s.forecast_id WHERE s.forecast_id=?',(int(forecast_id),)).fetchone()
        if not row:return []
        lineage=self.outlook_lineage(row['outlook_id'])
        marks=','.join('?' for _ in lineage)
        twins=self.db.execute(f'''SELECT s.forecast_id FROM outlook_signposts s JOIN forecasts f ON f.id=s.forecast_id
            LEFT JOIN resolutions r ON r.forecast_id=s.forecast_id
            WHERE s.outlook_id IN ({marks}) AND s.forecast_id<>? AND f.question=? AND r.forecast_id IS NULL''',
            (*lineage,int(forecast_id),row['question'])).fetchall()
        return [t['forecast_id'] for t in twins]

    def set_orientation(self, forecast_id, adverse_if_yes, severity, set_by='user'):
        """Mark which answer is the bad news for a forecast (for the risk register and gloom bias)."""
        if not self.get_forecast(forecast_id):
            raise ValueError('Unknown forecast ID.')
        if isinstance(severity,bool) or not isinstance(severity,int) or not 1<=severity<=5:
            raise ValueError('Severity must be an integer 1 (negligible) to 5 (systemic).')
        with self.db:
            self.db.execute('''INSERT INTO forecast_orientation(forecast_id,adverse_if_yes,severity,set_by,set_at)
                VALUES(?,?,?,?,?) ON CONFLICT(forecast_id) DO UPDATE SET adverse_if_yes=excluded.adverse_if_yes,
                severity=excluded.severity,set_by=excluded.set_by,set_at=excluded.set_at''',
                (int(forecast_id),int(bool(adverse_if_yes)),severity,set_by,utc_now()))

    def oriented_forecasts(self):
        """Every forecast whose 'bad news' direction is known: outlook signposts plus user-marked ones."""
        rows=self.db.execute('''SELECT f.id, f.question, f.probability, f.target_date, f.created, f.prompt_version,
              r.outcome, COALESCE(o.adverse_if_yes, s.adverse_if_yes) AS adverse_if_yes,
              COALESCE(o.severity, s.severity, 3) AS severity, s.outlook_id,
              CASE WHEN o.forecast_id IS NOT NULL THEN 'user' ELSE 'outlook' END AS orientation_source
            FROM forecasts f LEFT JOIN resolutions r ON r.forecast_id=f.id
            LEFT JOIN forecast_orientation o ON o.forecast_id=f.id
            LEFT JOIN outlook_signposts s ON s.forecast_id=f.id
            WHERE o.forecast_id IS NOT NULL OR s.forecast_id IS NOT NULL''').fetchall()
        out=[]
        for r in rows:
            item=dict(r)
            item['adverse_if_yes']=bool(item['adverse_if_yes'])
            item['p_adverse']=item['probability'] if item['adverse_if_yes'] else 1-item['probability']
            item['risk_score']=round(item['p_adverse']*item['severity'],3)
            item['adverse_occurred']=(None if item['outcome'] is None else
                                      int(item['outcome']==(1 if item['adverse_if_yes'] else 0)))
            out.append(item)
        return out

    def risk_register(self, limit=10, today=None):
        """Open, not-yet-due risks ranked by expected harm (P(adverse) x severity).

        Only the newest copy of a re-forecast signpost is listed."""
        day=(today or datetime.now(timezone.utc).date()).isoformat()
        open_rows=[r for r in self.oriented_forecasts() if r['outcome'] is None and r['target_date']>=day]
        newest={}
        for r in open_rows:
            key=r['question'].casefold()
            if key not in newest or r['id']>newest[key]['id']:newest[key]=r
        return sorted(newest.values(),key=lambda r:(-r['risk_score'],r['target_date']))[:max(1,int(limit))]

    def gloom_bias(self, min_n=15):
        """See below; each real-world question counts once (latest forecast of it)."""
        return self._gloom_bias(_latest_per_question(
            [r for r in self.oriented_forecasts() if r['adverse_occurred'] is not None]), min_n)

    def _gloom_bias(self, rows, min_n):
        """Are we too gloomy? Mean forecast P(adverse) minus how often the adverse side happened.

        Positive = too pessimistic, negative = bad news arrived more often than forecast.
        95% interval from the standard error of the per-forecast differences."""
        n=len(rows)
        out={'resolved':n,'min_required':min_n}
        if not n:
            out['verdict']='No resolved forecasts with a known adverse direction yet.'
            return out
        diffs=[r['p_adverse']-r['adverse_occurred'] for r in rows]
        mean=sum(diffs)/n
        mean_p=sum(r['p_adverse'] for r in rows)/n
        observed=sum(r['adverse_occurred'] for r in rows)/n
        sd=(sum((d-mean)**2 for d in diffs)/(n-1))**0.5 if n>1 else 0.0
        half=1.96*sd/(n**0.5) if n>1 else None
        out.update({'mean_forecast_p_adverse':round(mean_p,4),'observed_adverse_rate':round(observed,4),
                    'gloom_bias_points':round(100*mean,1),
                    'interval_points':[round(100*(mean-half),1),round(100*(mean+half),1)] if half is not None else None,
                    'adverse_frame_brier':round(sum((r['p_adverse']-r['adverse_occurred'])**2 for r in rows)/n,4)})
        if n<min_n or half is None:
            out['verdict']=f'Too few resolved risk forecasts to judge ({n}; need {min_n}).'
        elif mean-half>0:
            out['verdict']='TOO GLOOMY: adverse outcomes happened less often than forecast.'
        elif mean+half<0:
            out['verdict']='NOT GLOOMY ENOUGH: adverse outcomes happened more often than forecast.'
        else:
            out['verdict']='No detectable gloom bias: pessimism is matching reality so far.'
        return out

    def resolve_outlook(self, outlook_id, scenario_id, evidence_url, note=''):
        item=self.outlook(outlook_id)
        if not item:
            raise ValueError('Unknown outlook ID.')
        if item.get('resolved_scenario'):
            raise ValueError(f'Outlook #{int(outlook_id)} scenario is already resolved; outcomes are permanent.')
        if scenario_id not in {s['id'] for s in item['scenarios']}:
            raise ValueError('Choose one of the outlook\'s scenario letters.')
        if item['deadline']>datetime.now(timezone.utc).date().isoformat():
            raise ValueError(f'The outlook horizon runs to {item["deadline"]}; resolve its scenario after that date.')
        if (not isinstance(evidence_url,str) or not evidence_url.startswith(('https://','http://'))
                or not urlsplit(evidence_url).hostname):
            raise ValueError('Provide an evidence URL beginning with https:// or http:// and containing a hostname.')
        with self.db:
            for oid in self.outlook_lineage(outlook_id):
                self.db.execute('INSERT OR IGNORE INTO outlook_resolutions(outlook_id,scenario_id,evidence_url,note,resolved_at) '
                                'VALUES(?,?,?,?,?)',(oid,scenario_id,evidence_url,
                                (note if oid==int(outlook_id) else f'Propagated from outlook #{int(outlook_id)}. {note}').strip(),
                                utc_now()))

    def resolved_forecasts(self, unique=False):
        """Resolved forecasts, oldest first. unique=True keeps one row per real-world question
        (the latest forecast of it), so revisions of one signpost are not counted as independent
        evidence by statistics that assume independence (calibration, gloom bias)."""
        rows=[dict(r) for r in self.db.execute('''SELECT f.id, f.question, f.probability, f.prompt_version,
            f.target_date, f.created, r.outcome FROM forecasts f JOIN resolutions r ON r.forecast_id=f.id
            ORDER BY f.id''')]
        return _latest_per_question(rows) if unique else rows

    def forecast_packets(self, limit=2000):
        rows=self.db.execute('SELECT forecast_id FROM forecast_packets ORDER BY forecast_id DESC LIMIT ?',
                             (min(max(int(limit),1),5000),)).fetchall()
        return [{'forecast_id':r['forecast_id'], **self.forecast_packet(r['forecast_id'])} for r in rows]

    def forecast_packet(self, forecast_id):
        row=self.db.execute('SELECT * FROM forecast_packets WHERE forecast_id=?',(forecast_id,)).fetchone()
        if not row:return None
        data=json.loads(row['packet_json'])
        valid=hashlib.sha256(row['packet_json'].encode('utf-8')).hexdigest()==row['sha256']
        return {'as_of_utc':row['as_of_utc'],'sha256':row['sha256'],'checksum_valid':valid,
                'saved_at':row['saved_at'],'packet':data}

    def add_event_claims(self, claims, model_id, as_of_utc):
        added=0
        with self.db:
            for c in claims:
                result=self.db.execute('''INSERT OR IGNORE INTO event_claims
                    (source_article_id,actor,action,target,location,event_date,kind,evidence_quote,
                     claim_text,status,model_id,as_of_utc,recorded_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    c['article_id'],c['actor'],c['action'],c['target'],c['location'],c['event_date'],
                    c['kind'],c['evidence_quote'],c['claim_text'],'unverified_reported_claim',
                    model_id,as_of_utc,utc_now()))
                added+=result.rowcount
        return added

    def event_claims(self, limit=250):
        return [dict(r) for r in self.db.execute('''SELECT c.*, a.source AS publisher,
            a.url AS source_url, a.published AS article_published, a.collected AS article_first_seen
            FROM event_claims c JOIN articles a ON a.id=c.source_article_id
            ORDER BY c.id DESC LIMIT ?''',(min(max(int(limit),1),1000),))]

    def add_reference_class(self,label,focus,observations,positive,period_start,period_end,source_url,notes=''):
        from .calendar import iso_day
        from urllib.parse import urlsplit
        if not isinstance(label,str) or not label.strip() or len(label)>180:
            raise ValueError('Reference class needs a concise label.')
        if focus not in ('WORLD POLITICS','MARKETS','TRADE','CRISES','OTHER'):
            raise ValueError('Unsupported reference class focus.')
        if type(observations) is not int or type(positive) is not int or observations<1 or not 0<=positive<=observations:
            raise ValueError('Provide positive and total integer observations.')
        if iso_day(period_start)>iso_day(period_end) or iso_day(period_end)>datetime.now(timezone.utc).date():
            raise ValueError('Historical reference period must end no later than today.')
        if not isinstance(source_url,str) or not source_url.startswith('https://') or not urlsplit(source_url).hostname:
            raise ValueError('Reference class needs a valid HTTPS evidence URL.')
        if not isinstance(notes,str) or len(notes)>1200:raise ValueError('Notes too long.')
        with self.db:
            cur=self.db.execute('''INSERT INTO reference_classes(label,focus,observations,positive,
               period_start,period_end,source_url,notes,recorded_at) VALUES(?,?,?,?,?,?,?,?,?)''',
               (label.strip(),focus,observations,positive,period_start,period_end,source_url,notes,utc_now()))
            return cur.lastrowid

    def reference_classes(self):
        rows=[dict(r) for r in self.db.execute('SELECT * FROM reference_classes ORDER BY id DESC')]
        for row in rows:
            row['observed_rate']=round(row['positive']/row['observations'],6)
            row['smoothed_rate']=round((row['positive']+1)/(row['observations']+2),6)
            row['adequate_sample']=row['observations']>=20
        return rows

    def reference_class(self, identifier):
        for row in self.reference_classes():
            if row['id']==int(identifier):return row
        raise ValueError('Unknown historical reference class.')

    def forecast_audit(self, forecast_id):
        row=self.db.execute('SELECT audit_json FROM forecast_audits WHERE forecast_id=?',(forecast_id,)).fetchone()
        return json.loads(row['audit_json']) if row else None

    def audits(self, limit=500):
        rows=self.db.execute('SELECT forecast_id, audit_json FROM forecast_audits ORDER BY forecast_id DESC LIMIT ?',
                             (min(max(1,int(limit)),2000),)).fetchall()
        return [{'forecast_id':r['forecast_id'], **json.loads(r['audit_json'])} for r in rows]

    def forecasts(self, limit=500):
        rows = self.db.execute('''SELECT f.*, r.outcome, r.evidence_url AS resolution_url,
           r.note AS resolution_note, r.resolved_at FROM forecasts f
           LEFT JOIN resolutions r ON r.forecast_id=f.id
           ORDER BY f.id DESC LIMIT ?''',(min(max(1,int(limit)),2000),)).fetchall()
        return [dict(x) for x in rows]

    def get_forecast(self, forecast_id):
        row = self.db.execute('''SELECT f.*, r.outcome, r.evidence_url AS resolution_url,
           r.note AS resolution_note, r.resolved_at FROM forecasts f
           LEFT JOIN resolutions r ON r.forecast_id=f.id WHERE f.id=?''',(int(forecast_id),)).fetchone()
        return dict(row) if row else None

    def due_unresolved(self, today=None):
        """Open forecasts whose resolution deadline has passed (need a recorded outcome)."""
        day=(today or datetime.now(timezone.utc).date()).isoformat()
        return self.db.execute('''SELECT count(*) FROM forecasts f LEFT JOIN resolutions r
            ON r.forecast_id=f.id WHERE r.forecast_id IS NULL AND f.target_date<?''',(day,)).fetchone()[0]

    def add_briefing(self, data, evidence, model_id, prompt_version):
        with self.db:
            cur = self.db.execute('''INSERT INTO briefings(title,briefing,uncertainties,evidence_json,model_id,prompt_version,created)
                 VALUES(?,?,?,?,?,?,?)''', (data['title'],data['briefing'],data['uncertainties'],
                 json.dumps(evidence),model_id,prompt_version,utc_now()))
            return cur.lastrowid

    def briefings(self, limit=100):
        limit=min(max(1,int(limit)),5000)
        return [dict(x) for x in self.db.execute('SELECT * FROM briefings ORDER BY id DESC LIMIT ?', (limit,))]

    def resolve(self, forecast_id, outcome, evidence_url, note=''):
        if outcome not in (0, 1):
            raise ValueError('Outcome must be 0 or 1, not a probability.')
        existing=self.get_forecast(forecast_id)
        if not existing:
            raise ValueError('Unknown forecast ID.')
        if existing['outcome'] is not None:
            raise ValueError(f'Forecast #{int(forecast_id)} is already resolved; recorded outcomes are permanent.')
        if (not isinstance(evidence_url,str) or not evidence_url.startswith(('https://','http://'))
                or not urlsplit(evidence_url).hostname):
            raise ValueError('Provide an evidence URL beginning with https:// or http:// and containing a hostname.')
        twins=self.signpost_twins(forecast_id)
        with self.db:
            self.db.execute('''INSERT INTO resolutions(forecast_id,outcome,evidence_url,note,resolved_at)
                         VALUES(?,?,?,?,?)''', (forecast_id,outcome,evidence_url,note,utc_now()))
            # The same signpost re-forecast in a revised outlook is the same real-world
            # question: one outcome resolves every copy (each copy keeps its own probability).
            for twin in twins:
                self.db.execute('''INSERT OR IGNORE INTO resolutions(forecast_id,outcome,evidence_url,note,resolved_at)
                    VALUES(?,?,?,?,?)''',(twin,outcome,evidence_url,
                    f'Propagated from forecast #{int(forecast_id)} (same signpost, other outlook revision). {note}'.strip(),
                    utc_now()))
        return [int(forecast_id)]+twins

    def brier(self):
        row = self.db.execute('''SELECT count(*) AS count,
            AVG((f.probability-r.outcome)*(f.probability-r.outcome)) AS score
            FROM forecasts f JOIN resolutions r ON f.id=r.forecast_id''').fetchone()
        return {'count':row['count'], 'score':row['score']}

    def score_report(self):
        # Standard accuracy diagnostics: only manually resolved entries.
        rows=self.db.execute('''SELECT f.probability, f.prompt_version, f.created, f.target_date,
             r.outcome FROM forecasts f JOIN resolutions r ON f.id=r.forecast_id''').fetchall()
        bins=[]
        for low in range(0,10):
            subset=[r for r in rows if min(9,int(r['probability']*10))==low]
            if not subset:continue
            bins.append({'bin':f'{low*10:02d}-{(low+1)*10:02d}%',
                'n':len(subset), 'mean_predicted':round(sum(r['probability'] for r in subset)/len(subset),4),
                'observed_frequency':round(sum(r['outcome'] for r in subset)/len(subset),4)})
        by_method=[]
        for method in sorted({r['prompt_version'] for r in rows}):
            chosen=[r for r in rows if r['prompt_version']==method]
            by_method.append({'method':method,'resolved':len(chosen),
                 'brier':round(sum((r['probability']-r['outcome'])**2 for r in chosen)/len(chosen),5)})
        count_total=self.db.execute('SELECT count(*) FROM forecasts').fetchone()[0]
        # Same-forecast naive control, not a paired test of prompt variants.
        naive_brier=(sum((0.5-r['outcome'])**2 for r in rows)/len(rows)) if rows else None
        actual_brier=self.brier()['score']
        # Log loss (natural log), clipped so a 0/1 probability cannot produce infinity.
        def logloss(subset):
            if not subset:return None
            total=0.0
            for r in subset:
                p=min(max(float(r['probability']),1e-4),1-1e-4)
                total-=math.log(p if r['outcome']==1 else 1-p)
            return round(total/len(subset),5)
        by_horizon=[]
        for label,low,high in (('1-7 days',0,7),('8-30 days',8,30),('31-90 days',31,90),
                               ('91-180 days',91,180),('181+ days',181,10**6)):
            chosen=[]
            for r in rows:
                try:days=(date.fromisoformat(r['target_date'])-date.fromisoformat(r['created'][:10])).days
                except (TypeError,ValueError):continue
                if low<=days<=high:chosen.append(r)
            if chosen:
                by_horizon.append({'horizon':label,'resolved':len(chosen),
                    'brier':round(sum((r['probability']-r['outcome'])**2 for r in chosen)/len(chosen),5),
                    'log_loss':logloss(chosen)})
        for entry in by_method:
            entry['log_loss']=logloss([r for r in rows if r['prompt_version']==entry['method']])
        overdue=self.due_unresolved()
        misses=sorted(({'id':r['id'],'question':r['question'][:160],'probability':r['probability'],
                        'outcome':r['outcome'],'brier':round((r['probability']-r['outcome'])**2,4)}
                       for r in self.resolved_forecasts()),key=lambda x:-x['brier'])[:5]
        from .calibration import recalibration
        resolved_all=self.resolved_forecasts(unique=True)
        recal=recalibration([r['probability'] for r in resolved_all],[r['outcome'] for r in resolved_all])
        scenario_scores=[]
        for o in self.outlooks(2000):
            if not o.get('resolved_scenario'):continue
            probs=o['audit'].get('aggregation',{}).get('scenario_probability',{})
            if not probs:continue
            brier=sum((float(p)-(1 if k==o['resolved_scenario'] else 0))**2 for k,p in probs.items())
            p_true=min(max(float(probs.get(o['resolved_scenario'],0)),1e-4),1)
            scenario_scores.append({'outlook_id':o['id'],'resolved_scenario':o['resolved_scenario'],
                                    'probability_given':round(p_true,4),'multiclass_brier':round(brier,4),
                                    'log_loss':round(-math.log(p_true),4),'n_scenarios':len(probs)})
        unique={'count':len(resolved_all),
                'brier':(round(sum((r['probability']-r['outcome'])**2 for r in resolved_all)/len(resolved_all),5)
                         if resolved_all else None),
                'log_loss':logloss(resolved_all),
                'note':'One entry per real-world question (latest forecast); revisions are not double-counted.'}
        return {'by_question':unique,'biggest_misses':misses,'recalibration':recal,'gloom_bias':self.gloom_bias(),
                'scenario_forecasts':{'resolved':len(scenario_scores),'items':scenario_scores,
                    'mean_multiclass_brier':(round(sum(x['multiclass_brier'] for x in scenario_scores)/len(scenario_scores),4)
                                             if scenario_scores else None),
                    'note':'Uniform guessing over 3 scenarios scores 0.667 multiclass Brier; over 4, 0.75.'},'brier':self.brier(),'log_loss':logloss(rows),'naive_50_log_loss':(round(math.log(2),5) if rows else None),
                'naive_50_brier':naive_brier,'by_horizon':by_horizon,'overdue_unresolved':overdue,
                'skill_vs_naive_50':(round(1-actual_brier/naive_brier,5)
                                   if naive_brier and actual_brier is not None else None),
                'by_method':by_method, 'total_forecasts':count_total,
                'unresolved':count_total-len(rows), 'reliability_bins':bins,
                'warning':('Only manually resolved forecasts are scored; selection bias is possible. '
                           'Resolve every forecast past its deadline (YES or NO) so misses are not silently excluded.'
                           + (f' {overdue} forecast(s) are past deadline and unresolved.' if overdue else ''))}

    def export_json(self):
        return {'format':'news-oracle-ledger-v1','exported_at':utc_now(),
                'articles':self.articles(2000),'forecasts':self.forecasts(2000),
                'briefings':self.briefings(2000),'calibration':self.brier(),
                'audits':self.audits(2000),'schedules':self.schedules(),
                'event_claims':self.event_claims(1000),'reference_classes':self.reference_classes(),
                'frozen_packets':self.forecast_packets(2000),'outlooks':self.outlooks(2000),
                'score_report':self.score_report()}

    def close(self):
        self.db.close()
