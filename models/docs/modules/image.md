# `image` Module — Technical Reference

The `image` module runs image-to-image models. Today that is one model: the
**Real-ESRGAN anime-video v3 upscaler** (`SRVGGNetCompact`), used by the reader's
"Upscale" action. It sits next to `llm` as a sibling module (a module is a model
type). For the service architecture see [`models_guideline.md`](../models_guideline.md).

---

## File map

```
modules/image/
├── config.py        UpscalerConfig + load_configs() (reads models/*.json)
├── network.py       SRVGGNetCompact — the PyTorch net (layout matches upstream)
├── manager.py       lazy weight download + sha256 check + inference (UpscalerManager)
├── service.py       bytes in / PNG bytes out (ImageService)
├── router.py        POST /v1/images/upscale (thin)
├── dependencies.py  get_image_service
└── models/
    └── realesr-animevideov3.json
```

---

## Model JSON

| Field | Meaning |
|---|---|
| `id` | id clients may send as `?model=` |
| `weights_url` | where the `.pth` is downloaded from on first use |
| `sha256` | pinned digest; the file is verified **before** `torch.load(weights_only=True)` |
| `net_scale` | scale the net natively produces (`4`) |
| `output_scale` | scale returned (`2`); the x4 output is resized with `cv2.INTER_AREA` |
| `num_feat` / `num_conv` | net width / depth (`64` / `16`) |
| `device` | `"cpu"` (see below) |
| `tile` | tile edge in px; `0` = whole image in one pass |
| `description` | human text |
| `default` | `true` on the model used when `?model=` is omitted |

## Weights

Downloaded with `httpx` on first request (not at startup) to
`%LOCALAPPDATA%/nocturnal-models/image/{id}.pth` (fallback
`~/.cache/nocturnal-models/image/`). A cached file that fails the sha256 check is
re-downloaded; a download that fails it is discarded and raises.

## Why x4 net, x2 output

Running the x4 net and shrinking with `INTER_AREA` gives cleaner line art than a
native x2 net, and keeps one set of weights for any `output_scale`.

## CPU, and how to switch

The LLM owns the GPU, and `torch` from PyPI is CPU-only on Windows, so the
upscaler runs on CPU: ~2.5 s for a 609x1024 page. To use a GPU, install a CUDA
build of `torch` and set `"device": "cuda"` in the JSON — no code change. If VRAM
is tight, set `tile` (e.g. `256`) to bound memory.

## API

### `POST /v1/images/upscale[?model=<id>]`

- Request: body = raw image bytes, any `Content-Type: image/*`.
- `200` — `image/png`, exactly `2*width` x `2*height`.
- `400` — `{"detail": "Not a readable image."}` (or unknown model id).

Inference runs under one lock, so concurrent requests queue.
