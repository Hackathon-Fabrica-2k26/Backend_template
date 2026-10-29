"""Testes da conversão de laudo em PerfilApoio em memória (B#44)."""

import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.alunos.models import Aluno, Consentimento
from apps.alunos.services.laudo import CID, DIAGNOSTICO, PROMPT_PERFIL, SISTEMA_PERFIL
from apps.escolas.models import Config, Escola, Turma
from apps.pedagogico.models import PerfilApoio

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


def _criar_cenario_laudo(user, *, nome_aluno="João da Silva", com_consentimento=True):
    config = Config.objects.create(
        api_key="chave-secreta-gemini-laudo",
        modelo="gemini-3.8-flash",
    )
    escola = Escola.objects.create(nome="Escola Horizonte", config=config)
    user.escola = escola
    user.save(update_fields=["escola"])

    turma = Turma.objects.create(
        nome="2º Ano A",
        turno=Turma.TurnoChoices.MANHA,
        ano_letivo=2026,
        escola=escola,
    )
    turma.professores.add(user)

    aluno = Aluno.objects.create(
        nome=nome_aluno,
        matricula="2026101",
        turma=turma,
    )
    if com_consentimento:
        Consentimento.objects.create(
            aluno=aluno,
            aceito_em=timezone.now(),
        )
    return escola, turma, aluno


def _laudo_pdf(nome="laudo.pdf", conteudo=PDF_BYTES):
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


def test_laudo_cria_perfil_ativo_desativa_anterior_e_confere_nome_sem_acento(
    auth_client, user, monkeypatch
):
    _, _, aluno = _criar_cenario_laudo(user, nome_aluno="João da Silva")
    perfil_antigo = PerfilApoio.objects.create(
        aluno=aluno,
        necessidades=["Necessidade antiga"],
        estrategias=["Estratégia antiga"],
        observacoes="Observação antiga.",
        ativo=True,
    )

    chamadas = []

    def fake_pedir_laudo(arquivo_bytes, mime, api_key, modelo):
        chamadas.append(
            {
                "arquivo_bytes": arquivo_bytes,
                "mime": mime,
                "api_key": api_key,
                "modelo": modelo,
            }
        )
        return json.dumps(
            {
                "nome_no_documento": "  JOAO DA SILVA  ",
                "necessidades": [
                    "instruções curtas, uma etapa por vez",
                    "apoio visual",
                    "tempo extra para conclusão das atividades",
                ],
                "estrategias": [
                    "exemplos prontos no quadro",
                    "dividir atividades em blocos curtos",
                ],
                "observacoes": "Responde bem a combinados visuais.",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        fake_pedir_laudo,
    )

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf()},
        format="multipart",
    )

    assert resp.status_code == 200
    dados = resp.json()
    assert dados["nome_conferiu"] is True
    assert dados["arquivo_excluido_em"]
    assert "nome_no_documento" not in dados
    assert "nome_no_documento" not in dados["perfil_apoio"]

    perfil_antigo.refresh_from_db()
    assert perfil_antigo.ativo is False

    perfis_ativos = list(PerfilApoio.objects.filter(aluno=aluno, ativo=True))
    assert len(perfis_ativos) == 1
    novo_perfil = perfis_ativos[0]
    assert novo_perfil.pk == dados["perfil_apoio"]["id"]
    assert novo_perfil.necessidades == [
        "instruções curtas, uma etapa por vez",
        "apoio visual",
        "tempo extra para conclusão das atividades",
    ]
    assert novo_perfil.estrategias == [
        "exemplos prontos no quadro",
        "dividir atividades em blocos curtos",
    ]
    assert novo_perfil.observacoes == "Responde bem a combinados visuais."

    assert len(chamadas) == 1
    assert chamadas[0]["arquivo_bytes"] == PDF_BYTES
    assert chamadas[0]["mime"] == "application/pdf"
    assert chamadas[0]["api_key"] == "chave-secreta-gemini-laudo"
    assert chamadas[0]["modelo"] == "gemini-3.8-flash"
    assert "nome_no_documento" in PROMPT_PERFIL
    assert "Nunca faça diagnóstico" in SISTEMA_PERFIL


