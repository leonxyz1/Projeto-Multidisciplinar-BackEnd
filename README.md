# API Raizes do Nordeste

API REST para pedidos, pagamentos simulados, estoque por unidade e auditoria,
implementada com FastAPI, SQLAlchemy, Alembic e SQLite.

## Requisitos

- Python 3.10 ou superior
- Git
- OpenSSL para gerar um segredo JWT local (ou outro gerador seguro)

## Instalar e iniciar do zero

Na raiz do repositório, execute:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edite `.env` e substitua `JWT_SECRET=REPLACE_ME` por um segredo aleatório de
pelo menos 32 bytes. Por exemplo, gere um valor com `openssl rand -hex 32` e
cole-o no arquivo. As opções para expiração do token e modo do pagamento mock
também estão nesse arquivo.

Crie o banco e aplique as migrations:

```bash
alembic upgrade head
```

Carregue as unidades, produtos, estoques e usuários de demonstração:

```bash
python -m src.infrastructure.database.seed
```

Inicie a API:

```bash
uvicorn src.main:app --reload
```

A aplicação estará em `http://127.0.0.1:8000`. O Swagger interativo fica em
`http://127.0.0.1:8000/docs`; o contrato OpenAPI pode ser consultado em
`http://127.0.0.1:8000/openapi.json`, e a rota de saúde em `/saude`.

## Usuários de demonstração

O seed é idempotente. Todas as contas abaixo usam a senha `senha123`:

| Perfil | E-mail |
| --- | --- |
| CLIENTE | `cliente@example.com` |
| ATENDENTE | `atendente@example.com` |
| GERENTE | `gerente@example.com` |

O login `POST /auth/login` recebe formulário com `username` (o e-mail) e
`password`. No Swagger, use o token retornado como Bearer token para testar as
rotas protegidas. O cadastro público cria usuários com perfil `CLIENTE`.

## Testes

Com as dependências instaladas, execute:

```bash
python -m unittest discover -s tests -v
```

## Banco e arquivos locais

Por padrão, SQLite usa `database.sqlite3` na raiz. `DATABASE_URL` permite
configurar outro banco; para SQLite, por exemplo:

```dotenv
DATABASE_URL=sqlite:///./database.sqlite3
```

O arquivo `.env` contém configuração local e não deve ser commitado. Arquivos
de banco SQLite e ambientes virtuais também são ignorados pelo Git. Use
`.env.example` como referência, nunca como local para guardar segredos reais.
