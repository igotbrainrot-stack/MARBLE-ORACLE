"""v1.7.4: shuffle, repeat (all / album / one) and click-to-seek."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from oggcultist.player import REPEAT_MODES, PlayOrder, Song


def song(name, album='Album', artist='Artist', track=0):
    return Song(Path(f'/music/{artist}/{album}/{name}.opus'), name, artist, album, track=track, duration=100)


@pytest.fixture
def queue():
    a = [song(f'a{i}', 'Alpha', track=i) for i in range(1, 4)]
    b = [song(f'b{i}', 'Beta', track=i) for i in range(1, 4)]
    return a + b


def titles(songs):
    return [s.title if s else None for s in songs]


# ------------------------------------------------------------------ repeat
def test_repeat_off_plays_in_order_then_stops(queue):
    order = PlayOrder()
    order.load(queue, 4)
    assert titles([order.next(manual=False), order.next(manual=False)]) == ['b3', None]
    assert order.current.title == 'b3'


def test_repeat_all_wraps_to_start(queue):
    order = PlayOrder()
    order.set_repeat('all')
    order.load(queue, 5)
    assert order.next(manual=False).title == 'a1'


def test_repeat_one_replays_on_end_and_next_restarts_it(queue):
    order = PlayOrder()
    order.set_repeat('one')
    order.load(queue, 1)
    assert order.next(manual=False).title == 'a2'
    assert order.next(manual=False).title == 'a2'
    assert order.next(manual=True).title == 'a2'       # v1.8.2: Next goes back to the start, never on
    order.load(queue, 5)
    assert order.next(manual=True).title == 'a2'       # still locked on a2 (locked when first played)


def test_repeat_album_loops_the_current_songs_album(queue):
    order = PlayOrder()
    order.set_repeat('album')
    order.load(queue, 1)          # a2
    assert titles([order.next(False), order.next(False), order.next(False)]) == ['a3', 'a1', 'a2']


def test_repeat_album_uses_full_album_from_library_even_from_a_playlist(queue):
    library = {('artist', 'alpha'): queue[:3], ('artist', 'beta'): queue[3:]}
    order = PlayOrder(album_lookup=lambda s: library[(s.artist.casefold(), s.album.casefold())])
    order.set_repeat('album')
    order.load([queue[4]], 0)     # a playlist holding only b2
    assert titles([order.next(False), order.next(False), order.next(False)]) == ['b3', 'b1', 'b2']


def test_cycle_repeat_goes_through_all_modes():
    order = PlayOrder()
    assert [order.cycle_repeat() for _ in REPEAT_MODES] == ['all', 'album', 'one', 'off']
    with pytest.raises(ValueError):
        order.set_repeat('sometimes')


# ------------------------------------------------------------------ shuffle
def test_shuffle_plays_every_song_once_before_stopping(queue):
    order = PlayOrder(rng=random.Random(4))
    order.set_shuffle(True)
    order.load(queue, 2)
    heard = [order.current.title]
    while (nxt := order.next(manual=False)) is not None:
        heard.append(nxt.title)
    assert sorted(heard) == sorted(titles(queue)) and len(heard) == len(queue)


def test_shuffle_repeat_all_reshuffles_without_immediate_repeat(queue):
    order = PlayOrder(rng=random.Random(9))
    order.set_shuffle(True)
    order.set_repeat('all')
    order.load(queue, 0)
    heard = [order.current.title] + [order.next(manual=False).title for _ in range(23)]
    for start in range(0, 24, 6):
        assert sorted(heard[start:start + 6]) == sorted(titles(queue))    # each pass covers everything
    assert all(x != y for x, y in zip(heard, heard[1:]))                 # never the same song twice in a row


def test_shuffle_with_repeat_album_stays_in_album(queue):
    order = PlayOrder(rng=random.Random(1))
    order.set_shuffle(True)
    order.set_repeat('album')
    order.load(queue, 3)          # b1
    heard = {order.next(manual=False).title for _ in range(12)}
    assert heard == {'b1', 'b2', 'b3'}


def test_previous_follows_what_was_actually_played(queue):
    order = PlayOrder(rng=random.Random(3))
    order.set_shuffle(True)
    order.load(queue, 0)
    played = [order.current] + [order.next(manual=True) for _ in range(3)]
    back = [order.previous() for _ in range(3)]
    assert titles(back) == titles(played[2::-1])


def test_previous_at_start_without_history_restarts_or_wraps(queue):
    order = PlayOrder()
    order.load(queue, 0)
    assert order.previous().title == 'a1'
    order.set_repeat('all')
    assert order.previous().title == 'b3'


# ------------------------------------------------------------------ v1.8.1: loops lock onto what was playing
def test_repeat_one_locks_onto_the_song_playing_when_switched_on(queue):
    order = PlayOrder()
    order.load(queue, 1)                       # a2 playing
    order.set_repeat('one')
    assert order.next(manual=True).title == "a2"           # Next only restarts it (v1.8.2)...
    assert order.next(manual=False).title == 'a2'          # ...but when a song ends, a2 comes back
    assert order.next(manual=False).title == 'a2'
    order.load(queue, 4)                       # the user starts b2 from another page
    assert order.next(manual=False).title == 'a2'


def test_repeat_one_switched_on_with_nothing_playing_locks_onto_first_song(queue):
    order = PlayOrder()
    order.set_repeat('one')
    assert order.loop_song is None
    order.load(queue, 3)
    assert order.loop_song.title == 'b1'
    assert order.next(manual=False).title == 'b1'


def test_repeat_album_locks_onto_the_album_playing_when_switched_on(queue):
    order = PlayOrder()
    order.load(queue, 1)                       # Alpha
    order.set_repeat('album')
    assert order.locked_album == 'Alpha'
    order.load(queue, 4)                       # the user plays a Beta song
    assert order.next(manual=False).title == 'a1'          # back to the locked album
    assert titles([order.next(False), order.next(False), order.next(False)]) == ['a2', 'a3', 'a1']


def test_changing_repeat_mode_releases_the_lock(queue):
    order = PlayOrder()
    order.load(queue, 0)
    order.set_repeat('one')
    order.set_repeat('all', anchor=queue[3])
    assert order.loop_song is None and order.loop_album is None
    order.set_repeat('album', anchor=queue[3])
    assert order.locked_album == 'Beta'


# ------------------------------------------------------------------ v1.8.2: Loop One holds; Loop Album follows the selection
def test_loop_one_next_and_previous_only_restart_the_locked_song(queue):
    order = PlayOrder()
    order.load(queue, 1)                       # a2
    order.set_repeat('one')
    assert order.next(manual=True).title == 'a2'
    assert order.next(manual=True).title == 'a2'
    assert order.previous().title == 'a2'
    assert order.next(manual=False).title == 'a2'
    order.set_repeat('off')
    assert order.next(manual=True).title == 'a3'           # released: moves on again


def test_loop_album_can_lock_onto_a_selected_song_from_another_album(queue):
    order = PlayOrder()
    order.load(queue, 0)                       # a1 playing
    order.set_repeat('album', anchor=queue[4])  # but b2 was selected last
    assert order.locked_album == 'Beta'
    assert titles([order.next(False), order.next(False), order.next(False), order.next(False)]) == ['b1', 'b2', 'b3', 'b1']
