"""Line an English reference page up on a Japanese target page.

Extracted component of the `read` module (see `backend/docs/modules/read.md`), in
the same spirit as `scraper.py`: pure OpenCV, no Storage, no database. The two
pages are the same art at different resolutions (the reference is typically ~1.84x
larger, sometimes offset by ~40 px), so a similarity transform (scale + rotation +
translation) fits; SIFT features survive the scale change and the lettering
differences, and RANSAC discards matches that landed on text or edited art.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .errors import TranslateRefusal

_MIN_GOOD_MATCHES = 8
_MIN_INLIERS = 100  # real pairs give 400-1200; the worst spike pair gave 426
_MAX_RESIDUAL_P90 = 2.5  # px in target space; real pairs give <= 1.1
_RANSAC_THRESHOLD = 2.0
_RATIO = 0.75  # Lowe's ratio test

_REFUSAL = "These pages don't line up closely enough to translate by reference."


@dataclass(frozen=True)
class Alignment:
    matrix: np.ndarray  # 2x3 float, maps reference pixels -> target pixels
    inliers: int
    residual_p90: float  # 90th-percentile inlier error, in target pixels


def align(reference_gray: np.ndarray, target_gray: np.ndarray) -> Alignment:
    """Estimate the reference -> target transform, or raise `TranslateRefusal`."""
    sift = cv2.SIFT_create(nfeatures=8000)
    kp_ref, des_ref = sift.detectAndCompute(reference_gray, None)
    kp_tgt, des_tgt = sift.detectAndCompute(target_gray, None)
    if des_ref is None or des_tgt is None or len(kp_ref) < 2 or len(kp_tgt) < 2:
        raise TranslateRefusal(_REFUSAL)

    good = []
    for pair in cv2.BFMatcher().knnMatch(des_ref, des_tgt, k=2):
        if len(pair) == 2 and pair[0].distance < _RATIO * pair[1].distance:
            good.append(pair[0])
    if len(good) < _MIN_GOOD_MATCHES:
        raise TranslateRefusal(_REFUSAL)

    src = np.float32([kp_ref[m.queryIdx].pt for m in good])
    dst = np.float32([kp_tgt[m.trainIdx].pt for m in good])
    matrix, mask = cv2.estimateAffinePartial2D(
        src, dst, method=cv2.RANSAC, ransacReprojThreshold=_RANSAC_THRESHOLD
    )
    if matrix is None or mask is None:
        raise TranslateRefusal(_REFUSAL)

    keep = mask.ravel().astype(bool)
    inliers = int(keep.sum())
    if inliers < _MIN_INLIERS:
        raise TranslateRefusal(_REFUSAL)

    projected = src[keep] @ matrix[:, :2].T + matrix[:, 2]
    residual_p90 = float(np.percentile(np.linalg.norm(projected - dst[keep], axis=1), 90))
    if residual_p90 > _MAX_RESIDUAL_P90:
        raise TranslateRefusal(_REFUSAL)

    return Alignment(matrix=matrix, inliers=inliers, residual_p90=residual_p90)
