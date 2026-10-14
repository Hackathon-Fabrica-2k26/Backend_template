def test_health_sem_autenticacao(client):
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_docs_disponiveis(client):
    assert client.get("/api/docs/").status_code == 200


def test_schema_documenta_id_como_inteiro(client):
    schema = client.get("/api/schema/", {"format": "json"}).json()
    parametros = schema["paths"]["/api/items/{id}/"]["get"]["parameters"]
    id_param = next(p for p in parametros if p["name"] == "id")
    assert id_param["schema"]["type"] == "integer"
