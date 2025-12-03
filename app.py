from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui_mude_em_producao'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contadores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# Adicionar filtro personalizado para JSON
@app.template_filter('fromjson')
def fromjson_filter(value):
    """Converte string JSON para objeto Python"""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


# Modelos do Banco de Dados (mantenha os mesmos modelos anteriores)
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'cliente' ou 'contador'
    foto = db.Column(db.String(300), default='https://i.pravatar.cc/150?img=0')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    telefone = db.Column(db.String(20))
    bio = db.Column(db.Text)

    # Relacionamentos
    avaliacoes = db.relationship('Avaliacao', backref='usuario', lazy=True)
    propostas = db.relationship('Proposta', backref='cliente', lazy=True)
    mensagens_enviadas = db.relationship('Mensagem', foreign_keys='Mensagem.remetente_id', backref='remetente',
                                         lazy=True)
    mensagens_recebidas = db.relationship('Mensagem', foreign_keys='Mensagem.destinatario_id', backref='destinatario',
                                          lazy=True)


class Contador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    especialidade = db.Column(db.String(200), nullable=False)
    nota = db.Column(db.Float, default=0.0)
    avaliacoes_count = db.Column(db.Integer, default=0)
    foto = db.Column(db.String(300))
    tags = db.Column(db.String(500))  # JSON string
    tempo_resposta = db.Column(db.String(50), default='4 horas')
    localizacao = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    verificado = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    experiencia = db.Column(db.String(100))
    formacao = db.Column(db.String(200))

    # Relacionamentos
    usuario = db.relationship('Usuario', backref=db.backref('perfil_contador', uselist=False))
    avaliacoes = db.relationship('Avaliacao', backref='contador', lazy=True)
    propostas = db.relationship('Proposta', backref='contador', lazy=True)


