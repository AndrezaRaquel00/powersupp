import os
import uuid

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from dotenv import load_dotenv

# =========================
# Configuração básica / App
# =========================
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = os.getenv('FLASK_SECRET', 'sua_chave_secreta')

# =========================
# Configuração do e-mail
# =========================
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
# fallback: se não definir MAIL_DEFAULT_SENDER, usa o MAIL_USERNAME
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER') or app.config['MAIL_USERNAME']

mail = Mail(app)

# =========================
# Configuração do banco
# =========================
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'produtos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =========================
# Modelos
# =========================
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    imagem = db.Column(db.String(200), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    avaliacoes = db.relationship('Avaliacao', backref='produto', lazy=True)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(100), nullable=False)
    pedidos = db.relationship('Pedido', backref='usuario', lazy=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data = db.Column(db.DateTime, default=db.func.current_timestamp())
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True)
    endereco = db.relationship('Endereco', uselist=False, backref='pedido')

class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    produto = db.relationship('Produto')

class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    nota = db.Column(db.Integer)
    comentario = db.Column(db.Text)
    data = db.Column(db.DateTime, default=db.func.current_timestamp())

class Endereco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    cep = db.Column(db.String(20))
    rua = db.Column(db.String(100))
    numero_endereco = db.Column(db.String(10))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(50))
    cidade = db.Column(db.String(50))
    estado = db.Column(db.String(50))

# =========================
# Funções de e-mail
# =========================
def send_email(subject: str, recipients: list[str], body: str) -> None:
    """
    Envia e-mail simples em texto.
    Lança exceção se falhar (para podermos ver no log/flash).
    """
    msg = Message(subject=subject, recipients=recipients, body=body)
    mail.send(msg)

def enviar_confirmacao_cadastro(nome: str, email_destino: str) -> None:
    corpo = f"Olá {nome},\n\nSeu cadastro na Power Supps foi realizado com sucesso!\n\nObrigado por se juntar a nós!"
    send_email("Confirmação de cadastro - Power Supps", [email_destino], corpo)

def enviar_confirmacao_compra(email_destino: str, pedido_id: int, nome_cliente: str, total: float) -> None:
    corpo = (
        f"Olá {nome_cliente},\n\n"
        f"Recebemos seu pedido #{pedido_id}.\n"
        f"Valor total: R$ {total:.2f}\n\n"
        f"Em breve enviaremos novas atualizações.\n\nObrigado pela compra!"
    )
    send_email("Confirmação de Pedido - Power Supps", [email_destino], corpo)

def enviar_contato_para_admin(admin_email: str, nome: str, email: str, assunto: str, mensagem: str) -> None:
    corpo = (
        f"Novo contato recebido:\n\n"
        f"Nome: {nome}\n"
        f"E-mail: {email}\n"
        f"Assunto: {assunto}\n\n"
        f"Mensagem:\n{mensagem}"
    )
    send_email(f"[Power Supps] Contato: {assunto or 'Sem assunto'}", [admin_email], corpo)

def enviar_recuperacao(email_destino: str, link: str) -> None:
    corpo = (
        "Recebemos uma solicitação para redefinir sua senha na Power Supps.\n\n"
        f"Use o link abaixo para continuar:\n{link}\n\n"
        "Se você não solicitou, ignore este e-mail."
    )
    send_email("Recuperação de senha - Power Supps", [email_destino], corpo)

