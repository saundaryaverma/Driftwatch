import pytest

from driftwatch.suite import Case


def make_case(**kw):
    defaults = {"id": "c1", "prompt": "hi", "checks": [{"contains_any": ["hello"]}]}
    return Case(**{**defaults, **kw})


@pytest.fixture
def case():
    return make_case


class FakeClock:
    """Each call advances time by the next step, so latency is deterministic."""

    def __init__(self, step_seconds):
        self.t = 0.0
        self.step = step_seconds

    def __call__(self):
        self.t += self.step
        return self.t