class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contador_id = db.Column(db.Integer, db.ForeignKey('contador.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nota = db.Column(db.Float, nullable=False)
    comentario = db.Column(db.Text)
    data_avaliacao = db.Column(db.DateTime, default=datetime.utcnow)


class Proposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contador_id = db.Column(db.Integer, db.ForeignKey('contador.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pendente')  # pendente, aceita, recusada
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)


class Mensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    lida = db.Column(db.Boolean, default=False)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)


class AdminLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acao = db.Column(db.String(200), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_acao = db.Column(db.DateTime, default=datetime.utcnow)


# Dados iniciais (mantenha os mesmos dados)
contadores_iniciais = [
    {
        "nome": "Dr. João Silva",
        "especialidade": "Especialista em Tributário e MEI",
        "nota": 5.0,
        "avaliacoes_count": 35,
        "foto": "https://i.pravatar.cc/150?img=12",
        "tags": ["MEI", "Pequenas Empresas", "Consultoria"],
        "tempo_resposta": "2 horas",
        "localizacao": "São Paulo, SP",
        "descricao": "Especialista em contabilidade para MEI e pequenas empresas com 10 anos de experiência.",
        "verificado": True,
        "experiencia": "10 anos",
        "formacao": "CRC Ativo, Pós em Direito Tributário"
    },
    {
        "nome": "Dra. Maria Santos",
        "especialidade": "Contabilidade Empresarial Avançada",
        "nota": 4.8,
        "avaliacoes_count": 42,
        "foto": "https://i.pravatar.cc/150?img=8",
        "tags": ["Médias Empresas", "Auditoria", "BPO"],
        "tempo_resposta": "1 hora",
        "localizacao": "Rio de Janeiro, RJ",
        "descricao": "Contadora especializada em empresas de médio porte e auditoria.",
        "verificado": True,
        "experiencia": "8 anos",
        "formacao": "CRC Ativo, Mestrado em Controladoria"
    },
    {
        "nome": "Dr. Carlos Oliveira",
        "especialidade": "Folha de Pagamento e DP",
        "nota": 4.9,
        "avaliacoes_count": 28,
        "foto": "https://i.pravatar.cc/150?img=5",
        "tags": ["Folha de Pagamento", "DP", "eSocial"],
        "tempo_resposta": "3 horas",
        "localizacao": "Belo Horizonte, MG",
        "descricao": "Especialista em departamento pessoal e folha de pagamento.",
        "verificado": True,
        "experiencia": "12 anos",
        "formacao": "CRC Ativo, Graduação em Ciências Contábeis"
    }
]


def init_db():
    with app.app_context():
        # Drop todas as tabelas para recriar
        db.drop_all()
        db.create_all()

        # Criar usuário admin padrão
        if not Usuario.query.filter_by(email='admin@contadores.com').first():
            admin = Usuario(
                nome='Administrador Sistema',
                email='admin@contadores.com',
                senha=generate_password_hash('admin123'),
                tipo='admin',
                foto='https://i.pravatar.cc/150?img=12'  # Usa a mesma imagem do Dr. João Silva
            )
            db.session.add(admin)
            db.session.commit()

        # Adicionar contadores iniciais
        for contador_data in contadores_iniciais:
            # Criar usuário para o contador
            usuario = Usuario(
                nome=contador_data['nome'],
                email=f"{contador_data['nome'].lower().replace(' ', '.')}@contadores.com",
                senha=generate_password_hash('senha123'),
                tipo='contador',
                foto=contador_data['foto']
            )
            db.session.add(usuario)
            db.session.flush()  # Para obter o ID do usuário

            contador = Contador(
                usuario_id=usuario.id,
                nome=contador_data['nome'],
                especialidade=contador_data['especialidade'],
                nota=contador_data['nota'],
                avaliacoes_count=contador_data['avaliacoes_count'],
                foto=contador_data['foto'],
                tags=json.dumps(contador_data['tags']),
                tempo_resposta=contador_data['tempo_resposta'],
                localizacao=contador_data['localizacao'],
                descricao=contador_data.get('descricao', ''),
                verificado=contador_data.get('verificado', False),
                experiencia=contador_data.get('experiencia', ''),
                formacao=contador_data.get('formacao', '')
            )
            db.session.add(contador)

        db.session.commit()
        print("✅ Banco de dados inicializado com sucesso!")


# Funções auxiliares
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


def salvar_arquivo(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Adicionar UUID para evitar conflitos de nome
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        return f"/static/uploads/{unique_filename}"
    return None


# Rotas de Autenticação (mantenha as mesmas)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['usuario_nome'] = usuario.nome
            session['usuario_tipo'] = usuario.tipo
            session['usuario_email'] = usuario.email
            session['usuario_foto'] = usuario.foto

            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email ou senha incorretos!', 'error')

    return render_template('login.html')


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        tipo = request.form.get('tipo')

        if Usuario.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'error')
            return render_template('registro.html')

        usuario = Usuario(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha),
            tipo=tipo,
            foto=f"https://i.pravatar.cc/150?img={Usuario.query.count() + 1}"
        )

        db.session.add(usuario)
        db.session.commit()

        # Se for contador, criar perfil básico
        if tipo == 'contador':
            contador = Contador(
                usuario_id=usuario.id,
                nome=nome,
                especialidade='Especialidade a definir',
                foto=usuario.foto,
                tags=json.dumps([]),
                localizacao='Localização a definir',
                descricao='Descrição a ser preenchida'
            )
            db.session.add(contador)
            db.session.commit()

        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))

    return render_template('registro.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('index'))


# Rotas Principais
@app.route('/')
def index():
    # Se o usuário estiver logado como contador, redirecionar para o painel de solicitações
    if 'usuario_id' in session and session.get('usuario_tipo') == 'contador':
        return redirect(url_for('solicitacoes_contador'))

    contadores = Contador.query.filter_by(ativo=True).all()
    # Converter para formato JSON serializável
    contadores_data = []
    for contador in contadores:
        contadores_data.append({
            "id": contador.id,
            "nome": contador.nome,
            "especialidade": contador.especialidade,
            "nota": contador.nota,
            "avaliacoes_count": contador.avaliacoes_count,
            "foto": contador.foto,
            "tags": json.loads(contador.tags) if contador.tags else [],
            "tempo_resposta": contador.tempo_resposta,
            "localizacao": contador.localizacao,
            "descricao": contador.descricao,
            "verificado": contador.verificado,
            "usuario_id": contador.usuario_id  # Adicionar para o chat se necessário
        })

    return render_template('index.html',
                           contadores=contadores_data,
                           usuario_logado='usuario_id' in session,
                           usuario_tipo=session.get('usuario_tipo', ''))


# Mantenha todas as outras rotas existentes (filtrar, cadastrar_contador, enviar_proposta, etc.)
@app.route('/filtrar', methods=['POST'])
def filtrar():
    dados = request.get_json()
    q = dados.get('q', '')
    tags = dados.get('tags', [])

    query = Contador.query.filter_by(ativo=True)

    if q:
        query = query.filter(
            (Contador.especialidade.ilike(f'%{q}%')) |
            (Contador.nome.ilike(f'%{q}%')) |
            (Contador.descricao.ilike(f'%{q}%'))
        )

    if tags:
        for tag in tags:
            query = query.filter(Contador.tags.ilike(f'%{tag}%'))

    contadores = query.all()
    contadores_data = []

    for contador in contadores:
        contadores_data.append({
            "id": contador.id,
            "nome": contador.nome,
            "especialidade": contador.especialidade,
            "nota": contador.nota,
            "avaliacoes_count": contador.avaliacoes_count,
            "foto": contador.foto,
            "tags": json.loads(contador.tags) if contador.tags else [],
            "tempo_resposta": contador.tempo_resposta,
            "localizacao": contador.localizacao,
            "descricao": contador.descricao,
            "verificado": contador.verificado
        })

    return jsonify(contadores_data)


@app.route('/cadastrar_contador', methods=['POST'])
def cadastrar_contador():
    if 'usuario_id' not in session:
        return jsonify({"success": False, "message": "Usuário não logado!"})

    dados = request.get_json()

    # Verificar se o usuário é um contador
    usuario = Usuario.query.get(session['usuario_id'])
    if usuario.tipo != 'contador':
        return jsonify({"success": False, "message": "Apenas contadores podem cadastrar perfis!"})

    # Atualizar perfil do contador
    contador = Contador.query.filter_by(usuario_id=usuario.id).first()
    if not contador:
        contador = Contador(usuario_id=usuario.id)

    contador.nome = dados.get('nome', usuario.nome)
    contador.especialidade = dados.get('especialidade', '')
    contador.foto = dados.get('foto') or usuario.foto
    contador.tags = json.dumps(dados.get('tags', []))
    contador.localizacao = dados.get('localizacao', '')
    contador.tempo_resposta = dados.get('tempo_resposta', '4 horas')
    contador.descricao = dados.get('descricao', '')

    db.session.add(contador)
    db.session.commit()

    return jsonify({"success": True, "message": "Perfil atualizado com sucesso!"})


@app.route('/enviar_proposta', methods=['POST'])
def enviar_proposta():
    if 'usuario_id' not in session:
        return jsonify({"success": False, "message": "Usuário não logado!"})

    dados = request.get_json()

    proposta = Proposta(
        contador_id=dados.get('contador_id'),
        cliente_id=session['usuario_id'],
        mensagem=dados.get('mensagem'),
        status='pendente'
    )

    db.session.add(proposta)
    db.session.commit()

    return jsonify({"success": True, "message": "Proposta enviada com sucesso!"})


@app.route('/avaliar_contador', methods=['POST'])
def avaliar_contador():
    if 'usuario_id' not in session:
        return jsonify({"success": False, "message": "Usuário não logado!"})

    dados = request.get_json()
    contador_id = dados.get('contador_id')
    nota = dados.get('nota')
    comentario = dados.get('comentario', '')

    # Verificar se o usuário já avaliou este contador
    avaliacao_existente = Avaliacao.query.filter_by(
        contador_id=contador_id,
        usuario_id=session['usuario_id']
    ).first()

    if avaliacao_existente:
        return jsonify({"success": False, "message": "Você já avaliou este contador!"})

    # Criar nova avaliação
    avaliacao = Avaliacao(
        contador_id=contador_id,
        usuario_id=session['usuario_id'],
        nota=nota,
        comentario=comentario
    )

    db.session.add(avaliacao)

    # Atualizar nota média do contador
    contador = Contador.query.get(contador_id)
    total_avaliacoes = Avaliacao.query.filter_by(contador_id=contador_id).count()
    soma_notas = db.session.query(db.func.sum(Avaliacao.nota)).filter_by(contador_id=contador_id).scalar()

    contador.nota = soma_notas / total_avaliacoes if total_avaliacoes > 0 else nota
    contador.avaliacoes_count = total_avaliacoes

    db.session.commit()

    return jsonify({"success": True, "message": "Avaliação enviada com sucesso!"})


@app.route('/minhas_avaliacoes')
def minhas_avaliacoes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    avaliacoes = Avaliacao.query.filter_by(usuario_id=usuario_id) \
        .join(Contador) \
        .order_by(Avaliacao.data_avaliacao.desc()) \
        .all()

    # Calcular data limite para "avaliações recentes" (últimos 30 dias)
    from datetime import datetime, timedelta
    data_limite = datetime.utcnow() - timedelta(days=30)

    return render_template('avaliacoes.html',
                           avaliacoes=avaliacoes,
                           data_limite=data_limite)


@app.route('/perfil_contador/<int:contador_id>')
def perfil_contador(contador_id):
    contador = Contador.query.get_or_404(contador_id)
    avaliacoes = Avaliacao.query.filter_by(contador_id=contador_id)\
        .join(Usuario)\
        .order_by(Avaliacao.data_avaliacao.desc())\
        .all()

    contador_data = {
        "id": contador.id,
        "nome": contador.nome,
        "especialidade": contador.especialidade,
        "nota": contador.nota,
        "avaliacoes_count": contador.avaliacoes_count,
        "foto": contador.foto,
        "tags": json.loads(contador.tags) if contador.tags else [],
        "tempo_resposta": contador.tempo_resposta,
        "localizacao": contador.localizacao,
        "descricao": contador.descricao,
        "verificado": contador.verificado,
        "experiencia": contador.experiencia,
        "formacao": contador.formacao
    }

    return render_template('perfil_contador.html',
                           contador=contador_data,
                           avaliacoes=avaliacoes,
                           usuario_logado='usuario_id' in session)


# Rota Corrigida - Editar Perfil
@app.route('/editar_perfil', methods=['GET', 'POST'])
def editar_perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario = Usuario.query.get(session['usuario_id'])

    if request.method == 'POST':
        # Processar upload de arquivo
        foto_url = usuario.foto
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '':
                nova_foto = salvar_arquivo(file)
                if nova_foto:
                    foto_url = nova_foto

        # Atualizar dados básicos do usuário
        usuario.nome = request.form.get('nome', usuario.nome)
        usuario.email = request.form.get('email', usuario.email)
        usuario.foto = foto_url
        usuario.telefone = request.form.get('telefone', usuario.telefone)
        usuario.bio = request.form.get('bio', usuario.bio)

        # Se for contador, atualizar também o perfil do contador
        if usuario.tipo == 'contador':
            contador = Contador.query.filter_by(usuario_id=usuario.id).first()
            if contador:
                contador.nome = request.form.get('nome', usuario.nome)
                contador.especialidade = request.form.get('especialidade', contador.especialidade)
                contador.localizacao = request.form.get('localizacao', contador.localizacao)
                contador.descricao = request.form.get('descricao', contador.descricao)
                contador.tempo_resposta = request.form.get('tempo_resposta', contador.tempo_resposta)
                contador.foto = foto_url
                contador.experiencia = request.form.get('experiencia', contador.experiencia)
                contador.formacao = request.form.get('formacao', contador.formacao)

                tags = request.form.getlist('tags')
                contador.tags = json.dumps(tags)

        db.session.commit()

        # Atualizar a sessão
        session['usuario_nome'] = usuario.nome
        session['usuario_email'] = usuario.email
        session['usuario_foto'] = usuario.foto

        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('editar_perfil'))

    contador = None
    if usuario.tipo == 'contador':
        contador = Contador.query.filter_by(usuario_id=usuario.id).first()

    return render_template('editar_perfil.html', usuario=usuario, contador=contador)


