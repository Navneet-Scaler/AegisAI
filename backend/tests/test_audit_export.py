"""CSV export of the audit trail: who, what, when, the decision, and the
reasoning, the shape SOC 2 / ISO 27001 audit evidence typically expects."""

import csv
import io

from fastapi.testclient import TestClient

from aegis.main import app


def test_export_is_public_like_the_rest_of_the_read_surface():
    with TestClient(app) as client:
        response = client.get("/calls/export.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")


def test_export_route_does_not_get_shadowed_by_the_call_id_route():
    """/calls/export.csv must resolve to the export route, not be swallowed
    by GET /calls/{call_id} treating 'export.csv' as an id and 404ing."""
    with TestClient(app) as client:
        response = client.get("/calls/export.csv")
        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")


def test_export_contains_one_row_per_call_with_the_audit_columns():
    with TestClient(app) as client:
        client.post("/agent/run", json={"request": "Refund ticket TCK-4417.", "scenario": "refund"})

        response = client.get("/calls/export.csv")
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        assert len(rows) >= 3
        required_columns = {
            "call_id",
            "created_at",
            "agent_name",
            "tool_name",
            "verdict",
            "composite_score",
            "matched_rules",
            "judge_reasoning",
            "decided_by",
            "executed",
        }
        assert required_columns <= set(reader.fieldnames or [])


def test_export_can_be_filtered_by_verdict():
    with TestClient(app) as client:
        client.post("/agent/run", json={"request": "Refund ticket TCK-4417.", "scenario": "refund"})

        response = client.get("/calls/export.csv", params={"verdict": "allow"})
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        assert len(rows) >= 1
        assert all(row["verdict"] == "allow" for row in rows)


def test_export_can_be_filtered_by_tool_name():
    with TestClient(app) as client:
        client.post("/agent/run", json={"request": "Refund ticket TCK-4417.", "scenario": "refund"})

        response = client.get("/calls/export.csv", params={"tool_name": "create_refund"})
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        assert len(rows) >= 1
        assert all(row["tool_name"] == "create_refund" for row in rows)


def test_export_is_never_mutated_by_filtering_the_underlying_data():
    """A filtered export still reflects real, persisted rows, not a
    recomputation: filtering narrows which rows are included, it does not
    change what any row says."""
    with TestClient(app) as client:
        client.post("/agent/run", json={"request": "Refund ticket TCK-4417.", "scenario": "refund"})

        unfiltered = list(csv.DictReader(io.StringIO(client.get("/calls/export.csv").text)))
        filtered = list(
            csv.DictReader(
                io.StringIO(
                    client.get("/calls/export.csv", params={"tool_name": "create_refund"}).text
                )
            )
        )

        filtered_row = filtered[0]
        matching_unfiltered = next(r for r in unfiltered if r["call_id"] == filtered_row["call_id"])
        assert filtered_row == matching_unfiltered
