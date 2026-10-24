"""Testes automatizados para geração sob demanda de rascunho de PEI e PDF (B#46)."""

import json
from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from apps.alunos.models import Aluno, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.pedagogico.models import (
    Atividade,
    EnvioTrabalhos,
    PerfilApoio,
    Relatorio,
    Trabalho,
)
from apps.pedagogico.services.llm import LLMError
from apps.pedagogico.services.pei import DISCLAIMER_PEI

pytestmark = pytest.mark.django_db


def _criar_cenario_pei(user):
    config = Config.objects.create(
        api_key="chave-gemini-pei",
        modelo="gemini-3.8-flash",
    )
    escola = Escola.objects.create(nome="Escola Municipal Sol", config=config)
    user.escola = escola
    user.save(update_fields=["escola"])

    turma = Turma.objects.create(
        nome="3º Ano B",
        turno=Turma.TurnoChoices.MANHA,
        ano_letivo=2026,
        escola=escola,
    )
    turma.professores.add(user)

    responsavel = Responsavel.objects.create(
        nome="Marcos Ribeiro",
        cpf="12345678901",
        telefone="47999991111",
        endereco="Rua das Palmeiras, 42",
    )
    aluno = Aluno.objects.create(
        nome="Helena Ribeiro",
        matricula="2026045",
        nascimento=date(2017, 5, 10),
        turma=turma,
        responsavel=responsavel,
    )
    PerfilApoio.objects.create(
        aluno=aluno,
        necessidades=["Apoio visual em enunciados longos (laudo TDAH CID F90)"],
        estrategias=["Enunciados curtos e etapas numeradas"],
        observacoes="Helena Ribeiro responde bem a combinados visuais na turma 3º Ano B.",
        ativo=True,
    )
    atividade = Atividade.objects.create(
        turma=turma,
        criada_por=user,
        titulo="Leitura de fábula",
        origem=Atividade.OrigemChoices.TEXTO,
        texto_original="Leia a fábula.",
    )
    Relatorio.objects.create(
        aluno=aluno,
        atividade=atividade,
        tipo="atividade",
        dados={
            "pontos_fortes": ["Helena Ribeiro tem ótima expressão oral."],
            "observacoes": "Em 15/08/2026 conversamos com Marcos Ribeiro.",
        },
    )
    envio = EnvioTrabalhos.objects.create(
        atividade=atividade,
        enviado_por=user,
        total_arquivos=1,
    )
    Trabalho.objects.create(
        envio=envio,
        atividade=atividade,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
        status=Trabalho.StatusChoices.ANALISADO,
        descricao_ia=(
            "Helena Ribeiro compreendeu a história na turma 3º Ano B, "
            "mas precisou de mediação nas respostas escritas."
        ),
    )
    return escola, turma, aluno


def test_rascunho_pei_exige_autenticacao(client, user):
    _, _, aluno = _criar_cenario_pei(user)
    resp_post = client.post(f"/api/alunos/{aluno.id}/rascunho-pei/")
    resp_pdf = client.get(f"/api/alunos/{aluno.id}/rascunho-pei/pdf/")
    assert resp_post.status_code in (401, 403)
    assert resp_pdf.status_code in (401, 403)


def test_rascunho_pei_aluno_de_outra_turma_retorna_404(auth_client, user):
    outra_escola = Escola.objects.create(nome="Outra Escola")
    outra_turma = Turma.objects.create(
        nome="4º Ano A",
        turno=Turma.TurnoChoices.TARDE,
        ano_letivo=2026,
        escola=outra_escola,
    )
    aluno_alheio = Aluno.objects.create(nome="Lucas Mendes", turma=outra_turma)

    resp_post = auth_client.post(f"/api/alunos/{aluno_alheio.id}/rascunho-pei/")
    resp_pdf = auth_client.get(f"/api/alunos/{aluno_alheio.id}/rascunho-pei/pdf/")
    assert resp_post.status_code == 404
    assert resp_pdf.status_code == 404


