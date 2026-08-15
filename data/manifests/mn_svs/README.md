# MN-SVS corpus manifests

`corpus.yaml` is intentionally empty until an operator records external
consent, licensing, and training/derivative-model approval for score-aligned
native Standard Khalkha singing. The validator fails closed: `unknown`,
missing, expired, revoked, or conflicting evidence is excluded.

Use repository-relative POSIX paths and opaque consent references. Do not add
audio, names, contact details, contract text, or private storage URLs. Keep a
final split output frozen; create a new split version when eligible metadata or
grouping changes.

```powershell
python scripts/mn/validate_training_corpus.py data/manifests/mn_svs/corpus.yaml
python scripts/mn/split_training_corpus.py --manifest data/manifests/mn_svs/corpus.yaml --output data/manifests/mn_svs/splits.yaml
```

The checked-in empty template is expected to report zero eligible items until
the missing external corpus and rights records are supplied.
