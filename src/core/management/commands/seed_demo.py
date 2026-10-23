"""Dados demo para a apresentação.

Uso: ``python src/manage.py seed_demo`` (ou ``pdm run seed-demo``).

Idempotente: rodar de novo não duplica escolas, turmas, alunos, professores
nem relatórios. Os dados são claramente fictícios e servem só para a
apresentação; credenciais do professor demo estão documentadas no README
(definíveis por ``SEED_DEMO_PASSWORD`` / ``SEED_DEMO_API_KEY``).
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.pedagogico.models import Relatorio

SENHA_PROFESSOR_PADRAO = "demo-senha-123"
API_KEY_PADRAO = "demo-api-key-troque-no-admin"
EMAIL_PROFESSOR = "professor@demo.com"
NOME_ESCOLA = "Escola Marsupi Demo"

# Relatorio.dados segue o contrato da seção 6 de docs/contexto_projeto_ia.md.
RELATORIOS_DEMO = {
    "Aluno Alfa": {
        "profile_summary": (
            "Perfil com alto raciocínio visual e forte motivação por temáticas exploratórias,"
            " necessitando de suporte para autorregulação motora e previsibilidade sensorial."
        ),
        "radar_metrics": {
            "foco_sustentado": 40,
            "raciocinio_visual": 90,
            "interacao_social": 80,
            "regulacao_sensorial": 50,
            "coordenacao_fina": 60,
        },
        "strengths": [
            "Memória fotográfica e facilidade para associar símbolos visuais",
            "Empatia e disposição para dinâmicas colaborativas",
        ],
        "support_needs": [
            "Pausas ativas a cada 10 a 15 minutos para regulação física",
            "Uso de pistas visuais de rotina para diminuir ansiedade",
        ],
        "adapted_activities": [
            {
                "title": "Missão Espacial: Caligrafia nas Estrelas",
                "objective": "Trabalhar coordenação motora usando o hiperfoco em planetas",
                "duration": "15 minutos",
                "instructions": (
                    "O aluno traça constelações em folhas com guias pontilhadas antes da"
                    " escrita formal."
                ),
                "inclusive_tip": (
                    "Permitir que a turma inteira faça a 'missão', integrando a criança sem"
                    " estigmatizá-la."
                ),
            }
        ],
        "autonomy_coaching_tip": (
            "Professor, você notou se o aluno reage melhor quando o comando é falado ou quando"
            " há um desenho no quadro? Experimente pedir à IA: 'Como adaptar a instrução de"
            " matemática usando ícones visuais?'"
        ),
    },
    "Aluno Delta": {
        "profile_summary": (
            "Perfil dominante, lidera naturalmente os colegas e prefere metas curtas e"
            " objetivas; demonstra frustração em atividades longas e repetitivas."
        ),
        "radar_metrics": {
            "foco_sustentado": 65,
            "raciocinio_visual": 70,
            "interacao_social": 85,
            "regulacao_sensorial": 60,
            "coordenacao_fina": 45,
        },
        "strengths": [
            "Tomada de iniciativa rapidamente nas atividades em grupo",
            "Comunicação assertiva com colegas e professores",
        ],
        "support_needs": [
            "Dividir tarefas longas em desafios menores com metas visíveis",
            "Reforço positivo para sofrer menos quando comete erros",
        ],
        "adapted_activities": [
            {
                "title": "Camarada da Turma: Desafio Relâmpago",
                "objective": "Canalizar a liderança em um desafio curto de resolução de problemas",
                "duration": "10 minutos",
                "instructions": (
                    "O aluno conduz um time de 3 colegas em um quebra-cabeça com cartas, com"
                    " rodada nova a cada 2 minutos."
                ),
                "inclusive_tip": (
                    "Rodar o papel de líder entre todos, para evitar que o mesmo aluno"
                    " centralize as decisões."
                ),
            }
        ],
        "autonomy_coaching_tip": (
            "Professor, tente oferecer duas opções de desafio e deixe o aluno escolher antes"
            " de começar; alunos com perfil dominante aderem melhor quando sentem que"
            " decidiram."
        ),
    },
}

# 6 alunos fictícios, codinomes pedagógicos em vez de nomes reais (LGPD).
ALUNOS_DEMO = [
    {
        "nome": "Aluno Alfa",
        "turma": "Turma A",
        "perfil_disc": "I",
        "caracteristicas": {"hobby": "astronomia", "memoria": "visual"},
        "responsavel": {
            "nome": "Ana Demo",
            "email": "ana.demo@example.com",
            "telefone": "11991110001",
            "cpf": "12345678901",
            "endereco": "Rua Demo, 1",
        },
    },
    {
        "nome": "Aluno Beta",
        "turma": "Turma A",
        "perfil_disc": "S",
        "caracteristicas": {"rotina": "estável", "leitura": "assídua"},
        "responsavel": {
            "nome": "Bruno Demo",
            "email": "bruno.demo@example.com",
            "telefone": "11991110002",
            "cpf": "12345678902",
            "endereco": "Rua Demo, 2",
        },
    },
    {
        "nome": "Aluno Gama",
        "turma": "Turma A",
        "perfil_disc": "C",
        "caracteristicas": {"detalhe": "precisão", "jogo": "xadrez"},
        "responsavel": {
            "nome": "Carla Demo",
            "email": "carla.demo@example.com",
            "telefone": "11991110003",
            "cpf": "12345678903",
            "endereco": "Rua Demo, 3",
        },
    },
    {
        "nome": "Aluno Delta",
        "turma": "Turma B",
        "perfil_disc": "D",
        "caracteristicas": {"lideranca": "natural", "competição": "motiva"},
        "responsavel": {
            "nome": "Diego Demo",
            "email": "diego.demo@example.com",
            "telefone": "11991110004",
            "cpf": "12345678904",
            "endereco": "Rua Demo, 4",
        },
    },
    {
        "nome": "Aluno Épsilon",
        "turma": "Turma B",
        "perfil_disc": "I",
        "caracteristicas": {"social": "comunicativo", "musica": "admira"},
        "responsavel": {
            "nome": "Elisa Demo",
            "email": "elisa.demo@example.com",
            "telefone": "11991110005",
            "cpf": "12345678905",
            "endereco": "Rua Demo, 5",
        },
    },
    {
        "nome": "Aluno Zeta",
        "turma": "Turma B",
        "perfil_disc": "S",
        "caracteristicas": {"calma": "resiliente", "grupo": "colaborativo"},
        "responsavel": {
            "nome": "Fábio Demo",
            "email": "fabio.demo@example.com",
            "telefone": "11991110006",
            "cpf": "12345678906",
            "endereco": "Rua Demo, 6",
        },
    },
]


class Command(BaseCommand):
    help = "Cria os dados da apresentação (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        senha_professor = self._credencial_demo("SEED_DEMO_PASSWORD", SENHA_PROFESSOR_PADRAO)
        api_key_demo = self._credencial_demo("SEED_DEMO_API_KEY", API_KEY_PADRAO)
        User = get_user_model()

        # 1 escola + config (só cria Config quando a escola não tem nenhuma)
        escola, escola_criada = Escola.objects.get_or_create(
            nome=NOME_ESCOLA,
            defaults={"endereco": "Rua da Demo, 101"},
        )
        if escola.config_id is None:
            escola.config = Config.objects.create(
                api_key=api_key_demo,
                modelo="demo-model",
            )
            escola.save()

        # 1 professor
        professor, professor_criado = User.objects.get_or_create(
            email=EMAIL_PROFESSOR,
            defaults={
                "matricula": self._matricula_disponivel(User),
                "name": "Professor Demo",
                "ano": "1º ano",
                "escola": escola,
            },
        )
        if professor_criado:
            professor.set_password(senha_professor)
            professor.save()
        if professor.escola != escola:
            professor.escola = escola
            professor.save()

        # 2 turmas, com o professor ligado nas duas
        turmas = {}
        for nome_turma in ("Turma A", "Turma B"):
            turma, _ = Turma.objects.get_or_create(nome=nome_turma, escola=escola)
            turma.professores.add(professor)
            turmas[nome_turma] = turma

        # 6 alunos com responsável e perfil DISC
        alunos = {}
        for dados in ALUNOS_DEMO:
            responsavel, _ = Responsavel.objects.get_or_create(
                email=dados["responsavel"]["email"],
                defaults=dados["responsavel"],
            )
            aluno, _ = Aluno.objects.get_or_create(
                nome=dados["nome"],
                turma=turmas[dados["turma"]],
                defaults={"responsavel": responsavel},
            )
            if aluno.responsavel != responsavel:
                aluno.responsavel = responsavel
            if aluno.meta_dados is None:
                aluno.meta_dados = MetaDados.objects.create(
                    perfil_disc=dados["perfil_disc"],
                    caracteristicas=dados["caracteristicas"],
                )
            aluno.save()

            alunos[dados["nome"]] = aluno

        # 2 relatórios prontos
        relatorios_criados = 0
        for nome_aluno, dados in RELATORIOS_DEMO.items():
            aluno = alunos[nome_aluno]
            if aluno.relatorios.exists():
                continue
            Relatorio.objects.create(aluno=aluno, dados=dados)
            relatorios_criados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Escola: {NOME_ESCOLA} ({'criada' if escola_criada else 'já existia'})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"Professor: {EMAIL_PROFESSOR} (senha: {senha_professor})")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Turmas: {len(turmas)} | Alunos: {len(alunos)} |"
                f" Relatórios criados agora: {relatorios_criados}"
            )
        )
        self.stdout.write(self.style.SUCCESS("seed_demo concluído (idempotente)."))

    @staticmethod
    def _credencial_demo(variavel, padrao):
        """Credencial demo vem de variável de ambiente.

        Fora de ``DEBUG`` e sem a variável definida, o seed aborta para
        não encostar em deploys com credencial pública.
        """
        valor = os.environ.get(variavel)
        if valor:
            return valor
        if not settings.DEBUG:
            raise CommandError(f"Defina {variavel} para rodar o seed fora do DEBUG.")
        return padrao

    @staticmethod
    def _matricula_disponivel(User):
        for numero in range(1, 100):
            matricula = f"DEMO{numero:04d}"
            em_outro_usuario = (
                User.objects.filter(matricula=matricula).exclude(email=EMAIL_PROFESSOR).exists()
            )
            if not em_outro_usuario:
                return matricula
        raise RuntimeError("Nenhuma matrícula DEMO#### livre para o professor demo.")