def test_laudo_remove_itens_com_cid_diagnostico_remedio_medico_e_nome(
    auth_client, user, monkeypatch
):
    _, _, aluno = _criar_cenario_laudo(user, nome_aluno="Helena Ribeiro")

    def fake_pedir_laudo(arquivo_bytes, mime, api_key, modelo):
        return json.dumps(
            {
                "nome_no_documento": "Helena Ribeiro",
                "necessidades": [
                    "instruções curtas, uma etapa por vez",
                    "Quadro de TEA CID F84.0",
                    "Diagnóstico de TDAH com hiperatividade",
                    "Uso contínuo de risperidona 1mg",
                    "Relatório assinado pelo Dr. Carlos CRM 12345",
                    "Helena Ribeiro precisa de apoio visual",
                    "apoio visual com exemplos concretos",
                ],
                "estrategias": [
                    "pausas curtas entre blocos de exercícios",
                    "Adaptação para transtorno do espectro autista",
                    "Medicação ritalina antes do recreio",
                    "Acompanhamento com neurologista",
                ],
                "observacoes": (
                    "Engaja melhor em duplas colaborativas. "
                    "Possui laudo de dislexia F81.0 emitido pela psiquiatria. "
                    "Helena Ribeiro gosta de jogos matemáticos."
                ),
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        fake_pedir_laudo,
    )

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": SimpleUploadedFile("laudo.png", PNG_BYTES, content_type="image/png")},
        format="multipart",
    )

    assert resp.status_code == 200
    perfil = resp.json()["perfil_apoio"]
    assert perfil["necessidades"] == [
        "instruções curtas, uma etapa por vez",
        "apoio visual com exemplos concretos",
    ]
    assert perfil["estrategias"] == [
        "pausas curtas entre blocos de exercícios",
    ]
    assert perfil["observacoes"] == "Engaja melhor em duplas colaborativas."

    texto_total = " ".join([*perfil["necessidades"], *perfil["estrategias"], perfil["observacoes"]])
    assert not DIAGNOSTICO.search(texto_total)
    assert not CID.search(texto_total)
    assert "helena" not in texto_total.lower()
    assert "ribeiro" not in texto_total.lower()


def test_laudo_nome_conferiu_false_exige_confirmacao_e_salva_ao_confirmar(auth_client, user, monkeypatch):
    _, _, aluno = _criar_cenario_laudo(user, nome_aluno="Lucas Oliveira")

    def fake_pedir_laudo(arquivo_bytes, mime, api_key, modelo):
        return json.dumps(
            {
                "documento_valido": True,
                "nome_no_documento": "Mateus Souza",
                "necessidades": ["tempo extra"],
                "estrategias": ["enunciados objetivos"],
                "observacoes": "",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        fake_pedir_laudo,
    )

    # 1. Sem confirmação explícita -> 409 Conflict sem salvar perfil
    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf()},
        format="multipart",
    )

    assert resp.status_code == 409
    dados = resp.json()
    assert dados["confirmacao_necessaria"] is True
    assert "Mateus" not in json.dumps(dados, ensure_ascii=False)
    assert not PerfilApoio.objects.filter(aluno=aluno).exists()

    # 2. Reenvio com confirmar_nome=True -> 200 OK e perfil criado
    resp_confirmado = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf(), "confirmar_nome": True},
        format="multipart",
    )

    assert resp_confirmado.status_code == 200
    dados_confirmados = resp_confirmado.json()
    assert dados_confirmados["nome_conferiu"] is False
    assert "Mateus" not in json.dumps(dados_confirmados, ensure_ascii=False)
    assert PerfilApoio.objects.filter(aluno=aluno, ativo=True).exists()


