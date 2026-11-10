"""Read source metadata across the common Mutagen-supported audio containers."""
from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import mutagen

EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4', '.opus', '.ogg', '.oga', '.wav', '.wave', '.aif', '.aiff', '.aac', '.wma', '.ape', '.wv'}

# Standard, human-readable text tags copied through to Opus/Vorbis comments.
ALIASES = {
    'album artist': 'albumartist', 'album_artist': 'albumartist',
    'albumartists': 'albumartist', 'albumartist': 'albumartist',
    'date': 'date', 'year': 'date', 'releasedate': 'date',
    'originalyear': 'originalyear', 'originaldate': 'originaldate',
    'track': 'tracknumber', 'tracknumber': 'tracknumber',
    'disc': 'discnumber', 'disk': 'discnumber', 'discnumber': 'discnumber',
    'totaltracks': 'totaltracks', 'tracktotal': 'totaltracks',
    'disctotal': 'totaldiscs', 'totaldiscs': 'totaldiscs',
    'musicbrainz_albumid': 'musicbrainz_albumid',
    'musicbrainz_album_id': 'musicbrainz_albumid',
    'musicbrainz_releasegroupid': 'musicbrainz_releasegroupid',
    'musicbrainz_release_group_id': 'musicbrainz_releasegroupid',
    'musicbrainz_album_artist_id': 'musicbrainz_albumartistid',
    'musicbrainz_release_track_id': 'musicbrainz_trackid',
    'musicbrainz_albumartistid': 'musicbrainz_albumartistid',
    'musicbrainz_recordingid': 'musicbrainz_recordingid',
    'musicbrainz_trackid': 'musicbrainz_trackid',
    'releasetype': 'releasetype', 'compilation': 'compilation',
    'musicbrainz_album_type': 'releasetype',
    'musicbrainz_album_status': 'releasestatus',
    'musicbrainz_artist_id': 'musicbrainz_artistid',
    'wm/albumtitle': 'album', 'author': 'artist', 'wm/albumartist': 'albumartist',
    'wm/year': 'date', 'wm/tracknumber': 'tracknumber', 'wm/partofset': 'discnumber',
    'wm/originalreleaseyear': 'originaldate', 'wm/originalreleasedate': 'originaldate',
    'wm/musicbrainz/album_id': 'musicbrainz_albumid',
    'wm/musicbrainz/release_group_id': 'musicbrainz_releasegroupid',

}

# The known MP4 names are atom keys, not the names in Mutagen EasyMP4.
MP4_TAGS = {
    '\xa9nam':'title', '\xa9alb':'album', '\xa9ART':'artist', 'aART':'albumartist',
    '\xa9day':'date', '\xa9gen':'genre', '\xa9cmt':'comment', '\xa9wrt':'composer',
    'trkn':'tracknumber', 'disk':'discnumber', 'cpil':'compilation',
}
ID3_TAGS = {
    'TIT2':'title', 'TALB':'album', 'TPE1':'artist', 'TPE2':'albumartist',
    'TDRC':'date', 'TYER':'date', 'TDOR':'originaldate', 'TORY':'originaldate',
    'TRCK':'tracknumber', 'TPOS':'discnumber', 'TCON':'genre', 'TCOM':'composer',
    'TSRC':'isrc', 'TBPM':'bpm',
}


def normalize_key(key: str) -> str:
    key = str(key).strip().lower().replace('-', '_').replace(' ', '_')
    return ALIASES.get(key, key)


def string_values(value: Any) -> list[str]:
    """Decode containers' multi-value tags without embedding NUL in Vorbis text."""
    if value is None: return []
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and all(isinstance(i, int) for i in value):
            return [str(value[0]) + ('/' + str(value[1]) if value[1] else '')]
        out: list[str] = []
        for item in value: out.extend(string_values(item))
        return out
    # APETextValue exposes .value, but str(value) is what contains NUL-separated
    # entries. Handle it BEFORE generic attribute wrappers (e.g. ASF).
    if type(value).__name__ == 'APETextValue':
        return string_values(str(value))
    if isinstance(value, bytes):
        try: return string_values(value.decode('utf-8'))
        except UnicodeError: return []
    if isinstance(value, (int, float, str)):
        return [s for part in str(value).split('\x00') if (s := part.strip())]
    if hasattr(value, 'value'):
        return string_values(value.value)
    return []


def valid_text_values(values: list[str]) -> list[str]:
    return [v for v in values if len(v) <= 16000 and
            not any(ord(c) < 32 and c not in '\t\n' for c in v)]


