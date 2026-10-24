# pyright: reportIncompatibleVariableOverride=false
import os
from typing import cast

import factory
from django.contrib.auth import get_user_model

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.items.models import Item
from apps.pedagogico.models import (
    Atividade,
    AtividadeVariacao,
    EnvioTrabalhos,
    PerfilApoio,
    Relatorio,
    Trabalho,
    VariacaoAluno,
)

SENHA = os.getenv("SEED_DEMO_PASSWORD") or "Senha-forte-123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    matricula = factory.declarations.Sequence(lambda n: f"TESTE{n:06d}")
    email = factory.declarations.Sequence(lambda n: f"usuario{n}@example.com")
    name = factory.declarations.Sequence(lambda n: f"Usuário {n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.setdefault("password", SENHA)
        return model_class.objects.create_user(*args, **kwargs)


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    title = factory.declarations.Sequence(lambda n: f"Item {n}")
    owner = factory.declarations.SubFactory(UserFactory)


class ConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Config

    api_key = factory.declarations.Sequence(lambda n: f"key-{n}")
    modelo = factory.declarations.Sequence(lambda n: f"modelo-{n}")
    campos_form = factory.declarations.LazyFunction(dict)


class EscolaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Escola

    nome = factory.declarations.Sequence(lambda n: f"Escola {n}")
    endereco = factory.declarations.Sequence(lambda n: f"Rua {n}")
    config = factory.declarations.SubFactory(ConfigFactory)


class TurmaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Turma
        skip_postgeneration_save = True

    nome = factory.declarations.Sequence(lambda n: f"Turma {n}")
    escola = factory.declarations.SubFactory(EscolaFactory)

    @factory.declarations.PostGeneration
    def professores(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            turma = cast(Turma, self)
            for professor in extracted:
                turma.professores.add(professor)


class ResponsavelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Responsavel

    nome = factory.declarations.Sequence(lambda n: f"Responsável {n}")
    email = factory.declarations.Sequence(lambda n: f"responsavel{n}@example.com")
    cpf = factory.declarations.Sequence(lambda n: f"1234567890{n % 9 + 1}")
    telefone = factory.declarations.Sequence(lambda n: f"1198765432{n % 9 + 1}")
    endereco = factory.declarations.Sequence(lambda n: f"Endereço {n}")


class MetaDadosFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetaDados

    perfil_disc = factory.declarations.Iterator(["D", "I", "S", "C"])
    caracteristicas = factory.declarations.LazyAttribute(lambda o: {})


class AlunoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Aluno

    nome = factory.declarations.Sequence(lambda n: f"Aluno {n}")
    turma = factory.declarations.SubFactory(TurmaFactory)


class AtividadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Atividade

    turma = factory.declarations.SubFactory(TurmaFactory)
    criada_por = factory.declarations.SubFactory(UserFactory)
    titulo = factory.declarations.Sequence(lambda n: f"Atividade {n}")
    origem = Atividade.OrigemChoices.TEXTO
    texto_original = factory.declarations.Sequence(lambda n: f"Texto original {n}")
    objetivo = factory.declarations.Sequence(lambda n: f"Objetivo {n}")
    status = Atividade.StatusChoices.RASCUNHO


class AtividadeVariacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AtividadeVariacao

    atividade = factory.declarations.SubFactory(AtividadeFactory)
    numero = factory.declarations.Sequence(lambda n: n + 1)
    rotulo = factory.declarations.Sequence(lambda n: f"prova_v{n + 1}")
    eh_geral = False
    conteudo = factory.declarations.Sequence(lambda n: f"Conteúdo da variação {n + 1}")
    status = AtividadeVariacao.StatusChoices.RASCUNHO


class VariacaoAlunoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VariacaoAluno

    variacao = factory.declarations.SubFactory(AtividadeVariacaoFactory)
    aluno = factory.declarations.SubFactory(AlunoFactory)


class PerfilApoioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PerfilApoio

    aluno = factory.declarations.SubFactory(AlunoFactory)
    necessidades = factory.declarations.LazyFunction(lambda: ["Apoio visual"])
    estrategias = factory.declarations.LazyFunction(lambda: ["Enunciados curtos"])
    observacoes = ""
    ativo = True


class EnvioTrabalhosFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EnvioTrabalhos

    atividade = factory.declarations.SubFactory(AtividadeFactory)
    enviado_por = factory.declarations.SubFactory(UserFactory)
    total_arquivos = 1


class TrabalhoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Trabalho

    envio = factory.declarations.SubFactory(EnvioTrabalhosFactory)
    atividade = factory.declarations.LazyAttribute(lambda o: o.envio.atividade)
    aluno = None
    variacao = None
    nome_lido = "Aluno Teste"
    confianca_nome = 0.85
    identificacao = Trabalho.IdentificacaoChoices.PENDENTE
    descricao_ia = "Descrição gerada pela IA"
    dados_analise = factory.declarations.LazyFunction(dict)
    status = Trabalho.StatusChoices.ANALISADO


class RelatorioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Relatorio

    aluno = factory.declarations.SubFactory(AlunoFactory)
    atividade = None
    dados = factory.declarations.LazyFunction(dict)
