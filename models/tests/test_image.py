import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from models.app.main import create_app
from models.app.modules.image.config import load_configs
from models.app.modules.image.manager import UpscalerManager, verify_weights
from models.app.modules.image.network import SRVGGNetCompact

SHA = "b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d"


def test_network_upscales_4x():
    net = SRVGGNetCompact(num_feat=8, num_conv=2, upscale=4)
    out = net(torch.zeros(1, 3, 10, 12))
    assert out.shape == (1, 3, 40, 48)


def test_config_loads_shipped_json():
    cfgs = load_configs()
    cfg = cfgs["realesr-animevideov3"]
    assert cfg.net_scale == 4 and cfg.output_scale == 2 and cfg.device == "cpu" and cfg.default
    assert cfg.sha256 == SHA


def test_manager_output_is_double_size_bgr():
    m = UpscalerManager(load_configs())
    m._nets["realesr-animevideov3"] = SRVGGNetCompact(num_feat=8, num_conv=2, upscale=4).eval()  # skip download
    out = m.upscale(None, np.full((30, 20, 3), 200, np.uint8))
    assert out.shape == (60, 40, 3) and out.dtype == np.uint8


def test_bad_sha256_refuses_weights(tmp_path):
    bad = tmp_path / "w.pth"
    bad.write_bytes(b"not weights")
    with pytest.raises(ValueError, match="sha256"):
        verify_weights(bad, SHA)


def test_upscale_endpoint_rejects_non_image():
    client = TestClient(create_app())
    r = client.post("/v1/images/upscale", content=b"hello", headers={"Content-Type": "image/png"})
    assert r.status_code == 400 and r.json()["detail"] == "Not a readable image."


def test_weights_failure_surfaces_as_503(monkeypatch):
    from models.app.modules.image import manager as mgr
    from models.app.modules.image.manager import ModelUnavailableError, manager

    def boom(*a, **k):
        raise ModelUnavailableError("Could not obtain weights")
    monkeypatch.setattr(manager, "upscale", boom)
    import cv2
    ok, png = cv2.imencode(".png", np.zeros((4, 4, 3), np.uint8))
    r = TestClient(create_app()).post("/v1/images/upscale", content=png.tobytes(),
                                      headers={"Content-Type": "image/png"})
    assert r.status_code == 503 and "weights" in r.json()["detail"]


def test_download_sha_mismatch_is_not_a_client_error(tmp_path, monkeypatch):
    from models.app.modules.image import manager as mgr
    monkeypatch.setattr(mgr, "cache_dir", lambda: tmp_path)

    class FakeResp:
        def raise_for_status(self): pass
        def iter_bytes(self): return iter([b"junk"])
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr(mgr.httpx, "stream", lambda *a, **k: FakeResp())
    m = UpscalerManager(load_configs())
    with pytest.raises(mgr.ModelUnavailableError, match="sha256"):
        m.upscale(None, np.zeros((4, 4, 3), np.uint8))
