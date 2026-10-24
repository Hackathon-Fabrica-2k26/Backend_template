import io
import zipfile
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status

from apps.pedagogico.models import EnvioTrabalhos, Relatorio, Trabalho
from apps.pedagogico.services import LLMError
from tests.factories import AlunoFactory, AtividadeFactory, TurmaFactory, UserFactory


def criar_docx(texto: str) -> bytes:
    buf = io.BytesIO()
    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>{texto}</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml_content)
    return buf.getvalue()


def criar_imagem(formato: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(buf, format=formato)
    return buf.getvalue()


def criar_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


@pytest.fixture
def cenario(db):
    professor = UserFactory()
    turma = TurmaFactory(professores=[professor])
    aluno1 = AlunoFactory(nome="Lucas Gabriel Silva", turma=turma)
    aluno2 = AlunoFactory(nome="Mariana Costa", turma=turma)
    atividade = AtividadeFactory(aluno=aluno1, nome="Desenho Livre")
    return {
        "professor": professor,
        "turma": turma,
        "aluno1": aluno1,
        "aluno2": aluno2,
        "atividade": atividade,
    }


@pytest.mark.django_db
def test_envio_trabalhos_sem_arquivos_retorna_400(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    resp = auth_client.post(url, {}, format="multipart")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_envio_trabalhos_arquivo_vazio_retorna_400(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile("vazio.pdf", b"", content_type="application/pdf")
    resp = auth_client.post(url, {"arquivos": [arquivo]}, format="multipart")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_envio_trabalhos_formato_invalido_retorna_400(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile(
        "executavel.exe", b"MZ...", content_type="application/x-msdownload"
    )
    resp = auth_client.post(url, {"arquivos": [arquivo]}, format="multipart")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_envio_trabalhos_tamanho_maior_20mb_retorna_400(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    with patch("apps.pedagogico.services.trabalhos.TAMANHO_MAXIMO_BYTES", 10):
        arquivo = SimpleUploadedFile(
            "pesado.pdf", b"0123456789012345", content_type="application/pdf"
        )
        resp = auth_client.post(url, {"arquivos": [arquivo]}, format="multipart")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "20 MB" in str(resp.data) or "máximo" in str(resp.data)


@pytest.mark.django_db
def test_envio_trabalhos_multiplos_formatos_e_casamento_exato(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"

    arq_pdf = SimpleUploadedFile("trabalho.pdf", criar_pdf(), content_type="application/pdf")
    arq_png = SimpleUploadedFile("trabalho.png", criar_imagem("PNG"), content_type="image/png")
    arq_jpg = SimpleUploadedFile("trabalho.jpg", criar_imagem("JPEG"), content_type="image/jpeg")
    arq_docx = SimpleUploadedFile(
        "trabalho.docx",
        criar_docx("Lucas Gabriel Silva produziu uma redação"),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    mock_resposta_ia = {
        "nome_lido": "Lucas Gabriel Silva",
        "descricao": "Atividade bem elaborada com pintura e escrita.",
        "analise_pedagogica": {
            "pontos_fortes": ["Criatividade", "Coordenação motora fina"],
            "habilidades_observadas": ["Escrita espontânea"],
            "observacoes": "Demonstrou autonomia",
        },
    }

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value=mock_resposta_ia,
    ):
        resp = auth_client.post(
            url,
            {"arquivos": [arq_pdf, arq_png, arq_jpg, arq_docx]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_201_CREATED
    dados = resp.data
    assert dados["total_arquivos"] == 4
    assert dados["status"] == "concluido"
    assert len(dados["trabalhos"]) == 4

    # Verifica se os trabalhos foram criados e confirmados
    for t in dados["trabalhos"]:
        assert t["identificacao"] == "confirmada"
        assert t["aluno"] == cenario["aluno1"].id
        assert t["confianca"] == 1.0

    # Verifica se os Relatórios foram criados e vinculados à atividade
    relatorios = Relatorio.objects.filter(aluno=cenario["aluno1"], tipo="atividade")
    assert relatorios.count() == 4
    for r in relatorios:
        assert cenario["atividade"] in r.atividades.all()


@pytest.mark.django_db
def test_envio_trabalhos_duvida_gera_status_pendente(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    turma = cenario["turma"]
    # Cria outro aluno com nome similar para gerar dúvida
    AlunoFactory(nome="Lucas Gabriel de Souza", turma=turma)

    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arq_png = SimpleUploadedFile("trabalho.png", criar_imagem("PNG"), content_type="image/png")

    mock_resposta_ia = {
        "nome_lido": "Lucas Gabriel",
        "descricao": "Desenho com lápis de cor.",
        "analise_pedagogica": {"pontos_fortes": ["Cores"]},
    }

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value=mock_resposta_ia,
    ):
        resp = auth_client.post(url, {"arquivos": [arq_png]}, format="multipart")

    assert resp.status_code == status.HTTP_201_CREATED
    dados = resp.data
    assert dados["status"] == "revisao_pendente"
    trabalho = dados["trabalhos"][0]
    assert trabalho["identificacao"] == "pendente"

    # Nenhum relatório deve ter sido gerado enquanto pendente
    assert not Relatorio.objects.filter(tipo="atividade").exists()


@pytest.mark.django_db
def test_patch_trabalho_confirmacao_manual_gera_relatorio(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    envio = EnvioTrabalhos.objects.create(
        atividade=cenario["atividade"],
        enviado_por=cenario["professor"],
        total_arquivos=1,
        status=EnvioTrabalhos.StatusChoices.REVISAO_PENDENTE,
    )
    trabalho = Trabalho.objects.create(
        envio=envio,
        atividade=cenario["atividade"],
        aluno=None,
        nome_lido="Mariana",
        confianca=0.6,
        identificacao=Trabalho.IdentificacaoChoices.PENDENTE,
        descricao_ia="Colagem de gravuras",
        analise_pedagogica={"pontos_fortes": ["Organização"]},
    )

    url = f"/api/trabalhos/{trabalho.id}/"
    resp = auth_client.patch(
        url,
        {"aluno": cenario["aluno2"].id, "identificacao": "manual"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["identificacao"] == "manual"
    assert resp.data["aluno"] == cenario["aluno2"].id
    assert resp.data["confianca"] == 1.0

    # Verifica se o relatório foi gerado para Mariana
    relatorio = Relatorio.objects.get(aluno=cenario["aluno2"], tipo="atividade")
    assert relatorio.dados["descricao"] == "Colagem de gravuras"
    assert cenario["atividade"] in relatorio.atividades.all()

    # Envio deve ter sido atualizado para concluído
    envio.refresh_from_db()
    assert envio.status == EnvioTrabalhos.StatusChoices.CONCLUIDO


@pytest.mark.django_db
def test_patch_trabalho_aluno_de_outra_turma_retorna_400(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    aluno_outra_turma = AlunoFactory(nome="Estudante Externo")
    envio = EnvioTrabalhos.objects.create(
        atividade=cenario["atividade"],
        enviado_por=cenario["professor"],
        total_arquivos=1,
    )
    trabalho = Trabalho.objects.create(
        envio=envio,
        atividade=cenario["atividade"],
        aluno=None,
        identificacao=Trabalho.IdentificacaoChoices.PENDENTE,
    )

    url = f"/api/trabalhos/{trabalho.id}/"
    resp = auth_client.patch(
        url,
        {"aluno": aluno_outra_turma.id, "identificacao": "manual"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "não pertence à turma" in str(resp.data)


@pytest.mark.django_db
def test_isolamento_professor_outro_professor_recebe_404(cenario, auth_client):
    outro_professor = UserFactory()
    auth_client.force_authenticate(user=outro_professor)

    # Tentativa de POST na atividade de outro professor
    url_upload = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arq = SimpleUploadedFile("teste.pdf", criar_pdf(), content_type="application/pdf")
    resp_upload = auth_client.post(url_upload, {"arquivos": [arq]}, format="multipart")
    assert resp_upload.status_code == status.HTTP_404_NOT_FOUND

    # Tentativa de PATCH no trabalho de outro professor
    envio = EnvioTrabalhos.objects.create(
        atividade=cenario["atividade"],
        enviado_por=cenario["professor"],
        total_arquivos=1,
    )
    trabalho = Trabalho.objects.create(
        envio=envio,
        atividade=cenario["atividade"],
        identificacao=Trabalho.IdentificacaoChoices.PENDENTE,
    )
    url_patch = f"/api/trabalhos/{trabalho.id}/"
    resp_patch = auth_client.patch(
        url_patch,
        {"aluno": cenario["aluno1"].id, "identificacao": "confirmada"},
        format="json",
    )
    assert resp_patch.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_llm_falha_retorna_502(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arq = SimpleUploadedFile("trabalho.png", criar_imagem("PNG"), content_type="image/png")

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        side_effect=LLMError("Falha na API Gemini"),
    ):
        resp = auth_client.post(url, {"arquivos": [arq]}, format="multipart")

    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    assert "Falha na API Gemini" in resp.data["erro"]


@pytest.mark.django_db
def test_descarte_de_arquivos_sem_gravacao_em_disco(cenario, auth_client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arq_png = SimpleUploadedFile("trabalho_lgpd.png", criar_imagem("PNG"), content_type="image/png")

    mock_resposta_ia = {
        "nome_lido": "Lucas Gabriel Silva",
        "descricao": "Atividade LGPD com descarte.",
        "analise_pedagogica": {},
    }

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value=mock_resposta_ia,
    ):
        resp = auth_client.post(url, {"arquivos": [arq_png]}, format="multipart")

    assert resp.status_code == status.HTTP_201_CREATED
    # Verifica que nenhum arquivo foi persistido em disco
    arquivos_em_disco = list(tmp_path.rglob("*"))
    assert len(arquivos_em_disco) == 0
