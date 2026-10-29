"""Testes do endpoint POST /api/chamada/reconhecer/ (OCR com Gemini mockado)."""

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.escolas.services.chamada import PROMPT_USUARIO_CHAMADA, SYSTEM_PROMPT_CHAMADA
from apps.pedagogico.models import Atividade, Relatorio

from .factories import EscolaFactory

RECONHECER_URL = "/api/chamada/reconhecer/"

# Bytes mínimos simulando uma imagem JPEG e um PDF em memória.
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _imagem_valida(nome: str = "chamada.jpg", content_type: str = "image/jpeg", tamanho: int = 0):
    conteudo = (
        JPEG_BYTES if tamanho <= 0 else (JPEG_BYTES + b"x" * max(0, tamanho - len(JPEG_BYTES)))
    )
    return SimpleUploadedFile(nome, conteudo, content_type=content_type)


def _pdf_valido(nome: str = "chamada.pdf", tamanho: int = 0):
    conteudo = (
        PDF_BYTES if tamanho <= 0 else (PDF_BYTES + b"x" * max(0, tamanho - len(PDF_BYTES)))
    )
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


def test_chamada_reconhecer_exige_autenticacao(api_client, db):
    response = api_client.post(
        RECONHECER_URL,
        {"imagem": _imagem_valida()},
        format="multipart",
    )
    assert response.status_code == 401


def test_chamada_reconhecer_sem_imagem_retorna_400(auth_client, db):
    response = auth_client.post(RECONHECER_URL, {}, format="multipart")
    assert response.status_code == 400
    assert "imagem" in response.json()


def test_chamada_reconhecer_tipo_invalido_retorna_400(auth_client, db):
    arquivo = SimpleUploadedFile("lista.txt", b"1. Ana\n2. Bruno", content_type="text/plain")
    response = auth_client.post(RECONHECER_URL, {"imagem": arquivo}, format="multipart")
    assert response.status_code == 400
    assert "imagem" in response.json()


def test_chamada_reconhecer_acima_de_10mb_retorna_400(auth_client, db):
    acima_do_limite = 10 * 1024 * 1024 + 1
    arquivo = _imagem_valida(tamanho=acima_do_limite)
    response = auth_client.post(RECONHECER_URL, {"imagem": arquivo}, format="multipart")
    assert response.status_code in (400, 413)
    assert "imagem" in response.json()


