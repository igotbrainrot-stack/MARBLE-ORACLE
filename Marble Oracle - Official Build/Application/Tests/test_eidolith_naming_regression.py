"""EIDOLITH 0.4 filename regression tests (no GUI, no FFmpeg required).

    python3 Application/Tests/test_eidolith_naming_regression.py

Covers the user-reported Mr. Robot rename defect plus comparable Sonarr/Plex
and scene-style patterns. Expected names keep show, year, SxxEyy and the
episode title recognisable; release tags are removed without leaving
dangling brackets, and in-word punctuation is not destroyed.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))
from oracle_eidolith_core import fit_resolution, output_name, parse_media_name, standard_stem  # noqa: E402

AV1 = 'Balanced archive (default)'
CASES = [
    # User report (EIDOLITH 0.3 produced 'Mr Robot (2015) - S01E01 - eps1 0 hellofriend mov ( [AV1].mkv')
    ('Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov (1080p BluRay x265 RCVR).mkv', AV1,
     'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov [AV1].mkv'),
    ('Mr. Robot (2015) - S02E01 - eps2.0_unm4sk-pt1.tc (1080p BluRay x265 RCVR).mkv', AV1,
     'Mr. Robot (2015) - S02E01 - eps2.0_unm4sk-pt1.tc [AV1].mkv'),
    ('The Expanse (2015) - S03E06 - Immolation (1080p AMZN WEB-DL x265 RCVR).mkv', 'Fast CPU H.264',
     'The Expanse (2015) - S03E06 - Immolation [H264].mp4'),
    ("Star Trek - The Next Generation - S03E15 - Yesterday's Enterprise.mkv", AV1,
     "Star Trek - The Next Generation - S03E15 - Yesterday's Enterprise [AV1].mkv"),
    ('Spider-Man - S01E01 - A Proper Remux.mkv', AV1, 'Spider-Man - S01E01 - A Proper Remux [AV1].mkv'),
    ('Show Name - S01E02 - Title 1080p WEB-DL.mkv', AV1, 'Show Name - S01E02 - Title [AV1].mkv'),
    ('[Group] Show - S01E03 - Ep [1080p].mkv', AV1, 'Show - S01E03 - Ep [AV1].mkv'),
    ('Dune Part Two (2024) (2160p BluRay).mkv', AV1, 'Dune Part Two (2024) [AV1].mkv'),
    ('Movie (Part 2) (1999).mkv', AV1, 'Movie (Part 2) (1999) [AV1].mkv'),
    # Scene style must keep working exactly as in 0.3.
    ('Mr.Robot.S01E02.eps1.1_ones-and-zer0es.mpeg.1080p.BluRay.x265.mkv', AV1,
     'Mr Robot - S01E02 - eps1 1 ones-and-zer0es mpeg [AV1].mkv'),
    ('The.Office.US.S02E03.Office.Olympics.1080p.WEB-DL.mkv', AV1,
     'The Office US - S02E03 - Office Olympics [AV1].mkv'),
    ('Severance - 1x04 - The You You Are.mp4', 'NVIDIA HEVC (fast)', 'Severance - S01E04 - The You You Are [HEVC].mkv'),
    ('Dune.Part.Two.2024.2160p.BluRay.x265.mkv', 'NVIDIA AV1 (fast)', 'Dune Part Two (2024) [AV1].mkv'),
    ('my_home_movie.mp4', 'Fast CPU H.264', 'my_home_movie [H264].mp4'),
]


def main():
    failures = []
    for source, profile, expected in CASES:
        got = output_name(source, profile)
        if got != expected:
            failures.append(f'{source!r}\n   expected {expected!r}\n   got      {got!r}')
    info = parse_media_name('Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov (1080p BluRay x265 RCVR).mkv')
    assert (info['kind'], info['season'], info['episode']) == ('TV', 1, 1), info
    assert info['episode_title'] == 'eps1.0_hellofriend.mov', info
    # Never fabricate an episode number, and Keep source name is verbatim.
    assert standard_stem('mystery.mkv', 'TV episode') == 'mystery'
    src = 'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov (1080p BluRay x265 RCVR).mkv'
    assert standard_stem(src, 'Keep source name') == Path(src).stem
    # Results are always filesystem-safe on Windows.
    for source, profile, _ in CASES:
        name = output_name(source, profile)
        assert not any(ch in name for ch in '<>:"/\\|?*'), name
        assert name.count('(') == name.count(')') and name.count('[') == name.count(']'), name
    # Resolution: fit inside the box, keep aspect, even sizes, never upscale.
    fits = {(1920, 1080): (1280, 720), (1920, 804): (1280, 536), (3840, 2160): (1280, 720),
            (1080, 1920): (720, 1280), (1440, 1080): (960, 720), (1918, 1080): (1278, 720),
            (1280, 720): None, (720, 576): None, (320, 180): None}
    for (w, h), want in fits.items():
        got = fit_resolution(w, h, '720p')
        if got != want:
            failures.append(f'fit_resolution({w}x{h}, 720p) expected {want}, got {got}')
    assert fit_resolution(3840, 2160, '1080p') == (1920, 1080)
    assert fit_resolution(1920, 1080, 'Original') is None and fit_resolution(None, 1080, '720p') is None
    assert output_name(src, 'Faster CPU AV1', resolution='720p') == \
        'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov [AV1 720p].mkv'
    assert output_name(src, 'Fast AV1 (preset 8)') == 'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov [AV1].mkv'
    assert output_name(src, 'Lossless remux', resolution='720p').endswith('[Remux].mkv')
    # Short form (the panel's default): no episode title, no format tag.
    short = dict(episode_title=False, format_tag=False)
    assert output_name(src, 'Fast AV1 (preset 8)', resolution='720p', **short) == 'Mr. Robot (2015) - S01E01.mkv'
    assert output_name('Dune.Part.Two.2024.2160p.BluRay.x265.mkv', 'Fast CPU H.264', **short) == 'Dune Part Two (2024).mp4'
    assert output_name('my_home_movie.mp4', 'Fast CPU H.264', **short) == 'my_home_movie.mp4'
    assert output_name(src, 'Faster CPU AV1', episode_title=False) == 'Mr. Robot (2015) - S01E01 [AV1].mkv'
    assert output_name(src, 'Faster CPU AV1', format_tag=False) == 'Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov.mkv'
    # Audit fixes: numbers inside a title are not the release year; an empty
    # show title is taken from the folder or the source name is kept.
    audit = {'2001 A Space Odyssey (1968).mkv': '2001 A Space Odyssey (1968).mkv',
             'Blade Runner 2049 (2017).mkv': 'Blade Runner 2049 (2017).mkv',
             '1917 (2019).mkv': '1917 (2019).mkv',
             'Blade.Runner.2049.2017.1080p.BluRay.mkv': 'Blade Runner 2049 (2017).mkv',
             'Show S2024E05.mkv': 'Show S2024E05.mkv', '2012.mkv': '2012.mkv',
             'S01E01.mkv': 'S01E01.mkv',
             '/tv/Mr. Robot (2015)/Season 1/S01E01.mkv': 'Mr. Robot (2015) - S01E01.mkv',
             '/tv/Mr. Robot/1x02.mkv': 'Mr. Robot - S01E02.mkv',
             '/home/me/Downloads/S01E01.mkv': 'S01E01.mkv',
             '/tv/Season 1/S01E01.mkv': 'S01E01.mkv'}
    for source, expected in audit.items():
        got = output_name(source, 'Fast AV1 (preset 8)', **short)
        if got != expected:
            failures.append(f'{source!r}\n   expected {expected!r}\n   got      {got!r}')
    from oracle_eidolith_core import DEFAULT_PROFILE, PROFILE_ORDER, PROFILES
    assert DEFAULT_PROFILE == 'Fast AV1 (preset 8)' and 'Balanced archive' in PROFILE_ORDER
    assert 'Balanced archive (default)' not in PROFILE_ORDER
    assert PROFILES['Balanced archive (default)'] is PROFILES['Balanced archive']   # saved 0.3 settings still load
    if failures:
        raise SystemExit('NAMING FAILURES:\n' + '\n'.join(failures))
    print(f'EIDOLITH naming regression: {len(CASES)} cases + parser/safety/resolution checks PASSED')


if __name__ == '__main__':
    main()
