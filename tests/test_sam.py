"""Cover-before-read: boxes come back from SAM, code clips and filters them, nothing is stored or kept."""
import base64

import pytest

import app as app_module
import muse
import sam

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales", "reports_to": "md", "headcount": 2}]
# what the real endpoint returned for a black rectangle on a white page (mask payload shortened)
REAL = "<0f>0<|box;x1=40;y1=30;x2=119;y2=69;w=200;h=100;c=0.9064327478408813|><|mask;x=0;y=0;c=0.9;data=40,80,~!!!3b|>"


def test_a_real_looking_reply_gives_its_box_and_ignores_the_mask():
    assert sam.parse_regions(REAL) == [
        {"x1": 40, "y1": 30, "x2": 119, "y2": 69, "w": 200, "h": 100, "confidence": 0.91}]


def test_no_text_means_no_matches_not_an_error():
    assert sam.parse_regions("") == [] and sam.parse_regions(None) == []


def test_boxes_are_clipped_filtered_and_capped():
    many = "".join(f"<|box;x1=1;y1=1;x2=9;y2=9;w=10;h=10;c=0.{n}|>" for n in range(1, 10)) * 5
    got = sam.parse_regions(many)
    assert len(got) == sam.MAX_REGIONS and all(r["confidence"] >= sam.MIN_CONFIDENCE for r in got)
    assert got[0]["confidence"] >= got[-1]["confidence"]
    assert sam.parse_regions("<|box;x1=5;y1=5;x2=50;y2=50;w=20;h=20|>")[0]["x2"] == 19  # clipped to the page
    assert sam.parse_regions("<|box;x1=9;y1=9;x2=3;y2=3;w=20;h=20|>") == []  # upside down


@pytest.fixture
def client():
    return app_module.create_app().test_client()


@pytest.fixture
def token(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    client.post("/api/assistants", json={"role_id": "sales"}, headers=h)
    return client.post("/api/invites", json={"role_id": "sales"}, headers=h).json["token"]


def counts(client):
    db = client.application.config["STORE"]
    return {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}


def test_regions_come_back_and_nothing_is_stored(client, token, monkeypatch):
    seen = []
    monkeypatch.setattr(muse, "segment", lambda phrase, image, **k: seen.append((phrase, image)) or {
        "demo_mode": False, "demo_reason": None, "text": REAL})
    before = counts(client)
    r = client.post("/api/photo/regions", json={"token": token, "image": PNG, "phrase": " signature "})
    assert r.status_code == 200 and r.json["regions"][0]["x1"] == 40 and r.json["demo_mode"] is False
    assert seen == [("signature", PNG)] and counts(client) == before


@pytest.mark.parametrize("phrase", [None, "  ", "x" * (sam.MAX_PHRASE + 1)])
def test_a_missing_or_long_phrase_is_refused_before_any_model_call(client, token, monkeypatch, phrase):
    monkeypatch.setattr(muse, "segment", lambda *a, **k: pytest.fail("must not be called"))
    r = client.post("/api/photo/regions", json={"token": token, "image": PNG, "phrase": phrase})
    assert r.status_code == 400


def test_a_bad_image_is_refused_before_any_model_call(client, token, monkeypatch):
    monkeypatch.setattr(muse, "segment", lambda *a, **k: pytest.fail("must not be called"))
    r = client.post("/api/photo/regions", json={"token": token, "image": "data:image/gif;base64,R0lGODlh", "phrase": "stamp"})
    assert r.status_code == 400


def test_without_a_model_the_answer_is_labelled_and_empty(client, token):
    r = client.post("/api/photo/regions", json={"token": token, "image": PNG, "phrase": "signature"})
    assert r.json["demo_mode"] is True and r.json["regions"] == []


def test_the_request_asks_meta_not_to_keep_a_copy(monkeypatch):
    sent = []

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"output": [{"content": [{"type": "output_text", "text": "<|box;x1=1;y1=1;x2=5;y2=5;w=9;h=9|>"}]}]}'

    monkeypatch.delenv("FAKE_AI", raising=False)
    monkeypatch.setenv("META_API_KEY", "test")
    monkeypatch.setattr(muse.urllib.request, "urlopen", lambda req, timeout: sent.append(req) or Reply())
    out = muse.segment("signature", PNG)
    assert out["demo_mode"] is False and "<|box;" in out["text"]
    assert b'"store": false' in sent[0].data and sent[0].full_url == muse.RESPONSES_URL
