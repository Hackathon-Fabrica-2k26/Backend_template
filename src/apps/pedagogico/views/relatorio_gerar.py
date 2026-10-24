"""Geração do relatório pedagógico com apoio de IA (LGPD: payload anonimizado)."""

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alunos.models import Aluno
from apps.pedagogico.models import Atividade, Relatorio
from apps.pedagogico.serializers import RelatorioSerializer
from apps.pedagogico.services import (
    MODELO_PADRAO,
    LLMError,
    anonimizar,
    gerar_relatorio,
)


class RelatorioGerarSerializer(serializers.Serializer):
    """Dados que o professor fornece para a geração do relatório."""

    aluno = serializers.PrimaryKeyRelatedField(queryset=Aluno.objects.all())
    pontos_fortes = serializers.ListField(child=serializers.CharField())
    desafios = serializers.ListField(child=serializers.CharField())
    contexto_turma = serializers.CharField(required=False, allow_blank=True, default="")


class RelatorioGerarView(APIView):
    """Gera o relatório do aluno com IA a partir do que o professor informa.

    O payload enviado à LLM é anonimizado (nome, matrícula, CPF, responsável,
    datas e cidade nunca vão ao modelo); o aluno é tratado por codinome na resposta.
    """

    def post(self, request):
        entrada = RelatorioGerarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        aluno = entrada.validated_data["aluno"]

        # LGPD: professor só gera relatório para aluno das suas turmas.
        turma = aluno.turma
        if turma is None or not turma.professores.filter(pk=request.user.pk).exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        dados = {
            "aluno": aluno.pk,
            "pontos_fortes": entrada.validated_data.get("pontos_fortes", []),
            "desafios": entrada.validated_data.get("desafios", []),
            "contexto_turma": entrada.validated_data.get("contexto_turma", ""),
        }
        responsavel = aluno.responsavel.nome if aluno.responsavel else ""
        payload = anonimizar(dados, nome_aluno=aluno.nome, nome_responsavel=responsavel)

        config = request.user.escola.config if getattr(request.user, "escola", None) else None
        try:
            resposta = gerar_relatorio(
                payload,
                config.api_key if config else "",
                modelo=config.modelo if config else MODELO_PADRAO,
            )
        except LLMError as erro:
            return Response({"erro": str(erro)}, status=status.HTTP_502_BAD_GATEWAY)

        relatorio = Relatorio.objects.create(aluno=aluno, dados=resposta)
        for item in resposta.get("atividades") or []:
            titulo = str(item.get("titulo", "")).strip() if isinstance(item, dict) else ""
            if not titulo:
                continue
            atividade, _ = Atividade.objects.get_or_create(
                nome=titulo[:45],
                tipo="Sugestão de IA",
                aluno=aluno,
            )
            atividade.relatorios.add(relatorio)

        saida = RelatorioSerializer(relatorio)
        return Response(
            {
                "relatorio": saida.data,
                "payload_enviado": payload,
            },
            status=status.HTTP_201_CREATED,
        )
