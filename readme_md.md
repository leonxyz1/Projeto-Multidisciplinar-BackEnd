# 🍔 API Back-End — Rede "Raízes do Nordeste"

Projeto Multidisciplinar (Trilha Back-End) — UNINTER (2026).  
Solução de Back-End RESTful projetada para suportar a operação multicanal (**App, Totem, Balcão, Pickup e Web**) da rede de lanchonetes **Raízes do Nordeste**, contemplando gestão de pedidos, controle de estoque por unidade, programa de fidelização, integração de pagamento simulado (*Mock*) e conformidade com a **LGPD**.

---

## 📌 Índice
- [Arquitetura e Estrutura do Projeto](#-arquitetura-e-estrutura-do-projeto)
- [Tecnologias e Pré-requisitos](#-tecnologias-e-pré-requisitos)
- [Configuração de Variáveis de Ambiente (.env)](#-configuração-de-variáveis-de-ambiente-env)
- [Instalação e Execução Local](#-instalação-e-execução-local)
- [Documentação da API (Swagger / OpenAPI)](#-documentação-da-api-swagger--openapi)
- [Como Executar os Testes (Postman / Insomnia)](#-como-executar-os-testes-postman--insomnia)
- [Fluxo Crítico (MVP) e Regras de Negócio](#-fluxo-crítico-mvp-e-regras-de-negócio)
- [Segurança e LGPD](#-segurança-e-lgpd)
- [Links e Evidências](#-links-e-evidências)

---

## 🏗️ Arquitetura e Estrutura do Projeto

O projeto foi organizado seguindo o princípio da separação de responsabilidades em **4 camadas**:

```text
├── alembic/                        # Migrations do banco
├── src/
│   ├── api/                         # Rotas, schemas e dependências HTTP
│   ├── infrastructure/database/    # SQLAlchemy, SQLite e seed
│   ├── infrastructure/security.py  # Hash de senha e JWT
│   └── main.py                     # Aplicação FastAPI
├── tests/                           # Testes de API e persistência
├── alembic.ini
├── requirements.txt
└── readme_md.md
```

---

## 🛠️ Tecnologias e Pré-requisitos

> **Nota:** Certifique-se de ter os itens abaixo instalados antes de iniciar *(ajuste as versões conforme a stack utilizada no seu código)*.

- **Linguagem / Runtime:** Python `3.10+`
- **Framework / Persistência:** FastAPI, SQLAlchemy 2 e Alembic
- **Banco de Dados:** SQLite
- **Gerenciador de Pacotes:** `pip`
- **Ferramenta de Testes:** Postman ou Insomnia
- **Git:** `v2.40+`

---

## ⚙️ Configuração de Variáveis de Ambiente (.env)

Defina um segredo aleatório com pelo menos 32 bytes antes de iniciar a API:

```bash
export JWT_SECRET="$(openssl rand -hex 32)"
```

O SQLite usa `database.sqlite3` na raiz por padrão. Para usar outro arquivo,
defina `DATABASE_URL`, por exemplo `sqlite:///./local.sqlite3`.

---

## 🚀 Instalação e Execução Local

Siga o passo a passo abaixo no terminal:

### 1. Clonar o repositório
```bash
git clone https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
cd SEU-REPOSITORIO
```

### 2. Instalar as dependências
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. Criar o banco de dados e executar as Migrations
```bash
alembic upgrade head
```

### 4. Popular o banco com dados iniciais (Seed)
Para facilitar a validação imediata dos fluxos, execute o script de *seed* (cria unidades, produtos, estoque inicial e usuários de teste):
```bash
python -m src.infrastructure.database.seed
```

**Usuários padrão criados pelo Seed (para testes):**
| Perfil (Role) | E-mail | Senha |
| :--- | :--- | :--- |
| `CLIENTE` | `cliente@teste.local` | `senha123` |
| `ATENDENTE` | `atendente@teste.local` | `senha123` |
| `GERENTE` | `gerente@teste.local` | `senha123` |

### 5. Iniciar a API
```bash
uvicorn src.main:app --reload
```
A API estará disponível em: `http://localhost:8000`

---

## 📄 Documentação da API (Swagger / OpenAPI)

Com o servidor em execução, acesse a documentação interativa completa (com contratos de request/response, schemas e códigos de status) no navegador:

- **URL Local:** `http://localhost:8000/docs`
- **Rota do Swagger:** `/docs`

---

## 🧪 Como Executar os Testes

Execute os testes automatizados de autenticação e persistência:
```bash
python -m unittest discover -s tests -v
```

O fluxo JWT também pode ser validado na documentação interativa:

1. `POST /auth/cadastro` com `nome`, `email` e `senha` cria um usuário `CLIENTE`.
2. `POST /auth/login` recebe formulário OAuth2 (`username` = e-mail,
   `password` = senha) e retorna `access_token`.
3. Use `Authorization: Bearer <access_token>` em `GET /auth/me`; sem token ou
   com token inválido, a resposta é `401`.
4. O token de cliente recebe `403` em `GET /estoque`; o token do gerente do seed
   pode acessar a rota.

---

## 🔄 Fluxo Crítico (MVP) e Regras de Negócio

O MVP implementado fecha ponta a ponta o **Fluxo A (Pedido → Pagamento Mock → Atualização de Status)**:
- **Multicanalidade obrigatória:** Todo pedido exige o campo `canalPedido` (`APP`, `TOTEM`, `BALCAO`, `PICKUP`, `WEB`) e permite filtragem em `GET /pedidos?canalPedido=...&status=...`.
- **Validação de Estoque:** Pedidos com quantidade superior ao saldo disponível na unidade são bloqueados com erro padronizado `409 Conflict`.
- **Pagamento Mock:** Simula aprovação (atualizando o status do pedido e dando baixa no estoque) e recusa (mantendo integridade do pedido e retornando erro coerente).
- **Padronização de Erros:** Todas as falhas retornam um JSON uniforme contendo `error`, `message`, `details`, `timestamp` e `path`.

---

## 🔒 Segurança e LGPD

- **Autenticação e Autorização:** Rotas protegidas via **JWT** com controle de acesso baseado em perfis (`CLIENTE`, `ATENDENTE`, `GERENTE`).
- **Armazenamento Seguro:** Senhas armazenadas exclusivamente com *hash* criptográfico (ex.: `bcrypt`), nunca retornadas nas respostas da API.
- **Privacidade (LGPD):** Coleta minimizada de dados pessoais (execução de contrato para pedidos e consentimento explícito para o programa de fidelidade).
- **Logs e Auditoria:** Registro de ações sensíveis (criação de pedidos, pagamentos e alterações de status) para rastreabilidade operacional.

---

## 🔗 Links e Evidências

- **Repositório Público:** `https://github.com/SEU-USUARIO/SEU-REPOSITORIO`
- **Swagger Local:** `http://localhost:3000/api-docs`
- **Coleção Postman/Insomnia:** [`docs/Raizes_Nordeste_Collection.json`](./docs/Raizes_Nordeste_Collection.json)
- **Diagrama Entidade-Relacionamento (DER):** [`docs/der.png`](./docs/der.png)
- **Deploy *(Opcional)*:** *(Inserir link caso faça deploy em nuvem, ou remover esta linha)*

---

## 👤 Autor

**Seu Nome Completo**  
RU: `SEU_RU_AQUI` — UNINTER (2026)

---

## Persistência SQLite

A camada SQLAlchemy fica em `src/infrastructure/database/`. Por padrão, o SQLite
cria `database.sqlite3` na raiz do repositório; defina `DATABASE_URL` para usar
outro banco ou arquivo.

Instale as dependências Python de `requirements.txt` e execute as migrations e o
seed:

```bash
python -m pip install -r requirements.txt
alembic upgrade head
python -m src.infrastructure.database.seed
```

O seed é idempotente. As contas de demonstração usam a senha `senha123` e os
e-mails `cliente@teste.local`, `atendente@teste.local` e `gerente@teste.local`.

### Cadastro, login e rotas protegidas

Configure `JWT_SECRET` antes de iniciar a API. Gere um segredo local com:

```bash
export JWT_SECRET="$(openssl rand -hex 32)"
uvicorn src.main:app --reload
```

- `POST /auth/cadastro`: recebe `nome`, `email` e `senha`; novas contas recebem
  perfil `CLIENTE`, e a senha é armazenada somente como hash bcrypt.
- `POST /auth/login`: recebe formulário OAuth2 (`username` com o e-mail e
  `password` com a senha) e retorna um access token JWT válido por 30 minutos.
- `GET /auth/me`: exemplo de rota autenticada.
- `GET /estoque`: exige token Bearer de um usuário com perfil `GERENTE`.

Envie o token nas rotas protegidas como `Authorization: Bearer <token>`.
Credenciais ou tokens inválidos retornam `401`; perfil sem permissão retorna
`403`. O endpoint de cadastro nunca permite escolher o próprio perfil.