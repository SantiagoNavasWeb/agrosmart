from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "agrosmart_clave_secreta_2026"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///agrosmart.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ── MODELOS ──────────────────────────────

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id                  = db.Column(db.Integer, primary_key=True)
    nombre              = db.Column(db.String(100), nullable=False)
    correo              = db.Column(db.String(150), unique=True, nullable=False)
    contrasena          = db.Column(db.String(255), nullable=False)
    region              = db.Column(db.String(100), nullable=True)
    rol                 = db.Column(db.String(20), default="agricultor")
    activo              = db.Column(db.Boolean, default=True)
    fecha_registro      = db.Column(db.DateTime, default=datetime.utcnow)
    pregunta_seguridad  = db.Column(db.String(200), nullable=True)
    respuesta_seguridad = db.Column(db.String(255), nullable=True)
    consultas           = db.relationship("ConsultaAgricola", backref="usuario", lazy=True)


class Cultivo(db.Model):
    __tablename__ = "cultivos"
    id              = db.Column(db.Integer, primary_key=True)
    nombre          = db.Column(db.String(100), nullable=False)
    temporada_ideal = db.Column(db.String(50))
    temp_min        = db.Column(db.Float)
    temp_max        = db.Column(db.Float)
    lluvia_ideal    = db.Column(db.String(20))
    descripcion     = db.Column(db.Text)
    activo          = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "temporada_ideal": self.temporada_ideal,
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
            "lluvia_ideal": self.lluvia_ideal,
            "descripcion": self.descripcion,
        }


class ConsultaAgricola(db.Model):
    __tablename__ = "consultas"
    id            = db.Column(db.Integer, primary_key=True)
    usuario_id    = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    mes           = db.Column(db.String(20), nullable=False)
    region        = db.Column(db.String(100))
    temperatura   = db.Column(db.Float)
    nivel_lluvia  = db.Column(db.String(20))
    recomendacion = db.Column(db.Text)
    nivel_riesgo  = db.Column(db.String(20))
    fecha         = db.Column(db.DateTime, default=datetime.utcnow)


