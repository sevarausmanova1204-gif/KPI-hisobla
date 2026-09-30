import json

from kpi.config import Settings
from kpi.dashboard import build_data, render
from kpi.demo import AS_OF, demo_dataset


def test_demo_matches_spec_totals():
    data = build_data(demo_dataset(), Settings(), AS_OF, sample=True)
    totals = {r["name"]: r["total"] for r in data["salary"]}
    assert totals["Aziza"] == 4_820_000
    assert totals["Zuhra"] == 4_280_000
    assert totals["Muxsima"] == 4_160_000
    assert totals["Ruxshona"] == 4_160_000
    assert totals["Javohir"] == 3_920_000
    assert totals["Ruxsora"] == 2_900_000
    assert totals["Mashhura"] == 1_615_385
    assert totals["Behzod"] == 1_923_077
    assert data["meta"]["missing"] == ["Ruxsora"]


def test_render_embeds_json():
    data = build_data(demo_dataset(), Settings(), AS_OF, sample=True)
    html = render(data)
    assert "/*__DATA__*/null" not in html
    start = html.index("const DATA = ") + len("const DATA = ")
    end = html.index(";\n", start)
    assert json.loads(html[start:end])["meta"]["asOf"] == "17.09.2026"
