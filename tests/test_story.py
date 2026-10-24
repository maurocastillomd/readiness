from generate_data import BRIEF_DAY, generate
from readiness.engine import assess_squad
from readiness.models import Reading, ReadinessDriver, Status


def _squad():
    rs = [Reading(**r) for r in generate()]
    return {a.name: a for a in assess_squad(rs, BRIEF_DAY)}


def test_story_statuses():
    s = _squad()
    assert len(s) == 9
    assert s["D. Silva"].status is Status.REVIEW
    assert s["A. Rivera"].status is Status.MONITOR
    assert s["R. Bennett"].status is Status.MONITOR
    assert sum(a.status is Status.CLEARED for a in s.values()) == 6


def test_story_drivers():
    s = _squad()
    assert set(s["D. Silva"].drivers) == {ReadinessDriver.NEUROMUSCULAR,
                                          ReadinessDriver.PERCEPTUAL}
    assert s["A. Rivera"].drivers == [ReadinessDriver.AUTONOMIC]
    assert s["R. Bennett"].drivers == [ReadinessDriver.NEUROMUSCULAR]
    assert s["D. Silva"].load.acwr is not None  # heavy week as context


def test_bennett_is_a_decline_trend():
    s = _squad()
    nm = next(d for d in s["R. Bennett"].domains
              if d.domain.value == "neuromuscular")
    assert nm.consecutive_declines >= 3
