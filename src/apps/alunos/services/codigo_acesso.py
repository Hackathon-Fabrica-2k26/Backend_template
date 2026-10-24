"""Código de acesso do aluno e token de sessão do responsável (B#42)."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.utils import timezone

from apps.alunos.models import Aluno, AlunoResponsavel, CodigoAcessoAluno, Responsavel

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO = 8
VALIDADE_CODIGO = timedelta(days=7)
VALIDADE_TOKEN_SEGUNDOS = 24 * 60 * 60
SALT_TOKEN = "responsavel-acesso"


class CodigoInvalido(Exception):
    """Código inexistente, expirado, usado ou revogado (mensagem única de propósito)."""


def normalizar_codigo(codigo: str) -> str:
    return "".join(str(codigo).split()).replace("-", "").upper()


def hash_codigo(codigo: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), normalizar_codigo(codigo).encode(), hashlib.sha256
    ).hexdigest()


def revogar_codigos_ativos(aluno: Aluno) -> int:
    return CodigoAcessoAluno.objects.filter(
        aluno=aluno, usado_em__isnull=True, revogado_em__isnull=True
    ).update(revogado_em=timezone.now())


@transaction.atomic
def gerar_codigo(aluno: Aluno, professor) -> tuple[str, CodigoAcessoAluno]:
    """Revoga os códigos pendentes e gera um novo. O texto em claro só existe aqui."""
    revogar_codigos_ativos(aluno)
    agora = timezone.now()
    while True:
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_CODIGO))
        if not CodigoAcessoAluno.all_objects.filter(codigo_hash=hash_codigo(codigo)).exists():
            break
    registro = CodigoAcessoAluno.objects.create(
        aluno=aluno,
        codigo_hash=hash_codigo(codigo),
        gerado_por=professor,
        gerado_em=agora,
        expira_em=agora + VALIDADE_CODIGO,
    )
    return codigo, registro


@transaction.atomic
def vincular_responsavel(
    codigo: str, nome: str, email: str = "", parentesco: str = ""
) -> tuple[Responsavel, Aluno]:
    registro = (
        CodigoAcessoAluno.objects.select_for_update()
        .select_related("aluno")
        .filter(codigo_hash=hash_codigo(codigo))
        .first()
    )
    if registro is None or not registro.esta_valido:
        raise CodigoInvalido
    aluno = registro.aluno

    responsavel = None
    if email:
        responsavel = Responsavel.objects.filter(email__iexact=email).order_by("pk").first()
    if responsavel is None:
        responsavel = Responsavel.objects.create(nome=nome, email=email)

    vinculo = AlunoResponsavel.objects.filter(aluno=aluno, responsavel=responsavel).first()
    if vinculo is None:
        AlunoResponsavel.objects.create(aluno=aluno, responsavel=responsavel, parentesco=parentesco)
    elif parentesco and not vinculo.parentesco:
        vinculo.parentesco = parentesco
        vinculo.save(update_fields=["parentesco", "updated_at"])

    registro.usado_em = timezone.now()
    registro.save(update_fields=["usado_em", "updated_at"])
    return responsavel, aluno


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=SALT_TOKEN)


def emitir_token(responsavel: Responsavel, aluno: Aluno) -> str:
    return _signer().sign(f"{responsavel.pk}:{aluno.pk}")


@dataclass(frozen=True)
class SessaoResponsavel:
    responsavel: Responsavel
    aluno: Aluno


def validar_token(token: str) -> SessaoResponsavel | None:
    """Valida assinatura, 24h de validade e se o vínculo ainda existe."""
    try:
        valor = _signer().unsign(token, max_age=VALIDADE_TOKEN_SEGUNDOS)
        responsavel_id, aluno_id = (int(parte) for parte in valor.split(":"))
    except (BadSignature, SignatureExpired, ValueError):
        return None
    vinculo = (
        AlunoResponsavel.objects.select_related("responsavel", "aluno")
        .filter(responsavel_id=responsavel_id, aluno_id=aluno_id)
        .first()
    )
    if vinculo is None:
        return None
    return SessaoResponsavel(responsavel=vinculo.responsavel, aluno=vinculo.aluno)
