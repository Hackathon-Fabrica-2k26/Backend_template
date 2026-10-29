"""Habilidades do 1º ano do Ensino Fundamental (referência: BNCC) usadas para agrupar reforço.

A lista é fixa de propósito: com texto livre cada análise inventa um nome e os grupos
de reforço não fecham. A IA só pode devolver códigos desta lista.
"""

from typing import Any

LP = "Língua Portuguesa"
MA = "Matemática"

_LISTA = [
    ("LP-ALFABETO", LP, "Reconhecer e nomear as letras do alfabeto"),
    ("LP-CONSC-FONO", LP, "Perceber sons, sílabas e rimas das palavras"),
    ("LP-ESCR-PAL", LP, "Escrever palavras relacionando sons e letras"),
    ("LP-SEGM", LP, "Separar as palavras ao escrever frases"),
    ("LP-LEIT-PAL", LP, "Ler palavras simples"),
    ("LP-LEIT-FRASE", LP, "Ler e compreender frases curtas"),
    ("LP-INTERP", LP, "Localizar informações em textos curtos"),
    ("LP-PROD-TEXTO", LP, "Produzir frases e pequenos textos com apoio"),
    ("MA-NUM-ESCR", MA, "Ler e escrever números até 100"),
    ("MA-CONT", MA, "Contar e comparar quantidades"),
    ("MA-SEQ", MA, "Completar sequências e reconhecer padrões"),
    ("MA-ADI-SUB", MA, "Resolver adições e subtrações simples"),
    ("MA-PROB", MA, "Resolver problemas com enunciado curto"),
    ("MA-GEOM", MA, "Reconhecer figuras geométricas e posições no espaço"),
    ("MA-MEDIDAS", MA, "Comparar medidas e usar o calendário"),
]

HABILIDADES: list[dict[str, str]] = [
    {"codigo": codigo, "area": area, "nome": nome} for codigo, area, nome in _LISTA
]

CODIGOS_HABILIDADES = {h["codigo"] for h in HABILIDADES}
NOMES_HABILIDADES = {h["codigo"]: h["nome"] for h in HABILIDADES}


def filtrar_codigos(valor: Any, limite: int = 5) -> list[str]:
    """Mantém só códigos da lista, sem repetir e na ordem recebida (o resto é descartado)."""
    if not isinstance(valor, list):
        return []
    codigos: list[str] = []
    for item in valor:
        codigo = str(item).strip().upper() if item is not None else ""
        if codigo in CODIGOS_HABILIDADES and codigo not in codigos:
            codigos.append(codigo)
    return codigos[:limite]


def habilidades_para_prompt() -> str:
    return "\n".join(f"- {h['codigo']}: {h['nome']}" for h in HABILIDADES)


MIN_TRABALHOS_HABILIDADE = 2


def calcular_habilidades_aluno(aluno: Any) -> list[dict[str, Any]]:
    """Calcula a evolução do aluno por habilidade a partir dos seus trabalhos.

    Retorna para cada habilidade da lista fixa:
    - trabalhos_a_reforcar: quantos trabalhos mostraram como a reforçar
    - trabalhos_demonstrada: quantos trabalhos mostraram como demonstrada
    - em_reforco: True quando trabalhos_a_reforcar >= 2
    - ultimo_trabalho_em: data (created_at) do último trabalho com a habilidade
    """
    from apps.pedagogico.models import Trabalho

    trabalhos = (
        Trabalho.objects.filter(aluno=aluno, deleted__isnull=True)
        .exclude(status=Trabalho.StatusChoices.ERRO)
        .order_by("created_at")
    )

    contagem_reforcar: dict[str, int] = {}
    contagem_demonstrada: dict[str, int] = {}
    ultimo_trabalho: dict[str, Any] = {}

    for t in trabalhos:
        reforcar = set(filtrar_codigos(t.habilidades_a_reforcar, limite=15))
        demonstradas = set(filtrar_codigos(t.habilidades_demonstradas, limite=15))

        for cod in reforcar:
            contagem_reforcar[cod] = contagem_reforcar.get(cod, 0) + 1
            ultimo_trabalho[cod] = t.created_at

        for cod in demonstradas:
            contagem_demonstrada[cod] = contagem_demonstrada.get(cod, 0) + 1
            if cod not in ultimo_trabalho or t.created_at > ultimo_trabalho[cod]:
                ultimo_trabalho[cod] = t.created_at

    resultado = []
    for h in HABILIDADES:
        cod = h["codigo"]
        n_reforcar = contagem_reforcar.get(cod, 0)
        n_demonstrada = contagem_demonstrada.get(cod, 0)
        data_ult = ultimo_trabalho.get(cod)
        resultado.append(
            {
                "codigo": cod,
                "area": h["area"],
                "nome": h["nome"],
                "trabalhos_a_reforcar": n_reforcar,
                "trabalhos_demonstrada": n_demonstrada,
                "em_reforco": n_reforcar >= MIN_TRABALHOS_HABILIDADE,
                "ultimo_trabalho_em": data_ult.isoformat() if data_ult else None,
            }
        )
    return resultado


def calcular_habilidades_turma(turma: Any) -> list[dict[str, Any]]:
    """Calcula o resumo agregado da turma por habilidade.

    Apenas alunos com consentimento ativo são contabilizados (LGPD Art. 14).
    Retorna para cada habilidade a quantidade de alunos com em_reforco=True (>= 2 trabalhos).
    Nenhum dado pessoal ou nome de aluno é incluído na resposta agregada.
    """
    from apps.alunos.services import alunos_com_consentimento
    from apps.pedagogico.models import Trabalho

    alunos_turma = list(turma.alunos.filter(deleted__isnull=True, ativo=True))
    alunos_validos = list(alunos_com_consentimento(alunos_turma))

    if not alunos_validos:
        return [
            {
                "codigo": h["codigo"],
                "area": h["area"],
                "nome": h["nome"],
                "total_alunos_reforco": 0,
                "alunos_em_reforco": 0,
            }
            for h in HABILIDADES
        ]

    trabalhos = (
        Trabalho.objects.filter(aluno__in=alunos_validos, deleted__isnull=True)
        .exclude(status=Trabalho.StatusChoices.ERRO)
        .values_list("aluno_id", "habilidades_a_reforcar")
    )

    contagem_por_aluno: dict[int, dict[str, int]] = {}
    for aluno_id, codigos in trabalhos:
        for cod in set(filtrar_codigos(codigos, limite=15)):
            aluno_counts = contagem_por_aluno.setdefault(aluno_id, {})
            aluno_counts[cod] = aluno_counts.get(cod, 0) + 1

    alunos_reforco_por_hab: dict[str, int] = {}
    for aluno_counts in contagem_por_aluno.values():
        for cod, count in aluno_counts.items():
            if count >= MIN_TRABALHOS_HABILIDADE:
                alunos_reforco_por_hab[cod] = alunos_reforco_por_hab.get(cod, 0) + 1

    resultado = []
    for h in HABILIDADES:
        cod = h["codigo"]
        total = alunos_reforco_por_hab.get(cod, 0)
        resultado.append(
            {
                "codigo": cod,
                "area": h["area"],
                "nome": h["nome"],
                "total_alunos_reforco": total,
                "alunos_em_reforco": total,
            }
        )
    return resultado