def test_laudo_documento_invalido_retorna_422_e_nao_altera_perfis(auth_client, user, monkeypatch):
    _, _, aluno = _criar_cenario_laudo(user, nome_aluno="Lucas Oliveira")
    perfil_existente = PerfilApoio.objects.create(
        aluno=aluno,
        necessidades=["Necessidade anterior"],
        estrategias=["Estratégia anterior"],
        observacoes="Obs anterior",
        ativo=True,
    )

    def fake_pedir_laudo(arquivo_bytes, mime, api_key, modelo):
        return json.dumps(
            {
                "documento_valido": False,
                "tipo_documento": "boletim de urna",
                "motivo": "O documento enviado é um boletim de urna eleitoral.",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        fake_pedir_laudo,
    )

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf()},
        format="multipart",
    )

    assert resp.status_code == 422
    dados = resp.json()
    assert "não parece um laudo" in dados["erro"]
    assert dados["tipo_documento"] == "boletim de urna"
    assert dados["motivo"] == "O documento enviado é um boletim de urna eleitoral."

    # Perfil anterior continua ativo e intacto, e nenhum novo perfil foi criado
    perfil_existente.refresh_from_db()
    assert perfil_existente.ativo is True
    assert PerfilApoio.objects.filter(aluno=aluno).count() == 1


def test_laudo_nao_salva_arquivo_em_disco(auth_client, user, monkeypatch, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, _, aluno = _criar_cenario_laudo(user)

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        lambda *args, **kwargs: json.dumps(
            {
                "nome_no_documento": aluno.nome,
                "necessidades": ["apoio visual"],
                "estrategias": ["etapas numeradas"],
                "observacoes": "",
            }
        ),
    )

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf("laudo_confidencial.pdf")},
        format="multipart",
    )

    assert resp.status_code == 200
    arquivos_salvos = list(Path(tmp_path).rglob("*"))
    assert arquivos_salvos == []


def test_laudo_aluno_alheio_retorna_404(auth_client, user, monkeypatch):
    escola_alheia = Escola.objects.create(nome="Outra Escola")
    turma_alheia = Turma.objects.create(
        nome="4º Ano C",
        turno=Turma.TurnoChoices.TARDE,
        ano_letivo=2026,
        escola=escola_alheia,
    )
    aluno_alheio = Aluno.objects.create(nome="Aluno Alheio", turma=turma_alheia)
    Consentimento.objects.create(aluno=aluno_alheio, aceito_em=timezone.now())

    chamou_ia = False

    def fake_pedir_laudo(*args, **kwargs):
        nonlocal chamou_ia
        chamou_ia = True
        return "{}"

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        fake_pedir_laudo,
    )

    resp = auth_client.post(
        f"/api/alunos/{aluno_alheio.id}/laudo/",
        {"arquivo": _laudo_pdf()},
        format="multipart",
    )

    assert resp.status_code == 404
    assert chamou_ia is False


def test_laudo_sem_consentimento_retorna_403(auth_client, user, monkeypatch):
    _, _, aluno = _criar_cenario_laudo(user, com_consentimento=False)

    chamou_ia = False

    def fake_pedir_laudo(*args, **kwargs):
        nonlocal chamou_ia
        chamou_ia = True
        return "{}"

    monkeypatch.setattr(
        "apps.alunos.services.laudo._pedir_laudo_ao_gemini",
        fake_pedir_laudo,
    )

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf()},
        format="multipart",
    )

    assert resp.status_code == 403
    assert "consentimento" in resp.json()["erro"].lower()
    assert chamou_ia is False


def test_laudo_tipo_invalido_retorna_400(auth_client, user):
    _, _, aluno = _criar_cenario_laudo(user)
    arquivo_txt = SimpleUploadedFile("laudo.txt", b"conteudo texto", content_type="text/plain")

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": arquivo_txt},
        format="multipart",
    )

    assert resp.status_code == 400
    assert "arquivo" in resp.json()


def test_laudo_erro_ia_retorna_502_e_loga_sem_chave(auth_client, user, monkeypatch, caplog):
    _, _, aluno = _criar_cenario_laudo(user)

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.models = self

        def generate_content(self, **kwargs):
            raise RuntimeError("Quota exceeded on Gemini API")

    monkeypatch.setattr("google.genai.Client", FakeClient)

    resp = auth_client.post(
        f"/api/alunos/{aluno.id}/laudo/",
        {"arquivo": _laudo_pdf()},
        format="multipart",
    )

    assert resp.status_code == 502
    assert "erro" in resp.json()
    assert "chave-secreta-gemini-laudo" not in caplog.text
    assert "RuntimeError" in caplog.text
