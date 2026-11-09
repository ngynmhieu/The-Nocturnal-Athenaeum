"""Dev-only: run translate-by-reference on two local image files.

    python -m backend.scripts.try_translate <target> <reference> <out>

For eyeballing results on real pages locally. Never commit the images.
"""
from __future__ import annotations

import sys

import cv2

from backend.app.modules.read.translate import TranslateRefusal, translate_by_reference


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    target_path, reference_path, out_path = argv
    target, reference = cv2.imread(target_path), cv2.imread(reference_path)
    if target is None or reference is None:
        print("Could not read one of the input images.")
        return 2
    try:
        out = translate_by_reference(target, reference)
    except TranslateRefusal as refusal:
        print(f"Refused: {refusal.message}")
        return 1
    cv2.imwrite(out_path, out)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