class PQR(db.Model):
    __tablename__ = "pqr"
    id          = db.Column(db.Integer, primary_key=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tipo        = db.Column(db.String(20))
    asunto      = db.Column(db.String(150))
    descripcion = db.Column(db.Text)
    estado      = db.Column(db.String(20), default="pendiente")
    fecha       = db.Column(db.DateTime, default=datetime.utcnow)
    usuario     = db.relationship("Usuario", backref="pqrs")


# ── DATOS SIMULADOS ──────────────────────

CLIMA_SIMULADO = {
    "Cundinamarca": {
        "Enero":     {"temperatura": 14, "lluvia": "baja",  "temporada": "seca"},
        "Febrero":   {"temperatura": 15, "lluvia": "baja",  "temporada": "seca"},
        "Marzo":     {"temperatura": 16, "lluvia": "media", "temporada": "transicion"},
        "Abril":     {"temperatura": 18, "lluvia": "alta",  "temporada": "lluviosa"},
        "Mayo":      {"temperatura": 17, "lluvia": "alta",  "temporada": "lluviosa"},
        "Junio":     {"temperatura": 16, "lluvia": "media", "temporada": "seca"},
        "Julio":     {"temperatura": 14, "lluvia": "baja",  "temporada": "seca"},
        "Agosto":    {"temperatura": 15, "lluvia": "baja",  "temporada": "seca"},
        "Septiembre":{"temperatura": 16, "lluvia": "media", "temporada": "transicion"},
        "Octubre":   {"temperatura": 17, "lluvia": "alta",  "temporada": "lluviosa"},
        "Noviembre": {"temperatura": 17, "lluvia": "alta",  "temporada": "lluviosa"},
        "Diciembre": {"temperatura": 15, "lluvia": "media", "temporada": "transicion"},
    },
    "Boyaca": {
        "Enero":  {"temperatura": 12, "lluvia": "baja",  "temporada": "seca"},
        "Abril":  {"temperatura": 14, "lluvia": "alta",  "temporada": "lluviosa"},
        "Julio":  {"temperatura": 11, "lluvia": "baja",  "temporada": "seca"},
        "Octubre":{"temperatura": 13, "lluvia": "alta",  "temporada": "lluviosa"},
    },
    "Tolima": {
        "Enero":  {"temperatura": 28, "lluvia": "baja",  "temporada": "seca"},
        "Abril":  {"temperatura": 27, "lluvia": "alta",  "temporada": "lluviosa"},
        "Julio":  {"temperatura": 30, "lluvia": "baja",  "temporada": "seca"},
        "Octubre":{"temperatura": 26, "lluvia": "alta",  "temporada": "lluviosa"},
    },
}

MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

REGIONES = list(CLIMA_SIMULADO.keys())


# ── LOGICA DE RECOMENDACION ──────────────

def calcular_riesgo(cultivo, temperatura, lluvia):
    puntos = 0
    if cultivo.temp_min and cultivo.temp_max:
        if cultivo.temp_min <= temperatura <= cultivo.temp_max:
            puntos += 2
        elif abs(temperatura - cultivo.temp_min) <= 3 or abs(temperatura - cultivo.temp_max) <= 3:
            puntos += 1
    if cultivo.lluvia_ideal == lluvia:
        puntos += 2
    elif cultivo.lluvia_ideal == "media" and lluvia in ["baja", "alta"]:
        puntos += 1
    if puntos >= 3:
        return "bajo"
    elif puntos >= 2:
        return "medio"
    return "alto"


def generar_recomendaciones(temperatura, lluvia, temporada):
    cultivos = Cultivo.query.filter_by(activo=True).all()
    recomendaciones = []
    for cultivo in cultivos:
        riesgo = calcular_riesgo(cultivo, temperatura, lluvia)
        recomendaciones.append({
            "cultivo": cultivo.nombre,
            "riesgo": riesgo,
            "descripcion": cultivo.descripcion or "",
            "temporada_ideal": cultivo.temporada_ideal,
        })
    orden = {"bajo": 0, "medio": 1, "alto": 2}
    recomendaciones.sort(key=lambda x: orden.get(x["riesgo"], 3))
    return recomendaciones


# ── DECORADORES ──────────────────────────

def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Debes iniciar sesion primero.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorador


def admin_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if session.get("rol") != "admin":
            flash("Acceso restringido.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorador


# ── RUTAS DE AUTENTICACION ───────────────

@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo     = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "")
        usuario = Usuario.query.filter_by(correo=correo, activo=True).first()
        if usuario and check_password_hash(usuario.contrasena, contrasena):
            session["usuario_id"] = usuario.id
            session["nombre"]     = usuario.nombre
            session["rol"]        = usuario.rol
            flash("Bienvenido " + usuario.nombre, "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Correo o contrasena incorrectos.", "danger")
    return render_template("login.html")


PREGUNTAS_SEGURIDAD = [
    "Cual es el nombre de tu primera mascota?",
    "En que ciudad naciste?",
    "Cual es el apellido de soltera de tu madre?",
    "Cual es el nombre de tu escuela primaria?",
    "Cual es tu pelicula favorita?",
]

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre    = request.form.get("nombre", "").strip()
        correo    = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "")
        region    = request.form.get("region", "")
        pregunta  = request.form.get("pregunta_seguridad", "").strip()
        respuesta = request.form.get("respuesta_seguridad", "").strip().lower()
        if not nombre or not correo or not contrasena or not pregunta or not respuesta:
            flash("Todos los campos son obligatorios.", "danger")
            return render_template("registro.html", regiones=REGIONES, preguntas=PREGUNTAS_SEGURIDAD)
        if Usuario.query.filter_by(correo=correo).first():
            flash("Ya existe una cuenta con ese correo.", "warning")
            return render_template("registro.html", regiones=REGIONES, preguntas=PREGUNTAS_SEGURIDAD)
        nuevo = Usuario(
            nombre=nombre,
            correo=correo,
            contrasena=generate_password_hash(contrasena),
            region=region,
            rol="agricultor",
            pregunta_seguridad=pregunta,
            respuesta_seguridad=generate_password_hash(respuesta),
        )
        db.session.add(nuevo)
        db.session.commit()
        flash("Cuenta creada. Inicia sesion.", "success")
        return redirect(url_for("login"))
    return render_template("registro.html", regiones=REGIONES, preguntas=PREGUNTAS_SEGURIDAD)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesion cerrada.", "info")
    return redirect(url_for("login"))


# ── RUTAS AGRICULTOR ─────────────────────

@app.route("/dashboard")
@login_requerido
def dashboard():
    usuario = Usuario.query.get(session["usuario_id"])
    ultima_consulta = ConsultaAgricola.query.filter_by(
        usuario_id=usuario.id
    ).order_by(ConsultaAgricola.fecha.desc()).first()
    return render_template("dashboard.html", usuario=usuario,
                           ultima_consulta=ultima_consulta,
                           regiones=REGIONES, meses=MESES)


