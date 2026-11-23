"""OVERCAST headless tooling. Run python -m overcast.cli --help."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .engine import NewsOracleEngine, CONTEXT_PROFILES, DEFAULT_CONTEXT_PROFILE
from .lmstudio import DEFAULT_URL, DEFAULT_TIMEOUT, LMStudioClient


def main(argv=None):
    parser=argparse.ArgumentParser(description='OVERCAST — local, pessimism-first news forecasting (Marble Oracle compatible)')
    parser.add_argument('--state-dir',type=Path,help='Override state location; do not put it in the install directory')
    parser.add_argument('--api-url',default=DEFAULT_URL,help='Local LM Studio endpoint (default http://127.0.0.1:1234/v1)')
    parser.add_argument('--context',choices=list(CONTEXT_PROFILES),default=DEFAULT_CONTEXT_PROFILE,
                        help='Context length the model is loaded with in LM Studio; sizes evidence packets (default 16K)')
    parser.add_argument('--timeout',type=int,default=DEFAULT_TIMEOUT,
                        help=f'Seconds to wait for each local model call (default {DEFAULT_TIMEOUT})')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('models',help='List local LM Studio models')
    ev=sub.add_parser('events',help='Cluster locally cached headlines into event candidates')
    ev.add_argument('--days',type=int,default=14)
    pr=sub.add_parser('preview',help='Inspect source evidence BEFORE local model analysis')
    pr.add_argument('ids',nargs='+',type=int)
    pr.add_argument('--no-expand',action='store_true')
    sub.add_parser('fetch',help='Fetch no-login RSS feeds')
    a=sub.add_parser('articles',help='Show recent cached headlines')
    a.add_argument('--query',default='')
    b=sub.add_parser('brief',help='Brief selected article IDs')
    b.add_argument('ids',nargs='+',type=int); b.add_argument('--model',required=True)
    f=sub.add_parser('forecast',help='Forecast an outcome from cached article IDs')
    f.add_argument('ids',nargs='+',type=int)
    f.add_argument('--model',required=True); f.add_argument('--days',type=int,choices=[7,30,90,180,365],default=90)
    fm=sub.add_parser('multi',help='Multi-source forecast with optional claim-gap research and timing')
    fm.add_argument('ids',nargs='+',type=int)
    fm.add_argument('--model',required=True)
    fm.add_argument('--days',type=int,choices=[7,30,90,180,365],default=90)
    fm.add_argument('--no-expand',action='store_true')
    fm.add_argument('--gap-search',action='store_true',help='Optional bounded cached search for information gaps (one more LM call)')
    fm.add_argument('--timing',action='store_true',help='Optional local-model conditional event-timing buckets (one more LM call)')
    fm.add_argument('--base-id',type=int,help='Use saved, source-identified historical reference class (20+ observations)')
    fm.add_argument('--no-investigation',action='store_true',help='Skip extra local risk/incentives/links investigation pass')
    fm.add_argument('--models',nargs='+',help='Optional pool of 1-3 local model IDs, round-robin across the three lenses')
    fm.add_argument('--base-rate',type=float,default=None,help='User-verified historical base-rate probability (e.g. 0.25)')
    fm.add_argument('--base-rate-source',default='',help='Required reference when --base-rate supplied')
    fm.add_argument('--as-of',default='',help='Historical UTC ISO timestamp; first-seen must also predate it')
    fm.add_argument('--runs',type=int,default=3,choices=[1,2,3,4,5],help='Probability passes (>=3; extra runs cycle the lenses)')
    ol=sub.add_parser('outlook',help='BROAD OUTLOOK: scenarios, stress index and scorable signposts for a scope')
    ol.add_argument('scope',help='e.g. "GLOBAL EVENTS", "GLOBAL MARKETS", "TRADE & SUPPLY CHAINS", "CUSTOM SUBJECT"')
    ol.add_argument('--model',required=True); ol.add_argument('--query',default='',help='Subject for CUSTOM SUBJECT')
    ol.add_argument('--days',type=int,choices=[7,30,90,180,365],default=90)
    ol.add_argument('--runs',type=int,default=3,choices=[1,2,3,4,5],help='Independent ensemble runs (default 3)')
    sub.add_parser('outlooks',help='List broad outlooks')
    os_=sub.add_parser('outlook-show',help='Show one broad outlook with signposts and outcomes'); os_.add_argument('id',type=int)
    orz=sub.add_parser('outlook-resolve',help='Record which scenario happened (after the horizon ends)')
    orz.add_argument('id',type=int); orz.add_argument('scenario',choices=list('ABCD'))
    orz.add_argument('--evidence-url',required=True); orz.add_argument('--note',default='')
    sub.add_parser('forecasts',help='Show forecast ledger')
    sub.add_parser('claims',help='List extracted, source-anchored event CLAIMS (not verified facts)')
    sub.add_parser('relationships',help='List tentative shared-actor research links')
    ex=sub.add_parser('extract-events',help='Extract claims from selected cached articles using local LM Studio')
    ex.add_argument('ids',nargs='+',type=int);ex.add_argument('--model',required=True)
    fp=sub.add_parser('frozen-packet',help='Read exact SHA256-checked source excerpt snapshot for a forecast')
    fp.add_argument('id',type=int)
    sub.add_parser('base-rates',help='List user-entered historical reference classes and their sample sizes')
    ar=sub.add_parser('base-rate-add',help='Record verified historical yes/total observations for a reference class')
    ar.add_argument('label');ar.add_argument('--focus',required=True,choices=['WORLD POLITICS','MARKETS','TRADE','CRISES','OTHER'])
    ar.add_argument('--total',type=int,required=True);ar.add_argument('--yes',type=int,required=True)
    ar.add_argument('--period-start',required=True);ar.add_argument('--period-end',required=True)
    ar.add_argument('--source-url',required=True);ar.add_argument('--notes',default='')
    au=sub.add_parser('audit',help='View source and three-lens reasoning audit')
    au.add_argument('id',type=int)
    sub.add_parser('score-report',help='Brier and reliability-bucket diagnostics (resolved only)')
    sub.add_parser('calendar',help='Calendar: model-estimated event windows vs deadlines and manually sourced dates')
    add=sub.add_parser('schedule-add',help='Manually record a dated announcement and its supporting HTTPS URL')
    add.add_argument('title');add.add_argument('start_date');add.add_argument('end_date')
    add.add_argument('--source-url',required=True);add.add_argument('--source-note',default='')
    ics=sub.add_parser('calendar-export',help='Export all calendar dates and windows to an ICS file')
    ics.add_argument('path',type=Path)
    r=sub.add_parser('resolve',help='Record a verified yes/no result (one time)')
    r.add_argument('id',type=int); r.add_argument('outcome',type=int,choices=[0,1]); r.add_argument('--evidence-url',required=True)
    r.add_argument('--note',default='')
    sub.add_parser('score',help='Brier score of manually resolved forecasts')
    x=sub.add_parser('export',help='Save entire local ledger as JSON')
    x.add_argument('path',type=Path)
    args=parser.parse_args(argv)
    if args.timeout<10:
        parser.error('--timeout must be at least 10 seconds')
    engine=NewsOracleEngine(state_dir=args.state_dir,api_url=args.api_url,context_profile=args.context,
                            model_client=LMStudioClient(args.api_url,timeout=args.timeout))
    try:
        if args.command=='models': result=engine.models()
        elif args.command=='events': result=engine.events(days=args.days)
        elif args.command=='preview': result=engine.research_preview(args.ids,expand=not args.no_expand)
        elif args.command=='fetch': result=engine.refresh()
        elif args.command=='articles': result=engine.articles(query=args.query)
        elif args.command=='brief': result=engine.briefing(args.ids,args.model)
        elif args.command=='forecast': result=engine.forecast(args.ids,args.model,args.days)
        elif args.command=='multi':
            as_of=None
            if args.as_of:
                as_of=datetime.fromisoformat(args.as_of.replace('Z','+00:00'))
                if as_of.tzinfo is None:raise ValueError('--as-of must include a timezone offset, e.g. +00:00')
            def progress(step,total,label):
                print(f'[{step}/{total}] {label}…',file=sys.stderr,flush=True)
            result=engine.forecast_multi(args.ids,args.model,args.days,expand=not args.no_expand,
                baseline=args.base_rate,baseline_source=args.base_rate_source,as_of=as_of,
                model_ids=args.models,investigate=not args.no_investigation,
                gap_search=args.gap_search,timing=args.timing,reference_class_id=args.base_id,
                progress=progress,runs=args.runs)
        elif args.command=='outlook':
            coverage=engine.coverage(args.scope,query=args.query)
            def progress(step,total,label):
                print(f'[{step}/{total}] {label}…',file=sys.stderr,flush=True)
            result=engine.broad_outlook(coverage['article_ids'],args.model,scope=args.scope,query=args.query,
                                        horizon_days=args.days,runs=args.runs,coverage=coverage,progress=progress)
        elif args.command=='outlooks':
            result=[{k:o[k] for k in ('id','created','scope','horizon_days','deadline','stress_index',
                     'strategic_question','resolved_scenario')} for o in engine.outlooks()]
        elif args.command=='outlook-show': result=engine.outlook_detail(args.id)
        elif args.command=='outlook-resolve':
            engine.resolve_outlook(args.id,args.scenario,args.evidence_url,args.note)
            result={'resolved_outlook':args.id,'scenario':args.scenario}
        elif args.command=='forecasts': result=engine.forecasts()
        elif args.command=='claims': result=engine.event_claims()
        elif args.command=='relationships': result=engine.relationship_leads()
        elif args.command=='extract-events': result=engine.extract_events(args.ids,args.model)
        elif args.command=='frozen-packet': result=engine.forecast_packet(args.id)
        elif args.command=='base-rates': result=engine.reference_classes()
        elif args.command=='base-rate-add':
            result={'created_id':engine.add_reference_class(args.label,args.focus,args.total,args.yes,
                   args.period_start,args.period_end,args.source_url,args.notes)}
        elif args.command=='audit': result=engine.forecast_audit(args.id)
        elif args.command=='calendar': result=engine.calendar_items()
        elif args.command=='schedule-add':
            result={'created_id':engine.add_scheduled_event(args.title,args.start_date,args.end_date,
                       args.source_url,args.source_note)}
        elif args.command=='calendar-export':
            path=args.path.expanduser()
            path.write_text(engine.calendar_ics(),encoding='utf-8',newline='')
            result={'written_to':str(path)}
        elif args.command=='score-report': result=engine.score_report()
        elif args.command=='resolve':
            engine.resolve(args.id,args.outcome,args.evidence_url,args.note)
            result={'resolved':args.id,'outcome':args.outcome}
        elif args.command=='score': result=engine.performance()
        else:
            path=args.path.expanduser()
            path.write_text(json.dumps(engine.export_json(),indent=2,ensure_ascii=False),encoding='utf-8')
            result={'written_to':str(path)}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1,f'ERROR: {exc}\n')
    finally:
        engine.close()


if __name__=='__main__':
    raise SystemExit(main())
