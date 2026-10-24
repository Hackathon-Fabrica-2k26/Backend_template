"""Serviço sob demanda de geração de pontos de atenção do aluno com IA.

Regras de negócio e LGPD (B#45):
- Calculado sob demanda (não cria model nem migração, e NUNCA cria Atividade).
- Só consulta a IA se o aluno tiver pelo menos 3 Trabalhos analisados
  (status='analisado') com `descricao_ia` preenchida.
- Com menos de 3 trabalhos analisados, devolve `pontos: []`, `disclaimer`,
  `minimo_trabalhos: 3` e `mensagem: "São necessários pelo menos 3 trabalhos analisados."`.
- Envia ao Gemini SOMENTE a lista de textos `descricao_ia` anonimizados
  (sem nome do aluno, sem responsável, sem nome da turma, sem datas e sem CPF).
- Solicita padrões pedagógicos observados em linguagem cautelosa
  ("foi observado...", "vale conversar..."), com base pedagógica,
  proibindo estritamente qualquer diagnóstico clínico, CID ou condição de saúde.
"""

import json
import re

from apps.alunos.models import Aluno
from apps.pedagogico.models import Trabalho

from .anonimizar import anonimizar
from .llm import (
    DISCLAIMER,
    MODELO_PADRAO,
    LLMError,
    _extrair_json,
    _pedir_ao_gemini,
)

MINIMO_TRABALHOS_PONTOS_ATENCAO = 3
MENSAGEM_MINIMO_TRABALHOS = "São necessários pelo menos 3 trabalhos analisados."

# Expressões regulares para remover códigos CID, termos clínicos e datas residuais.
CID_RE = re.compile(r"\b(?:CID(?:-\d+)?\s*)?[A-Z]\d{2}(?:\.\d+)?\b", re.IGNORECASE)
DATA_CURTA_RE = re.compile(r"\b(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b")
TERMOS_CLINICOS_RE = re.compile(
    r"\b("
    r"tdah|tea|autismo|autista|dislexia|disl[eé]xic[oa]|discalculia|disgrafia|"
    r"tod|transtorno[s]?|s[ií]ndrome[s]?|defici[eê]ncia[s]?|laudo[s]?|"
    r"diagn[oó]stico[s]?|psiqui[aá]tric[oa][s]?|neurol[oó]gic[oa][s]?|"
    r"medica[cç][aã]o|medicamento[s]?|ritalina|superdota[cç][aã]o|altas\s+habilidades"
    r")\b",
    re.IGNORECASE,
)

PROMPT_PONTOS_ATENCAO = (
    "Você receberá apenas descrições pedagógicas anonimizadas de trabalhos "
    "realizados por um mesmo estudante ao longo de diferentes atividades.\n"
    "Identifique padrões pedagógicos recorrentes observados nesses trabalhos "
    "para apoiar a professora em uma conversa construtiva com a família.\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use SEMPRE linguagem cautelosa de padrão observado (por exemplo: "
    "'Foi observado ao longo das atividades...', 'Vale conversar sobre...').\n"
    "2. Apresente uma base pedagógica clara e construtiva para cada ponto.\n"
    "3. NUNCA emita diagnóstico médico, psicológico ou clínico, NUNCA cite "
    "código CID, transtornos, síndromes, laudos médicos, medicação ou "
    "qualquer condição de saúde.\n"
    "4. Não invente nomes, datas ou turmas.\n"
    "5. Não sugira nem crie novas atividades escolares automaticamente.\n\n"
    "Responda APENAS com um JSON válido, sem texto adicional, no formato:\n"
    "{\n"
    '  "pontos": [\n'
    "    {\n"
    '      "padrao": "Resumo curto do padrão pedagógico observado",\n'
    '      "texto": "Foi observado ... Vale conversar ...",\n'
    '      "base_pedagogica": "Fundamentação pedagógica prática e acolhedora",\n'
    '      "total_trabalhos": 3\n'
    "    }\n"
    "  ]\n"
    "}"
)


def _limpar_texto_clinico(texto: str) -> str:
    """Remove menções a CID e termos clínicos/diagnósticos de uma string."""
    limpo = CID_RE.sub("", texto)
    limpo = TERMOS_CLINICOS_RE.sub("", limpo)
    limpo = re.sub(r"\s{2,}", " ", limpo)
    limpo = re.sub(r"(?:[,;:/-]\s*){2,}", "", limpo)
    return limpo.strip(" ,;:-")


