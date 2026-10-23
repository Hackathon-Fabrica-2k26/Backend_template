"""Função pura de anonimização: dados do relatório -> payload sem PII (LGPD art. 14).

Nada de nome real, CPF, responsável, cidade ou data de nascimento pode chegar
à LLM. O nome do aluno é trocado por um codinome e os campos sensíveis são
removidos antes do envio.
"""

import re

# Codinomes possíveis para o aluno.
CODINOMES = (
    "Aluno Alfa",
    "Aluno Beta",
    "Aluno Charlie",
    "Aluno Delta",
    "Aluno Echo",
    "Aluno Foxtrot",
    "Aluno Golf",
    "Aluno Hotel",
    "Aluno India",
    "Aluno Juliett",
    "Aluno Kilo",
    "Aluno Lima",
)

# Chaves identificáveis, excluídas do payload em qualquer nível da estrutura.
CHAVES_PII = frozenset(
    {
        "cpf",
        "email",
        "telefone",
        "endereco",
        "endereço",
        "cidade",
        "responsavel",
        "responsável",
        "responsaveis",
        "responsáveis",
        "data_nascimento",
        "data_de_nascimento",
        "nascimento",
    }
)

# 000.000.000-00, 00000000000, 000 000 000 00...
CPF_MD = re.compile(r"\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}")


# Menções de responsável no texto corrido: "Responsável: Nome" e variações.
RESPONSAVEL_MD = re.compile(r"(?i)(respons[aá]vel(is)?|pais|cuidador(a)?)\s*:\s*[^.;\n]+[.;]?\s*")


def anonimizar(dados: dict, nome_aluno: str = "") -> dict:
    """Devolve um payload sem dados pessoais, pronto para ir à LLM.

    - "nome_aluno" é substituído por um codinome (ex.: "Aluno Alfa") em todos
      os textos do payload.
    - Sequências que parecem CPF são removidas dos textos.
    - Chaves sensíveis são completamente removidas.
    - "aluno" (id do aluno) é removido do payload enviado à LLM.

    "dados" normalmente contém "aluno", "pontos_fortes", "desafios" e
    "contexto_turma"; "nome_aluno" é o nome real do aluno buscado pelo
    chamador (a função é pura e nunca o devolve).
    """
    codinome = _escolher_codinome(nome_aluno)
    payload = _limpar(dados, nome_aluno, codinome)
    if nome_aluno:
        payload["codinome_aluno"] = codinome
    return payload


def _escolher_codinome(nome_aluno: str) -> str:
    if not nome_aluno:
        return CODINOMES[0]
    return CODINOMES[sum(1 for letra in nome_aluno if letra.isalpha()) % len(CODINOMES)]


def _limpar(valor, nome_aluno: str, codinome: str):
    """Limpa recursivamente dicionários, listas e textos."""
    if isinstance(valor, dict):
        return {
            chave: _limpar(item, nome_aluno, codinome)
            for chave, item in valor.items()
            if chave not in CHAVES_PII and chave != "aluno"
        }
    if isinstance(valor, list):
        return [_limpar(item, nome_aluno, codinome) for item in valor]
    if isinstance(valor, str):
        texto = valor.replace(nome_aluno, codinome) if nome_aluno else valor
        texto = RESPONSAVEL_MD.sub("", texto)
        texto = CPF_MD.sub("", texto)
        # Vestígios de separadores deixados pela remoção do CPF.
        return re.sub(r"(?:[.,;:/|]\s*){2,}", "", texto).strip()
    return valor
