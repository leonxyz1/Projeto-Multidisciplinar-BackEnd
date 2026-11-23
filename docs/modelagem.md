# Modelagem do banco de dados

Os diagramas abaixo refletem as tabelas criadas pelas migrations Alembic e as
classes SQLAlchemy em `src/infrastructure/database/models.py`.

## Diagrama entidade-relacionamento

```mermaid
erDiagram
    UNIDADES {
        int id PK
        varchar nome UK
        varchar endereco
        boolean ativa
    }

    USUARIOS {
        int id PK
        int unidade_id FK
        varchar nome
        varchar email UK
        varchar senha_hash
        varchar perfil
        datetime created_at
    }

    PRODUTOS {
        int id PK
        varchar sku UK
        varchar nome
        text descricao
        decimal preco
        boolean sazonal
        boolean ativo
    }

    ESTOQUES {
        int unidade_id PK, FK
        int produto_id PK, FK
        int quantidade
        boolean disponivel
    }

    FIDELIDADES {
        int id PK
        int usuario_id FK, UK
        boolean aceita_fidelidade
        int pontos_saldo
    }

    PEDIDOS {
        int id PK
        int cliente_id FK
        int criado_por_id FK
        int unidade_id FK
        varchar canal_pedido
        varchar status
        decimal valor_bruto
        decimal valor_desconto
        decimal total
        datetime created_at
    }

    ITENS_PEDIDO {
        int pedido_id PK, FK
        int produto_id PK, FK
        int quantidade
        decimal preco_unitario
        decimal subtotal
    }

    PAGAMENTOS {
        int id PK
        int pedido_id FK
        varchar chave_idempotencia UK
        varchar metodo
        varchar status
        decimal valor
        json payload
        datetime created_at
    }

    MOVIMENTACOES_ESTOQUE {
        int id PK
        int pedido_id FK
        int unidade_id FK
        int produto_id FK
        int usuario_id FK
        varchar tipo
        int quantidade
        datetime created_at
    }

    AUDITORIAS {
        int id PK
        int usuario_id FK
        int unidade_id FK
        varchar acao
        varchar entidade
        int entidade_id
        json detalhes
        datetime created_at
    }

    UNIDADES o|--o{ USUARIOS : "unidade_id"
    UNIDADES ||--o{ ESTOQUES : "unidade_id"
    PRODUTOS ||--o{ ESTOQUES : "produto_id"
    USUARIOS ||--o| FIDELIDADES : "usuario_id unico"
    USUARIOS o|--o{ PEDIDOS : "cliente_id"
    USUARIOS ||--o{ PEDIDOS : "criado_por_id"
    UNIDADES ||--o{ PEDIDOS : "unidade_id"
    PEDIDOS ||--o{ ITENS_PEDIDO : "pedido_id"
    PRODUTOS ||--o{ ITENS_PEDIDO : "produto_id"
    PEDIDOS ||--o{ PAGAMENTOS : "pedido_id"
    PEDIDOS ||--o{ MOVIMENTACOES_ESTOQUE : "pedido_id"
    UNIDADES ||--o{ MOVIMENTACOES_ESTOQUE : "unidade_id"
    PRODUTOS ||--o{ MOVIMENTACOES_ESTOQUE : "produto_id"
    USUARIOS ||--o{ MOVIMENTACOES_ESTOQUE : "usuario_id"
    USUARIOS ||--o{ AUDITORIAS : "usuario_id"
    UNIDADES ||--o{ AUDITORIAS : "unidade_id"
```

## Diagrama de classes

```mermaid
classDiagram
    class UnidadeModel {
        +int id
        +str nome
        +str endereco
        +bool ativa
    }

    class UsuarioModel {
        +int id
        +int? unidade_id
        +str nome
        +str email
        +str senha_hash
        +str perfil
        +datetime created_at
    }

    class ProdutoModel {
        +int id
        +str sku
        +str nome
        +str? descricao
        +Decimal preco
        +bool sazonal
        +bool ativo
    }

    class EstoqueModel {
        +int unidade_id
        +int produto_id
        +int quantidade
        +bool disponivel
    }

    class FidelidadeModel {
        +int id
        +int usuario_id
        +bool aceita_fidelidade
        +int pontos_saldo
    }

    class PedidoModel {
        +int id
        +int? cliente_id
        +int criado_por_id
        +int unidade_id
        +str canal_pedido
        +str status
        +Decimal valor_bruto
        +Decimal valor_desconto
        +Decimal total
        +datetime created_at
    }

    class ItemPedidoModel {
        +int pedido_id
        +int produto_id
        +int quantidade
        +Decimal preco_unitario
        +Decimal subtotal
    }

    class PagamentoModel {
        +int id
        +int pedido_id
        +str chave_idempotencia
        +str metodo
        +str status
        +Decimal valor
        +dict payload
        +datetime created_at
    }

    class MovimentacaoEstoqueModel {
        +int id
        +int pedido_id
        +int unidade_id
        +int produto_id
        +int usuario_id
        +str tipo
        +int quantidade
        +datetime created_at
    }

    class AuditoriaModel {
        +int id
        +int usuario_id
        +int unidade_id
        +str acao
        +str entidade
        +int entidade_id
        +dict detalhes
        +datetime created_at
    }

    UnidadeModel "0..1" -- "0..*" UsuarioModel : unidade_id
    UnidadeModel "1" -- "0..*" EstoqueModel : unidade_id
    ProdutoModel "1" -- "0..*" EstoqueModel : produto_id
    UsuarioModel "1" -- "0..1" FidelidadeModel : usuario_id unico
    UsuarioModel "0..1" -- "0..*" PedidoModel : cliente_id
    UsuarioModel "1" -- "0..*" PedidoModel : criado_por_id
    UnidadeModel "1" -- "0..*" PedidoModel : unidade_id
    PedidoModel "1" -- "0..*" ItemPedidoModel : pedido_id
    ProdutoModel "1" -- "0..*" ItemPedidoModel : produto_id
    PedidoModel "1" -- "0..*" PagamentoModel : pedido_id
    PedidoModel "1" -- "0..*" MovimentacaoEstoqueModel : pedido_id
    UnidadeModel "1" -- "0..*" MovimentacaoEstoqueModel : unidade_id
    ProdutoModel "1" -- "0..*" MovimentacaoEstoqueModel : produto_id
    UsuarioModel "1" -- "0..*" MovimentacaoEstoqueModel : usuario_id
    UsuarioModel "1" -- "0..*" AuditoriaModel : usuario_id
    UnidadeModel "1" -- "0..*" AuditoriaModel : unidade_id
```
