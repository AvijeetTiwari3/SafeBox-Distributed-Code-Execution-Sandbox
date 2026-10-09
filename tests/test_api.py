"""
SafeBox Test Suite: REST API & Broker Endpoints
Validates API contracts, language endpoints, and telemetry schemas.
"""
import pytest
from starlette.testclient import TestClient
from safebox.app.main import app

client = TestClient(app)

def test_get_languages():
    response = client.get("/api/v1/languages")
    assert response.status_code == 200
    data = response.json()
    assert "python" in data
    assert "cpp" in data
    assert "javascript" in data

def test_api_execute_python_ac():
    payload = {
        "code": "print('API Execution Success')",
        "language": "python",
        "expected_output": "API Execution Success"
    }
    response = client.post("/api/v1/execute", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["verdict"] == "ACCEPTED"
    assert "API Execution Success" in res["stdout"]

def test_api_submit_async_job():
    payload = {
        "code": "print(42)",
        "language": "python"
    }
    response = client.post("/api/v1/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "QUEUED"

def test_get_pool_stats():
    response = client.get("/api/v1/pool/stats")
    assert response.status_code == 200
    data = response.json()
    assert "pool_capacities" in data

def test_get_prometheus_metrics():
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "safebox_executions_total" in response.text
