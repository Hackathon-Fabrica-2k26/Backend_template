"""Testes automatizados para os pontos de atenção sob demanda (B#45)."""

import json
from datetime import date

import pytest

from apps.alunos.models import Aluno, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.pedagogico.models import Atividade, EnvioTrabalhos, Trabalho
from apps.pedagogico.services.llm import DISCLAIMER, LLMError
from apps.pedagogico.services.pontos_atencao import (
    MENSAGEM_MINIMO_TRABALHOS,
    MINIMO_TRABALHOS_PONTOS_ATENCAO,
)

pytestmark = pytest.mark.django_db


def _criar_cenario_professor(user):
    config = Config.objects.create(
        api_key="chave-gemini-teste",
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
        telefone="47999991111",
    )
    aluno = Aluno.objects.create(
        nome="Helena Ribeiro",
        matricula="2026045",
        nascimento=date(2017, 5, 10),
        turma=turma,
        responsavel=responsavel,
    )
    atividade = Atividade.objects.create(
        turma=turma,
        criada_por=user,
        titulo="Leitura e interpretação de fábula",
        origem=Atividade.OrigemChoices.TEXTO,
        texto_original="Leia a fábula e responda às questões.",
    )
    envio = EnvioTrabalhos.objects.create(
        atividade=atividade,
        enviado_por=user,
        total_arquivos=3,
    )
    return escola, turma, aluno, atividade, envio


def test_pontos_atencao_menos_de_3_trabalhos_nao_chama_ia(auth_client, user, monkeypatch):
    _, _, aluno, atividade, envio = _criar_cenario_professor(user)

    # Cria apenas 2 trabalhos analisados com descricao_ia, 1 sem descricao_ia e 1 recebido.
    Trabalho.objects.create(
        envio=envio,
        atividade=atividade,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
        status=Trabalho.StatusChoices.ANALISADO,
        descricao_ia="Respostas curtas nas perguntas abertas.",
    )
    Trabalho.objects.create(
        envio=envio,
        atividade=atividade,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
        status=Trabalho.StatusChoices.ANALISADO,
        descricao_ia="Deixou a última questão de escrita em branco.",
    )
    Trabalho.objects.create(
        envio=envio,
        atividade=atividade,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
        status=Trabalho.StatusChoices.ANALISADO,
        descricao_ia="   ",
    )
    Trabalho.objects.create(
        envio=envio,
        atividade=atividade,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.PENDENTE,
        status=Trabalho.StatusChoices.RECEBIDO,
        descricao_ia="Texto de trabalho ainda não analisado.",
    )

    chamou_ia = False

    def _falso_gemini(*args, **kwargs):
        nonlocal chamou_ia
        chamou_ia = True
        return "{}"

    monkeypatch.setattr(
        "apps.pedagogico.services.pontos_atencao._pedir_ao_gemini",
        _falso_gemini,
    )

    total_atividades_antes = Atividade.objects.count()
    resp = auth_client.get(f"/api/alunos/{aluno.id}/pontos-atencao/")

    assert resp.status_code == 200
    dados = resp.json()
    assert dados["pontos"] == []
    assert dados["minimo_trabalhos"] == MINIMO_TRABALHOS_PONTOS_ATENCAO
    assert dados["disclaimer"] == DISCLAIMER
    assert dados["mensagem"] == MENSAGEM_MINIMO_TRABALHOS
    assert chamou_ia is False
    assert Atividade.objects.count() == total_atividades_antes


