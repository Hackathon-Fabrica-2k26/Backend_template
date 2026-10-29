from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document
from reportlab.pdfgen import canvas
from rest_framework import status

from apps.pedagogico.models import Atividade
from apps.pedagogico.services import MAX_TAMANHO_BYTES

from .factories import AtividadeFactory, EscolaFactory, TurmaFactory

LIST_URL = reverse("atividade-list")
EXTRAIR_URL = reverse("atividade-extrair")


def _cria_turmas(professor):
    """Turma do professor e outra turma sem vínculo com o professor."""
    turma_do_professor = TurmaFactory(professores=[professor])
    outra_turma = TurmaFactory()
    return turma_do_professor, outra_turma


def test_atividade_list_exige_autenticacao(api_client, db):
    response = api_client.get(LIST_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_atividade_detail_de_turma_alheia_retorna_404(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    atividade = AtividadeFactory(turma=outra_turma)
    url = reverse("atividade-detail", args=[atividade.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json().get("titulo") is None


def test_atividade_list_filtra_por_turma(auth_client, db, user):
    turma, outra_turma = _cria_turmas(user)
    minha = AtividadeFactory(turma=turma, titulo="Minha atividade")
    AtividadeFactory(turma=outra_turma, titulo="Atividade alheia")
    response = auth_client.get(LIST_URL, {"turma": turma.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [minha.pk]


def test_atividade_list_nao_retorna_turmas_alheias(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    alheia = AtividadeFactory(turma=outra_turma)
    response = auth_client.get(LIST_URL)
    ids = [item["id"] for item in response.data["results"]]
    assert alheia.pk not in ids


def test_atividade_busca_por_titulo(auth_client, db, user):
    turma, _ = _cria_turmas(user)
    AtividadeFactory(turma=turma, titulo="Leitura dirigida")
    AtividadeFactory(turma=turma, titulo="Ditado")
    response = auth_client.get(LIST_URL, {"search": "Leitura"})
    titulos = [item["titulo"] for item in response.data["results"]]
    assert titulos == ["Leitura dirigida"]


def test_atividade_create_sem_campos_retorna_400(auth_client, db):
    response = auth_client.post(LIST_URL, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_atividade_create_com_turma_inexistente_retorna_400(auth_client, db):
    formulario = {
        "titulo": "Nova Atividade",
        "texto_original": "Conteúdo da atividade",
        "turma": 99999,
    }
    response = auth_client.post(LIST_URL, formulario)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_atividade_create_turma_alheia_retorna_400(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    formulario = {
        "titulo": "Nova Atividade",
        "texto_original": "Conteúdo da atividade",
        "turma": outra_turma.pk,
    }
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "turma" in response.json()


def test_atividade_create_valido(auth_client, db, user):
    turma, _ = _cria_turmas(user)
    formulario = {
        "titulo": "Nova Atividade",
        "origem": "pdf",
        "texto_original": "Texto extraído do PDF",
        "objetivo": "Trabalhar interpretação",
        "turma": turma.pk,
    }
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["titulo"] == "Nova Atividade"
    assert response.data["turma"] == turma.pk
    assert response.data["criada_por"] == user.pk
    assert response.data["status"] == "rascunho"


def test_atividade_create_com_descricao_preenche_objetivo(auth_client, db, user):
    turma, _ = _cria_turmas(user)
    formulario = {
        "titulo": "Atividade com Descrição",
        "origem": "docx",
        "texto_original": "Texto extraído do DOCX",
        "descricao": "Objetivo enviado via campo descricao",
        "turma": turma.pk,
    }
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["objetivo"] == "Objetivo enviado via campo descricao"


def _gerar_pdf_em_memoria(texto: str, nome: str = "atividade_fracoes.pdf") -> SimpleUploadedFile:
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(72, 720, texto)
    c.showPage()
    c.save()
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="application/pdf")


def _gerar_docx_em_memoria(texto: str, nome: str = "exercicio_ciencias.docx") -> SimpleUploadedFile:
    buffer = BytesIO()
    doc = Document()
    doc.add_paragraph(texto)
    doc.save(buffer)
    return SimpleUploadedFile(
        nome,
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def test_extrair_pdf_com_ia_mockada_nao_salva_no_banco(auth_client, db, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()
    turma, _ = _cria_turmas(user)

    capturado = {}

    def fake_gemini(conteudo, api_key, modelo):
        capturado["conteudo"] = conteudo
        capturado["api_key"] = api_key
        return (
            '{"titulo": "Frações na Prática", '
            '"descricao": "Exercícios sobre frações equivalentes."}'
        )

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake_gemini)

    arquivo_pdf = _gerar_pdf_em_memoria(
        "Resolva as frações equivalentes. CPF 123.456.789-00 Data 10/03/2017."
    )
    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_pdf, "turma": turma.pk},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    dados = response.json()
    assert dados["titulo"] == "Frações na Prática"
    assert dados["descricao"] == "Exercícios sobre frações equivalentes."
    assert "Resolva as frações equivalentes" in dados["texto_original"]
    assert dados["origem"] == "pdf"
    assert Atividade.objects.count() == 0
    # PII não vai para a LLM
    assert "123.456.789-00" not in capturado["conteudo"]
    assert "10/03/2017" not in capturado["conteudo"]


def test_extrair_docx_com_ia_mockada_nao_salva_no_banco(auth_client, db, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()

    monkeypatch.setattr(
        "apps.pedagogico.services.llm._pedir_ao_gemini",
        lambda c, k, m: (
            '{"titulo": "Ciclo da Água", "descricao": "Estudo sobre evaporação e chuva."}'
        ),
    )

    arquivo_docx = _gerar_docx_em_memoria("Explique as etapas do ciclo da água na natureza.")
    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_docx},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    dados = response.json()
    assert dados["titulo"] == "Ciclo da Água"
    assert dados["descricao"] == "Estudo sobre evaporação e chuva."
    assert "ciclo da água" in dados["texto_original"]
    assert dados["origem"] == "docx"
    assert Atividade.objects.count() == 0


def test_extrair_fallback_quando_ia_falha(auth_client, db, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()

    def fake_erro(*args, **kwargs):
        raise RuntimeError("Gemini indisponível")

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake_erro)

    texto_longo = "A" * 350
    arquivo_docx = _gerar_docx_em_memoria(texto_longo, nome="minha_prova_bimestral.docx")
    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_docx},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    dados = response.json()
    assert dados["titulo"] == "minha_prova_bimestral"
    assert dados["descricao"] == "A" * 300
    assert len(dados["descricao"]) == 300
    assert dados["texto_original"] == texto_longo
    assert dados["origem"] == "docx"


def test_extrair_tipo_invalido_retorna_400(auth_client, db):
    arquivo_invalido = SimpleUploadedFile(
        "notas.txt",
        b"conteudo texto puro",
        content_type="text/plain",
    )
    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_invalido},
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "arquivo" in response.json()


def test_extrair_arquivo_maior_que_20mb_retorna_400(auth_client, db):
    arquivo_grande = SimpleUploadedFile(
        "grande.pdf",
        b"%PDF-1.4\n",
        content_type="application/pdf",
    )
    arquivo_grande.size = MAX_TAMANHO_BYTES + 1
    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_grande},
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "arquivo" in response.json()


def test_extrair_turma_alheia_retorna_400(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    arquivo_pdf = _gerar_pdf_em_memoria("Texto de teste")
    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_pdf, "turma": outra_turma.pk},
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "turma" in response.json()


def test_extrair_imagem_com_gemini_mockado(auth_client, db, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()

    capturado = {}

    def fake_multimodal(**kwargs):
        capturado.update(kwargs)
        return {
            "texto_original": "Resolva as questões de matemática.",
            "titulo": "Questões de matemática",
            "descricao": "Praticar resolução de problemas.",
        }

    monkeypatch.setattr(
        "apps.pedagogico.views.atividade_extrair.extrair_atividade_multimodal",
        fake_multimodal,
    )

    arquivo = SimpleUploadedFile(
        "atividade.png",
        b"conteudo de imagem para teste",
        content_type="image/png",
    )

    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["origem"] == "png"
    assert response.data["texto_original"] == (
        "Resolva as questões de matemática."
    )
    assert response.data["titulo"] == "Questões de matemática"
    assert capturado["mime_type"] == "image/png"
    assert capturado["api_key"] == user.escola.config.api_key
    assert capturado["conteudo_bytes"] == b"conteudo de imagem para teste"
    assert Atividade.objects.count() == 0

@pytest.mark.parametrize(
    ("nome", "mime_type", "origem"),
    [
        ("atividade.jpg", "image/jpeg", "jpg"),
        ("atividade.png", "image/png", "png"),
        ("atividade.webp", "image/webp", "webp"),
    ],
)
def test_extrair_imagem_por_formato(
    auth_client, db, user, monkeypatch, nome, mime_type, origem
):
    user.escola = EscolaFactory()
    user.save()

    capturado = {}

    def fake_multimodal(**kwargs):
        capturado.update(kwargs)
        return {
            "texto_original": "Resolva as questões.",
            "titulo": "Questões",
            "descricao": "Praticar os exercícios propostos.",
        }

    monkeypatch.setattr(
        "apps.pedagogico.views.atividade_extrair.extrair_atividade_multimodal",
        fake_multimodal,
    )

    arquivo = SimpleUploadedFile(
        nome,
        b"bytes de teste da imagem",
        content_type=mime_type,
    )

    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["origem"] == origem
    assert capturado["mime_type"] == mime_type
    assert capturado["conteudo_bytes"] == b"bytes de teste da imagem"

def test_rejeita_arquivo_acima_limite_real(auth_client, db):
    conteudo = b"x" * (MAX_TAMANHO_BYTES + 1)

    arquivo = SimpleUploadedFile(
        "atividade.png",
        conteudo,
        content_type="image/png",
    )

    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "20 MB" in str(response.data)


def test_extrair_atividade_documento_invalido_multimodal_retorna_422(
    auth_client, db, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()

    def fake_generate_content(*args, **kwargs):
        class RespostaFake:
            text = (
                '{"documento_valido": false, "tipo_documento": "boletim de urna", '
                '"motivo": "Este arquivo é um boletim de urna eleitoral, não uma atividade.", '
                '"texto_original": "", "titulo": "", "descricao": ""}'
            )

        return RespostaFake()

    monkeypatch.setattr(
        "google.genai.models.Models.generate_content",
        fake_generate_content,
    )

    arquivo = SimpleUploadedFile(
        "boletim.png",
        b"bytes simulando imagem de boletim",
        content_type="image/png",
    )

    contagem_antes = Atividade.objects.count()

    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo},
        format="multipart",
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    dados = response.json()
    assert dados["erro"] == "Este arquivo não parece uma atividade escolar."
    assert dados["tipo_documento"] == "boletim de urna"
    assert "boletim de urna" in dados["motivo"]
    assert Atividade.objects.count() == contagem_antes


def test_extrair_atividade_documento_invalido_texto_retorna_422(
    auth_client, db, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()

    def fake_gemini(conteudo, api_key, modelo):
        return (
            '{"documento_valido": false, "tipo_documento": "receita médica", '
            '"motivo": "O documento refere-se a uma receita médica particular.", '
            '"titulo": "", "descricao": ""}'
        )

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake_gemini)

    arquivo_docx = _gerar_docx_em_memoria(
        "Tomar Paracetamol 500mg de 8 em 8 horas se dor.",
        nome="receita.docx",
    )

    contagem_antes = Atividade.objects.count()

    response = auth_client.post(
        EXTRAIR_URL,
        {"arquivo": arquivo_docx},
        format="multipart",
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    dados = response.json()
    assert dados["erro"] == "Este arquivo não parece uma atividade escolar."
    assert dados["tipo_documento"] == "receita médica"
    assert "receita médica" in dados["motivo"]
    assert Atividade.objects.count() == contagem_antes

