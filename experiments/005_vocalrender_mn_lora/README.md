# Experiment 005: VocalRender-MN LoRA adaptation

Status: **blocked — prerequisites only**.

This directory is a planning placeholder. It contains no launchable training
configuration, hyperparameters, checkpoint path, or training command. No LoRA
training, preprocessing, checkpoint writing, or data acquisition is authorized
by Milestone 0.

Training may be designed only after all of the following are documented and
approved:

- licensed and consented native Mongolian singing data with score alignment;
- benchmark evidence covering high-risk Л/Г/Х/soft-sign contexts;
- a tokenizer/input strategy selected by controlled raw-text versus explicit-
  metadata experiments;
- train/validation splits that prevent singer and song leakage;
- a policy for filtering synthetic Music3 material using GREEN/YELLOW/RED
  evidence without treating synthetic output as native ground truth;
- an upstream regression/rehearsal strategy proving score control remains
  intact;
- resource and training-use manifest approvals;
- a GPU/storage budget, rollback plan, and measurable evaluation criteria.

Until then, pronunciation overrides remain sidecar research metadata and the
released VocalRender path remains the raw-lyric baseline. Any future run must
create a new schema-versioned record under the [experiment contract](../README.md)
and keep checkpoints and generated audio outside the repository.

