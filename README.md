# Backend

API REST com Django + DRF, usuário customizado por e-mail, autenticação JWT, documentação Swagger, tarefas Celery e admin Unfold.

## Requisitos
- Python 3.11+
- [PDM](https://pdm-project.org) (`pip install pdm`)

## Instalação
```bash
pdm install -G dev
cp .env.example .env      # obrigatório: define SECRET_KEY e DEBUG=True para desenvolvimento
pdm run migrate
pdm run createsuperuser
pdm run dev               # http://localhost:8000
```

Sem PDM:
```bash
pip install -r requirements.txt
cp .env.example .env
python src/manage.py migrate
python src/manage.py createsuperuser
python src/manage.py runserver
```

## Comandos (`pdm run <comando>`)
| Comando | Ação |
|---|---|
| `dev` / `runserver` | servidor de desenvolvimento |
| `migrate` / `makemigrations` | migrações |
| `createsuperuser` | cria superusuário |
| `seed-demo` | cria os dados da apresentação (idempotente) |
| `shell` | shell Django |
| `startapp <nome>` | novo app |
| `redis` / `redis-down` | sobe / derruba o Redis do `docker-compose.yml` |
| `celery` / `beat` | worker / agendador |
| `test` / `test-cov` | testes / com cobertura |
| `check` / `format` | ruff check / ruff format |
| `loaddata` / `dumpdata` | fixtures |
| `model` | diagrama de modelos |
| `export` | atualiza `requirements.txt` |

## Redis e Celery (opcional)
Sem `REDIS_URL` as tarefas Celery rodam de forma síncrona, e não é preciso Redis. Para rodar com worker de verdade:

```bash
pdm run redis        # sobe o Redis via docker compose (porta 6379)
# no .env: REDIS_URL=redis://localhost:6379/0
pdm run dev          # terminal 1
pdm run celery       # terminal 2
```

`pdm run redis-down` derruba o container. Para mudar a porta do host, use `REDIS_PORT` (e ajuste a `REDIS_URL`).

## Dados demo
Comando idempotente para preparar a apresentação (rodar de novo não duplica):

```bash
pdm run seed-demo
```

Cria: 1 escola + config, 1 professor, 2 turmas, 6 alunos (com responsável e perfil DISC) e 2 relatórios prontos seguindo o contrato de `docs/contexto_projeto_ia.md` (seção 6).

| Credencial | Valor |
|---|---|
| E-mail | `professor@demo.com` |
| Matrícula | `DEMO0001` |
| Senha | `demo-senha-123` |

São dados de apresentação, claramente fictícios. Troque a `api_key` da `Config` no admin antes de chamar a LLM de verdade.

## Endpoints
| Rota | Descrição |
|---|---|
| `POST /api/auth/register/` | cria usuário (`email`, `name`, `password`) |
| `POST /api/auth/login/` | `email` + `password`; retorna `access` e `refresh` |
| `POST /api/auth/refresh/` | renova o `access` |
| `GET /api/auth/me/` | usuário autenticado |
| `/api/items/` | CRUD de exemplo (filtro `done`, busca `search`, ordenação `ordering`) |
| `/api/docs/` | Swagger |
| `/health/` | health check |
| `/admin/` | painel administrativo |

Envie o token como `Authorization: Bearer <access>`.

### Desativar o JWT em desenvolvimento
Com `AUTH_DISABLED=True` no `.env` (e `DEBUG=True`), requisições sem token passam a ser o usuário `dev@example.com`, criado automaticamente. Um token válido continua tendo prioridade. Com `DEBUG=False` o app não inicia com essa opção ligada.

Nos testes automatizados, use a fixture `auth_client` (`force_authenticate`).

## Variáveis (`.env`)
| Variável | Padrão | Uso |
|---|---|---|
| `SECRET_KEY` | obrigatória | chave do Django; o app não inicia sem ela quando `DEBUG=False` |
| `DEBUG` | `False` | modo debug (`.env.example` define `True`) |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | hosts permitidos |
| `CORS_ALLOWED_ORIGINS` | vazio | origens do front-end; vazio com `DEBUG=True` libera todas |
| `CSRF_TRUSTED_ORIGINS` | vazio | origens HTTPS do admin atrás de proxy |
| `AUTH_DISABLED` | `False` | desativa o JWT em desenvolvimento (exige `DEBUG=True`) |
| `DATABASE_URL` | vazio (SQLite) | ex.: `postgres://user:senha@host:5432/banco` |
| `REDIS_URL` | vazio (Celery síncrono) | broker do Celery, ex.: `redis://localhost:6379/0` |
| `REDIS_PORT` | `6379` | porta do Redis no host (`docker-compose.yml`) |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | backend de e-mail (`smtp.EmailBackend` em produção) |
| `EMAIL_HOST` | `localhost` | servidor SMTP (ex.: `smtp.gmail.com`) |
| `EMAIL_PORT` | `587` | porta SMTP |
| `EMAIL_HOST_USER` | vazio | usuário SMTP |
| `EMAIL_HOST_PASSWORD` | vazio | senha SMTP (ex.: senha de app do Gmail) |
| `EMAIL_USE_TLS` | `True` | ativa STARTTLS |
| `EMAIL_USE_SSL` | `False` | ativa SSL direto |
| `EMAIL_TIMEOUT` | `10` | timeout de conexão SMTP em segundos |
| `DEFAULT_FROM_EMAIL` | `Marsupi <no-reply@marsupi.local>` | remetente padrão dos e-mails (OTP) |

## Deploy
O `Procfile` define `release`, `web` (gunicorn) e `worker` (Celery). Configure `SECRET_KEY` (antes do primeiro push), `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` e `REDIS_URL` no ambiente.

Para o código OTP chegar por e-mail em produção, configure também as variáveis de SMTP:
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL="Marsupi <no-reply@marsupi.local>"
```