# =========================
# Rotas
# =========================
@app.route('/')
def index():
    produtos_db = Produto.query.all()
    return render_template("index.html", produtos=produtos_db)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        usuario_db = Usuario.query.filter_by(nome=usuario, senha=senha).first()
        if usuario_db:
            session['usuario'] = usuario
            flash(f'Bem-vindo, {usuario}!')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Você saiu da conta')
    return redirect(url_for('index'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['usuario']
        senha = request.form['senha']
        email_cadastro = request.form.get('email')  # opcional: se o form tiver

        if Usuario.query.filter_by(nome=nome).first():
            flash('Usuário já existe')
            return redirect(url_for('cadastro'))

        novo_usuario = Usuario(nome=nome, senha=senha)
        db.session.add(novo_usuario)
        db.session.commit()

        # Envio do e-mail:
        try:
            if email_cadastro:
                enviar_confirmacao_cadastro(nome, email_cadastro)
            else:
                # Se não tiver email no formulário, notifica o admin
                admin_email = os.getenv('ADMIN_EMAIL') or app.config['MAIL_DEFAULT_SENDER']
                enviar_contato_para_admin(
                    admin_email,
                    nome,
                    admin_email,
                    "Novo cadastro",
                    f"O usuário '{nome}' acabou de se cadastrar (sem e-mail no formulário)."
                )
        except Exception as e:
            # Mantemos o fluxo mesmo com erro de e-mail
            print("Falha ao enviar e-mail de cadastro:", e)

        flash('Usuário cadastrado com sucesso! Faça login.')
        return redirect(url_for('login'))
    return render_template('cadastro.html')

@app.route('/carrinho')
def carrinho():
    if 'usuario' not in session:
        flash('Faça login para acessar o carrinho')
        return redirect(url_for('login'))

    carrinho = session.get('carrinho', {})
    itens = []
    total = 0

    for prod_id_str, quantidade in carrinho.items():
        prod_id = int(prod_id_str)
        produto = Produto.query.get(prod_id)

        if produto:
            subtotal = produto.preco * quantidade
            total += subtotal
            itens.append({
                "produto": produto,
                "quantidade": quantidade,
                "subtotal": subtotal,
            })

    # ====================================================================================
    # 🎁 FRETE GRÁTIS – CONFIGURAÇÃO ORIGINAL
    frete_minimo = 250  # valor para liberar frete grátis
    valor_faltante = max(0, frete_minimo - total)
    tem_frete_gratis = total >= frete_minimo
    # ====================================================================================

    # ====================================================================================
    # 📦 NOVO: FRETE CALCULADO POR CEP + FRETE PADRÃO R$ 19,90
    frete = session.get("frete", None)          # salvo na sessão após calcular
    cep_usuario = session.get("cep_usuario")    # CEP digitado pelo usuário

    if tem_frete_gratis:
        frete = 0
    elif frete is None:
        # Se o usuário ainda não calculou, deixamos vazio
        frete = None

    total_geral = total + (frete if frete else 0)
    # ====================================================================================

    return render_template(
        "carrinho.html",
        itens=itens,
        total=total,
        tem_frete_gratis=tem_frete_gratis,
        valor_faltante=valor_faltante,
        frete=frete,
        cep_usuario=cep_usuario,
        total_geral=total_geral
    )

@app.route('/adicionar_ao_carrinho/<int:id>')
def adicionar_ao_carrinho(id):
    if 'usuario' not in session:
        flash('Faça login para adicionar produtos ao carrinho')
        return redirect(url_for('login'))

    carrinho = session.get('carrinho', {})

    # Garante que as chaves sejam STRINGS para o JSON funcionar
    id_str = str(id)

    carrinho[id_str] = carrinho.get(id_str, 0) + 1

    session['carrinho'] = carrinho
    flash("Produto adicionado ao carrinho!")
    return redirect(url_for('index'))

@app.route('/alterar-quantidade/<int:produto_id>', methods=['POST'])
def alterar_quantidade(produto_id):
    carrinho = session.get('carrinho', {})

    produto_id_str = str(produto_id)
    acao = request.form.get("acao")

    if produto_id_str in carrinho:

        if acao == "mais":
            carrinho[produto_id_str] += 1

        elif acao == "menos":
            carrinho[produto_id_str] -= 1
            if carrinho[produto_id_str] <= 0:
                del carrinho[produto_id_str]

    session['carrinho'] = carrinho
    return redirect(url_for('carrinho'))

@app.route('/remover_do_carrinho/<int:produto_id>', methods=['POST'])
def remover_do_carrinho(produto_id):
    carrinho = session.get('carrinho', {})
    if produto_id in carrinho:
        del carrinho[produto_id]
    session['carrinho'] = carrinho
    flash('Produto removido do carrinho com sucesso!')
    return redirect(url_for('carrinho'))

@app.route('/limpar_carrinho', methods=['POST'])
def limpar_carrinho():
    session['carrinho'] = {}
    flash('Carrinho limpo com sucesso!')
    return redirect(url_for('carrinho'))

@app.route('/calcular_frete', methods=['POST'])
def calcular_frete():
    cep = request.form.get("cep")

    if not cep or len(cep) < 8:
        flash("CEP inválido. Digite um CEP válido.", "error")
        return redirect(url_for('carrinho'))

    carrinho = session.get('carrinho', {})

    # Calcula subtotal total
    total = 0
    for prod_id_str, quantidade in carrinho.items():
        prod_id = int(prod_id_str)
        produto = Produto.query.get(prod_id)
        if produto:
            total += produto.preco * quantidade

    # Aplica regra do frete
    if total >= 250:
        frete = 0.0
    else:
        frete = 19.90

    # Salva na sessão
    session["cep_usuario"] = cep
    session["frete"] = frete

    flash(f"Frete calculado! Valor do frete: R$ {frete:.2f}", "success")
    return redirect(url_for('carrinho'))

@app.route("/frete-gratis")
def frete_gratis():
    return render_template("frete_gratis.html")

@app.route('/finalizar_compra', methods=['GET', 'POST'])
def finalizar_compra():
    if 'usuario' not in session:
        flash('Faça login para finalizar a compra')
        return redirect(url_for('login'))

    if request.method == 'POST':
        cep = request.form.get('cep')
        rua = request.form.get('rua')
        numero_endereco = request.form.get('numero')
        complemento = request.form.get('complemento')
        bairro = request.form.get('bairro')
        cidade = request.form.get('cidade')
        estado = request.form.get('estado')
        email_cliente = request.form.get('email')

        if not all([cep, rua, numero_endereco, bairro, cidade, estado, email_cliente]):
            flash('Preencha todos os campos, incluindo o e-mail para confirmação.')
            return redirect(url_for('finalizar_compra'))

        usuario = Usuario.query.filter_by(nome=session['usuario']).first()
        pedido = Pedido(usuario_id=usuario.id)
        db.session.add(pedido)
        db.session.flush()

        endereco = Endereco(
            pedido_id=pedido.id,
            cep=cep,
            rua=rua,
            numero_endereco=numero_endereco,
            complemento=complemento,
            bairro=bairro,
            cidade=cidade,
            estado=estado
        )
        db.session.add(endereco)

        total = 0.0
        carrinho = session.get("carrinho", {})

        itens_para_email = []

        for pid, quantidade in carrinho.items():
            prod = Produto.query.get(pid)
            if prod:
                total += float(prod.preco) * quantidade

                # salvar itens na tabela ItemPedido
                for _ in range(quantidade):
                    item = ItemPedido(pedido_id=pedido.id, produto_id=pid)
                    db.session.add(item)

                itens_para_email.append({
                    "produto": prod.nome,
                    "quantidade": quantidade,
                    "preco": prod.preco
                })

        db.session.commit()

        session['carrinho'] = {}

        try:
            enviar_confirmacao_compra(
                nome=session.get('usuario', 'Cliente'),
                email_destino=email_cliente,
                itens=itens_para_email,
                total=total
            )
        except Exception as e:
            print("Falha ao enviar e-mail de pedido:", e)

        return render_template('obrigado.html', nome=session.get('usuario', 'Cliente'))

    return render_template('finalizar_compra.html')

@app.route('/avaliar/<int:produto_id>', methods=['POST'])
def avaliar(produto_id):
    if 'usuario' not in session:
        flash('Faça login para avaliar')
        return redirect(url_for('login'))

    nota = int(request.form['nota'])
    comentario = request.form['comentario']
    usuario = Usuario.query.filter_by(nome=session['usuario']).first()

    avaliacao = Avaliacao(usuario_id=usuario.id, produto_id=produto_id, nota=nota, comentario=comentario)
    db.session.add(avaliacao)
    db.session.commit()
    flash('Avaliação enviada com sucesso!')
    return redirect(url_for('index'))

@app.route('/meus-pedidos')
def meus_pedidos():
    if 'usuario' not in session:
        flash('Faça login para ver seus pedidos')
        return redirect(url_for('login'))

    usuario = Usuario.query.filter_by(nome=session['usuario']).first()
    pedidos = Pedido.query.filter_by(usuario_id=usuario.id).order_by(Pedido.data.desc()).all()
    return render_template('meus_pedidos.html', pedidos=pedidos)

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if 'usuario' not in session:
        flash('Faça login para adicionar produtos')
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form['nome']
        preco = float(request.form['preco'])
        imagem = request.files['imagem']

        if imagem and allowed_file(imagem.filename):
            ext = imagem.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # opcional: filename = secure_filename(filename)
            imagem.save(caminho_completo)

            novo_produto = Produto(nome=nome, imagem=filename, preco=preco)
            db.session.add(novo_produto)
            db.session.commit()

            flash('Produto adicionado com sucesso!')
            return redirect(url_for('index'))
        else:
            flash("Formato de imagem inválido. Use .jpg, .png, .gif ou .jpeg")
            return redirect(url_for('adicionar'))

    return render_template("adicionar.html")

@app.route('/excluir/<int:id>', methods=['POST'])
def excluir(id):
    if 'usuario' not in session:
        flash('Faça login para excluir produtos')
        return redirect(url_for('login'))

    produto = Produto.query.get_or_404(id)
    caminho_img = os.path.join(app.config['UPLOAD_FOLDER'], produto.imagem)
    if os.path.exists(caminho_img):
        os.remove(caminho_img)

    db.session.delete(produto)
    db.session.commit()

    carrinho = session.get('carrinho', [])
    if id in carrinho:
        carrinho.remove(id)
        session['carrinho'] = carrinho

    flash('Produto excluído com sucesso!')
    return redirect(url_for('index'))

@app.route('/contato', methods=['GET', 'POST'])
def contato():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        assunto = request.form.get('assunto')
        mensagem = request.form.get('mensagem')
        admin_email = os.getenv('ADMIN_EMAIL') or app.config['MAIL_DEFAULT_SENDER']
        try:
            enviar_contato_para_admin(admin_email, nome, email, assunto, mensagem)
            flash('Mensagem enviada! Em breve entraremos em contato.', 'success')
        except Exception as e:
            flash(f'Erro ao enviar mensagem: {e}', 'danger')
        return redirect(url_for('contato'))
    return render_template('contact.html')

@app.route('/recuperar', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form.get('email')
        token = 'TOKEN123456'
        link = url_for('login', _external=True) + f'?reset={token}'
        try:
            enviar_recuperacao(email, link)
            flash('E-mail de recuperação enviado.', 'info')
        except Exception as e:
            flash(f'Erro: {e}', 'danger')
        return redirect(url_for('recover'))
    return render_template('recover.html')
@app.route('/faq')
def faq():
    faqs = [
        ("Quais formas de pagamento são aceitas?", "Aceitamos Pix, cartão de crédito, débito e boleto bancário."),
        ("Os produtos são originais?", "Sim! Todos os nossos suplementos e roupas são 100% originais e com nota fiscal."),
        ("Quanto tempo demora a entrega?", "O prazo médio é de 3 a 10 dias úteis, dependendo da sua região."),
        ("Vocês enviam para todo o Brasil?", "Sim, realizamos entregas em todo o território nacional."),
        ("Como acompanho meu pedido?", "Você pode acessar a aba 'Meus Pedidos' no menu superior para acompanhar o status."),
        ("Posso trocar um produto?", "Sim, temos uma política de troca em até 7 dias após o recebimento."),
        ("O whey protein é indicado para iniciantes?", "Sim, ele ajuda na recuperação muscular e pode ser usado por quem está começando."),
        ("As roupas possuem tamanhos grandes?", "Sim, trabalhamos com tamanhos do P ao GG e alguns modelos até XG."),
        ("Os produtos têm garantia?", "Sim, todos os produtos têm garantia de fabricação conforme o fornecedor."),
        ("Posso comprar sem criar uma conta?", "Não. É necessário ter uma conta para garantir segurança e controle do pedido."),
        ("Vocês têm loja física?", "Atualmente, atendemos apenas online, com envios rápidos e suporte personalizado."),
        ("Como funciona o frete grátis?", "Oferecemos frete grátis em compras acima de R$250,00."),
        ("O site é seguro?", "Sim! Nosso site utiliza criptografia SSL e gateways de pagamento confiáveis."),
        ("Posso cancelar meu pedido?", "Sim, o cancelamento é possível antes da expedição do pedido."),
        ("Qual o prazo para reembolso?", "O reembolso é feito em até 5 dias úteis após a confirmação da devolução."),
        ("Os suplementos têm validade longa?", "Sim, todos são enviados com no mínimo 6 meses de validade."),
        ("Vocês têm atendimento pelo WhatsApp?", "Sim! Nosso atendimento via WhatsApp está disponível de segunda a sábado."),
        ("As roupas encolhem na lavagem?", "Não, nossos tecidos são de alta qualidade e resistentes a lavagens."),
        ("Vocês oferecem desconto para academia ou grupos?", "Sim! Entre em contato para saber mais sobre nossos pacotes corporativos."),
        ("Como posso entrar em contato com o suporte?", "Você pode usar o chat do site ou enviar um e-mail para suporte@gymware.com.br."),
    ]
    return render_template('faq.html', faqs=faqs)


@app.route('/teste-email')
def teste_email():
    try:
        admin = os.getenv("ADMIN_EMAIL") or app.config['MAIL_DEFAULT_SENDER']
        msg = Message(
            subject="Teste de E-mail Flask",
            recipients=[admin],
            body="Este é um e-mail de teste enviado pelo Flask usando Gmail + .env"
        )
        mail.send(msg)
        return "✅ E-mail enviado com sucesso! Verifique sua caixa de entrada."
    except Exception as e:
        return f"❌ Erro ao enviar e-mail: {e}"

import pandas as pd
import matplotlib.pyplot as plt
import os

@app.route('/admin/relatorios')
def relatorios_admin():
    import matplotlib.pyplot as plt
    import pandas as pd
    import os

    # Criar pasta /static/graficos se não existir
    pasta_graficos = os.path.join(app.static_folder, "graficos")
    os.makedirs(pasta_graficos, exist_ok=True)

    # Buscar itens vendidos
    itens = ItemPedido.query.all()

    dados = []
    for item in itens:
        if item.produto:
            dados.append(item.produto.nome)

    if not dados:
        return render_template("relatorios.html", grafico=None)

    df = pd.DataFrame(dados, columns=["produto"])

    # Contagem de vendas por produto
    vendas = df["produto"].value_counts()

    # Criar gráfico horizontal
    plt.figure(figsize=(10, 6))
    
    # Barras horizontais (barh)
    plt.barh(
        vendas.index,
        vendas.values,
        color="#1a73e8"  # azul padrão PowerSupps
    )

    # Título e rótulos
    plt.title("Produtos mais vendidos", fontsize=16)
    plt.xlabel("Quantidade vendida")
    plt.ylabel("Produto")

    # Inverte para mostrar o produto mais vendido no topo
    plt.gca().invert_yaxis()

    # Valores nas barras
    for i, v in enumerate(vendas.values):
        plt.text(v + 0.1, i, str(v), va='center', fontsize=10)

    # Caminho da imagem
    caminho_imagem = os.path.join(pasta_graficos, "vendas_barra_horizontal.png")
    plt.savefig(caminho_imagem, bbox_inches="tight")
    plt.close()

    return render_template("relatorios.html", grafico="graficos/vendas_barra_horizontal.png")


@app.route("/enviar-relatorio")
def enviar_relatorio():
    admin_email = os.getenv("ADMIN_EMAIL") or app.config['MAIL_DEFAULT_SENDER']

    # ============ 1. Buscar dados do banco ============
    total_usuarios = Usuario.query.count()
    total_produtos = Produto.query.count()
    total_pedidos = Pedido.query.count()

    total_vendas = 0
    pedidos = Pedido.query.all()
    for pedido in pedidos:
        for item in pedido.itens:
            total_vendas += item.produto.preco

    # ============ 2. Criar relatório em texto ============
    relatorio = (
        "📊 RELATÓRIO DA POWER SUPPS\n\n"
        f"• Total de usuários cadastrados: {total_usuarios}\n"
        f"• Total de produtos cadastrados: {total_produtos}\n"
        f"• Total de pedidos realizados: {total_pedidos}\n"
        f"• Faturamento total estimado: R$ {total_vendas:.2f}\n\n"
        "O gráfico com os produtos mais vendidos está anexado neste e-mail."
    )

    # ============ 3. Gerar novamente o gráfico (igual ao relatórios_admin) ============
    pasta_graficos = os.path.join(app.static_folder, "graficos")
    os.makedirs(pasta_graficos, exist_ok=True)

    itens = ItemPedido.query.all()
    dados = []

    for item in itens:
        if item.produto:
            dados.append({
                "produto": item.produto.nome,
                "preco": item.produto.preco
            })

    if dados:
        import pandas as pd
        import matplotlib.pyplot as plt

        df = pd.DataFrame(dados)
        vendas = df["produto"].value_counts()

        plt.figure(figsize=(10, 6))
        vendas.plot(kind="bar")
        plt.title("Produtos mais vendidos")
        plt.xlabel("Produto")
        plt.ylabel("Quantidade vendida")

        caminho_imagem = os.path.join(pasta_graficos, "vendas.png")
        plt.savefig(caminho_imagem, bbox_inches="tight")
        plt.close()
    else:
        caminho_imagem = None

    # ============ 4. Enviar o e-mail COM ANEXO ============
    try:
        msg = Message(
            subject="📊 Relatório da Loja - Power Supps",
            recipients=[admin_email],
            body=relatorio
        )

        # anexar gráfico se existir
        if caminho_imagem and os.path.exists(caminho_imagem):
            with app.open_resource(caminho_imagem) as fp:
                msg.attach("grafico_vendas.png", "image/png", fp.read())

        mail.send(msg)

    except Exception as e:
        return f"Erro ao enviar relatório: {e}"

    return render_template("enviar_relatorio.html")


# =========================
# Execução
# =========================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # para desenvolvimento local
    app.run(host="127.0.0.1", port=5000, debug=True)



def enviar_confirmacao_compra(nome: str, email_destino: str, itens: list[dict], total: float) -> None:
    """
    Envia e-mail de confirmação de compra.
    `itens` deve ser uma lista de dicionários no formato:
        {"produto": "Nome", "quantidade": 2, "preco": 50.0}
    """
    try:
        lista_itens = "\n".join(
            [f"- {item['produto']} (x{item['quantidade']}) - R$ {item['preco'] * item['quantidade']:.2f}"
             for item in itens]
        )

        corpo = (
            f"Olá {nome},\n\n"
            f"Obrigado pela sua compra na Power Supps! 🎉\n\n"
            f"Aqui estão os detalhes do seu pedido:\n\n"
            f"{lista_itens}\n\n"
            f"Total: R$ {total:.2f}\n\n"
            f"Em breve você receberá mais informações sobre o envio.\n\n"
            f"Equipe Power Supps."
        )

        msg = Message(
            subject="Confirmação da sua compra - Power Supps",
            recipients=[email_destino],
            body=corpo
        )
        mail.send(msg)

    except Exception as e:
        print(f"❌ Erro ao enviar e-mail de compra: {e}")
        raise