def text_tag(tags: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        arr = tags.get(normalize_key(key), [])
        if arr and arr[0].strip(): return arr[0].strip()
    return ''


def year_of(value: str) -> str:
    m = re.match(r'^(1[0-9]{3}|20[0-9]{2}|21[0-9]{2})(?:\D|$)', value.strip())
    return m.group(1) if m else ''


def parse_num(value: str, default: int = 0) -> int:
    m = re.match(r'^(\d+)', str(value).strip())
    return int(m.group(1)) if m else default


def is_compilation(tags: dict[str, list[str]]) -> bool:
    value = text_tag(tags, 'compilation').lower()
    # Featured artists do NOT turn an album into a compilation.
    return value in ('1', 'yes', 'true') or text_tag(tags, 'albumartist').casefold() == 'various artists'


def read_audio(path: Path) -> tuple[dict[str, list[str]], float, str, int]:
    """Return tags, duration, codec guess and average bitrate. Missing metadata stays missing."""
    raw = mutagen.File(path, easy=False)
    if raw is None or getattr(raw, 'info', None) is None:
        raise ValueError('Unrecognised or damaged audio file')
    info = raw.info
    tags: dict[str, list[str]] = {}
    raw_tags = getattr(raw, 'tags', None)
    if raw_tags:
        for key, value in raw_tags.items():
            strkey = str(key)
            k = normalize_key(strkey)
            if k in {'metadata_block_picture', 'coverart', 'coverartmime'} or k.startswith('apic'):
                continue
            if strkey in MP4_TAGS:
                k = MP4_TAGS[strkey]
            elif strkey in ID3_TAGS:
                k = ID3_TAGS[strkey]
            elif len(strkey) >= 4 and re.fullmatch(r'[A-Z][A-Z0-9]{3}(?::.*)?', strkey) and not strkey.startswith('TXXX:'):
                # Use the supported ID3 map + EasyID3; do not leak raw frame IDs.
                continue
            elif strkey.startswith('TXXX:'):
                k = normalize_key(strkey[5:])
            elif strkey.startswith('----:com.apple.iTunes:'):
                k = normalize_key(strkey.split(':', 2)[-1].replace(' ', '_'))
            if k in ('trkn', 'disk'):
                k = 'tracknumber' if k == 'trkn' else 'discnumber'
            if hasattr(value, 'text'):
                vals = string_values(value.text)
            else:
                vals = string_values(value)
            # Avoid storing opaque or binary tag data as text.
            vals = valid_text_values(vals)
            if vals and k:
                tags.setdefault(k, []).extend(vals)
    # Easy Mutagen adds aliases, notably ID3 MusicBrainz TXXX names.
    try:
        easy = mutagen.File(path, easy=True)
        if easy is not None and getattr(easy, 'tags', None):
            for key, value in easy.tags.items():
                k = normalize_key(str(key))
                vals = valid_text_values(string_values(value))
                if vals and k and not tags.get(k): tags[k] = vals
    except (Exception,):
        pass
    for key in list(tags):
        tags[key] = list(dict.fromkeys(tags[key]))
    dur = float(getattr(info, 'length', 0) or 0)
    bitrate = int(getattr(info, 'bitrate', 0) or 0)
    codec = type(raw).__name__.lower()
    return tags, dur, codec, bitrate


# Treat specific remix/edit suffixes as evidence of *remixer credit*, not proof
# of the original performer, official album or release date. This enables local
# conversion of untagged YouTube MP3 exports without a speculative web match.
_FILENAME_REMIX = re.compile(
    r"^(?P<song>.+)\s+(?:-\s*(?P<dash>[\w][^\[\]()]*?)|"
    r"\((?P<round>[\w][^()]*)\)|\[(?P<square>[\w][^\[\]]*)\])$",
    re.UNICODE,
)
_NOISE_SUFFIX = re.compile(
    r"\s*[\[(](?:official\s+(?:music\s+)?(?:audio|video)|lyrics?\s*(?:video)?|"
    r"hq|hd|audio|320\s?kbps|youtube)[\]) ]*\s*$", re.I
)
_CREDIT_END = re.compile(r"^(?P<name>.+?)\s+(?P<kind>remix|edit|bootleg|rework)$", re.I)
_GENERIC_CREDITS = {'original', 'official', 'unknown', 'extended', 'radio', 'club', 'new', 'full', 'best'}

def filename_remix_credit(stem: str) -> tuple[str, str] | None:
    """Return (remixer, full cleaned title) for an explicit final remix credit."""
    name = stem.strip()
    while True:
        trimmed = _NOISE_SUFFIX.sub('', name).strip()
        if trimmed == name: break
        name = trimmed
    match = _FILENAME_REMIX.match(name)
    if not match: return None
    credit = (match.group('dash') or match.group('round') or match.group('square') or '').strip()
    tag = _CREDIT_END.fullmatch(credit)
    if not tag: return None
    remixer = re.sub(r'\s+', ' ', tag.group('name')).strip(' -_.')
    if (not remixer or len(remixer) > 70 or len(match.group('song')) < 2 or
            remixer.casefold() in _GENERIC_CREDITS or
            not any(c.isalpha() for c in remixer)):
        return None
    return remixer, name



@dataclass
class Track:
    source: Path
    size: int
    tags: dict[str, list[str]] = field(default_factory=dict)
    duration: float = 0.0
    codec: str = ''
    bitrate: int = 0
    title: str = ''
    unverified_title: bool = False
    artist: str = ''
    albumartist: str = ''
    album: str = ''
    year: str = ''
    date: str = ''
    originaldate: str = ''
    track: int = 0
    disc: int = 0
    disc_total: int = 0
    track_total: int = 0
    release_id: str = ''
    releasegroup_id: str = ''
    release_type: str = ''
    compilation: bool = False
    issues: list[str] = field(default_factory=list)
    note: str = ''
    lookup_issue: str = ''
    duplicate_group: str = ''
    target: Path | None = None
    status: str = 'Review'
    edited: bool = False
    inferred_track: bool = False
    cover_key: str = ''
    filename_inferred: bool = False
    filename_inference_note: str = ''

    @classmethod
    def from_path(cls, path: Path) -> 'Track':
        tags, dur, codec, bitrate = read_audio(path)
        originaldate = text_tag(tags, 'originaldate', 'originalyear')
        date = text_tag(tags, 'date')
        track = cls(
            source=path, size=path.stat().st_size, tags=tags, duration=dur,
            codec=codec, bitrate=bitrate,
            title=text_tag(tags,'title'), artist=text_tag(tags,'artist'),
            albumartist=text_tag(tags,'albumartist'), album=text_tag(tags,'album'),
            year=year_of(originaldate) or year_of(date), date=date,
            originaldate=originaldate,
            track=parse_num(text_tag(tags,'tracknumber')),
            disc=parse_num(text_tag(tags,'discnumber'),1),
            disc_total=parse_num(text_tag(tags,'totaldiscs')) or parse_num(text_tag(tags,'discnumber').partition('/')[2]),
            track_total=parse_num(text_tag(tags,'totaltracks')) or parse_num(text_tag(tags,'tracknumber').partition('/')[2]),
            release_id=text_tag(tags,'musicbrainz_albumid'),
            releasegroup_id=text_tag(tags,'musicbrainz_releasegroupid'),
            release_type=text_tag(tags,'releasetype'),
            compilation=is_compilation(tags),
        )
        if not track.title:
            track.title = path.stem
            track.unverified_title = True
        # Never override real tags, even partial ones. A final "Agartha Remix"
        # credit is strong enough to make a clearly labelled local collection,
        # but it does not establish the original artist or release year.
        if not any(text_tag(tags, k) for k in
                   ('title', 'artist', 'albumartist', 'album', 'date',
                    'originaldate', 'originalyear', 'tracknumber')):
            inferred = filename_remix_credit(path.stem)
            if inferred:
                remixer, cleaned_title = inferred
                track.title = cleaned_title
                track.unverified_title = False
                track.albumartist = remixer
                track.album = f'{remixer} Remixes'
                track.release_type = 'remix collection'
                track.filename_inferred = True
                track.filename_inference_note = (
                    f'Filename suffix indicates remixer {remixer}; original artist, '
                    'album and release year remain unknown. Track order is provisional. '
                    'Edit metadata to correct.')
                track.tags['remixer'] = [remixer]
                track.tags['oggcultist_metadata_source'] = ['filename_remix_suffix']
        return track

    def set_tag(self, key: str, value: str) -> None:
        key = normalize_key(key)
        if value: self.tags[key] = [value]
        else: self.tags.pop(key, None)
        if key == 'title' and value: self.unverified_title = False
        if key == 'tracknumber': self.inferred_track = False
        self.edited = True

    def album_key(self) -> str:
        """Key for cover reuse. Release MBID wins; isolate colliding, untagged albums by source folder."""
        if self.cover_key:
            return self.cover_key
        if self.release_id:
            return 'release:' + self.release_id.casefold()
        base = '|'.join([self.albumartist.casefold(), self.album.casefold(), self.year, self.release_type.casefold()])
        # Covers of same artist/album/year across independent source folders remain consistent.
        return 'album:' + base

    def album_group(self) -> tuple[str, str]:
        # Treat CD1 / CD 2 / Disc 03 source directories as one album.
        parent = self.source.parent
        if re.fullmatch(r'(?:cd|disc|disk)\s*0*\d+', parent.name, re.I):
            parent = parent.parent
        return (str(parent.resolve()).casefold(), self.album.casefold())
