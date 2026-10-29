"""The image must carry every module the app imports: a missing one boots a dead service (503) after a deploy."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_every_root_module_is_copied_into_the_image():
    copied = set(re.search(r"(?m)^COPY (app\.py .*?) \./$", (ROOT / "Dockerfile").read_text(encoding="utf-8")).group(1).split())
    modules = {p.name for p in ROOT.glob("*.py")}
    assert modules <= copied, sorted(modules - copied)
