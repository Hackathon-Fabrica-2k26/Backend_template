# Marsupi: Backend

API do **Marsupi**, copiloto pedagógico inclusivo para professores dos anos iniciais do Ensino Fundamental, criado no Hackathon Fábrica de Software 2026 (IFC Araquari), desafio *"Do Zero à Autonomia: 24H com IA"*.

O professor cadastra turmas a partir da foto da chamada, envia atividades e trabalhos dos alunos e recebe da IA (Gemini) adaptações de atividade, relatórios, pontos de atenção e rascunho de PEI. O responsável acessa o perfil de apoio do aluno por um código de acesso.

Stack: Django + DRF, JWT com OTP por e-mail, Celery, Swagger (drf-spectacular) e admin Unfold.

## Apps (`src/apps/`)
| App | Responsabilidade |
|---|---|
| `users` | professor (login por matrícula), JWT, OTP, logout |
| `escolas` | escola, turma, `Config` (chave do Gemini, cifrada no banco), reconhecimento da chamada por foto |
| `alunos` | aluno, responsável, consentimento, laudo, código de acesso do responsável, pontos de atenção, rascunho de PEI |
| `pedagogico` | atividades e variações, trabalhos, relatórios, perfil de apoio, habilidades e evolução |

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
| `populate` | popula o banco com dados essenciais e mockados (idempotente) |
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
| Senha | `SEED_DEMO_PASSWORD` (padrão `demo-senha-123` em desenvolvimento) |

A senha e a `api_key` demo vêm das variáveis de ambiente; o padrão público (`demo-senha-123` / `demo-api-key-troque-no-admin`) vale **só quando `DEBUG=True`**. Com `DEBUG=False` e sem as variáveis, o comando aborta — isso evita subir em deploy (Dokku) uma conta de professor com senha pública:

```bash
SEED_DEMO_PASSWORD=minha-senha SEED_DEMO_API_KEY=minha-chave pdm run seed-demo
```

São dados de apresentação, claramente fictícios. Troque a `api_key` da `Config` no admin antes de chamar a LLM de verdade.

## População do Banco de Dados (Database Seeding)
Comando customizado e idempotente para popular o banco de dados com dados essenciais de catálogo e dados mockados realistas para desenvolvimento e testes locais.

```bash
# Execução padrão via PDM (ou python src/manage.py seed_db)
pdm run populate

# Execução limpando dados anteriores antes de semear
python src/manage.py seed_db --clear

# Execução customizando o volume de dados mockados
python src/manage.py seed_db --count 20
python src/manage.py seed_db --users 10 --escolas 3 --turmas-por-escola 2 --alunos-por-turma 5
```

### Credenciais geradas por padrão:
| Perfil | E-mail | Matrícula | Senha |
|---|---|---|---|
| **Superusuário** | `admin@exemplo.com` | `ADMIN0001` | `admin123` |
| **Professor** | `professor1@exemplo.com` | `PROF0001` | `senha123` |

Variáveis de ambiente opcionais (`.env`):
- `SEED_ADMIN_EMAIL`: e-mail do superusuário gerado (padrão: `admin@exemplo.com`).
- `SEED_ADMIN_PASSWORD`: senha do superusuário gerado (padrão: `admin123`).
- `SEED_USER_PASSWORD`: senha comum atribuída aos professores mockados (padrão: `senha123`).

## Endpoints
A lista completa, com os corpos de requisição, fica no Swagger em `/api/docs/` (em produção exige login).

| Rota | Descrição |
|---|---|
| `POST /api/auth/login/` | `matricula` + `password`; devolve `access`/`refresh` ou, com OTP, um `otp_token` |
| `POST /api/auth/otp/verify/` · `otp/resend/` | confirma o código enviado por e-mail e devolve os tokens · reenvia o código |
| `POST /api/auth/refresh/` · `logout/` | renova o `access` (com rotação do `refresh`) · invalida o `refresh` |
| `GET /api/auth/me/` · `me/resumo/` | professor autenticado · resumo do painel inicial |
| `/api/escolas/`, `/api/turmas/` | escolas e turmas do professor |
| `POST /api/chamada/reconhecer/` | lê os nomes da foto da chamada |
| `/api/alunos/` | alunos, laudo, pontos de atenção, rascunho de PEI (JSON e PDF) e código de acesso do responsável |
| `/api/atividades/`, `/api/variacoes/` | atividades da turma e variações adaptadas pela IA (`atividades/extrair/` lê a atividade de uma foto) |
| `/api/trabalhos/`, `/api/relatorios/` | trabalhos enviados e relatórios gerados (`relatorios/gerar/`) |
| `/api/habilidades/`, `/api/perfis-apoio/` | habilidades BNCC e evolução · perfil de apoio do aluno |
| `/api/responsavel/...` | área do responsável: acesso por código, aluno, consentimento, laudo e perfil de apoio |
| `/health/` · `/admin/` | health check · painel administrativo |

Envie o token como `Authorization: Bearer <access>`. O `access` dura 30 minutos.

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
| `CONFIG_FERNET_KEY` | vazio | chave Fernet que cifra a chave do Gemini no banco; obrigatória com `DEBUG=False` e não pode ser trocada depois |
| `SECURE_HSTS_SECONDS` | `31536000` | duração do HSTS em produção (`0` com `DEBUG=True`) |
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
| `SEED_DEMO_PASSWORD` | vazio | senha do professor demo do `seed_demo`; padrão `demo-senha-123` só com `DEBUG=True`, obrigatória fora dele |
| `SEED_DEMO_API_KEY` | vazio | `api_key` demo da `Config` criada pelo `seed_demo`; mesmo comportamento da senha |

## Deploy
O `Procfile` define `release`, `web` (gunicorn) e `worker` (Celery). Configure `SECRET_KEY` e `CONFIG_FERNET_KEY` (antes do primeiro push), `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` e `REDIS_URL` no ambiente.

O cache (usado pelo OTP e pelo rate limit) é compartilhado entre os workers do gunicorn: usa o Redis quando `REDIS_URL` está definida ou, por padrão, o próprio banco de dados (`DatabaseCache` na tabela `django_cache`, criada automaticamente no passo `release` com `python src/manage.py createcachetable`).

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

