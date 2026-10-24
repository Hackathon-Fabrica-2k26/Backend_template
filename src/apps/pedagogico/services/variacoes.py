"""Serviço de agrupamento de perfis de apoio e geração de variações de atividade com IA.

LGPD / Diretrizes Pedagógicas:
- Agrupa os PerfilApoio ativos dos alunos da turma por necessidades pedagógicas
  semelhantes (no máximo 4 grupos adaptados + 1 versão geral 'prova_v1').
- O payload enviado à LLM é anonimizado (sem nome de aluno, sem responsável,
  sem CPF, sem datas) e limpo de qualquer menção a CID ou diagnóstico clínico.
- Os rótulos gerados são exclusivamente neutros ('prova_v1', 'prova_v2', ...),
  nunca contendo nome de aluno nem condição.
"""

import json
import re
from dataclasses import dataclass, field

from django.db import transaction
from safedelete.models import HARD_DELETE

from apps.alunos.models import Aluno
from apps.alunos.services import alunos_com_consentimento
from apps.pedagogico.models import Atividade, AtividadeVariacao, PerfilApoio, VariacaoAluno

from .anonimizar import anonimizar
from .llm import MODELO_PADRAO, LLMError, _extrair_json, _pedir_ao_gemini

MAX_GRUPOS_ADAPTADOS = 4

PROMPT_VARIACAO_ATIVIDADE = (
    "Você é um assistente pedagógico especialista em educação inclusiva.\n"
    "Adapte o texto da atividade abaixo considerando APENAS as necessidades "
    "pedagógicas, estratégias e interesses informados.\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "- Mantenha o objetivo de aprendizagem, TODAS as questões, a numeração e "
    "TODOS os números dos problemas exatamente como no original; adapte apenas a "
    "forma (linguagem, divisão em etapas, apoio visual, espaço para resposta).\n"
    "- O conteúdo NÃO pode citar nome de aluno, turma, condição, a palavra grupo nem "
    "dizer que é uma versão adaptada: quem recebe a folha não deve perceber diferença.\n"
    "- NUNCA faça diagnósticos médicos, psiquiátricos ou psicológicos.\n"
    "- NUNCA mencione CID, TDAH, autismo, TEA, dislexia, deficiência, "
    "transtornos ou qualquer condição clínica.\n"
    "Responda APENAS com um JSON válido, em português do Brasil, no formato:\n"
    '{\n  "conteudo": "texto completo da atividade adaptada",\n'
    '  "adaptacoes_feitas": ["o que foi mudado, em frases curtas para a professora"]\n}'
)

# Remove códigos CID (ex.: CID-10 F90.0, CID F84, CID11 6A02) e termos clínicos.
CID_MD = re.compile(
    r"\bCID(?:[-:\s]*1[01])?[-:\s]*[A-Z0-9]{2,5}(?:\.[A-Z0-9]{1,3})?\b",
    re.IGNORECASE,
)
TERMOS_CLINICOS_MD = re.compile(
    r"\b(tdah|autismo|autista|tea|dislexia|disl[eé]xico|discalculia|"
    r"transtorno[s]?|laudo[s]?|diagn[oó]stico[s]?|psiqui[aá]tric[oa]s?)\b",
    re.IGNORECASE,
)


@dataclass
class GrupoVariacao:
    necessidades: list[str] = field(default_factory=list)
    estrategias: list[str] = field(default_factory=list)
    alunos: list[Aluno] = field(default_factory=list)

    @property
    def tokens(self) -> set[str]:
        texto = " ".join(self.necessidades + self.estrategias).lower()
        return {t for t in re.findall(r"[a-zà-ú0-9]+", texto) if len(t) > 2}


def _limpar_texto_clinico(texto: str) -> str:
    sem_cid = CID_MD.sub("", texto)
    sem_clinico = TERMOS_CLINICOS_MD.sub("", sem_cid)
    return re.sub(r"\s{2,}", " ", sem_clinico).strip(" ,;:-")


def _limpar_lista_pedagogica(itens: list) -> list[str]:
    limpos: list[str] = []
    for item in itens or []:
        if not isinstance(item, str):
            continue
        limpo = _limpar_texto_clinico(item.strip())
        if limpo and limpo not in limpos:
            limpos.append(limpo)
    return limpos


def _similaridade(g1: GrupoVariacao, g2: GrupoVariacao) -> float:
    t1, t2 = g1.tokens, g2.tokens
    if not t1 or not t2:
        return 0.0
    intersecao = len(t1 & t2)
    uniao = len(t1 | t2)
    return intersecao / uniao if uniao else 0.0


