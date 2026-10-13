"""pytest 公共夹具。"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEMO_RULESET = ROOT / "data" / "samples" / "ruleset-pipl-audit-demo.json"
DEMO_CARD = ROOT / "data" / "samples" / "card-demo.json"
AUTHORITATIVE_RULESET = ROOT / "data" / "rules" / "ruleset-pipl-audit-2025.json"


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture
def demo_ruleset():
    from paudit.rules.loader import load_ruleset

    return load_ruleset(str(DEMO_RULESET))


@pytest.fixture
def demo_card():
    return json.loads(DEMO_CARD.read_text(encoding="utf-8"))
