"""Função pura de anonimização: dados do relatório -> payload sem PII (LGPD art. 14).

Nada de nome real, CPF, responsável, cidade ou data de nascimento pode chegar
à LLM. Matrícula também é removida. O nome do aluno é trocado por um codinome
e os campos sensíveis são removidos antes do envio.
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
# A comparação ignora maiúsculas e espaços ("Cidade" e "data de nascimento" casam).
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
        "matricula",
        "data_nascimento",
        "data_de_nascimento",
        "nascimento",
        "nome",
        "data",
    }
)

# 000.000.000-00, 00000000000, 000 000 000 00...
CPF_MD = re.compile(r"\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}")

# Datas completas no formato dd/mm/aaaa.
DATA_MD = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")


# Menções de responsável no texto corrido: "Responsável: Nome" e variações.
RESPONSAVEL_MD = re.compile(r"(?i)(respons[aá]vel(is)?|pais|cuidador(a)?)\s*:\s*[^.;\n]+[.;]?\s*")


def anonimizar(dados: dict, nome_aluno: str = "", nome_responsavel: str = "") -> dict:
    """Devolve um payload sem dados pessoais, pronto para ir à LLM.

    - "nome_aluno" é substituído por um codinome (ex.: "Aluno Alfa") em todos
      os textos do payload; o primeiro nome isolado também é trocado. A troca
      não diferencia maiúsculas de minúsculas.
    - "nome_responsavel", quando informado, é trocado por "o responsável".
    - Matrícula e demais identificadores são removidos das chaves do payload.
    - Datas (dd/mm/aaaa) e sequências que parecem CPF são removidas dos textos.
    - Chaves sensíveis são completamente removidas (comparação sem
      diferenciar maiúsculas de minúsculas).
    - "aluno" (id do aluno) é removido do payload enviado à LLM.

    "dados" normalmente contém "aluno", "pontos_fortes", "desafios" e
    "contexto_turma"; "nome_aluno" e "nome_responsavel" são os nomes reais
    buscados pelo chamador (a função é pura e nunca os devolve).
    """
    codinome = _escolher_codinome(nome_aluno)
    payload = _limpar(dados, nome_aluno, codinome, nome_responsavel)
    if nome_aluno:
        payload["codinome_aluno"] = codinome
    return payload


def _escolher_codinome(nome_aluno: str) -> str:
    if not nome_aluno:
        return CODINOMES[0]
    return CODINOMES[sum(1 for letra in nome_aluno if letra.isalpha()) % len(CODINOMES)]


def _trocar(texto: str, nome: str, troca: str) -> str:
    """Substitui o nome completo e o primeiro nome isolado, ignorando maiúsculas."""
    if not nome:
        return texto
    partes = nome.split()
    for occorrencia in (nome, partes[0] if partes else ""):
        if len(occorrencia) > 2:
            padrao = re.compile(rf"\b{re.escape(occorrencia)}\b", re.IGNORECASE)
            texto = padrao.sub(troca, texto)
    return texto


def _chave(chave: str) -> str:
    """Chave em minúsculas e sem espaços, para casar com CHAVES_PII."""
    return chave.lower().replace(" ", "_")


def _limpar(valor, nome_aluno: str, codinome: str, nome_responsavel: str = ""):
    """Limpa recursivamente dicionários, listas e textos."""
    if isinstance(valor, dict):
        return {
            chave: _limpar(item, nome_aluno, codinome, nome_responsavel)
            for chave, item in valor.items()
            if _chave(chave) not in CHAVES_PII and _chave(chave) != "aluno"
        }
    if isinstance(valor, list):
        return [_limpar(item, nome_aluno, codinome, nome_responsavel) for item in valor]
    if isinstance(valor, str):
        texto = RESPONSAVEL_MD.sub("", valor)
        texto = _trocar(texto, nome_aluno, codinome)
        texto = _trocar(texto, nome_responsavel, "o responsável")
        texto = DATA_MD.sub("", texto)
        texto = CPF_MD.sub("", texto)
        # Vestígios de separadores deixados pelas remoções.
        return re.sub(r"(?:[.,;:/|]\s*){2,}", "", texto).strip()
    return valor
