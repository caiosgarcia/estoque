from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, json, zipfile, io, os, requests
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'estoque_secret_2024'
DB = 'estoque.db'

# ── banco de dados ──────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            nome TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT
        );
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            categoria_id INTEGER,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        );
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );
    ''')
    # usuário admin padrão
    c.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, nome) VALUES ('admin','admin123','Administrador')")
    conn.commit()
    conn.close()

# ── decorador de login ──────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── rotas de autenticação ───────────────────────────────────────────────────

@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha   = request.form['senha']
        conn = get_db()
        u = conn.execute('SELECT * FROM usuarios WHERE usuario=? AND senha=?', (usuario, senha)).fetchone()
        conn.close()
        if u:
            session['usuario'] = u['usuario']
            session['nome']    = u['nome']
            return redirect(url_for('menu'))
        flash('Usuário ou senha incorretos.', 'erro')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── menu ────────────────────────────────────────────────────────────────────

@app.route('/menu')
@login_required
def menu():
    conn = get_db()
    total_produtos   = conn.execute('SELECT COUNT(*) FROM produtos').fetchone()[0]
    total_categorias = conn.execute('SELECT COUNT(*) FROM categorias').fetchone()[0]
    total_movim      = conn.execute('SELECT COUNT(*) FROM movimentacoes').fetchone()[0]
    estoque_baixo    = conn.execute('SELECT COUNT(*) FROM produtos WHERE quantidade < 5').fetchone()[0]
    conn.close()
    return render_template('menu.html',
        total_produtos=total_produtos,
        total_categorias=total_categorias,
        total_movim=total_movim,
        estoque_baixo=estoque_baixo)

# ── produtos ────────────────────────────────────────────────────────────────

@app.route('/produtos')
@login_required
def produtos():
    conn = get_db()
    lista = conn.execute('''
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.nome
    ''').fetchall()
    categorias = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('produtos.html', produtos=lista, categorias=categorias)

@app.route('/produtos/novo', methods=['POST'])
@login_required
def produto_novo():
    conn = get_db()
    conn.execute('INSERT INTO produtos (nome,descricao,preco,quantidade,categoria_id) VALUES (?,?,?,?,?)',
        (request.form['nome'], request.form['descricao'],
         float(request.form['preco']), int(request.form['quantidade']),
         request.form['categoria_id'] or None))
    conn.commit(); conn.close()
    flash('Produto cadastrado com sucesso!', 'ok')
    return redirect(url_for('produtos'))

@app.route('/produtos/editar/<int:id>', methods=['POST'])
@login_required
def produto_editar(id):
    conn = get_db()
    conn.execute('UPDATE produtos SET nome=?,descricao=?,preco=?,quantidade=?,categoria_id=? WHERE id=?',
        (request.form['nome'], request.form['descricao'],
         float(request.form['preco']), int(request.form['quantidade']),
         request.form['categoria_id'] or None, id))
    conn.commit(); conn.close()
    flash('Produto atualizado!', 'ok')
    return redirect(url_for('produtos'))

@app.route('/produtos/excluir/<int:id>')
@login_required
def produto_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM produtos WHERE id=?', (id,))
    conn.commit(); conn.close()
    flash('Produto excluído!', 'ok')
    return redirect(url_for('produtos'))

# ── categorias ──────────────────────────────────────────────────────────────

@app.route('/categorias')
@login_required
def categorias():
    conn = get_db()
    lista = conn.execute('SELECT * FROM categorias ORDER BY nome').fetchall()
    conn.close()
    return render_template('categorias.html', categorias=lista)

@app.route('/categorias/nova', methods=['POST'])
@login_required
def categoria_nova():
    conn = get_db()
    conn.execute('INSERT INTO categorias (nome,descricao) VALUES (?,?)',
        (request.form['nome'], request.form['descricao']))
    conn.commit(); conn.close()
    flash('Categoria criada!', 'ok')
    return redirect(url_for('categorias'))

@app.route('/categorias/editar/<int:id>', methods=['POST'])
@login_required
def categoria_editar(id):
    conn = get_db()
    conn.execute('UPDATE categorias SET nome=?,descricao=? WHERE id=?',
        (request.form['nome'], request.form['descricao'], id))
    conn.commit(); conn.close()
    flash('Categoria atualizada!', 'ok')
    return redirect(url_for('categorias'))

@app.route('/categorias/excluir/<int:id>')
@login_required
def categoria_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM categorias WHERE id=?', (id,))
    conn.commit(); conn.close()
    flash('Categoria excluída!', 'ok')
    return redirect(url_for('categorias'))

# ── movimentações ───────────────────────────────────────────────────────────

@app.route('/movimentacoes')
@login_required
def movimentacoes():
    conn = get_db()
    lista = conn.execute('''
        SELECT m.*, p.nome as produto_nome
        FROM movimentacoes m JOIN produtos p ON m.produto_id = p.id
        ORDER BY m.data DESC
    ''').fetchall()
    produtos = conn.execute('SELECT * FROM produtos ORDER BY nome').fetchall()
    conn.close()
    return render_template('movimentacoes.html', movimentacoes=lista, produtos=produtos)

@app.route('/movimentacoes/nova', methods=['POST'])
@login_required
def movimentacao_nova():
    pid  = int(request.form['produto_id'])
    tipo = request.form['tipo']
    qtd  = int(request.form['quantidade'])
    conn = get_db()
    prod = conn.execute('SELECT quantidade FROM produtos WHERE id=?', (pid,)).fetchone()
    nova_qtd = prod['quantidade'] + qtd if tipo == 'entrada' else prod['quantidade'] - qtd
    if nova_qtd < 0:
        flash('Quantidade insuficiente em estoque!', 'erro')
    else:
        conn.execute('UPDATE produtos SET quantidade=? WHERE id=?', (nova_qtd, pid))
        conn.execute('INSERT INTO movimentacoes (produto_id,tipo,quantidade,data,observacao) VALUES (?,?,?,?,?)',
            (pid, tipo, qtd, datetime.now().strftime('%d/%m/%Y %H:%M'), request.form.get('observacao','')))
        conn.commit()
        flash('Movimentação registrada!', 'ok')
    conn.close()
    return redirect(url_for('movimentacoes'))

@app.route('/movimentacoes/excluir/<int:id>')
@login_required
def movimentacao_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM movimentacoes WHERE id=?', (id,))
    conn.commit(); conn.close()
    flash('Movimentação excluída!', 'ok')
    return redirect(url_for('movimentacoes'))

# ── usuários ────────────────────────────────────────────────────────────────

@app.route('/usuarios')
@login_required
def usuarios():
    conn = get_db()
    lista = conn.execute('SELECT * FROM usuarios').fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/usuarios/novo', methods=['POST'])
@login_required
def usuario_novo():
    conn = get_db()
    try:
        conn.execute('INSERT INTO usuarios (usuario,senha,nome) VALUES (?,?,?)',
            (request.form['usuario'], request.form['senha'], request.form['nome']))
        conn.commit()
        flash('Usuário criado!', 'ok')
    except:
        flash('Usuário já existe!', 'erro')
    conn.close()
    return redirect(url_for('usuarios'))

@app.route('/usuarios/editar/<int:id>', methods=['POST'])
@login_required
def usuario_editar(id):
    conn = get_db()
    conn.execute('UPDATE usuarios SET nome=?,senha=? WHERE id=?',
        (request.form['nome'], request.form['senha'], id))
    conn.commit(); conn.close()
    flash('Usuário atualizado!', 'ok')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/excluir/<int:id>')
@login_required
def usuario_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM usuarios WHERE id!=1 AND id=?', (id,))
    conn.commit(); conn.close()
    flash('Usuário excluído!', 'ok')
    return redirect(url_for('usuarios'))

# ── exportar JSON/ZIP ───────────────────────────────────────────────────────

@app.route('/exportar')
@login_required
def exportar():
    conn = get_db()
    dados = {
        'exportado_em': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'usuarios':       [dict(r) for r in conn.execute('SELECT id,usuario,nome FROM usuarios').fetchall()],
        'categorias':     [dict(r) for r in conn.execute('SELECT * FROM categorias').fetchall()],
        'produtos':       [dict(r) for r in conn.execute('SELECT * FROM produtos').fetchall()],
        'movimentacoes':  [dict(r) for r in conn.execute('SELECT * FROM movimentacoes').fetchall()],
    }
    conn.close()
    json_bytes = json.dumps(dados, ensure_ascii=False, indent=2).encode('utf-8')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('estoque.json', json_bytes)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True, download_name='estoque_export.zip')

# ── importar dados ───────────────────────────────────────────────────

@app.route('/importar')
@login_required
def importar_page():
    conn = get_db()
    importados = conn.execute('SELECT * FROM produtos WHERE descricao LIKE "%[importado]%"').fetchall()
    conn.close()
    return render_template('importar.html', importados=importados)

@app.route('/importar/executar', methods=['POST'])
@login_required
def importar_executar():
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename.endswith('.json'):
        flash('Selecione um arquivo .json válido.', 'erro')
        return redirect(url_for('importar_page'))
    try:
        dados = json.loads(arquivo.read().decode('utf-8'))
        conn = get_db()
        count_cat = count_prod = count_mov = count_usr = 0

        for item in dados.get('usuarios', []):
            existe = conn.execute('SELECT id FROM usuarios WHERE usuario=?', (item['usuario'],)).fetchone()
            if not existe:
                conn.execute('INSERT INTO usuarios (usuario,senha,nome) VALUES (?,?,?)',
                    (item['usuario'], item.get('senha','123456'), item['nome']))
                count_usr += 1
            else:
                conn.execute('UPDATE usuarios SET nome=? WHERE usuario=?',
                    (item['nome'], item['usuario']))

        for item in dados.get('categorias', []):
            existe = conn.execute('SELECT id FROM categorias WHERE nome=?', (item['nome'],)).fetchone()
            if not existe:
                conn.execute('INSERT INTO categorias (nome,descricao) VALUES (?,?)',
                    (item['nome'], item.get('descricao','')))
                count_cat += 1
            else:
                conn.execute('UPDATE categorias SET descricao=? WHERE nome=?',
                    (item.get('descricao',''), item['nome']))

        for item in dados.get('produtos', []):
            existe = conn.execute('SELECT id FROM produtos WHERE nome=?', (item['nome'],)).fetchone()
            if not existe:
                conn.execute('INSERT INTO produtos (nome,descricao,preco,quantidade,categoria_id) VALUES (?,?,?,?,?)',
                    (item['nome'], item.get('descricao',''), float(item.get('preco',0)),
                     int(item.get('quantidade',0)), item.get('categoria_id')))
                count_prod += 1
            else:
                conn.execute('UPDATE produtos SET descricao=?,preco=?,quantidade=?,categoria_id=? WHERE nome=?',
                    (item.get('descricao',''), float(item.get('preco',0)),
                     int(item.get('quantidade',0)), item.get('categoria_id'), item['nome']))

        for item in dados.get('movimentacoes', []):
            conn.execute('INSERT INTO movimentacoes (produto_id,tipo,quantidade,data,observacao) VALUES (?,?,?,?,?)',
                (item['produto_id'], item['tipo'], item['quantidade'],
                 item.get('data',''), item.get('observacao','')))
            count_mov += 1

        conn.commit()
        conn.close()
        flash(f'Importado: {count_usr} usuários, {count_cat} categorias, {count_prod} produtos, {count_mov} movimentações.', 'ok')
    except Exception as e:
        flash(f'Erro ao importar: {e}', 'erro')
    return redirect(url_for('importar_page'))

# ── sobre ───────────────────────────────────────────────────────────────────

@app.route('/sobre')
@login_required
def sobre():
    return render_template('sobre.html')

# ── relatório ───────────────────────────────────────────────────────────────

@app.route('/relatorio')
@login_required
def relatorio():
    conn = get_db()
    produtos = conn.execute('''
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.quantidade ASC
    ''').fetchall()
    conn.close()
    return render_template('relatorio.html', produtos=produtos)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
