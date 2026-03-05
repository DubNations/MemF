from pathlib import Path

from cognitive_os.experiments.generate_datasets import SCENARIOS, generate


def test_dataset_generation_sizes(tmp_path: Path):
    out = tmp_path / "data"
    generate(out)
    files = list(out.glob("*.jsonl"))
    assert len(files) == 9
    for f in files:
        name = f.stem
        lines = [x for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(lines) == SCENARIOS[name]["size"]
