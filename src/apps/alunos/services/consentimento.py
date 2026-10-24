"""Regras de consentimento do responsável (LGPD, Art. 14)."""

from django.db import transaction
from django.utils import timezone
from safedelete.models import HARD_DELETE

from apps.alunos.models import Aluno, Consentimento
from apps.alunos.models.consentimento import FINALIDADE_PADRAO


def tem_consentimento_ativo(aluno: Aluno) -> bool:
    return Consentimento.objects.filter(
        aluno=aluno, finalidade=FINALIDADE_PADRAO, revogado_em__isnull=True
    ).exists()


def alunos_com_consentimento(alunos) -> list[Aluno]:
    """Mantém apenas os alunos com consentimento ativo."""
    alunos = list(alunos)
    ativos = set(
        Consentimento.objects.filter(
            aluno__in=alunos, finalidade=FINALIDADE_PADRAO, revogado_em__isnull=True
        ).values_list("aluno_id", flat=True)
    )
    return [a for a in alunos if a.pk in ativos]


@transaction.atomic
def revogar_consentimento(consentimento: Consentimento) -> Consentimento:
    """Revoga o consentimento e apaga definitivamente os dados derivados da IA
    (PerfilApoio, Relatorio, Trabalho, atribuições de variação) e seus históricos.
    """
    from apps.pedagogico.models import PerfilApoio, Relatorio, Trabalho, VariacaoAluno

    consentimento.revogado_em = timezone.now()
    consentimento.save(update_fields=["revogado_em", "updated_at"])

    for modelo in (PerfilApoio, Relatorio, Trabalho, VariacaoAluno):
        ids = list(
            modelo.all_objects.filter(aluno_id=consentimento.aluno_id).values_list("pk", flat=True)
        )
        if not ids:
            continue
        modelo.all_objects.filter(pk__in=ids).delete(force_policy=HARD_DELETE)
        # Depois do delete: a exclusão definitiva grava um registro "-" no histórico.
        modelo.history.filter(id__in=ids).delete()
    return consentimento
