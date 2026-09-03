"""Contract for the frame-pacing director (SPEC.md P1-P4)."""

from itertools import pairwise

from fuddy_duddy.director import MIN_GAP_FRAMES, Director
from fuddy_duddy.event import Phase, SyscallEvent


def ev(name: str) -> SyscallEvent:
    return SyscallEvent(1, name, Phase.ENTER)


def drain(director: Director, frames: int = 400) -> list[str]:
    names: list[str] = []
    for frame in range(frames):
        names.extend(event.name for event in director.poll(frame))
    return names


def test_empty_director_releases_nothing():  # P4
    director = Director()
    assert director.poll(0) == []
    assert director.poll(100) == []


def test_all_fed_events_released_in_order():  # P1
    director = Director()
    names = ["a", "b", "c", "d", "e"]
    for name in names:
        director.feed(ev(name))
    assert drain(director) == names


def test_at_most_one_release_per_frame():  # P2
    director = Director()
    for name in "abcde":
        director.feed(ev(name))
    assert all(len(director.poll(frame)) <= 1 for frame in range(400))


def test_releases_are_paced():  # P2
    director = Director()
    for name in "abcde":
        director.feed(ev(name))
    released_on = [frame for frame in range(400) if director.poll(frame)]
    gaps = [b - a for a, b in pairwise(released_on)]
    assert gaps, "nothing released"
    assert all(gap >= MIN_GAP_FRAMES for gap in gaps)
