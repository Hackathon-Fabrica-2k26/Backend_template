# AGENTS.md

Backend Django + DRF. Siga estes padrões ao adicionar código.

## Estrutura
- `src/config/`: settings, urls raiz, celery, wsgi/asgi
- `src/core/`: `BaseModel` e utilidades compartilhadas
- `src/apps/<app>/`: um app por domínio (`models`, `serializers`, `views`, `urls`, `tasks`, `admin`)
- `tests/`: pytest-django; fixtures em `tests/conftest.py` (`api_client`, `user`, `auth_client`)

## Comandos
- `pdm install -G dev`: instala dependências
- `cp .env.example .env`, depois `pdm run migrate` e `pdm run createsuperuser`: primeira execução
- `pdm run dev`: servidor em http://localhost:8000
- `pdm run makemigrations`
- `pdm run startapp <nome>`: cria app (mova para `src/apps/` e ajuste `name`/`label` em `apps.py`)
- `pdm run test`, `pdm run check` (ruff), `pdm run format`
- `pdm run celery`: worker (roda da raiz, `celery -A src.config`) (sem `REDIS_URL` as tasks rodam síncronas)

## Convenções
- Modelos herdam `core.models.BaseModel` (timestamps, histórico e exclusão lógica). Use `Model.all_objects` para ver excluídos.
- Todas as rotas exigem JWT por padrão. Libere uma rota explicitamente com `permission_classes = [AllowAny]`.
- Filtre querysets pelo usuário dono quando o dado for privado; item de outro usuário deve dar 404.
- Listas usam paginação de 20, `filterset_fields`, `search_fields` e `ordering_fields`.
- Rotas ficam em `apps/<app>/urls.py` e são incluídas em `config/urls.py` sob `/api/`.
- Registre novos apps em `INSTALLED_APPS` (`apps.<nome>`).
- Admin usa `unfold.admin.ModelAdmin` junto com `SimpleHistoryAdmin`.
- Configuração vem de variáveis de ambiente (`.env`); nunca coloque segredo no código.
- Docs da API: `/api/docs/`. Health: `/health/`.
- Em `get_queryset` que usa `self.request.user`, devolva `Model.objects.none()` quando `getattr(self, "swagger_fake_view", False)` for verdadeiro (geração do schema).
- Exclusão e restauração de `BaseModel` registram o motivo no histórico; no admin, use `SafeDeleteAdmin` para ver e restaurar excluídos.
- Testes criam dados com as factories de `tests/factories.py` (`UserFactory`, `ItemFactory`); crie uma factory por modelo novo.
- Cadastro tem limite de 10 requisições/hora (`throttle_scope = "register"`); novos limites vão em `DEFAULT_THROTTLE_RATES`.

## Adicionar um recurso novo
1. `pdm run startapp nome`, mover para `src/apps/nome`, ajustar `apps.py`
2. Modelo herdando `BaseModel`; `pdm run makemigrations nome`
3. Serializer, ViewSet, `urls.py` com `DefaultRouter`
4. Incluir a rota em `config/urls.py` e o app em `INSTALLED_APPS`
5. Testes em `tests/test_nome.py` cobrindo 401, dono errado (404) e validação (400)
6. `pdm run check && pdm run test`
