# AGENTS.md

Backend Django + DRF. Siga estes padrões ao adicionar código.

## Estrutura
- `src/config/`: settings, urls raiz, celery, wsgi/asgi
- `src/core/`: `BaseModel`, `DevAuthentication` e utilidades compartilhadas
- `src/apps/users/`: usuário customizado (`AbstractUser`, login por e-mail, campo `name`, sem `username`); `AUTH_USER_MODEL = "users.User"`
- `src/apps/<app>/`: um app por domínio. `models/`, `serializers/`, `views/`, `admin/` e `tasks/` são **pacotes**, com um arquivo por entidade nomeado pelo que ele é (ex.: `models/item.py`, `serializers/item.py`, `views/item.py`); `urls.py` e `apps.py` ficam soltos
- `tests/`: pytest-django; fixtures em `tests/conftest.py` (`api_client`, `user`, `auth_client`)

## Comandos
- `pdm install -G dev`: instala dependências
- `cp .env.example .env`, depois `pdm run migrate` e `pdm run createsuperuser`: primeira execução
- `pdm run dev`: servidor em http://localhost:8000
- `pdm run makemigrations`
- `pdm run startapp <nome>`: cria app (mova para `src/apps/` e ajuste `name`/`label` em `apps.py`)
- `pdm run test`, `pdm run check` (ruff), `pdm run format`
- `pdm run redis` / `pdm run redis-down`: sobe/derruba o Redis (docker compose); depois defina `REDIS_URL=redis://localhost:6379/0` no `.env`
- `pdm run celery`: worker (roda da raiz, `celery -A src.config`) (sem `REDIS_URL` as tasks rodam síncronas)

## Convenções
- Modelos herdam `core.models.BaseModel` (timestamps, histórico e exclusão lógica). Use `Model.all_objects` para ver excluídos.
- Referencie o usuário com `settings.AUTH_USER_MODEL` (FK) ou `get_user_model()`; novos campos do usuário vão em `apps/users/models/user.py`.
- `AUTH_DISABLED=True` no `.env` (com `DEBUG=True`) desativa o JWT: requisições sem token viram `dev@example.com`. Para testes automatizados use `auth_client`.
- Todas as rotas exigem JWT por padrão. Libere uma rota explicitamente com `permission_classes = [AllowAny]`.
- Filtre querysets pelo usuário dono quando o dado for privado; item de outro usuário deve dar 404.
- Listas usam paginação de 20, `filterset_fields`, `search_fields` e `ordering_fields`.
- Rotas ficam em `apps/<app>/urls.py` e são incluídas em `config/urls.py` sob `/api/`.
- Registre novos apps em `INSTALLED_APPS` (`apps.<nome>`).
- Em trabalho paralelo entre issues/apps, relações com modelos ainda não integrados podem ser referenciadas por string (`"app.Model"`), sem criar um modelo substituto no app dependente. A migration só deve ser gerada quando o app/model de destino estiver disponível na branch base; então atualize a branch com `dev` e rode `pdm run makemigrations <app>` para registrar a dependência correta da migration inicial do outro app.
- Ao trabalhar numa issue dependente, use uma branch própria baseada na branch que contém a dependência quando disponível. Antes disso, é permitido implementar models, serializers e testes usando referências string, mas não invente migrations sem o app de destino.
- Não crie `models.py`, `views.py` etc. com várias classes. Um arquivo por entidade dentro do pacote e reexporte no `__init__.py` (com `__all__`); sem o reexport no `__init__.py`, o Django não registra o modelo, o admin nem a task.
- Admin usa `unfold.admin.ModelAdmin` junto com `SimpleHistoryAdmin`.
- Configuração vem de variáveis de ambiente (`.env`); nunca coloque segredo no código.
- Docs da API: `/api/docs/`. Health: `/health/`.
- Em `get_queryset` que usa `self.request.user`, devolva `Model.objects.none()` quando `getattr(self, "swagger_fake_view", False)` for verdadeiro (geração do schema).
- Exclusão e restauração de `BaseModel` registram o motivo no histórico; no admin, use `SafeDeleteAdmin` para ver e restaurar excluídos.
- Testes criam dados com as factories de `tests/factories.py` (`UserFactory`, `ItemFactory`); crie uma factory por modelo novo.
- Cadastro tem limite de 10 requisições/hora (`throttle_scope = "register"`); novos limites vão em `DEFAULT_THROTTLE_RATES`.

## Adicionar um recurso novo
1. `pdm run startapp nome`, mover para `src/apps/nome`, ajustar `apps.py`; apagar `models.py`, `views.py`, `admin.py` e criar os pacotes `models/`, `serializers/`, `views/`, `admin/`
2. `models/<entidade>.py` herdando `BaseModel` + reexport no `models/__init__.py`; `pdm run makemigrations nome`
3. `serializers/<entidade>.py`, `views/<entidade>.py` (ViewSet), `urls.py` com `DefaultRouter`, todos reexportados nos `__init__.py`
4. Incluir a rota em `config/urls.py` e o app em `INSTALLED_APPS`
5. Testes em `tests/test_nome.py` cobrindo 401, dono errado (404) e validação (400)
6. `pdm run check && pdm run test`; se uma relação de modelo apontar para app ainda ausente, registre essa dependência como bloqueio de integração e não crie um modelo temporário no app do domínio dependente.