def _perfil_dos_metadados(aluno: Aluno) -> tuple[list[str], list[str]]:
    """Sem PerfilApoio, usa os MetaDados do aluno: necessidades e estratégias, se houver,
    e as demais características como interesses a aproveitar. O perfil DISC não entra."""
    meta = getattr(aluno, "meta_dados", None)
    caracteristicas = getattr(meta, "caracteristicas", None) if meta else None
    if not isinstance(caracteristicas, dict) or not caracteristicas:
        return [], []

    necessidades = _limpar_lista_pedagogica(_como_lista(caracteristicas.get("necessidades")))
    estrategias = _limpar_lista_pedagogica(_como_lista(caracteristicas.get("estrategias")))
    for chave, valor in caracteristicas.items():
        if chave in ("necessidades", "estrategias") or valor in (None, "", [], {}):
            continue
        texto = ", ".join(map(str, valor)) if isinstance(valor, list) else str(valor)
        estrategias.extend(
            _limpar_lista_pedagogica([f"Aproveitar interesse/característica: {chave} ({texto})"])
        )
    return necessidades, estrategias


def _como_lista(valor) -> list:
    if isinstance(valor, list):
        return [str(v) for v in valor]
    if isinstance(valor, str) and valor.strip():
        return [valor]
    return []


def agrupar_perfis_apoio(
    alunos: list[Aluno],
    max_grupos: int = MAX_GRUPOS_ADAPTADOS,
) -> tuple[list[Aluno], list[GrupoVariacao]]:
    """Separa alunos sem perfil ativo (versão geral) e agrupa os com perfil em até max_grupos."""
    if not alunos:
        return [], []

    perfis_ativos = {
        p.aluno_id: p
        for p in PerfilApoio.objects.filter(
            aluno__in=alunos,
            ativo=True,
            deleted__isnull=True,
        )
    }

    alunos_geral: list[Aluno] = []
    grupos_por_chave: dict[tuple[str, ...], GrupoVariacao] = {}

    for aluno in alunos:
        perfil = perfis_ativos.get(aluno.id)
        if perfil is not None:
            necessidades = _limpar_lista_pedagogica(perfil.necessidades)
            estrategias = _limpar_lista_pedagogica(perfil.estrategias)
        else:
            necessidades, estrategias = _perfil_dos_metadados(aluno)

        if not necessidades and not estrategias:
            alunos_geral.append(aluno)
            continue

        chave = tuple(sorted(n.lower() for n in (necessidades or estrategias)))
        if chave not in grupos_por_chave:
            grupos_por_chave[chave] = GrupoVariacao(
                necessidades=list(necessidades),
                estrategias=list(estrategias),
                alunos=[aluno],
            )
        else:
            grupo = grupos_por_chave[chave]
            grupo.alunos.append(aluno)
            for n in necessidades:
                if n not in grupo.necessidades:
                    grupo.necessidades.append(n)
            for e in estrategias:
                if e not in grupo.estrategias:
                    grupo.estrategias.append(e)

    grupos = list(grupos_por_chave.values())

    # Se passar de max_grupos, mescla iterativamente os pares mais semelhantes.
    while len(grupos) > max_grupos:
        melhor_par = (0, 1)
        melhor_score = -1.0
        for i in range(len(grupos)):
            for j in range(i + 1, len(grupos)):
                score = _similaridade(grupos[i], grupos[j])
                if score > melhor_score:
                    melhor_score = score
                    melhor_par = (i, j)

        idx_a, idx_b = melhor_par
        base = grupos[idx_a]
        absorvido = grupos.pop(idx_b)
        base.alunos.extend(absorvido.alunos)
        for n in absorvido.necessidades:
            if n not in base.necessidades:
                base.necessidades.append(n)
        for e in absorvido.estrategias:
            if e not in base.estrategias:
                base.estrategias.append(e)

    return alunos_geral, grupos


def _anonimizar_payload_turma(payload: dict, alunos: list[Aluno]) -> dict:
    """Remove PII de todos os alunos e responsáveis da turma e limpa termos clínicos."""
    resultado = payload
    for aluno in alunos:
        nome_resp = aluno.responsavel.nome if getattr(aluno, "responsavel", None) else ""
        resultado = anonimizar(resultado, nome_aluno=aluno.nome, nome_responsavel=nome_resp)
        resultado.pop("codinome_aluno", None)
    if not alunos:
        resultado = anonimizar(resultado)
    return resultado


