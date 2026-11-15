"""The one place the suite's release number is written.

Workspaces keep their own component versions (EIDOLITH's engine, the embedded
Oggcultist); this is the version of the Marble Oracle release as a whole, shown
in the window title, printed by --version and stamped into the build manifest.
"""
SUITE_NAME = 'Marble Oracle'
SUITE_VERSION = '0.4.9.4'
RELEASE_DATE = '2026-11-16'
RELEASE_TITLE = 'Backup data sources: Stooq key, more stock and crypto feeds, rune stones at small sizes'


def suite_title() -> str:
    return f'{SUITE_NAME} {SUITE_VERSION}'
