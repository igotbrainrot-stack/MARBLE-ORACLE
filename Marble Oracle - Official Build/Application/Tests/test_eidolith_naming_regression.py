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
from oracle_eidolith_core import output_name, parse_media_name, standard_stem  # noqa: E402

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
    if failures:
        raise SystemExit('NAMING FAILURES:\n' + '\n'.join(failures))
    print(f'EIDOLITH naming regression: {len(CASES)} cases + parser/safety checks PASSED')


if __name__ == '__main__':
    main()