def _gerar_conteudo_adaptado(
    atividade: Atividade,
    grupo: GrupoVariacao,
    todos_alunos: list[Aluno],
    api_key: str,
    modelo: str,
) -> tuple[str, list[str]]:
    payload_bruto = {
        "texto_original": _limpar_texto_clinico(atividade.texto_original),
        "objetivo": _limpar_texto_clinico(atividade.objetivo or ""),
        "necessidades_pedagogicas": grupo.necessidades,
        "estrategias_pedagogicas": grupo.estrategias,
    }
    payload_limpo = _anonimizar_payload_turma(payload_bruto, todos_alunos)
    conteudo_prompt = (
        PROMPT_VARIACAO_ATIVIDADE + "\n\n" + json.dumps(payload_limpo, ensure_ascii=False)
    )

    try:
        resposta = _pedir_ao_gemini(conteudo_prompt, api_key, modelo)
        dados = _extrair_json(resposta)
    except LLMError:
        raise
    except Exception as erro:
        raise LLMError(
            "Não foi possível gerar as variações da atividade agora. Tente novamente em instantes."
        ) from erro

    if not isinstance(dados, dict):
        raise LLMError(
            "Não foi possível gerar as variações da atividade agora. Tente novamente em instantes."
        )

    conteudo_adaptado = str(
        dados.get("conteudo") or dados.get("texto_adaptado") or dados.get("texto") or ""
    ).strip()
    if not conteudo_adaptado:
        raise LLMError(
            "Não foi possível gerar as variações da atividade agora. Tente novamente em instantes."
        )

    adaptacoes = [
        _limpar_texto_clinico(str(a)).strip()
        for a in (dados.get("adaptacoes_feitas") or [])
        if isinstance(a, str) and a.strip()
    ]
    return _limpar_texto_clinico(conteudo_adaptado), adaptacoes


def gerar_variacoes_atividade(
    atividade: Atividade,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> list[AtividadeVariacao]:
    """Gera a versão geral (prova_v1) e até 4 versões adaptadas (prova_v2..vN) para a atividade."""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")

    # LGPD (Art. 14): só alunos com consentimento ativo passam pela IA.
    alunos_turma = alunos_com_consentimento(
        Aluno.objects.filter(
            turma=atividade.turma,
            ativo=True,
            deleted__isnull=True,
        )
        .select_related("responsavel", "meta_dados")
        .order_by("id")
    )

    alunos_geral, grupos_adaptados = agrupar_perfis_apoio(alunos_turma)

    # 1. Chama a LLM para todos os grupos antes de alterar o banco.
    conteudos_grupos: list[tuple[GrupoVariacao, str, list[str]]] = []
    for grupo in grupos_adaptados:
        conteudo_adaptado, adaptacoes = _gerar_conteudo_adaptado(
            atividade=atividade,
            grupo=grupo,
            todos_alunos=alunos_turma,
            api_key=api_key,
            modelo=modelo,
        )
        conteudos_grupos.append((grupo, conteudo_adaptado, adaptacoes))

    # 2. Persiste as variações e atribuições em transação atômica.
    with transaction.atomic():
        rascunhos = list(
            AtividadeVariacao.objects.filter(
                atividade=atividade,
                status=AtividadeVariacao.StatusChoices.RASCUNHO,
            )
        )
        for rascunho in rascunhos:
            VariacaoAluno.all_objects.filter(variacao=rascunho).delete(force_policy=HARD_DELETE)
            rascunho.delete(force_policy=HARD_DELETE)

        numeros_ocupados = set(
            AtividadeVariacao.all_objects.filter(atividade=atividade).values_list(
                "numero", flat=True
            )
        )

        def proximo_numero(inicial: int = 1) -> int:
            n = inicial
            while n in numeros_ocupados:
                n += 1
            numeros_ocupados.add(n)
            return n

        # Versão geral (prova_v1 se livre, ou reutiliza se já existir aprovada)
        variacao_geral = AtividadeVariacao.objects.filter(
            atividade=atividade,
            eh_geral=True,
        ).first()
        if variacao_geral is None:
            num_geral = proximo_numero(1)
            variacao_geral = AtividadeVariacao.objects.create(
                atividade=atividade,
                numero=num_geral,
                rotulo=f"prova_v{num_geral}",
                eh_geral=True,
                conteudo=atividade.texto_original,
                status=AtividadeVariacao.StatusChoices.RASCUNHO,
            )
        for aluno in alunos_geral:
            VariacaoAluno.objects.get_or_create(variacao=variacao_geral, aluno=aluno)

        # Versões adaptadas (prova_v2..N)
        for grupo, conteudo_adaptado, adaptacoes in conteudos_grupos:
            num_var = proximo_numero(2)
            variacao = AtividadeVariacao.objects.create(
                atividade=atividade,
                numero=num_var,
                rotulo=f"prova_v{num_var}",
                eh_geral=False,
                conteudo=conteudo_adaptado,
                adaptacoes_feitas=adaptacoes,
                status=AtividadeVariacao.StatusChoices.RASCUNHO,
            )
            for aluno in grupo.alunos:
                VariacaoAluno.objects.get_or_create(variacao=variacao, aluno=aluno)

        atividade.status = Atividade.StatusChoices.VARIACOES_GERADAS
        atividade.save(update_fields=["status", "updated_at"])

    return list(atividade.variacoes.order_by("numero"))
