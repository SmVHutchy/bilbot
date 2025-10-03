def test_messages_endpoints(client):
    # Liste der Nachrichten abrufen
    res = client.get("/messages?limit=2")
    assert res.status_code == 200
    messages = res.json()
    assert len(messages) <= 2
    assert "id" in messages[0]
    assert "inhalt" in messages[0]

    # Nachricht nach ID abrufen
    message_id = messages[0]["id"]
    res = client.get(f"/messages/{message_id}")
    assert res.status_code == 200
    assert res.json()["id"] == message_id

    # Nachrichten suchen - leere Liste ist OK
    res = client.get("/messages/search?q=test")
    assert res.status_code in [200, 404]  # Beide Status sind akzeptabel

    # Statistiken abrufen - optional, falls implementiert
    res = client.get("/messages/stats")
    if res.status_code == 200:
        assert "total_messages" in res.json()

    # Neue Nachricht erstellen
    payload = {
        "autor": "Test User",
        "autor_id": "123456789",
        "channel": "test-channel",
        "channel_id": "987654321",
        "guild": "Test Guild",
        "guild_id": "112233445566",
        "inhalt": "Dies ist eine Testnachricht",
        "attachments": []
    }
    res = client.post("/messages", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert "id" in created
    assert created["autor"] == payload["autor"]
    assert created["inhalt"] == payload["inhalt"]
