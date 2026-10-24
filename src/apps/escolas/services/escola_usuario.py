"""Descobre a escola e a configuração de IA do professor logado.

A IA usa a chave da ``Config`` da escola do professor. Professor criado pelo
``createsuperuser`` ou pelo admin pode estar sem escola; nesse caso a escola vem
das turmas dele ou, havendo uma única escola cadastrada, é ela. O vínculo é
gravado no usuário para as próximas chamadas.
"""

from apps.escolas.models import Config, Escola, Turma


def escola_do_usuario(user, salvar=True):
    escola = getattr(user, "escola", None)
    if escola is not None or not getattr(user, "is_authenticated", False):
        return escola

    turma = Turma.objects.filter(professores=user).select_related("escola").first()
    escola = turma.escola if turma else None
    if escola is None:
        escolas = list(Escola.objects.all()[:2])
        if len(escolas) == 1:
            escola = escolas[0]

    if escola is not None and salvar:
        user.escola = escola
        user.save(update_fields=["escola"])
    return escola


def config_ia_do_usuario(user, escola=None):
    escola = escola or escola_do_usuario(user)
    config = getattr(escola, "config", None) if escola else None
    if config is not None:
        return config

    # Escola sem Config ligada: com uma única Config com chave, usa e liga.
    configs = list(Config.objects.exclude(api_key="")[:2])
    if len(configs) != 1:
        return None
    config = configs[0]
    if escola is not None:
        escola.config = config
        escola.save(update_fields=["config"])
    return config
