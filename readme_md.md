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
├── docs/                           # Diagramas (DER, Casos de Uso, Classes) e coleção de testes
│   ├── der.png
│   └── Raizes_Nordeste_Collection.json
├── src/
│   ├── domain/                     # Entidades, Enums (canalPedido, status) e regras puras de negócio
│   ├── application/                # Casos de uso / Services (criar pedido, pagamento mock, fidelidade)
│   ├── infrastructure/             # Banco de dados (ORM, Migrations, Seeds), Repositórios, Logs e Gateway Mock
│   └── api/                        # Controllers, Rotas, Middlewares (Auth/JWT, Erros) e config do Swagger
├── .env.example                    # Modelo de variáveis de ambiente
├── README.md                       # Documentação de execução
└── package.json                    # (ou pom.xml / requirements.txt — adapte à sua stack)
```

---

## 🛠️ Tecnologias e Pré-requisitos

> **Nota:** Certifique-se de ter os itens abaixo instalados antes de iniciar *(ajuste as versões conforme a stack utilizada no seu código)*.

- **Linguagem / Runtime:** Node.js `v20+` *(ex.: ou Java 21 / Python 3.11+)*
- **Banco de Dados:** PostgreSQL `v15+` *(ou MySQL / SQLite)*
- **Gerenciador de Pacotes:** npm `v10+` *(ou yarn / maven / pip)*
- **Ferramenta de Testes:** Postman ou Insomnia
- **Git:** `v2.40+`

---

## ⚙️ Configuração de Variáveis de Ambiente (.env)

1. Na raiz do projeto, faça uma cópia do arquivo `.env.example` e renomeie para `.env`:
   ```bash
   cp .env.example .env
   ```

2. Preencha as variáveis conforme o seu ambiente local:
   ```env
   # Servidor
   PORT=3000
   NODE_ENV=development

   # Banco de Dados
   DATABASE_URL="postgresql://usuario:senha@localhost:5432/raizes_nordeste?schema=public"

   # Autenticação e Segurança
   JWT_SECRET="sua_chave_secreta_forte_aqui"
   JWT_EXPIRES_IN="1h"

   # Pagamento Mock
   PAYMENT_MOCK_MODE="default"
   ```

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
npm install
```
*(Substitua pelo comando da sua tecnologia, se necessário)*

### 3. Criar o banco de dados e executar as Migrations
Certifique-se de que o serviço do banco de dados está ativo e execute:
```bash
npm run migrate
```
*(Ex.: `npx prisma migrate dev` ou `npm run typeorm migration:run`)*

### 4. Popular o banco com dados iniciais (Seed)
Para facilitar a validação imediata dos fluxos, execute o script de *seed* (cria unidades, produtos, estoque inicial e usuários de teste):
```bash
npm run seed
```

**Usuários padrão criados pelo Seed (para testes):**
| Perfil (Role) | E-mail | Senha |
| :--- | :--- | :--- |
| `CLIENTE` | `cliente@exemplo.com` | `SenhaSegura123` |
| `ATENDENTE` | `atendente@exemplo.com` | `SenhaSegura123` |
| `GERENTE` | `gerente@exemplo.com` | `SenhaSegura123` |

### 5. Iniciar a API
```bash
npm run dev
```
A API estará disponível em: `http://localhost:3000`

---

## 📄 Documentação da API (Swagger / OpenAPI)

Com o servidor em execução, acesse a documentação interativa completa (com contratos de request/response, schemas e códigos de status) no navegador:

- **URL Local:** `http://localhost:3000/api-docs`
- **Rota do Swagger:** `/api-docs`

---

## 🧪 Como Executar os Testes (Postman / Insomnia)

A evidência executável dos **11 cenários de teste** (6 positivos e 5 negativos) está disponível no repositório.

### Passo a passo para reproduzir:
1. Garanta que a API esteja rodando e que o **Seed** foi executado.
2. Abra o **Postman** (ou **Insomnia**) e clique em **Import**.
3. Selecione o arquivo da coleção localizado em:  
   `docs/Raizes_Nordeste_Collection.json` *(ajuste o caminho caso salve na raiz)*.
4. Execute as requisições seguindo a **ordem sugerida das pastas**:
   1. **`Auth`**: Execute `01-Login com sucesso` para obter o `accessToken` (JWT). Configure esse token na aba *Authorization > Bearer Token* (ou na variável de ambiente `{{token}}` da coleção). Em seguida, valide os cenários negativos `401` (sem token) e `403` (perfil sem permissão).
   2. **`Unidades` e `Produtos`**: Valide a consulta de unidades e a listagem paginada do cardápio (`?page=1&limit=10`).
   3. **`Pedidos`**: Teste primeiro os cenários negativos (`422` sem `canalPedido` e `409` sem estoque) e depois execute `03-Criar pedido valido` (`201`).
   4. **`Pagamentos`**: Utilize o `pedidoId` gerado no passo anterior para testar o pagamento mock recusado (`400`) e o aprovado (`200`, alterando o status para `COZINHA`).
   5. **`Fidelidade`**: Consulte o saldo de pontos do cliente autenticado.

### Testes Automatizados *(Opcional)*
Caso deseje rodar a suíte de testes unitários/integração via terminal:
```bash
npm test
```

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