@app.route("/consulta", methods=["GET", "POST"])
@login_requerido
def consulta():
    resultado = None
    if request.method == "POST":
        region      = request.form.get("region", "")
        mes         = request.form.get("mes", "")
        temperatura = request.form.get("temperatura", type=float)
        lluvia      = request.form.get("lluvia", "")
        clima = {}
        if region in CLIMA_SIMULADO and mes in CLIMA_SIMULADO[region]:
            clima = CLIMA_SIMULADO[region][mes]
            temperatura = clima["temperatura"]
            lluvia      = clima["lluvia"]
        elif not temperatura or not lluvia:
            flash("Completa todos los campos.", "warning")
            return render_template("consulta.html", regiones=REGIONES, meses=MESES)
        temporada = clima.get("temporada", "desconocida")
        recomendaciones = generar_recomendaciones(temperatura, lluvia, temporada)
        riesgo_general = recomendaciones[0]["riesgo"] if recomendaciones else "alto"
        texto = ", ".join([r["cultivo"] + " (" + r["riesgo"] + ")" for r in recomendaciones[:3]])
        nueva = ConsultaAgricola(
            usuario_id=session["usuario_id"], mes=mes, region=region,
            temperatura=temperatura, nivel_lluvia=lluvia,
            recomendacion=texto, nivel_riesgo=riesgo_general,
        )
        db.session.add(nueva)
        db.session.commit()
        resultado = {
            "region": region, "mes": mes, "temperatura": temperatura,
            "lluvia": lluvia, "temporada": temporada,
            "recomendaciones": recomendaciones,
        }
    return render_template("consulta.html", regiones=REGIONES, meses=MESES, resultado=resultado)


@app.route("/historial")
@login_requerido
def historial():
    consultas = ConsultaAgricola.query.filter_by(
        usuario_id=session["usuario_id"]
    ).order_by(ConsultaAgricola.fecha.desc()).all()
    return render_template("historial.html", consultas=consultas)


@app.route("/pqr", methods=["GET", "POST"])
@login_requerido
def pqr():
    if request.method == "POST":
        tipo        = request.form.get("tipo")
        asunto      = request.form.get("asunto")
        descripcion = request.form.get("descripcion")
        nueva = PQR(
            usuario_id=session["usuario_id"],
            tipo=tipo,
            asunto=asunto,
            descripcion=descripcion,
        )
        db.session.add(nueva)
        db.session.commit()
        flash("PQR enviada correctamente.", "success")
        return redirect(url_for("pqr"))
    mis_pqrs = PQR.query.filter_by(
        usuario_id=session["usuario_id"]
    ).order_by(PQR.fecha.desc()).all()
    return render_template("pqr.html", mis_pqrs=mis_pqrs)


# ── RUTAS ADMIN ──────────────────────────

@app.route("/admin/usuarios")
@login_requerido
@admin_requerido
def admin_usuarios():
    usuarios = Usuario.query.order_by(Usuario.fecha_registro.desc()).all()
    return render_template("admin/usuarios.html", usuarios=usuarios)


@app.route("/admin/usuarios/toggle/<int:uid>")
@login_requerido
@admin_requerido
def toggle_usuario(uid):
    usuario = Usuario.query.get_or_404(uid)
    usuario.activo = not usuario.activo
    db.session.commit()
    estado = "activado" if usuario.activo else "desactivado"
    flash("Usuario " + usuario.nombre + " " + estado, "info")
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/cultivos", methods=["GET", "POST"])
@login_requerido
@admin_requerido
def admin_cultivos():
    if request.method == "POST":
        nombre      = request.form.get("nombre", "").strip()
        temp_min    = request.form.get("temp_min", type=float)
        temp_max    = request.form.get("temp_max", type=float)
        lluvia      = request.form.get("lluvia", "")
        temporada   = request.form.get("temporada", "")
        descripcion = request.form.get("descripcion", "")
        if nombre:
            cultivo = Cultivo(nombre=nombre, temp_min=temp_min, temp_max=temp_max,
                              lluvia_ideal=lluvia, temporada_ideal=temporada,
                              descripcion=descripcion)
            db.session.add(cultivo)
            db.session.commit()
            flash("Cultivo " + nombre + " agregado.", "success")
    cultivos = Cultivo.query.order_by(Cultivo.nombre).all()
    return render_template("admin/cultivos.html", cultivos=cultivos)


@app.route("/admin/cultivos/eliminar/<int:cid>")
@login_requerido
@admin_requerido
def eliminar_cultivo(cid):
    cultivo = Cultivo.query.get_or_404(cid)
    cultivo.activo = False
    db.session.commit()
    flash("Cultivo " + cultivo.nombre + " eliminado.", "info")
    return redirect(url_for("admin_cultivos"))


@app.route("/admin/pqr")
@login_requerido
@admin_requerido
def admin_pqr():
    pqrs = PQR.query.order_by(PQR.fecha.desc()).all()
    return render_template("admin/pqr.html", pqrs=pqrs)


@app.route("/admin/pqr/estado/<int:pid>/<estado>")
@login_requerido
@admin_requerido
def cambiar_estado_pqr(pid, estado):
    pqr_item = PQR.query.get_or_404(pid)
    pqr_item.estado = estado
    db.session.commit()
    flash("Estado actualizado.", "success")
    return redirect(url_for("admin_pqr"))