# Adicione esta nova rota para Minhas Solicitações
@app.route('/minhas_solicitacoes')
def minhas_solicitacoes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']

    # Buscar propostas enviadas pelo usuário
    propostas = Proposta.query.filter_by(cliente_id=usuario_id) \
        .join(Contador) \
        .order_by(Proposta.data_envio.desc()) \
        .all()

    # Calcular data limite para "solicitações recentes" (últimos 30 dias)
    from datetime import datetime, timedelta
    data_limite = datetime.utcnow() - timedelta(days=30)

    return render_template('solicitacoes.html',
                           propostas=propostas,
                           data_limite=data_limite)


# Nova rota para Solicitações do Contador
@app.route('/solicitacoes_contador')
def solicitacoes_contador():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario = Usuario.query.get(session['usuario_id'])
    if usuario.tipo != 'contador':
        flash('Acesso restrito a contadores!', 'error')
        return redirect(url_for('index'))

    contador = Contador.query.filter_by(usuario_id=usuario.id).first()
    if not contador:
        flash('Perfil de contador não encontrado!', 'error')
        return redirect(url_for('index'))

    # Buscar propostas recebidas pelo contador
    propostas = Proposta.query.filter_by(contador_id=contador.id) \
        .join(Usuario, Proposta.cliente_id == Usuario.id) \
        .order_by(Proposta.data_envio.desc()) \
        .all()

    # Calcular data limite para "solicitações recentes"
    from datetime import datetime, timedelta
    data_limite = datetime.utcnow() - timedelta(days=30)

    return render_template('solicitacoes_contador.html',
                           propostas=propostas,
                           contador=contador,
                           data_limite=data_limite)


# Rota para responder proposta
@app.route('/responder_proposta', methods=['POST'])
def responder_proposta():
    if 'usuario_id' not in session:
        return jsonify({"success": False, "message": "Usuário não logado!"})

    usuario = Usuario.query.get(session['usuario_id'])
    if usuario.tipo != 'contador':
        return jsonify({"success": False, "message": "Acesso restrito a contadores!"})

    dados = request.get_json()
    proposta_id = dados.get('proposta_id')
    status = dados.get('status')
    mensagem_resposta = dados.get('mensagem_resposta', '')

    proposta = Proposta.query.get_or_404(proposta_id)

    # Verificar se a proposta pertence ao contador
    contador = Contador.query.filter_by(usuario_id=usuario.id).first()
    if proposta.contador_id != contador.id:
        return jsonify({"success": False, "message": "Proposta não encontrada!"})

    proposta.status = status
    # Podemos adicionar a mensagem de resposta se quiser armazenar
    # proposta.resposta = mensagem_resposta

    db.session.commit()

    return jsonify({"success": True, "message": f"Proposta {status} com sucesso!"})


if __name__ == '__main__':
    # init_db()  # COMENTE esta linha
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
