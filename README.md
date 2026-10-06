# Flow

> Uma pequena linguagem de pipelines que transpila para Python.

Flow tem uma única ideia central: **tudo é pipeline**. Você escreve
transformações encadeadas com `|>` e o transpiler gera o Python aninhado
equivalente.

```flow
users
    |> filter(.active and .age > 18)
    |> map(.email)
    |> unique()
    |> sort()
    |> print()
```

vira

```python
print(
    sorted(
        set(
            map(
                lambda _x: _x['email'],
                filter(lambda _x: _x['active'] and _x['age'] > 18, users)
            )
        )
    )
)
```

O objetivo **não** é competir com Python. É ter um projeto de compilador
real, pequeno o suficiente para caber na cabeça, mas completo o bastante
para exercitar lexing, parsing, resolução de nomes, inferência de tipos
com unificação, IR, lowering e geração de código — de ponta a ponta.

## Arquitetura

```
              ┌─────────────────────────────────────────────┐
              │                                             │
  source.flow │  users |> filter(.active) |> map(.email) …  │
              │                                             │
              └─────────────────────────────────────────────┘
                              │
                              ▼
                         ①  Lexer ─────────────► tokens
                              │
                              ▼
                         ②  Parser ────────────► AST
                              │
                              ▼
                         ③  Name resolution ──► AST + escopos validados
                              │
                              ▼
                         ④  Type checking ─────► AST + tipos inferidos
                              │
                              ▼
                         ⑤  IR builder ─────────► IR (chamadas aninhadas)
                              │
                              ▼
                         ⑥  Python generator ──► output.py
```

Cada etapa é um arquivo. Cada etapa tem contrato de entrada e saída
explícitos. Trocar o backend Python por JS, Go ou LLVM significa escrever
um novo `*_gen.py` — nada acima do IR precisa mudar.

## Estrutura

```
flow/
├── main.py              # CLI
├── tokens.py            # tipos de token
├── lexer.py             # texto → tokens
├── ast_nodes.py         # definição da AST
├── parser.py            # tokens → AST
├── name_resolver.py     # validação de escopos
├── flow_types.py        # sistema de tipos + unificação
├── type_checker.py      # inferência de tipos
├── ir.py                # representação intermediária
├── ir_builder.py        # AST → IR (lowering)
├── python_gen.py        # IR → Python
├── tests/
│   └── test_flow.py
└── examples/
    ├── users.flow
    ├── numbers.flow
    └── nested.flow
```

> **Nota sobre o nome `flow_types.py`:** o arquivo **não** se chama
> `types.py` porque isso colidiria com o módulo `types` da stdlib do
> Python. A mesma regra vale para qualquer arquivo do projeto: evite nomes
> que sombreiem a biblioteca padrão (`types`, `token`, `parser`, `io`...).

## Como rodar

Não tem dependências. É Python 3.11+ puro.

```bash
# Executar os testes
python tests/test_flow.py

# Imprimir o Python gerado
python main.py examples/users.flow

# Escrever num arquivo
python main.py examples/users.flow -o users.py

# Inspecionar AST e IR
python main.py examples/users.flow --ast --ir

# Executar o resultado direto
python main.py examples/users.flow --run

# Pular o type checker (útil para depurar parsing)
python main.py examples/users.flow --no-typecheck
```

## A linguagem

### Pipelines

O operador `|>` encadeia estágios. Cada estágio é uma chamada `f(args)`.
O valor do estágio anterior é passado como **último argumento** de `f`:

```flow
a |> f(x) |> g()    # vira   g(f(x, a))
```

Essa é a regra inteira. Todo o resto do compilador existe para fazer isso
funcionar bem.

### Predicados com `.field`

Dentro de um argumento, `.` se refere ao elemento que flui pelo estágio.
Isso vira uma lambda:

```flow
users |> filter(.active and .age > 18)
# filter(lambda _x: _x['active'] and _x['age'] > 18, users)
```

`.` pode aparecer dentro de qualquer expressão, com `and`/`or`/`not`,
comparações, aritmética e acesso a campos aninhados:

```flow
orders |> filter(.total > 100 or not .customer.vip)
# filter(lambda _x: _x['total'] > 100 or not _x['customer']['vip'], orders)
```

### Funções de usuário

```flow
fn is_even(n):
    (n % 2) == 0

fn square(n):
    n * n

nums
    |> filter(is_even)
    |> map(square)
    |> sum()
    |> print()
```

Funções definidas com `fn` podem ser usadas como estágios ou como
argumentos de estágios. São polimórficas (a assinatura é gerada com
variáveis de tipo frescas), mas monomórficas dentro do próprio corpo.

### Literais

```flow
42             # Int
3.14           # Float
"hello"        # Str
true / false   # Bool
[1, 2, 3]      # List[Int]
{name: "A"}    # Record (dict em Python)
```

### Builtins