def test_chamada_reconhecer_sucesso_limpa_numeros_duplicatas_e_nao_salva_nada(
    auth_client, db, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()

    capturado = {}

    def fake_ocr(imagem_bytes, mime, api_key, modelo):
        capturado.update(
            {
                "imagem_bytes": imagem_bytes,
                "mime": mime,
                "api_key": api_key,
                "modelo": modelo,
            }
        )
        return (
            "```json\n"
            '{"nomes": ['
            '{"nome": "1. Alice Souza", "confianca": 0.96}, '
            '{"nome": "02 - Bruno Lima", "confianca": 0.72}, '
            '{"nome": "alice souza", "confianca": 0.80}, '
            '"  3) Carla   Mendes  ", '
            '{"nome": "", "confianca": 0.5}'
            "]}\n```"
        )

    monkeypatch.setattr("apps.escolas.services.chamada._pedir_ocr_ao_gemini", fake_ocr)

    contagens_antes = (
        Escola.objects.count(),
        Config.objects.count(),
        Turma.objects.count(),
        Aluno.objects.count(),
        Responsavel.objects.count(),
        MetaDados.objects.count(),
        Atividade.objects.count(),
        Relatorio.objects.count(),
    )

    response = auth_client.post(
        RECONHECER_URL,
        {"imagem": _imagem_valida("chamada.png", "image/png")},
        format="multipart",
    )

    assert response.status_code == 200
    assert response.json() == {
        "nomes": [
            {"nome": "Alice Souza", "confianca": 0.96},
            {"nome": "Bruno Lima", "confianca": 0.72},
            {"nome": "Carla Mendes", "confianca": 1.0},
        ],
        "nomes_texto": [
            "Alice Souza",
            "Bruno Lima",
            "Carla Mendes",
        ],
    }
    assert capturado["imagem_bytes"] == JPEG_BYTES
    assert capturado["mime"] == "image/png"
    assert capturado["api_key"] == user.escola.config.api_key
    assert capturado["modelo"] == user.escola.config.modelo

    contagens_depois = (
        Escola.objects.count(),
        Config.objects.count(),
        Turma.objects.count(),
        Aluno.objects.count(),
        Responsavel.objects.count(),
        MetaDados.objects.count(),
        Atividade.objects.count(),
        Relatorio.objects.count(),
    )
    assert contagens_depois == contagens_antes


def test_chamada_reconhecer_aceita_pdf_e_ignora_campos_extras_e_datas(
    auth_client, db, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()

    capturado = {}

    def fake_ocr(imagem_bytes, mime, api_key, modelo):
        capturado.update({"imagem_bytes": imagem_bytes, "mime": mime})
        return (
            '{"nomes": ['
            '{"nome": "1. Daniel Rocha 14/05/2017", "confianca": 0.91, '
            '"data_nascimento": "14/05/2017", "observacoes": "Consulta médica"}, '
            '{"nome": "2. Eduarda Alves", "confianca": 1.5, "observacao": "Falta justificada"}, '
            '{"nome": "3. Felipe Costa", "confianca": -0.2, "matricula": "2026003"}'
            "]}"
        )

    monkeypatch.setattr("apps.escolas.services.chamada._pedir_ocr_ao_gemini", fake_ocr)

    response = auth_client.post(
        RECONHECER_URL,
        {"imagem": _pdf_valido("lista_chamada.pdf")},
        format="multipart",
    )

    assert response.status_code == 200
    dados = response.json()
    assert capturado["imagem_bytes"] == PDF_BYTES
    assert capturado["mime"] == "application/pdf"
    assert dados == {
        "nomes": [
            {"nome": "Daniel Rocha", "confianca": 0.91},
            {"nome": "Eduarda Alves", "confianca": 1.0},
            {"nome": "Felipe Costa", "confianca": 0.0},
        ],
        "nomes_texto": [
            "Daniel Rocha",
            "Eduarda Alves",
            "Felipe Costa",
        ],
    }
    for item in dados["nomes"]:
        assert set(item.keys()) == {"nome", "confianca"}
        assert "14/05/2017" not in item["nome"]

    # Verifica que o prompt instrui a extrair só a coluna de nomes e ignorar datas/observações
    assert "coluna de nomes" in SYSTEM_PROMPT_CHAMADA.lower()
    assert "datas de nascimento" in SYSTEM_PROMPT_CHAMADA.lower()
    assert "observações" in SYSTEM_PROMPT_CHAMADA.lower()
    assert "confianca" in PROMPT_USUARIO_CHAMADA.lower()


def test_chamada_reconhecer_sem_config_da_escola_retorna_502(auth_client, db, user):
    user.escola = None
    user.save()

    response = auth_client.post(
        RECONHECER_URL,
        {"imagem": _imagem_valida("chamada.webp", "image/webp")},
        format="multipart",
    )
    assert response.status_code == 502
    assert "credencial" in response.json()["erro"]


def test_chamada_reconhecer_erro_da_ia_retorna_502(auth_client, db, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()

    def fake_ocr(imagem_bytes, mime, api_key, modelo):
        raise RuntimeError("Falha no Gemini")

    monkeypatch.setattr("apps.escolas.services.chamada._pedir_ocr_ao_gemini", fake_ocr)

    response = auth_client.post(
        RECONHECER_URL,
        {"imagem": _imagem_valida()},
        format="multipart",
    )
    assert response.status_code == 502
    assert "Não foi possível reconhecer os nomes" in response.json()["erro"]


def test_chamada_reconhecer_documento_invalido_retorna_422_e_nao_cria_nada(
    auth_client, db, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()

    def fake_ocr(imagem_bytes, mime, api_key, modelo):
        return (
            '{"documento_valido": false, "tipo_documento": "boletim de urna", '
            '"motivo": "O documento refere-se a um boletim de urna eleitoral.", '
            '"nomes": []}'
        )

    monkeypatch.setattr("apps.escolas.services.chamada._pedir_ocr_ao_gemini", fake_ocr)

    contagens_antes = (
        Escola.objects.count(),
        Turma.objects.count(),
        Aluno.objects.count(),
    )

    response = auth_client.post(
        RECONHECER_URL,
        {"imagem": _imagem_valida()},
        format="multipart",
    )

    assert response.status_code == 422
    dados = response.json()
    assert dados["erro"] == "Este arquivo não parece uma lista de chamada."
    assert dados["tipo_documento"] == "boletim de urna"
    assert "boletim de urna" in dados["motivo"]

    contagens_depois = (
        Escola.objects.count(),
        Turma.objects.count(),
        Aluno.objects.count(),
    )
    assert contagens_depois == contagens_antes


def test_chamada_reconhecer_sem_nomes_com_confianca_minima_retorna_422(
    auth_client, db, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()

    def fake_ocr(imagem_bytes, mime, api_key, modelo):
        return (
            '{"documento_valido": true, "tipo_documento": "lista de chamada", '
            '"motivo": "", "nomes": [{"nome": "Rascunho ilegível", "confianca": 0.2}]}'
        )

    monkeypatch.setattr("apps.escolas.services.chamada._pedir_ocr_ao_gemini", fake_ocr)

    response = auth_client.post(
        RECONHECER_URL,
        {"imagem": _imagem_valida()},
        format="multipart",
    )

    assert response.status_code == 422
    dados = response.json()
    assert dados["erro"] == "Este arquivo não parece uma lista de chamada."
    assert dados["tipo_documento"] == "lista de chamada"
    assert "confiança mínima" in dados["motivo"]

