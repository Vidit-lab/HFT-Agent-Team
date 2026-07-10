def test_run_cycle_is_an_honest_stub(client):
    response = client.post("/api/run-cycle")
    assert response.status_code == 501
    assert "Phase 4" in response.json()["detail"]