def _anonimizar_descricao_trabalho(
    descricao: str,
    nome_aluno: str,
    nome_responsavel: str,
    nome_turma: str,
) -> str:
    """Anonimiza a descrição de um trabalho removendo nome, turma, datas e termos clínicos."""
    anon = anonimizar(
        {"descricao": descricao},
        nome_aluno=nome_aluno,
        nome_responsavel=nome_responsavel,
    )
    texto = str(anon.get("descricao") or "")
    codinome = str(anon.get("codinome_aluno") or "")
    if codinome:
        texto = re.sub(rf"\b{re.escape(codinome)}\b", "o estudante", texto, flags=re.IGNORECASE)

    if nome_turma and len(nome_turma.strip()) > 1:
        texto = re.sub(
            rf"\b{re.escape(nome_turma.strip())}\b",
            "",
            texto,
            flags=re.IGNORECASE,
        )

    texto = DATA_CURTA_RE.sub("", texto)
    texto = _limpar_texto_clinico(texto)
    return texto.strip()


def gerar_pontos_atencao_aluno(
    aluno: Aluno,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> dict:
    """Calcula sob demanda os pontos de atenção do aluno a partir dos trabalhos analisados."""
    trabalhos_qs = (
        Trabalho.objects.filter(
            aluno=aluno,
            status=Trabalho.StatusChoices.ANALISADO,
            deleted__isnull=True,
        )
        .exclude(descricao_ia="")
        .order_by("created_at", "id")
    )

    nome_aluno = aluno.nome or ""
    nome_responsavel = aluno.responsavel.nome if getattr(aluno, "responsavel", None) else ""
    nome_turma = aluno.turma.nome if getattr(aluno, "turma", None) else ""

    descricoes_brutas = [
        t.descricao_ia.strip() for t in trabalhos_qs if (t.descricao_ia or "").strip()
    ]

    if len(descricoes_brutas) < MINIMO_TRABALHOS_PONTOS_ATENCAO:
        return {
            "pontos": [],
            "disclaimer": DISCLAIMER,
            "minimo_trabalhos": MINIMO_TRABALHOS_PONTOS_ATENCAO,
            "mensagem": MENSAGEM_MINIMO_TRABALHOS,
        }

    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")

    descricoes_anonimizadas = [
        _anonimizar_descricao_trabalho(
            descricao=desc,
            nome_aluno=nome_aluno,
            nome_responsavel=nome_responsavel,
            nome_turma=nome_turma,
        )
        for desc in descricoes_brutas
    ]
    descricoes_anonimizadas = [d for d in descricoes_anonimizadas if d]

    if len(descricoes_anonimizadas) < MINIMO_TRABALHOS_PONTOS_ATENCAO:
        return {
            "pontos": [],
            "disclaimer": DISCLAIMER,
            "minimo_trabalhos": MINIMO_TRABALHOS_PONTOS_ATENCAO,
            "mensagem": MENSAGEM_MINIMO_TRABALHOS,
        }

    total_analisados = len(descricoes_anonimizadas)
    payload_ia = {
        "total_trabalhos_analisados": total_analisados,
        "descricoes_trabalhos": descricoes_anonimizadas,
    }
    conteudo = PROMPT_PONTOS_ATENCAO + "\n\n" + json.dumps(payload_ia, ensure_ascii=False)

    try:
        resposta = _pedir_ao_gemini(conteudo, api_key, modelo)
        dados = _extrair_json(resposta)
    except LLMError:
        raise
    except Exception as erro:
        raise LLMError(
            "Não foi possível gerar os pontos de atenção agora. Tente novamente em instantes."
        ) from erro

    if not isinstance(dados, dict) or not isinstance(dados.get("pontos"), list):
        raise LLMError(
            "Não foi possível gerar os pontos de atenção agora. Tente novamente em instantes."
        )

    pontos_limpos: list[dict] = []
    for item in dados.get("pontos", []):
        if not isinstance(item, dict):
            continue
        padrao = _limpar_texto_clinico(str(item.get("padrao") or "").strip())
        texto = _limpar_texto_clinico(str(item.get("texto") or "").strip())
        base_pedagogica = _limpar_texto_clinico(str(item.get("base_pedagogica") or "").strip())
        if not padrao or not texto or not base_pedagogica:
            continue

        total_item = item.get("total_trabalhos", total_analisados)
        try:
            total_int = int(total_item)
        except (TypeError, ValueError):
            total_int = total_analisados
        if total_int < 1 or total_int > total_analisados:
            total_int = total_analisados

        pontos_limpos.append(
            {
                "padrao": padrao,
                "texto": texto,
                "base_pedagogica": base_pedagogica,
                "total_trabalhos": total_int,
            }
        )

    return {
        "pontos": pontos_limpos,
        "disclaimer": DISCLAIMER,
        "minimo_trabalhos": MINIMO_TRABALHOS_PONTOS_ATENCAO,
    }
