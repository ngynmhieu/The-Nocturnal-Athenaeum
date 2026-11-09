import math

import pytest

from backend.app.modules.read.translate import TranslateRefusal, align

from .conftest import gray, make_page


def test_aligns_scaled_shifted_reference(pair):
    target, reference, _ = pair
    a = align(gray(reference), gray(target))
    assert a.inliers >= 100 and a.residual_p90 <= 1.5
    scale = math.hypot(a.matrix[0, 0], a.matrix[1, 0])
    assert abs(scale - 1 / 1.84) < 0.01


def test_unrelated_reference_is_refused():
    with pytest.raises(TranslateRefusal) as e:
        align(gray(make_page(1, 1885, 1200, ["X"])), gray(make_page(2, 1024, 610, ["Y"])))
    assert e.value.message == "These pages don't line up closely enough to translate by reference."