| Flow      | Python       | Tipo (aprox.)                     |
|-----------|--------------|-----------------------------------|
| `filter`  | `filter`     | `(a → Bool, List[a]) → List[a]`   |
| `map`     | `map`        | `(a → b, List[a]) → List[b]`      |
| `unique`  | `set`        | `List[a] → List[a]`¹              |
| `sort`    | `sorted`     | `List[a] → List[a]`               |
| `len`     | `len`        | `List[a] → Int`                   |
| `sum`     | `sum`        | `List[Int] → Int`                 |
| `min/max` | `min`/`max`  | `List[a] → a`                     |
| `range`   | `range`      | `Int → List[Int]`                 |
| `str/int/float/bool` | idem | genéricas                  |
| `print`   | `print`      | `a → None`                        |

¹ Ao nível de tipos, `unique` devolve `List` mesmo emitindo `set(...)` no
Python. É uma simplificação deliberada — sem ela, `unique |> sort` não
typechecka, apesar de `sorted(set(...))` ser perfeitamente válido.

### Nota sobre iteradores

`map` e `filter` do Python 3 são **preguiçosos** — devolvem iteradores,
não listas. O Flow herda esse comportamento sem cerimônia:

```flow
nums |> map(.x) |> print()        # imprime <map object at 0x...>
nums |> map(.x) |> list() |> print()  # imprime [1, 2, 3]
```

Estágios que materializam: `list`, `sort`, `unique`, `sum`. Estágios
preguiçosos: `map`, `filter`, `reversed`, `zip`, `enumerate`.

## O sistema de tipos

Flow tem um sistema de tipos Hindley–Milner simplificado, com:

- variáveis de tipo (`TVar`) e unificação estrutural;
- esquemas polimórficos para builtins (cada builtin é uma *factory* que
  devolve uma assinatura fresca a cada uso);
- **registros abertos** (`TRecord(..., open=True)`), que é o que permite
  que `.field` exija apenas *alguns* campos do argumento implícito sem
  exigir que o argumento tenha **só** esses campos.

O unificador detecta `unify(t, t)` e devolve direto, evitando ciclos.

Erros de tipo apontam para a linha do `.flow` original.

## Limitações conhecidas

- **Sem classes/objetos.** Todo dado nomeado é um `dict` — por isso
  `.field` vira `['field']` e não `.field` no Python gerado.
- **Sem módulos.** Um arquivo `.flow` = um programa.
- **Sem `for`/`if` nominal.** A linguagem é só pipelines; fluxo de
  controle é feito via `filter`/`map`.
- **Sem type classes.** `sort` espera `List`, não `Iterable`. `unique`
  mente no sistema de tipos por isso.
- **Sem source maps.** Erros apontam para `line:col` do `.flow`, mas não
  há mapeamento fino do Python gerado de volta ao original.

## Extensões naturais

Em ordem de "menor esforço / maior retorno":

1. **`for user in users |> filter(.active):`** — misturar pipeline com
   laço.
2. **`import` de outros `.flow`** — reaproveitar funções `fn`.
3. **Type classes / traits** — generalizar `sort` para `Iterable`,
   resolver o "`unique` mente" de verdade.
4. **Source maps completas** — tabela de ranges IR↔Python.
5. **Backend JS** — `js_gen.py` reutilizando lexer, parser, resolver,
   type checker e IR. A separação AST→IR→gen existe exatamente para isso.

## Exemplos

### `examples/users.flow`

```flow
users = [
    {name: "Alice",   active: true,  age: 30, email: "alice@example.com"},
    {name: "Bob",     active: false, age: 25, email: "bob@example.com"},
    {name: "Charlie", active: true,  age: 17, email: "charlie@example.com"},
    {name: "Alice",   active: true,  age: 30, email: "alice@example.com"},
]

users
    |> filter(.active and .age > 18)
    |> map(.email)
    |> unique()
    |> sort()
    |> print()
```

Saída: `['alice@example.com']`

### `examples/numbers.flow`

```flow
fn is_even(n):
    (n % 2) == 0

fn square(n):
    n * n

nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

nums
    |> filter(is_even)
    |> map(square)
    |> sum()
    |> print()
```

Saída: `220`

### `examples/nested.flow`

```flow
orders = [
    {id: 1, customer: {name: "Alice", vip: true},  total: 200},
    {id: 2, customer: {name: "Bob",   vip: false}, total: 50},
    {id: 3, customer: {name: "Alice", vip: true},  total: 120},
]

orders
    |> filter(.total > 100 or not .customer.vip)
    |> map(.customer.name)
    |> unique()
    |> sort()
    |> print()
```

Saída: `['Alice', 'Bob']`

## Por que existe

Flow é um exercício de **compiladores antes de runtime**. Ele complementa
projetos como [Forge] (análise estática, CFG, data-flow) e antecede algo
como [Lumina] (linguagem completa com LLVM, memória, runtime). A ideia é
ter, num escopo controlado, cada etapa de um compilador real — e ter
disciplina para não transformá-lo numa segunda Lumina antes da hora.

A decisão mais "transpiladora" do projeto — o pulo do gato — mora em
`ir_builder.py`: a regra de que **`a |> f(args)` vira `f(args, a)`**. É
uma linha de código, mas é ela que transforma uma linguagem declarativa
de pipelines em chamadas aninhadas naturais de Python.
