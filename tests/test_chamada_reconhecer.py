"""Testes do endpoint POST /api/chamada/reconhecer/ (OCR com Gemini mockado)."""

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.pedagogico.models import Atividade, Relatorio

from .factories import EscolaFactory

RECONHECER_URL = "/api/chamada/reconhecer/"

# Bytes mínimos simulando uma imagem JPEG em memória.
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def _imagem_valida(nome: str = "chamada.jpg", content_type: str = "image/jpeg", tamanho: int = 0):
    conteudo = (
        JPEG_BYTES if tamanho <= 0 else (JPEG_BYTES + b"x" * max(0, tamanho - len(JPEG_BYTES)))
    )
    return SimpleUploadedFile(nome, conteudo, content_type=content_type)


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
            '"1. Alice Souza", '
            '"02 - Bruno Lima", '
            '"alice souza", '
            '"  3) Carla   Mendes  ", '
            '""'
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
            "Alice Souza",
            "Bruno Lima",
            "Carla Mendes",
        ]
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
