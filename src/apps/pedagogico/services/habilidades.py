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
