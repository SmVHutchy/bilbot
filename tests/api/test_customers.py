from uuid import UUID

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_customer_crud(client):
    # Create
    payload = {"name": "Max Mustermann", "email": "max@example.com", "address": "Musterstraße 1"}
    res = client.post("/customers", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert "id" in created
    UUID(created["id"])  # valid UUID hex
    assert created["name"] == payload["name"]

    cid = created["id"]

    # Read
    res = client.get(f"/customers/{cid}")
    assert res.status_code == 200
    assert res.json()["email"] == payload["email"]

    # Update
    upd = {"name": "Maxi Mustermann", "email": "maxi@example.com", "address": "Neue Straße 2"}
    res = client.put(f"/customers/{cid}", json=upd)
    assert res.status_code == 200
    assert res.json()["name"] == "Maxi Mustermann"

    # List
    res = client.get("/customers")
    assert res.status_code == 200
    assert any(c["id"] == cid for c in res.json())

    # Delete
    res = client.delete(f"/customers/{cid}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True

    # Not found after delete
    res = client.get(f"/customers/{cid}")
    assert res.status_code == 404
