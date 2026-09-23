from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from aquawatch.api import create_app


@pytest.fixture
def client(engine):
    with TestClient(create_app(engine)) as client:
        client.headers["X-AquaWatch-Token"] = client.get("/api/session").json()["token"]
        yield client


def test_dashboard_and_static_assets(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    data = client.get("/api/overview").json()
    assert data["meters"] == 120
    assert data["readings"] == 10796
    assert data["active_cases"] == 27
    assert data["review_amount_cents"] == 25500
    assert len(data["daily"]) == 90


def test_filter_and_search(client):
    rows = client.get("/api/cases?kind=billing_mismatch&status=open").json()
    assert len(rows) == 6
    assert len(client.get("/api/cases?q=M-0001").json()) == 1
    assert client.get("/api/cases?q=does-not-exist").json() == []


def test_invoice_volume_review_is_explainable_and_conservative(client):
    rows = client.get("/api/billing/reconciliation").json()
    assert len(rows) == 120
    assert {
        status: sum(r["status"] == status for r in rows)
        for status in {"matched", "mismatch", "incomplete", "counter_reset"}
    } == {"matched": 110, "mismatch": 2, "incomplete": 4, "counter_reset": 4}
    mismatch = next(r for r in rows if r["meter_id"] == "M-0029")
    assert mismatch["signed_volume_difference_liters"] == 12000
    assert mismatch["case_id"]
    detail = client.get(f"/api/cases/{mismatch['case_id']}").json()
    assert detail["kind"] == "volume_mismatch"
    assert detail["amount_cents"] == 0
    assert next(r for r in rows if r["meter_id"] == "M-0007")["measured_volume_liters"] is None


def test_state_history_replay_and_conflict(client):
    item = client.get("/api/cases").json()[0]
    url = f"/api/cases/{item['id']}"
    payload = dict(
        status="investigating", note="Checking the tariff applied to this invoice.", version=1
    )
    assert client.patch(url, json=payload).status_code == 200
    assert client.patch(url, json=payload).status_code == 409
    assert client.post("/api/import/demo").status_code == 200
    detail = client.get(url).json()
    assert detail["status"] == "investigating" and len(detail["history"]) == 1
    assert (
        client.patch(
            url,
            json=dict(
                status="resolved", note="Synthetic discrepancy verified against tariff.", version=2
            ),
        ).status_code
        == 200
    )
    assert len(client.get(url).json()["history"]) == 2


def test_concurrent_case_updates_have_one_winner(client):
    item = client.get("/api/cases").json()[0]
    url = f"/api/cases/{item['id']}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: (
                    client.patch(
                        url,
                        json=dict(
                            status="investigating", note="Parallel operator update", version=1
                        ),
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(results) == [200, 409]
    assert len(client.get(url).json()["history"]) == 1


def test_invalid_transition_blank_note_and_missing_case(client):
    item = client.get("/api/cases").json()[0]
    url = f"/api/cases/{item['id']}"
    assert (
        client.patch(
            url, json=dict(status="resolved", note="Skipping investigation", version=1)
        ).status_code
        == 422
    )
    assert (
        client.patch(url, json=dict(status="investigating", note="     ", version=1)).status_code
        == 422
    )
    assert client.get("/api/cases/does-not-exist").status_code == 404


def test_request_security(client):
    assert (
        client.post("/api/import/demo", headers={"X-AquaWatch-Token": "incorrect"}).status_code
        == 403
    )
    assert client.get("/api/session", headers={"Host": "attacker.example"}).status_code == 400
    assert client.get("/").headers["X-Content-Type-Options"] == "nosniff"


def test_non_ascii_write_token_is_rejected_without_mutation(client):
    before = client.get("/api/runs").json()
    response = client.post("/api/import/demo", headers={b"X-AquaWatch-Token": b"\xff"})
    assert response.status_code == 403
    assert client.get("/api/runs").json() == before


def test_upload_failure_ledger_and_replay(client):
    bad = client.post(
        "/api/import?as_of=2026-08-30",
        files={"file": ("bad.csv", b"wrong,header\n1,2\n", "text/csv")},
    )
    assert bad.status_code == 422
    assert client.get("/api/runs").json()[0]["status"] == "failed"
    sample = client.get("/api/sample.csv").content
    first = client.post(
        "/api/import?as_of=2026-08-30", files={"file": ("daily.csv", sample, "text/csv")}
    )
    second = client.post(
        "/api/import?as_of=2026-08-30", files={"file": ("daily.csv", sample, "text/csv")}
    )
    assert first.status_code == 200 and first.json()["accepted"] == 120
    assert second.json()["replayed"]
    assert (
        client.post(
            "/api/import?as_of=2026-08-01", files={"file": ("daily.csv", sample, "text/csv")}
        ).status_code
        == 422
    )


def test_csv_export_and_benchmark(client):
    response = client.get("/api/export/cases.csv")
    assert response.status_code == 200 and "attachment" in response.headers["Content-Disposition"]
    assert len(response.text.splitlines()) == 28
    result = client.get("/api/evaluation").json()
    assert result["false_negatives"] == 4 and result["true_positives"] == 27
