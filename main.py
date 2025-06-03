import pdfkit
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, redirect
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'chave_secreta'  # chave para usar session

# Carrega as credenciais
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Inicializa o Firestore
db = firestore.client()

#  CURSOS #
# Pagina inicial com todos os cursos
@app.route('/')
def index():
    user_id = session.get('usuario_id')
    cursos_ref = db.collection('cursos').stream()
    cursos = []

    for doc in cursos_ref:
        data = doc.to_dict()
        data['id'] = doc.id
        cursos.append(data)

    progresso_usuario = {}

    if user_id:
        progresso_usuario = {}

        # Filtra somente as inscrições do usuário logado
        progresso_docs = db.collection('inscricoes').where('user_id', '==', user_id).stream()

        for doc in progresso_docs:
            progresso = doc.to_dict()
            etapas_concluidas = progresso.get('etapas_concluidas', [])
            curso_id = progresso.get('curso_id')

            curso_doc = db.collection('cursos').document(curso_id).get()
            if curso_doc.exists:
                total_etapas = len(curso_doc.to_dict().get('etapas', []))
                progresso_usuario[curso_id] = {
                    'concluido': len(etapas_concluidas) == total_etapas,
                    'em_andamento': 0 <= len(etapas_concluidas) < total_etapas
                }


    return render_template('index.html', cursos=cursos, progresso_usuario=progresso_usuario)

@app.route("/curso/<curso_id>")
def detalhes_curso(curso_id):
    doc_ref = db.collection("cursos").document(curso_id)
    doc = doc_ref.get()
    if doc.exists:
        curso = doc.to_dict()
        curso['id'] = doc.id
        print(curso)
        return render_template("curso_detalhes.html", curso=curso, curso_id=curso_id)
    else:
        return "Curso não encontrado"
    
# inscreve um usuario em um curso
@app.route('/inscrever/<curso_id>', methods=['POST'])
def inscrever(curso_id):
    user_id = session.get('usuario_id', False)
    if not user_id:
        return redirect(url_for('login'))
    inscricao_ref = db.collection('inscricoes').document(f'{session['usuario_id']}_{curso_id}')
    inscricao = inscricao_ref.get()

    

    if inscricao.exists:
        flash("Usuário já está inscrito neste curso.!", "danger")
        return redirect(url_for('detalhes_curso', curso_id=curso_id))

    inscricao_ref.set({
        "user_id": session['usuario_id'],
        "curso_id": curso_id,
        "concluido": False,
        "data_inscricao": datetime.now()
    })
    
    return redirect(url_for('curso_etapa', curso_id=curso_id))

# exibir etapas do curso:
@app.route('/curso_etapa/<curso_id>')
def curso_etapa(curso_id):
    user_id = session.get('usuario_id', False)
    if not user_id:
        return redirect(url_for('login'))
    curso_ref = db.collection('cursos').document(curso_id)
    curso_doc = curso_ref.get()
    
    if not curso_doc.exists:
        return "Curso não encontrado", 404

    curso = curso_doc.to_dict()
    etapas = curso.get('etapas', [])
    total_etapas = len(etapas)

    user_id = session.get('usuario_id')
    if not user_id:
        return redirect(url_for('login'))  # redireciona se não estiver logado

    # Recuperar o progresso específico do usuário para este curso
    progresso_ref = db.collection('inscricoes').document(f'{user_id}_{curso_id}')
    progresso_doc = progresso_ref.get()

    if progresso_doc.exists:
        progresso_data = progresso_doc.to_dict()
        etapas_concluidas = progresso_data.get('etapas_concluidas', [])
        data_conclusao = progresso_data.get('data_conclusao', [])
    else:
        etapas_concluidas = []

    # Calcular porcentagem de progresso
    progresso_percentual = int((len(etapas_concluidas) / total_etapas) * 100) if total_etapas > 0 else 0

    return render_template(
        'curso_etapas.html',
        data_conclusao = data_conclusao,
        curso=curso,
        etapas_concluidas=etapas_concluidas,
        curso_id=curso_id,
        progresso_percentual=progresso_percentual
    )


