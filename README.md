# 🌱 AgroSmart — Instrucciones de instalación

## Requisitos previos
- Python 3.10 o superior instalado
- Pip (viene incluido con Python)

---

## Paso 1 — Verificar que Python está instalado
Abre la terminal (cmd en Windows o terminal en Mac/Linux) y escribe:

```
python --version
```

Debe mostrar algo como: Python 3.10.x  
Si no está instalado, descárgalo desde: https://www.python.org/downloads/

---

## Paso 2 — Crear entorno virtual (recomendado)
En la carpeta del proyecto ejecuta:

```
python -m venv venv
```

Activar el entorno:
- Windows:   venv\Scripts\activate
- Mac/Linux: source venv/bin/activate

---

## Paso 3 — Instalar dependencias

```
pip install -r requirements.txt
```

Esto instala:
- Flask          → framework web
- Flask-SQLAlchemy → manejo de base de datos
- Werkzeug       → seguridad de contraseñas

---

## Paso 4 — Ejecutar la aplicación

```
python app.py
```

Abrir en el navegador: http://127.0.0.1:5000

---

## Usuarios de prueba (creados automáticamente)

| Rol           | Correo                  | Contraseña |
|---------------|-------------------------|------------|
| Administrador | admin@agrosmart.com     | admin123   |
| Agricultor    | juan@agrosmart.com      | 1234       |

---

## Estructura de carpetas esperada

```
agrosmart/
├── app.py               ← archivo principal (este)
├── requirements.txt     ← dependencias
├── agrosmart.db         ← base de datos (se crea automáticamente)
└── templates/           ← archivos HTML (pendiente por crear)
    ├── base.html
    ├── login.html
    ├── registro.html
    ├── dashboard.html
    ├── consulta.html
    ├── historial.html
    └── admin/
        ├── usuarios.html
        └── cultivos.html
```

---

## Próximos pasos del proyecto
1. Crear los templates HTML en la carpeta /templates
2. Agregar estilos CSS (Bootstrap o Tailwind)
3. Conectar los formularios con las rutas de Flask
4. Agregar gráficas del clima con Chart.js
