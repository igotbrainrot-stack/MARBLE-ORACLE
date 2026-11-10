"""Opt-in, rate-limited MusicBrainz release-group matching (no audio upload)."""
from __future__ import annotations
import json
import re
import time
import threading
from urllib.error import HTTPError
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib import parse, request
from .. import __version__
from ..metadata import Track, year_of


class MetadataLookupError(Exception): pass


def artist_credit(credit: list) -> str:
    return ''.join(item if isinstance(item,str) else (item.get('name', item.get('artist',{}).get('name','')) + item.get('joinphrase',''))
                   for item in credit).strip()


def simplified(s: str) -> str:
    return re.sub(r'[^\w]+', '', s.casefold())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, simplified(a), simplified(b)).ratio()


class MusicBrainz:
    # Shared limiter: separate GUI and CLI instances cannot exceed API cadence.
    _request_lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, contact_email: str):
        contact_email = contact_email.strip()
        if '@' not in contact_email:
            raise MetadataLookupError('Enter a contact email in Settings before using MusicBrainz.')
        self.user_agent = f'Oggcultist/{__version__} (mailto:{contact_email})'
        self.last_request = 0.0

    def search(self, album: str, albumartist: str) -> list[dict]:
        if not album.strip() or not albumartist.strip():
            raise MetadataLookupError('Album and album artist are required for a reliable search.')
        # Escape literal backslashes and quotes in MusicBrainz/Lucene phrases.
        clean_album = album.replace('\\', '\\\\').replace('"', '\\"')
        clean_artist = albumartist.replace('\\', '\\\\').replace('"', '\\"')
        query = f'releasegroup:"{clean_album}" AND artist:"{clean_artist}"'
        url = 'https://musicbrainz.org/ws/2/release-group/?' + parse.urlencode({'query': query, 'fmt': 'json', 'limit': 6})
        req = request.Request(url, headers={'User-Agent':self.user_agent, 'Accept':'application/json'})
        try:
            with MusicBrainz._request_lock:
                for attempt in range(4):
                    gap = time.monotonic() - MusicBrainz._last_request
                    if gap < 1.2: time.sleep(1.2 - gap)
                    MusicBrainz._last_request = time.monotonic()
                    try:
                        with request.urlopen(req, timeout=12) as response:
                            data = json.load(response)
                        break
                    except HTTPError as exc:
                        if exc.code not in (429, 503) or attempt >= 3:
                            raise
                        retry_header = exc.headers.get('Retry-After') if exc.headers else None
                        delay = min(30.0, 2.0 * (2 ** attempt))
                        if retry_header:
                            try:
                                delay = min(30.0, max(0.0, float(retry_header)))
                            except (ValueError, TypeError):
                                try:
                                    date = parsedate_to_datetime(retry_header)
                                    if date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
                                    delay = min(30.0, max(0.0, (date - datetime.now(timezone.utc)).total_seconds()))
                                except (TypeError, ValueError, OverflowError):
                                    pass
                        time.sleep(delay)
        except Exception as exc:
            raise MetadataLookupError('MusicBrainz lookup failed: ' + str(exc)) from exc
        results = []
        for item in data.get('release-groups',[]):
            name = artist_credit(item.get('artist-credit',[]))
            album_sim, artist_sim = similarity(item.get('title',''),album),similarity(name,albumartist)
            score = int(item.get('score',0) or 0)
            # Strict: both names must be nearly exact, rather than trusting fuzzy server rank.
            reliable = album_sim >= 0.97 and artist_sim >= 0.94 and score >= 90
            results.append({
                'id': item.get('id',''), 'album':item.get('title',''), 'albumartist':name,
                'originaldate':item.get('first-release-date',''),
                'year':year_of(item.get('first-release-date','')),
                'releasetype':item.get('primary-type',''),
                'secondary_types':item.get('secondary-types',[]),
                'compilation': name.casefold() == 'various artists',
                'score':score, 'reliable':reliable,
                'match':round(100*(album_sim + artist_sim)/2),
            })
        return results

    @staticmethod
    def confident(candidates: list[dict]) -> dict | None:
        if not candidates or not candidates[0]['reliable'] or not candidates[0]['year']:
            return None
        best = candidates[0]
        # Alternative candidates can be different edits or similarly named albums.
        for other in candidates[1:]:
            if other['match'] >= 94 and best['score'] - other['score'] < 8:
                return None
        return best

    @staticmethod
    def auto_lookup_safe(group: list[Track]) -> bool:
        """Never replace identifiers inferred from actual MusicBrainz tagging."""
        # Provisional folders made from YouTube suffixes are not official albums.
        # Never auto-apply a release-group match to them.
        if any(t.filename_inferred for t in group):
            return False
        ids = {t.releasegroup_id.casefold() for t in group if t.releasegroup_id}
        releases = {t.release_id.casefold() for t in group if t.release_id}
        if len(ids) > 1 or len(releases) > 1:
            for t in group:
                t.lookup_issue = 'Conflicting MusicBrainz IDs in this album — manual review required'
            return False
        return not (ids or releases)

    @staticmethod
    def apply(track: Track, result: dict) -> None:
        track.album = result['album']
        track.albumartist = result['albumartist']
        track.originaldate = result['originaldate']
        track.year = result['year']
        track.releasegroup_id = result['id']
        track.release_type = result['releasetype']
        track.compilation = result['compilation']
        track.set_tag('album', track.album)
        track.set_tag('albumartist', track.albumartist)
        track.set_tag('originaldate', track.originaldate)
        track.set_tag('musicbrainz_releasegroupid', track.releasegroup_id)
        if track.release_type: track.set_tag('releasetype', track.release_type)
        track.set_tag('compilation','1' if track.compilation else '0')
