# 📦 EstoqueRP — Sistema de Controle de Estoque

## Como rodar

### 1. Instale as dependências

```
pip install flask requests
```

### 2. Execute o sistema

```
python app.py
```

### 3. Acesse no navegador

```
http://localhost:5000
```

### Login padrão

- **Usuário:** admin
- **Senha:** admin123

---

## Interfaces (UIs) implementadas

1. 🔐 Login
2. 🏠 Menu / Dashboard
3. 📦 Produtos (Insert, Update, Delete, Select)
4. 🗂️ Categorias (Insert, Update, Delete, Select)
5. 🔄 Movimentações (Insert, Delete, Select)
6. 👥 Usuários (Insert, Update, Delete, Select)
7. 📊 Relatório de Estoque
8. 🌐 Importar JSON
9. 📤 Exportar JSON + ZIP
10. ℹ️ Sobre

## Banco de dados (SQLite)

- `usuarios` — Login e controle de acesso
- `categorias` — Categorias de produtos
- `produtos` — Cadastro de produtos
- `movimentacoes` — Entradas e saídas de estoque
