import io
import json
import zipfile
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status

from apps.pedagogico.models import EnvioTrabalhos, Relatorio, Trabalho
from apps.pedagogico.services import DISCLAIMER, LLMError
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
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=professor,
        titulo="Desenho Livre",
    )
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
    arquivo = SimpleUploadedFile(
        "vazio.pdf",
        b"",
        content_type="application/pdf",
    )

    resp = auth_client.post(url, {"arquivos": [arquivo]}, format="multipart")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_envio_trabalhos_formato_invalido_retorna_400(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile(
        "executavel.exe",
        b"MZ...",
        content_type="application/x-msdownload",
    )

    resp = auth_client.post(url, {"arquivos": [arquivo]}, format="multipart")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_envio_trabalhos_tamanho_maior_20mb_retorna_400(
    cenario,
    auth_client,
):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"

    with patch(
        "apps.pedagogico.services.trabalhos.TAMANHO_MAXIMO_BYTES",
        10,
    ):
        arquivo = SimpleUploadedFile(
            "pesado.pdf",
            b"0123456789012345",
            content_type="application/pdf",
        )
        resp = auth_client.post(
            url,
            {"arquivos": [arquivo]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "20 MB" in str(resp.data) or "máximo" in str(resp.data)


@pytest.mark.django_db
def test_envio_trabalhos_multiplos_formatos_e_casamento_exato(
    cenario,
    auth_client,
):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"

    arq_pdf = SimpleUploadedFile(
        "trabalho.pdf",
        criar_pdf(),
        content_type="application/pdf",
    )
    arq_png = SimpleUploadedFile(
        "trabalho.png",
        criar_imagem("PNG"),
        content_type="image/png",
    )
    arq_jpg = SimpleUploadedFile(
        "trabalho.jpg",
        criar_imagem("JPEG"),
        content_type="image/jpeg",
    )
    arq_docx = SimpleUploadedFile(
        "trabalho.docx",
        criar_docx("Lucas Gabriel Silva produziu uma redação"),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
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

    for trabalho in dados["trabalhos"]:
        assert trabalho["identificacao"] == "confirmada"
        assert trabalho["aluno"] == cenario["aluno1"].id
        assert trabalho["confianca_nome"] == 1.0
        assert trabalho["status"] == "analisado"

    relatorios = Relatorio.objects.filter(
        aluno=cenario["aluno1"],
        tipo="atividade",
    )
    assert relatorios.count() == 4

    for relatorio in relatorios:
        assert relatorio.atividade == cenario["atividade"]
        assert relatorio.disclaimer == DISCLAIMER
        assert relatorio.dados["atividade_titulo"] == "Desenho Livre"


@pytest.mark.django_db
def test_envio_trabalhos_duvida_gera_status_pendente(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    turma = cenario["turma"]

    AlunoFactory(nome="Lucas Gabriel de Souza", turma=turma)

    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile(
        "trabalho.png",
        criar_imagem("PNG"),
        content_type="image/png",
    )

    mock_resposta_ia = {
        "nome_lido": "Lucas Gabriel",
        "descricao": "Desenho com lápis de cor.",
        "analise_pedagogica": {"pontos_fortes": ["Cores"]},
    }

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value=mock_resposta_ia,
    ):
        resp = auth_client.post(
            url,
            {"arquivos": [arquivo]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["status"] == "revisao_pendente"
    assert resp.data["trabalhos"][0]["identificacao"] == "pendente"
    assert not Relatorio.objects.filter(tipo="atividade").exists()


@pytest.mark.django_db
def test_primeiro_nome_unico_exige_confirmacao_manual(
    cenario,
    auth_client,
):
    auth_client.force_authenticate(user=cenario["professor"])
    atividade = cenario["atividade"]

    arquivo = SimpleUploadedFile(
        "trabalho.png",
        criar_imagem(),
        content_type="image/png",
    )

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value={
            "nome_lido": "Mariana",
            "descricao": "Desenho de uma paisagem.",
            "analise_pedagogica": {},
        },
    ):
        response = auth_client.post(
            f"/api/atividades/{atividade.pk}/trabalhos/",
            {"arquivos": [arquivo]},
            format="multipart",
        )

    assert response.status_code == status.HTTP_201_CREATED

    trabalho = Trabalho.objects.get(
        envio__atividade=atividade,
        nome_lido="Mariana",
    )

    assert trabalho.aluno == cenario["aluno2"]
    assert trabalho.identificacao == Trabalho.IdentificacaoChoices.PENDENTE
    assert trabalho.confianca_nome == 0.9
    assert trabalho.confirmado_por is None
    assert not Relatorio.objects.filter(
        dados__trabalho_id=trabalho.pk,
    ).exists()


@pytest.mark.django_db
def test_nome_parecido_exige_confirmacao_manual(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    atividade = cenario["atividade"]

    arquivo = SimpleUploadedFile(
        "trabalho.png",
        criar_imagem(),
        content_type="image/png",
    )

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value={
            "nome_lido": "Marina Costa",
            "descricao": "Atividade de escrita.",
            "analise_pedagogica": {},
        },
    ):
        response = auth_client.post(
            f"/api/atividades/{atividade.pk}/trabalhos/",
            {"arquivos": [arquivo]},
            format="multipart",
        )

    assert response.status_code == status.HTTP_201_CREATED

    trabalho = Trabalho.objects.get(
        envio__atividade=atividade,
        nome_lido="Marina Costa",
    )

    assert trabalho.aluno == cenario["aluno2"]
    assert trabalho.identificacao == Trabalho.IdentificacaoChoices.PENDENTE
    assert 0.85 <= trabalho.confianca_nome < 1.0
    assert trabalho.confirmado_por is None
    assert not Relatorio.objects.filter(
        dados__trabalho_id=trabalho.pk,
    ).exists()


@pytest.mark.django_db
def test_patch_trabalho_confirmacao_manual_gera_relatorio(
    cenario,
    auth_client,
):
    auth_client.force_authenticate(user=cenario["professor"])
    envio = EnvioTrabalhos.objects.create(
        atividade=cenario["atividade"],
        enviado_por=cenario["professor"],
        total_arquivos=1,
    )
    trabalho = Trabalho.objects.create(
        envio=envio,
        atividade=cenario["atividade"],
        aluno=None,
        nome_lido="Mariana",
        confianca_nome=0.6,
        identificacao=Trabalho.IdentificacaoChoices.PENDENTE,
        descricao_ia="Colagem de gravuras",
        dados_analise={"pontos_fortes": ["Organização"]},
        status=Trabalho.StatusChoices.ANALISADO,
    )

    resp = auth_client.patch(
        f"/api/trabalhos/{trabalho.id}/",
        {
            "aluno": cenario["aluno2"].id,
            "identificacao": "confirmada",
        },
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["identificacao"] == "confirmada"
    assert resp.data["aluno"] == cenario["aluno2"].id
    assert resp.data["confianca_nome"] == 1.0
    assert resp.data["confirmado_por"] == cenario["professor"].id

    relatorio = Relatorio.objects.get(
        aluno=cenario["aluno2"],
        tipo="atividade",
    )
    assert relatorio.dados["descricao"] == "Colagem de gravuras"
    assert relatorio.atividade == cenario["atividade"]
    assert relatorio.disclaimer == DISCLAIMER


@pytest.mark.django_db
def test_patch_trabalho_aluno_de_outra_turma_retorna_400(
    cenario,
    auth_client,
):
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

    resp = auth_client.patch(
        f"/api/trabalhos/{trabalho.id}/",
        {
            "aluno": aluno_outra_turma.id,
            "identificacao": "confirmada",
        },
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "não pertence à turma" in str(resp.data)


@pytest.mark.django_db
def test_isolamento_professor_outro_professor_recebe_404(
    cenario,
    auth_client,
):
    outro_professor = UserFactory()
    auth_client.force_authenticate(user=outro_professor)

    url_upload = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile(
        "teste.pdf",
        criar_pdf(),
        content_type="application/pdf",
    )
    resp_upload = auth_client.post(
        url_upload,
        {"arquivos": [arquivo]},
        format="multipart",
    )
    assert resp_upload.status_code == status.HTTP_404_NOT_FOUND

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

    resp_patch = auth_client.patch(
        f"/api/trabalhos/{trabalho.id}/",
        {
            "aluno": cenario["aluno1"].id,
            "identificacao": "confirmada",
        },
        format="json",
    )
    assert resp_patch.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_llm_falha_retorna_502(cenario, auth_client):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile(
        "trabalho.png",
        criar_imagem("PNG"),
        content_type="image/png",
    )

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        side_effect=LLMError("Falha na API Gemini"),
    ):
        resp = auth_client.post(
            url,
            {"arquivos": [arquivo]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    assert "Falha na API Gemini" in resp.data["erro"]


@pytest.mark.django_db
def test_descarte_de_arquivos_sem_gravacao_em_disco(
    cenario,
    auth_client,
    tmp_path,
    settings,
):
    settings.MEDIA_ROOT = tmp_path
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"
    arquivo = SimpleUploadedFile(
        "trabalho_lgpd.png",
        criar_imagem("PNG"),
        content_type="image/png",
    )

    mock_resposta_ia = {
        "nome_lido": "Lucas Gabriel Silva",
        "descricao": "Atividade LGPD com descarte.",
        "analise_pedagogica": {},
    }

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value=mock_resposta_ia,
    ):
        resp = auth_client.post(
            url,
            {"arquivos": [arquivo]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_201_CREATED
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.django_db
def test_prompt_gemini_nao_recebe_nomes_dos_alunos():
    from apps.pedagogico.services.trabalhos import (
        analisar_trabalho_com_gemini,
    )

    resposta_json = json.dumps(
        {
            "nome_lido": "Aluno do documento",
            "descricao": "Atividade escolar.",
            "analise_pedagogica": {},
        }
    )

    with (
        patch("google.genai.Client") as cliente_mock,
        patch(
            "apps.pedagogico.services.trabalhos.extrair_texto_docx",
            return_value="Conteúdo escolar.",
        ),
    ):
        cliente_mock.return_value.models.generate_content.return_value.text = (
            resposta_json
        )

        analisar_trabalho_com_gemini(
            conteudo=b"conteudo-ficticio",
            mime_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            nome_arquivo="trabalho.docx",
            api_key="chave-ficticia",
        )

    chamada = cliente_mock.return_value.models.generate_content.call_args
    prompt_enviado = "\n".join(chamada.kwargs["contents"])

    assert "Lucas Gabriel Silva" not in prompt_enviado
    assert "Mariana Costa" not in prompt_enviado
    assert "Nomes dos estudantes da turma" not in prompt_enviado


@pytest.mark.django_db
def test_envio_trabalhos_arquivo_fora_de_contexto_gera_status_erro_sem_relatorio(
    cenario,
    auth_client,
):
    auth_client.force_authenticate(user=cenario["professor"])
    url = f"/api/atividades/{cenario['atividade'].id}/trabalhos/"

    arq_invalido = SimpleUploadedFile("comprovante.png", criar_imagem("PNG"), content_type="image/png")
    arq_valido = SimpleUploadedFile("trabalho.png", criar_imagem("PNG"), content_type="image/png")

    def fake_analise(conteudo, mime_type, nome_arquivo, api_key, modelo="gemini-3.8-flash"):
        if nome_arquivo == "comprovante.png":
            return {
                "documento_valido": False,
                "tipo_documento": "comprovante bancário",
                "motivo": "O documento enviado parece um comprovante bancário.",
                "nome_lido": "",
                "descricao": "O documento enviado parece um comprovante bancário.",
                "analise_pedagogica": {},
                "habilidades_demonstradas": [],
                "habilidades_a_reforcar": [],
            }
        return {
            "documento_valido": True,
            "tipo_documento": "trabalho escolar",
            "motivo": "",
            "nome_lido": "Lucas Gabriel Silva",
            "descricao": "Desenho com lápis de cor.",
            "analise_pedagogica": {"pontos_fortes": ["Cores"]},
            "habilidades_demonstradas": ["EF15AR04"],
            "habilidades_a_reforcar": [],
        }

    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        side_effect=fake_analise,
    ):
        resp = auth_client.post(
            url,
            {"arquivos": [arq_invalido, arq_valido]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_201_CREATED
    dados = resp.data
    assert dados["total_arquivos"] == 2
    assert len(dados["trabalhos"]) == 2

    trabalho_invalido = next(t for t in dados["trabalhos"] if t["status"] == "erro")
    assert trabalho_invalido["aluno"] is None
    assert trabalho_invalido["identificacao"] == "sem_aluno"
    assert "comprovante bancário" in trabalho_invalido["descricao_ia"]
    assert trabalho_invalido["dados_analise"]["erro"] == "Este arquivo não parece um trabalho escolar."
    assert trabalho_invalido["dados_analise"]["tipo_documento"] == "comprovante bancário"
    assert trabalho_invalido["habilidades_demonstradas"] == []
    assert trabalho_invalido["habilidades_a_reforcar"] == []

    trabalho_valido = next(t for t in dados["trabalhos"] if t["status"] == "analisado")
    assert trabalho_valido["aluno"] == cenario["aluno1"].id
    assert trabalho_valido["identificacao"] == "confirmada"
    assert trabalho_valido["habilidades_demonstradas"] == ["EF15AR04"]

    relatorios = Relatorio.objects.filter(tipo="atividade")
    assert relatorios.count() == 1
    assert relatorios.first().aluno == cenario["aluno1"]


@pytest.mark.django_db
def test_analisar_trabalho_gemini_recusa_documento_invalido():
    from apps.pedagogico.services.trabalhos import analisar_trabalho_com_gemini

    resposta_gemini = json.dumps(
        {
            "documento_valido": False,
            "tipo_documento": "panfleto",
            "motivo": "O arquivo é um panfleto comercial de mercado.",
        }
    )

    with patch("google.genai.Client") as mock_client:
        mock_client.return_value.models.generate_content.return_value.text = resposta_gemini
        resultado = analisar_trabalho_com_gemini(
            conteudo=b"bytes-falsos",
            mime_type="image/png",
            nome_arquivo="panfleto.png",
            api_key="chave",
        )

    assert resultado["documento_valido"] is False
    assert resultado["tipo_documento"] == "panfleto"
    assert "panfleto comercial" in resultado["motivo"]
    assert resultado["habilidades_demonstradas"] == []
    assert resultado["habilidades_a_reforcar"] == []