def test_pontos_atencao_3_ou_mais_trabalhos_anonimiza_payload_e_nao_cria_atividade(
    auth_client, user, monkeypatch
):
    _, _, aluno, atividade, envio = _criar_cenario_professor(user)

    descricoes = [
        (
            "Em 15/08/2026 na turma 3º Ano B, Helena Ribeiro (Responsável: Marcos Ribeiro) "
            "compreendeu a ideia central, mas omitiu conectivos nas frases longas."
        ),
        (
            "No dia 2026-08-22, Helena demonstrou boa leitura oral na turma 3º Ano B, "
            "porém deixou incompletas as respostas discursivas mais extensas."
        ),
        (
            "Helena Ribeiro organizou bem os tópicos iniciais, mas precisou de "
            "mediação passo a passo para concluir a produção escrita (laudo TDAH CID F90)."
        ),
    ]
    for desc in descricoes:
        Trabalho.objects.create(
            envio=envio,
            atividade=atividade,
            aluno=aluno,
            identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
            status=Trabalho.StatusChoices.ANALISADO,
            descricao_ia=desc,
        )

    prompts_recebidos: list[str] = []

    def _falso_gemini(conteudo: str, api_key: str, modelo: str) -> str:
        prompts_recebidos.append(conteudo)
        return json.dumps(
            {
                "pontos": [
                    {
                        "padrao": "Conclusão de respostas discursivas extensas",
                        "texto": (
                            "Foi observado ao longo das atividades que as respostas "
                            "discursivas mais longas costumam ficar parciais. Vale "
                            "conversar com a família sobre estratégias de etapas curtas."
                        ),
                        "base_pedagogica": (
                            "A divisão de enunciados escritos em roteiros curtos "
                            "favorece a organização textual e a autonomia gradual."
                        ),
                        "total_trabalhos": 3,
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "apps.pedagogico.services.pontos_atencao._pedir_ao_gemini",
        _falso_gemini,
    )

    total_atividades_antes = Atividade.objects.count()
    resp = auth_client.get(f"/api/alunos/{aluno.id}/pontos-atencao/")

    assert resp.status_code == 200
    dados = resp.json()
    assert dados["minimo_trabalhos"] == 3
    assert dados["disclaimer"] == DISCLAIMER
    assert "mensagem" not in dados
    assert len(dados["pontos"]) == 1

    ponto = dados["pontos"][0]
    assert ponto["padrao"] == "Conclusão de respostas discursivas extensas"
    assert "Foi observado" in ponto["texto"]
    assert "Vale conversar" in ponto["texto"]
    assert "roteiros curtos" in ponto["base_pedagogica"]
    assert ponto["total_trabalhos"] == 3

    # Nunca cria Atividade
    assert Atividade.objects.count() == total_atividades_antes

    # Verifica que o payload enviado ao Gemini não contém nome, responsável, turma, datas ou CID
    assert len(prompts_recebidos) == 1
    prompt_enviado = prompts_recebidos[0]
    for proibido in (
        "Helena",
        "Ribeiro",
        "Marcos",
        "3º Ano B",
        "15/08/2026",
        "2026-08-22",
        "TDAH",
        "F90",
        "Aluno Alfa",
    ):
        assert proibido.lower() not in prompt_enviado.lower()


def test_pontos_atencao_turma_alheia_retorna_404(auth_client, user):
    outra_escola = Escola.objects.create(nome="Outra Escola")
    outra_turma = Turma.objects.create(
        nome="4º Ano A",
        turno=Turma.TurnoChoices.TARDE,
        ano_letivo=2026,
        escola=outra_escola,
    )
    aluno_alheio = Aluno.objects.create(
        nome="Lucas Mendes",
        turma=outra_turma,
    )

    resp = auth_client.get(f"/api/alunos/{aluno_alheio.id}/pontos-atencao/")
    assert resp.status_code == 404


def test_pontos_atencao_erro_ia_retorna_502(auth_client, user, monkeypatch):
    _, _, aluno, atividade, envio = _criar_cenario_professor(user)

    for i in range(3):
        Trabalho.objects.create(
            envio=envio,
            atividade=atividade,
            aluno=aluno,
            identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
            status=Trabalho.StatusChoices.ANALISADO,
            descricao_ia=f"Observação pedagógica do trabalho {i + 1}.",
        )

    def _falhar_gemini(*args, **kwargs):
        raise LLMError("Serviço de IA temporariamente indisponível.")

    monkeypatch.setattr(
        "apps.pedagogico.services.pontos_atencao._pedir_ao_gemini",
        _falhar_gemini,
    )

    resp = auth_client.get(f"/api/alunos/{aluno.id}/pontos-atencao/")
    assert resp.status_code == 502
    assert "erro" in resp.json()


def test_api_root_inclui_aluno_pontos_atencao(auth_client):
    resp = auth_client.get("/api/")
    assert resp.status_code == 200
    assert "aluno-pontos-atencao" in resp.json()