# ── API INTERNA ──────────────────────────

@app.route("/api/clima/<region>/<mes>")
@login_requerido
def api_clima(region, mes):
    if region in CLIMA_SIMULADO and mes in CLIMA_SIMULADO[region]:
        return jsonify({"ok": True, "data": CLIMA_SIMULADO[region][mes]})
    return jsonify({"ok": False, "mensaje": "Datos no disponibles"}), 404


@app.route("/api/cultivos")
@login_requerido
def api_cultivos():
    cultivos = Cultivo.query.filter_by(activo=True).all()
    return jsonify([c.to_dict() for c in cultivos])


# ── DATOS INICIALES ──────────────────────

def crear_datos_iniciales():
    if Usuario.query.count() == 0:
        admin = Usuario(
            nombre="Administrador",
            correo="admin@agrosmart.com",
            contrasena=generate_password_hash("admin123"),
            rol="admin", activo=True,
        )
        agricultor = Usuario(
            nombre="Juan Felipe",
            correo="juan@agrosmart.com",
            contrasena=generate_password_hash("1234"),
            region="Cundinamarca",
            rol="agricultor", activo=True,
        )
        db.session.add_all([admin, agricultor])

    if Cultivo.query.count() == 0:
        cultivos_iniciales = [
            Cultivo(nombre="Papa",   temp_min=10, temp_max=20, lluvia_ideal="alta",  temporada_ideal="lluviosa",    descripcion="Cultivo de clima frio, ideal en Cundinamarca y Boyaca."),
            Cultivo(nombre="Maiz",   temp_min=18, temp_max=30, lluvia_ideal="media", temporada_ideal="todo el anio",descripcion="Cultivo versatil, requiere buena humedad."),
            Cultivo(nombre="Tomate", temp_min=18, temp_max=28, lluvia_ideal="media", temporada_ideal="seca",        descripcion="Prefiere clima calido y riego controlado."),
            Cultivo(nombre="Arroz",  temp_min=22, temp_max=35, lluvia_ideal="alta",  temporada_ideal="lluviosa",    descripcion="Necesita alta temperatura y abundante agua."),
            Cultivo(nombre="Frijol", temp_min=16, temp_max=26, lluvia_ideal="media", temporada_ideal="transicion",  descripcion="Adaptable a climas medios, sensible a heladas."),
            Cultivo(nombre="Yuca",   temp_min=24, temp_max=35, lluvia_ideal="media", temporada_ideal="todo el anio",descripcion="Resistente a sequia, cultivo de tierras calidas."),
        ]
        db.session.add_all(cultivos_iniciales)

    db.session.commit()
    print("Datos iniciales creados.")

@app.route("/olvide-contrasena", methods=["GET", "POST"])
def olvide_contrasena():
    usuario = None
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        usuario = Usuario.query.filter_by(correo=correo).first()
        if not usuario:
            flash("No existe una cuenta con ese correo.", "danger")
            return render_template("olvide_contrasena.html")
        if not usuario.pregunta_seguridad:
            flash("Esta cuenta no tiene pregunta de seguridad configurada. Contacta al administrador.", "warning")
            return render_template("olvide_contrasena.html")
        return render_template("olvide_contrasena.html", usuario=usuario)
    return render_template("olvide_contrasena.html")


@app.route("/verificar-seguridad", methods=["POST"])
def verificar_seguridad():
    correo   = request.form.get("correo", "").strip()
    respuesta = request.form.get("respuesta_seguridad", "").strip().lower()
    usuario  = Usuario.query.filter_by(correo=correo).first()
    if not usuario or not check_password_hash(usuario.respuesta_seguridad, respuesta):
        flash("Respuesta incorrecta. Intenta de nuevo.", "danger")
        return render_template("olvide_contrasena.html", usuario=usuario)
    return render_template("resetear_contrasena.html", correo=correo)


@app.route("/resetear-contrasena", methods=["POST"])
def resetear_contrasena():
    correo    = request.form.get("correo", "").strip()
    nueva     = request.form.get("contrasena", "")
    confirmar = request.form.get("confirmar", "")
    if nueva != confirmar:
        flash("Las contrasenas no coinciden.", "danger")
        return render_template("resetear_contrasena.html", correo=correo)
    usuario = Usuario.query.filter_by(correo=correo).first()
    if usuario:
        usuario.contrasena = generate_password_hash(nueva)
        db.session.commit()
        flash("Contrasena actualizada correctamente. Ya puedes iniciar sesion.", "success")
        return redirect(url_for("login"))
    flash("Ocurrio un error. Intenta de nuevo.", "danger")
    return redirect(url_for("olvide_contrasena"))
    
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        crear_datos_iniciales()
    print("AgroSmart corriendo en http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