# Rota para concluir uma etapa do curso
@app.route('/concluir_etapa/<curso_id>/<int:etapa_index>', methods=['POST'])
def concluir_etapa(curso_id, etapa_index):
    user_id = session.get('usuario_id')

    if not user_id:
        flash("Usuário não autenticado.")
        return redirect(url_for('login'))  # ou outra página apropriada

    progresso_ref = db.collection('inscricoes').document(f'{user_id}_{curso_id}')


    progresso_doc = progresso_ref.get()

    if progresso_doc.exists:
        progresso = progresso_doc.to_dict()
        etapas_concluidas = set(progresso.get('etapas_concluidas', []))
    else:
        etapas_concluidas = set()

    etapas_concluidas.add(etapa_index)

    # Verificar número total de etapas do curso
    curso_doc = db.collection('cursos').document(curso_id).get()
    total_etapas = len(curso_doc.to_dict().get('etapas', [])) if curso_doc.exists else 0

    # Verifica se todas as etapas foram concluídas
    data_conclusao = None
    if len(etapas_concluidas) == total_etapas and total_etapas > 0:
        data_conclusao = datetime.now()

    # Montar dados para atualizar
    dados_atualizados = {
        'etapas_concluidas': list(etapas_concluidas)
    }

    if data_conclusao:
        dados_atualizados['data_conclusao'] = data_conclusao

    progresso_ref.set(dados_atualizados, merge=True)

    return redirect(url_for('curso_etapa', curso_id=curso_id))

# rota para gerar o certificado
@app.route('/certificado/<curso_id>')
def certificado(curso_id):
    user_nome = session.get('usuario_nome')
    curso = db.collection('cursos').document(curso_id).get().to_dict()
    data = datetime.now().strftime("%d/%m/%Y")

    # Gera o HTML a partir do template
    rendered = render_template('certificado.html', nome=user_nome, curso=curso, data=data)

    # Gera o PDF a partir do HTML renderizado
    pdf = pdfkit.from_string(rendered, False)

    # Retorna o PDF como resposta para download
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=certificado_{curso_id}.pdf'

    return response

    # Se preferir redirecionar após geração, salve o PDF e use redirect('/')


#  USUÁRIO #

# Criar conta para se inscrever nos cursos
@app.route('/criar_conta', methods=['GET', 'POST'])
def criar_conta():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

        usuarios_ref = db.collection('usuarios')
        existente = usuarios_ref.where('email', '==', email).get()

        if existente:
            flash("Email já cadastrado!", "error")
            return redirect(url_for('criar_conta'))

       
        novo_usuario_ref = usuarios_ref.add({
            'nome': nome,
            'email': email,
            'senha': senha
        })


        flash("Conta criada com sucesso!", "success")
        session['usuario_id'] = novo_usuario_ref[1].id
        session['usuario_nome'] = nome
        return redirect(url_for('index'))

    return render_template('criar_conta.html')

# Fazer login na conta
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        usuarios_ref = db.collection('usuarios')
        resultado = usuarios_ref.where('email', '==', email).get()

        if not resultado:
            flash("Usuário não encontrado", "error")
            return redirect(url_for('login'))

        user_doc = resultado[0]
        user_data = user_doc.to_dict()

        if user_data['senha'] == senha:
            session['usuario_id'] = user_doc.id
            session['usuario_nome'] = user_data['nome']
            flash("Login bem-sucedido!", "success")
            return redirect(url_for('index'))
        else:
            flash("Senha incorreta", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

# Sair da conta
@app.route('/logout')
def logout():
    session.clear()
    flash("Você saiu da sua conta", "info")
    return redirect(url_for('login'))

# Iniciar o site
if __name__ == "__main__":
    app.run(debug=False)