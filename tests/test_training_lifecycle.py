import numpy as np
import pytest
import torch

from vocalrender.preprocessing.svs_preprocessor import SVSPreprocessor
from vocalrender.training.config import load_svs_train_config
from vocalrender.training.resume import capture_local_runtime_state, restore_local_runtime_state
from vocalrender.training.runtime import require_finite
from vocalrender.training.provenance import ensure_run_manifest, update_run_status


def _minimal_config(train):
    return {
        "model": {"pretrained_path": "model"},
        "data": {"preprocessed_data_path": "data"},
        "train": train,
    }


def test_total_steps_is_canonical_and_legacy_aliases_must_agree():
    cfg = load_svs_train_config(_minimal_config({"total_steps": 4}))
    assert cfg.train.total_steps == cfg.train.num_iters == cfg.train.max_steps == 4

    legacy = load_svs_train_config(_minimal_config({"num_iters": 3, "max_steps": 3}))
    assert legacy.train.total_steps == 3

    with pytest.raises(ValueError, match="Conflicting legacy"):
        load_svs_train_config(_minimal_config({"num_iters": 3, "max_steps": 4}))
    with pytest.raises(ValueError, match="conflicts with legacy"):
        load_svs_train_config(_minimal_config({"total_steps": 4, "num_iters": 3}))


def test_nonfinite_values_fail_before_optimizer_step():
    require_finite("loss", torch.tensor(1.0))
    with pytest.raises(FloatingPointError, match="Non-finite loss"):
        require_finite("loss", torch.tensor(float("nan")))
    with pytest.raises(FloatingPointError, match="Non-finite gradient norm"):
        require_finite("gradient norm", float("inf"))


def test_numpy_rng_is_restored_with_runtime_state():
    class FakeAccelerator:
        rank = 0
        device = torch.device("cpu")

    accelerator = FakeAccelerator()
    np.random.seed(1234)
    state = capture_local_runtime_state(accelerator, data_epoch=2, batches_seen_in_epoch=3, samples_seen=4)
    expected = np.random.random(4)
    np.random.random(20)
    restore_local_runtime_state(state, accelerator)
    assert np.array_equal(np.random.random(4), expected)


def test_cuda_preprocessing_never_silently_falls_back(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA.*unavailable"):
        SVSPreprocessor("unused", device="cuda")


def test_run_provenance_is_immutable_but_horizon_can_extend(tmp_path):
    model = tmp_path / "model"
    data = tmp_path / "data"
    model.mkdir()
    data.mkdir()
    (model / "config.json").write_text('{"model":"tiny"}', encoding="utf-8")
    (data / "manifest.json").write_text('{"items":[]}', encoding="utf-8")

    raw = _minimal_config({"total_steps": 2})
    raw["model"]["pretrained_path"] = str(model)
    raw["data"]["preprocessed_data_path"] = str(data)
    first = ensure_run_manifest(tmp_path / "run", load_svs_train_config(raw), world_size=1)

    raw["train"]["total_steps"] = 4
    resumed = ensure_run_manifest(tmp_path / "run", load_svs_train_config(raw), world_size=1)
    assert resumed["run_id"] == first["run_id"]

    (data / "manifest.json").write_text('{"items":[1]}', encoding="utf-8")
    with pytest.raises(ValueError, match="provenance changed"):
        ensure_run_manifest(tmp_path / "run", load_svs_train_config(raw), world_size=1)

    update_run_status(tmp_path / "run", status="interrupted", step=2)
    assert '"status": "interrupted"' in (tmp_path / "run" / "run_status.json").read_text()
