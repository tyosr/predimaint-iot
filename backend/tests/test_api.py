from .conftest import auth

def sample(**overrides):
    data = {"seq": 1, "temperature": 25, "humidity": 55, "vibration_rate": 0, "vibration_edges": 0, "current_rms": 0, "current_source": "simulated"}
    return data | overrides

def test_login_and_machine_requires_auth(client):
    assert client.get("/api/machines").status_code == 401
    assert client.post("/api/auth/login", json={"email":"technician@test.local", "password":"wrong"}).status_code == 401
    assert client.get("/api/machines", headers=auth(client, "technician")).status_code == 200

def test_telemetry_persists_and_creates_threshold_alert(client):
    assert client.post("/api/telemetry/test-machine", json=sample(temperature=75)).status_code == 401
    response = client.post("/api/telemetry/test-machine", headers=auth(client, "manager"), json=sample(temperature=75))
    assert response.status_code == 202
    h = auth(client, "technician")
    assert client.get("/api/machines/test-machine/telemetry", headers=h).json()[0]["temperature"] == 75
    alerts = client.get("/api/alerts", headers=h).json()
    assert alerts[0]["severity"] == "critical"

def test_director_cannot_acknowledge_alert(client):
    client.post("/api/telemetry/test-machine", headers=auth(client, "manager"), json=sample(temperature=80))
    h = auth(client, "director")
    alert_id = client.get("/api/alerts", headers=h).json()[0]["id"]
    assert client.post(f"/api/alerts/{alert_id}/acknowledge", headers=h).status_code == 403

def test_only_manager_can_update_thresholds(client):
    tech = auth(client, "technician"); manager = auth(client, "manager")
    path = "/api/thresholds/test-machine/temperature"
    assert client.put(path, headers=tech, json={"warning":55,"critical":75}).status_code == 403
    assert client.put(path, headers=manager, json={"warning":55,"critical":75}).status_code == 200

def test_invalid_reading_rejected(client):
    response = client.post("/api/telemetry/test-machine", headers=auth(client, "manager"), json=sample(humidity=140))
    assert response.status_code == 422

def test_normal_reading_closes_active_alert(client):
    manager = auth(client, "manager")
    client.post("/api/telemetry/test-machine", headers=manager, json=sample(temperature=75))
    client.post("/api/telemetry/test-machine", headers=manager, json=sample(seq=2, temperature=40))
    alerts = client.get("/api/alerts", headers=auth(client, "technician")).json()
    assert alerts[0]["status"] == "closed"

def test_manager_can_register_machine_and_sensor(client):
    manager = auth(client, "manager")
    technician = auth(client, "technician")
    machine = {"id": "pump-02", "name": "Pompe 02", "description": "Pompe de test"}
    assert client.post("/api/machines", headers=technician, json=machine).status_code == 403
    assert client.post("/api/machines", headers=manager, json=machine).status_code == 201
    assert client.post("/api/machines", headers=manager, json=machine).status_code == 409
    sensor = {"metric": "temperature", "sensor_type": "DHT22", "gpio": 27, "unit": "°C"}
    created = client.post("/api/machines/pump-02/sensors", headers=manager, json=sensor)
    assert created.status_code == 201
    assert created.json()["machine_id"] == "pump-02"
    assert client.get("/api/machines/pump-02/sensors", headers=auth(client, "director")).json()[0]["metric"] == "temperature"

def test_manager_can_update_and_toggle_sensor(client):
    manager = auth(client, "manager")
    created = client.post(
        "/api/machines/test-machine/sensors",
        headers=manager,
        json={"metric": "temperature", "sensor_type": "DHT22", "gpio": 27, "unit": "°C"},
    )
    assert created.status_code == 201
    sensor_id = created.json()["id"]
    assert client.patch(
        f"/api/sensors/{sensor_id}", headers=manager,
        json={"sensor_type": "DHT22-AM2302", "enabled": False},
    ).json()["enabled"] is False
    assert client.patch(
        f"/api/sensors/{sensor_id}", headers=manager,
        json={"enabled": True},
    ).json()["enabled"] is True
    assert client.patch(
        f"/api/sensors/{sensor_id}", headers=auth(client, "technician"),
        json={"enabled": False},
    ).status_code == 403

def test_sensor_metadata_rejects_unknown_fields(client):
    manager = auth(client, "manager")
    created = client.post(
        "/api/machines/test-machine/sensors",
        headers=manager,
        json={"metric": "humidity", "sensor_type": "DHT22", "gpio": 27, "unit": "%"},
    )
    response = client.patch(
        f"/api/sensors/{created.json()['id']}", headers=manager,
        json={"machine_id": "other-machine"},
    )
    assert response.status_code == 422

def test_manager_can_archive_without_deleting_history(client):
    manager = auth(client, "manager")
    response = client.delete("/api/machines/test-machine", headers=manager)
    assert response.status_code == 200
    assert response.json()["active"] is False
    assert client.get("/api/machines", headers=auth(client, "technician")).json() == []

def test_manager_threshold_requires_critical_above_warning(client):
    manager = auth(client, "manager")
    response = client.put("/api/thresholds/test-machine/temperature", headers=manager, json={"warning": 80, "critical": 70})
    assert response.status_code == 422

def test_unregistered_machine_cannot_ingest_measurements(client):
    response = client.post("/api/telemetry/unknown", headers=auth(client, "manager"), json=sample())
    assert response.status_code == 404