def test_post_rascunho_pei_consolida_dados_anonimiza_e_nao_persiste(auth_client, user, monkeypatch):
    _, _, aluno = _criar_cenario_pei(user)
    prompts_capturados: list[str] = []

    def _falso_gemini(conteudo: str, api_key: str, modelo: str) -> str:
        prompts_capturados.append(conteudo)
        return json.dumps(
            {
                "objetivos": [
                    "Ampliar a autonomia na produção escrita com roteiros curtos.",
                ],
                "adaptacoes": [
                    "Apresentar enunciados divididos em etapas numeradas com apoio visual.",
                ],
                "estrategias": [
                    "Utilizar organizadores gráficos antes da escrita discursiva.",
                ],
                "acompanhamento": [
                    "Registros quinzenais das produções escritas em portfólio.",
                ],
                "observacoes": ("Rascunho elaborado com foco nas potencialidades orais e visuais."),
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "apps.pedagogico.services.pei._pedir_ao_gemini",
        _falso_gemini,
    )

    total_relatorios_antes = Relatorio.objects.count()
    total_perfis_antes = PerfilApoio.objects.count()
    total_atividades_antes = Atividade.objects.count()

    resp = auth_client.post(f"/api/alunos/{aluno.id}/rascunho-pei/")
    assert resp.status_code == 200
    dados = resp.json()

    assert dados["objetivos"] == ["Ampliar a autonomia na produção escrita com roteiros curtos."]
    assert dados["adaptacoes"] == [
        "Apresentar enunciados divididos em etapas numeradas com apoio visual."
    ]
    assert dados["estrategias"] == ["Utilizar organizadores gráficos antes da escrita discursiva."]
    assert dados["acompanhamento"] == ["Registros quinzenais das produções escritas em portfólio."]
    assert "potencialidades orais" in dados["observacoes"]
    assert dados["disclaimer"] == DISCLAIMER_PEI

    # Nada é persistido no banco
    assert Relatorio.objects.count() == total_relatorios_antes
    assert PerfilApoio.objects.count() == total_perfis_antes
    assert Atividade.objects.count() == total_atividades_antes

    # Verifica anonimização e remoção de CID/termos clínicos no prompt enviado à IA
    assert len(prompts_capturados) == 1
    prompt_enviado = prompts_capturados[0]
    for proibido in (
        "Helena",
        "Ribeiro",
        "Marcos",
        "12345678901",
        "3º Ano B",
        "15/08/2026",
        "TDAH",
        "F90",
    ):
        assert proibido.lower() not in prompt_enviado.lower()


def test_get_rascunho_pei_pdf_gera_pdf_sem_cpf_e_sem_responsavel(auth_client, user, monkeypatch):
    _, _, aluno = _criar_cenario_pei(user)

    monkeypatch.setattr(
        "apps.pedagogico.services.pei._pedir_ao_gemini",
        lambda c, k, m: json.dumps(
            {
                "objetivos": ["Consolidar leitura compreensiva."],
                "adaptacoes": ["Tempo estendido em atividades escritas."],
                "estrategias": ["Mediação com pistas visuais."],
                "acompanhamento": ["Observação contínua em sala."],
                "observacoes": "Evolução consistente ao longo do bimestre.",
            },
            ensure_ascii=False,
        ),
    )

    resp = auth_client.get(f"/api/alunos/{aluno.id}/rascunho-pei/pdf/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")

    leitor = PdfReader(BytesIO(resp.content))
    texto_pdf = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)

    assert "Helena Ribeiro" in texto_pdf
    assert "Consolidar leitura compreensiva" in texto_pdf
    assert "Rascunho para revisão da professora e da coordenação" in texto_pdf
    # Minimização LGPD: sem CPF e sem nome/endereço do responsável no PDF
    assert "12345678901" not in texto_pdf
    assert "Marcos Ribeiro" not in texto_pdf
    assert "Rua das Palmeiras" not in texto_pdf


def test_rascunho_pei_erro_ia_retorna_502(auth_client, user, monkeypatch):
    _, _, aluno = _criar_cenario_pei(user)

    def _falhar(*args, **kwargs):
        raise LLMError("Falha na comunicação com o Gemini.")

    monkeypatch.setattr("apps.pedagogico.services.pei._pedir_ao_gemini", _falhar)

    resp_post = auth_client.post(f"/api/alunos/{aluno.id}/rascunho-pei/")
    resp_pdf = auth_client.get(f"/api/alunos/{aluno.id}/rascunho-pei/pdf/")
    assert resp_post.status_code == 502
    assert "erro" in resp_post.json()
    assert resp_pdf.status_code == 502
    assert "erro" in resp_pdf.json()


def test_api_root_inclui_rotas_rascunho_pei(auth_client):
    resp = auth_client.get("/api/")
    assert resp.status_code == 200
    dados = resp.json()
    assert "aluno-rascunho-pei" in dados
    assert "aluno-rascunho-pei-pdf" in dados
