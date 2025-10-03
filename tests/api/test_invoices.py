from uuid import UUID

def create_customer(client):
    payload = {"name": "Alice", "email": "alice@example.com"}
    res = client.post("/customers", json=payload)
    assert res.status_code == 201
    return res.json()["id"]


def test_invoice_crud(client):
    # Prepare a customer
    cid = create_customer(client)

    # Create invoice
    payload = {"customer_id": cid, "amount": 123.45, "currency": "EUR", "description": "Dienstleistung"}
    res = client.post("/invoices", json=payload)
    assert res.status_code == 201
    inv = res.json()
    assert "id" in inv
    UUID(inv["id"])  # valid UUID
    assert inv["status"] == "open"

    iid = inv["id"]

    # Read invoice
    res = client.get(f"/invoices/{iid}")
    assert res.status_code == 200
    assert res.json()["amount"] == 123.45

    # Update invoice (change amount and status via query)
    payload_upd = {"customer_id": cid, "amount": 200.0, "currency": "EUR", "description": "Update"}
    res = client.put(f"/invoices/{iid}?status_value=paid", json=payload_upd)
    assert res.status_code == 200
    data = res.json()
    assert data["amount"] == 200.0
    assert data["status"] == "paid"

    # List invoices
    res = client.get("/invoices")
    assert res.status_code == 200
    assert any(i["id"] == iid for i in res.json())

    # Delete invoice
    res = client.delete(f"/invoices/{iid}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True

    # Not found after delete
    res = client.get(f"/invoices/{iid}")
    assert res.status_code == 404
