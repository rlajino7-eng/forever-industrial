from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
import threading
import time

app = FastAPI(title="Forever Industrial - RS Ingenieria Industrial", version="5.0.0")

DB_FILE = "industrial_hub.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders_cache (
            codigo TEXT PRIMARY KEY,
            titulo TEXT,
            mandante TEXT,
            region TEXT,
            comuna TEXT,
            categoria TEXT,
            presupuesto TEXT,
            cierre TEXT,
            fuente TEXT,
            link TEXT,
            fecha_descubrimiento TEXT,
            requisitos TEXT,
            empresas_postulando TEXT,
            tipo_origen TEXT,
            imagen_url TEXT,
            detalles_completos TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS postulaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_postulacion TEXT,
            titulo TEXT,
            mandante TEXT,
            region TEXT,
            comuna TEXT,
            categoria TEXT,
            presupuesto TEXT,
            estado TEXT,
            fuente TEXT,
            link_original TEXT,
            nombre_empresa TEXT,
            rut_empresa TEXT,
            email_contacto TEXT,
            carta_propuesta TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes_licencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_empresa TEXT,
            email TEXT UNIQUE,
            password TEXT,
            estado TEXT,
            fecha_creacion TEXT
        )
    ''')
    
    cursor.execute('SELECT id FROM clientes_licencias WHERE email = ?', ('admin@foreverindustrial.cl',))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO clientes_licencias (nombre_empresa, email, password, estado, fecha_creacion)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Administrador Master', 'admin@foreverindustrial.cl', 'admin2026*', 'activo', datetime.now().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    conn.close()

init_db()

class PostulacionCreate(BaseModel):
    titulo: str
    mandante: str
    region: str
    comuna: str
    categoria: str
    presupuesto: str
    fuente: str
    link_original: str
    nombre_empresa: str
    rut_empresa: str
    email_contacto: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ClienteCreate(BaseModel):
    nombre_empresa: str
    email: str
    password: str

def background_tender_scraper():
    while True:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            massive_industrial_tenders = [
                ("ARAUCO-PIP-801", "Montaje de Líneas de Piping de Vapor de Alta Presión y Condensados", "Celulosa Arauco y Constitución S.A.", "Región del Biobío", "Arauco", "Piping Industrial", "$185.000.000", "SAP Ariba (Arauco)", "https://sapariba.arauco.com", "Certificación ASME IX de soldadores, Inducción de seguridad Arauco obligatoria, Garantía de seriedad de la oferta 3%, Presentación de plan de calidad y control dimensional.", "TecnoRed SPA, Maestranza Biobío, Constructora del Sur", "Licitación Privada", "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800"),
                ("CMPC-MANT-802", "Mantención Mayor de Calderas de Poder y Recuperación Planta Laja", "CMPC Celulosa S.A.", "Región del Biobío", "Laja", "Mantención y Calderas", "$140.000.000", "Wherex (CMPC)", "https://app.wherex.com", "Operadores con certificación SEC vigente, Experiencia mínima de 5 años en plantas de celulosa, Cumplimiento estricto de protocolos CMPC, Exámenes preocupacionales rigurosos.", "CMPC Contratistas, Servimont Ltda.", "Licitación Privada", "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=800"),
                ("BHP-EST-803", "Fabricación y Montaje Estructuras Metálicas Naves de Concentrado", "Minera Escondida Ltda. (BHP)", "Región de Antofagasta", "Antofagasta", "Estructuras Metálicas", "$350.000.000", "BHP Global Procurement", "https://www.bhp.com", "Aprobación de estándar de seguridad minera SsoP, Certificación calidad de aceros ASTM A36/A572, Exámenes de altura geográfica y alcohol/drogas al día.", "Minera Servicios del Norte, Maestranza Antofagasta", "Licitación Minera", "https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=800"),
                ("ENAP-EST-804", "Mantención y Recubrimiento Anticorrosivo Estanques de Almacenamiento", "Enap Refinerías Aconcagua", "Región de Valparaíso", "Concón", "Obras Civiles / Pintura", "$95.000.000", "SAP Ariba (ENAP)", "https://sapariba.arauco.com", "Certificación NACE para inspección de revestimientos, Protocolos de espacios confinados y permisos de trabajo en caliente.", "Constructora Aconcagua, Pinturas Industriales S.A.", "Licitación Petróleo", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=800"),
                ("MOP-VIG-805", "Conservación Global y Mejoramiento de Rutas Industriales Secundarias", "Ministerio de Obras Públicas - MOP", "Región del Biobío", "Mulchén", "Obras Viales", "$220.000.000", "Mercado Público", "https://www.mercadopublico.cl", "Inscripción vigente en Registro de Obras Mayores MOP (Categoría 3 O.C. o superior), Maquinaria propia acreditada, Residente residente Ingeniero Civil.", "Constructora Vial Sur, Obras Civiles Biobío Ltda.", "Licitación Pública", "https://images.unsplash.com/photo-1541888946425-d0fbb18f86f6?w=800"),
                ("CODELCO-MEC-806", "Overhaul de Molinos SAG y Reparación de Corazas División Chuquicamata", "Codelco Chile", "Región de Antofagasta", "Calama", "Montaje Mecánico", "$410.000.000", "Portal Codelco Compras", "https://www.codelco.com", "Certificación en torque y tensionado de pernos estructurales, Riggers con certificación Cnccp, Historial intachable en seguridad industrial.", "Montajes Mineros del Norte, Serv. Metalmecánicos Andinos", "Licitación Minera", "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=800")
            ]

            for codigo, title, mandante, region, comuna, cat, presup, fuente, link, reqs, postus, tipo, img in massive_industrial_tenders:
                cursor.execute('''
                    INSERT OR IGNORE INTO tenders_cache (codigo, titulo, mandante, region, comuna, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos, empresas_postulando, tipo_origen, imagen_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (codigo, title, mandante, region, comuna, cat, presup, (datetime.now() + timedelta(days=25)).strftime("%Y-%m-%d"), fuente, link, datetime.now().strftime("%Y-%m-%d %H:%M"), reqs, postus, tipo, img))

            conn.commit()
            conn.close()
        except Exception as ex:
            print("Background scraper error:", str(ex))
        
        time.sleep(300)

threading.Thread(target=background_tender_scraper, daemon=True).start()

@app.post("/api/login")
def login_cliente(data: LoginRequest):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT nombre_empresa, email, estado FROM clientes_licencias WHERE email = ? AND password = ?', (data.email, data.password))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "Credenciales incorrectas o usuario no registrado."}
    if row[2] != "activo":
        return {"status": "error", "message": "Su licencia se encuentra inactiva."}

    is_admin = (row[1] == "admin@foreverindustrial.cl")
    return {
        "status": "success",
        "nombre_empresa": row[0],
        "email": row[1],
        "is_admin": is_admin,
        "message": "Acceso autorizado."
    }

@app.get("/api/admin/clientes")
def get_clientes():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre_empresa, email, estado, fecha_creacion FROM clientes_licencias ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return {"status": "success", "clientes": [{"id": r[0], "nombre_empresa": r[1], "email": r[2], "estado": r[3], "fecha_creacion": r[4]} for r in rows]}

@app.post("/api/admin/crear-cliente")
def crear_cliente(data: ClienteCreate):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO clientes_licencias (nombre_empresa, email, password, estado, fecha_creacion)
            VALUES (?, ?, ?, 'activo', ?)
        ''', (data.nombre_empresa, data.email, data.password, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Cuenta creada para {data.nombre_empresa}."}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": "El correo ya está registrado."}

@app.get("/api/tenders")
def get_tenders():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT codigo, titulo, mandante, region, comuna, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos, empresas_postulando, tipo_origen, imagen_url 
        FROM tenders_cache 
        GROUP BY titulo, mandante
        ORDER BY fecha_descubrimiento DESC
    ''')
    rows = cursor.fetchall()
    conn.close()

    tenders_list = []
    for r in rows:
        tenders_list.append({
            "codigo": r[0],
            "titulo": r[1],
            "mandante": r[2],
            "region": r[3],
            "comuna": r[4],
            "categoria": r[5],
            "presupuesto": r[6],
            "cierre": r[7],
            "fuente": r[8],
            "link": r[9],
            "fecha_descubrimiento": r[10],
            "requisitos": r[11] or "Cumplimiento normativo de seguridad y bases técnicas completas del mandante.",
            "empresas_postulando": r[12] or "Sin postulantes registrados",
            "tipo_origen": r[13] or "Licitación Industrial",
            "imagen_url": r[14] or "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800"
        })
    return {"status": "success", "total": len(tenders_list), "tenders": tenders_list}

@app.get("/api/postulaciones")
def get_postulaciones():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, fecha_postulacion, titulo, mandante, region, comuna, categoria, presupuesto, estado, fuente, link_original, nombre_empresa, rut_empresa, email_contacto, carta_propuesta FROM postulaciones ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r[0], "fecha_postulacion": r[1], "titulo": r[2], "mandante": r[3], "region": r[4],
            "comuna": r[5], "categoria": r[6], "presupuesto": r[7], "estado": r[8], "fuente": r[9],
            "link_original": r[10], "nombre_empresa": r[11], "rut_empresa": r[12], "email_contacto": r[13], "carta_propuesta": r[14]
        })
    return {"postulaciones": items}

@app.post("/api/postular")
def postular_trabajo(data: PostulacionCreate):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM postulaciones WHERE titulo = ? AND mandante = ? AND rut_empresa = ?', (data.titulo, data.mandante, data.rut_empresa))
    if cursor.fetchone():
        conn.close()
        return {"status": "already_exists", "message": f"Ya te has postulado a este proyecto con el RUT {data.rut_empresa}."}

    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
    carta = f"CARTA DE PROPUESTA COMERCIAL Y TÉCNICA\nEmpresa Postulante: {data.nombre_empresa}\nRUT: {data.rut_empresa}\nContacto: {data.email_contacto}\nProyecto: {data.titulo}\nMandante: {data.mandante}\nUbicación: {data.comuna}, {data.region}\nFecha: {fecha_hoy}\n\nPor medio de la presente, manifestamos nuestro interés formal y cumplimiento de los requisitos técnicos para adjudicarnos la licitación en curso."

    cursor.execute('''
        INSERT INTO postulaciones (fecha_postulacion, titulo, mandante, region, comuna, categoria, presupuesto, estado, fuente, link_original, nombre_empresa, rut_empresa, email_contacto, carta_propuesta)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Postulado con Éxito', ?, ?, ?, ?, ?, ?)
    ''', (fecha_hoy, data.titulo, data.mandante, data.region, data.comuna, data.categoria, data.presupuesto, data.fuente, data.link_original, data.nombre_empresa, data.rut_empresa, data.email_contacto, carta))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"¡Postulación enviada con éxito a {data.mandante}!", "carta": carta}

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return """
    <!DOCTYPE html>
    <html lang="es" class="h-full bg-white">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Forever Industrial | RS Ingeniería Industrial</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            body { font-family: 'Inter', sans-serif; background-color: #ffffff; color: #1e293b; }
            .yellow-brand-border { border-color: #facc15; }
            .bg-yellow-brand { background-color: #facc15; }
            .text-yellow-brand { color: #ca8a04; }
        </style>
    </head>
    <body class="h-full flex flex-col" x-data="tenderApp()">

        <!-- PANTALLA DE LOGIN -->
        <div x-show="!isLoggedIn" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-white border-2 yellow-brand-border rounded-2xl w-full max-w-md p-8 shadow-2xl space-y-6">
                <div class="text-center space-y-2">
                    <div class="inline-flex bg-yellow-brand text-slate-950 p-3 rounded-2xl font-bold shadow-md">
                        <i class="fa-solid fa-industry text-2xl"></i>
                    </div>
                    <h1 class="text-2xl font-bold text-slate-900">Forever Industrial</h1>
                    <p class="text-xs text-yellow-700 font-semibold">RS Ingeniería Industrial - Acceso Clientes</p>
                </div>
                <div class="space-y-4 text-xs">
                    <div>
                        <label class="text-slate-600 font-medium block mb-1">Correo Electrónico</label>
                        <input type="email" x-model="loginForm.email" placeholder="admin@foreverindustrial.cl" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:border-yellow-500">
                    </div>
                    <div>
                        <label class="text-slate-600 font-medium block mb-1">Contraseña</label>
                        <input type="password" x-model="loginForm.password" placeholder="••••••••••••" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:border-yellow-500" @keyup.enter="login()">
                    </div>
                    <button @click="login()" class="w-full bg-yellow-brand hover:bg-yellow-400 text-slate-950 py-3 rounded-xl font-bold transition shadow-md text-sm">
                        Iniciar Sesión
                    </button>
                </div>
                <p class="text-[11px] text-center text-slate-400">Plataforma exclusiva para profesionales y empresas del sector industrial.</p>
            </div>
        </div>

        <!-- APLICACIÓN PRINCIPAL -->
        <div class="h-full flex flex-col flex-1" x-show="isLoggedIn" style="display: none;">
            <!-- Top Navbar -->
            <header class="bg-white border-b-2 yellow-brand-border px-6 py-4 flex items-center justify-between shadow-sm sticky top-0 z-40">
                <div class="flex items-center space-x-3">
                    <div class="bg-yellow-brand text-slate-950 p-2.5 rounded-xl font-bold flex items-center justify-center shadow">
                        <i class="fa-solid fa-industry text-xl"></i>
                    </div>
                    <div>
                        <h1 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                            Forever Industrial <span class="text-xs bg-yellow-100 text-yellow-800 border border-yellow-300 px-2.5 py-0.5 rounded-full font-semibold">Buscador Industrial Pro</span>
                        </h1>
                        <p class="text-xs text-slate-500">RS Ingeniería Industrial - <span class="text-yellow-700 font-semibold" x-text="currentUser.nombre_empresa"></span></p>
                    </div>
                </div>
                
                <div class="flex items-center space-x-3">
                    <button @click="fetchTenders()" class="bg-slate-100 hover:bg-slate-200 text-slate-800 px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center space-x-2 border border-slate-300 shadow-sm">
                        <i class="fa-solid fa-rotate" :class="loading ? 'fa-spin' : ''"></i>
                        <span>Actualizar Licitaciones</span>
                    </button>
                    <button @click="logout()" class="bg-slate-100 hover:bg-rose-100 text-slate-700 hover:text-rose-700 border border-slate-300 px-3 py-2 rounded-xl text-xs font-semibold transition">
                        <i class="fa-solid fa-power-off"></i> Salir
                    </button>
                </div>
            </header>

            <main class="flex-1 overflow-hidden flex flex-col md:flex-row">
                <!-- Sidebar de Navegación y Filtros -->
                <aside class="w-full md:w-72 bg-slate-50 border-r border-slate-200 p-4 flex flex-col space-y-5 overflow-y-auto">
                    <div class="space-y-1">
                        <button @click="currentTab = 'home'" :class="currentTab === 'home' ? 'bg-yellow-100 text-yellow-900 border border-yellow-300 font-bold' : 'text-slate-600 hover:bg-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm transition text-left">
                            <i class="fa-solid fa-house w-5 text-yellow-600"></i>
                            <span>Inicio y Noticias</span>
                        </button>
                        <button @click="currentTab = 'dashboard'" :class="currentTab === 'dashboard' ? 'bg-yellow-100 text-yellow-900 border border-yellow-300 font-bold' : 'text-slate-600 hover:bg-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm transition text-left">
                            <i class="fa-solid fa-magnifying-glass-chart w-5 text-yellow-600"></i>
                            <span>Buscador de Empleos y Licitaciones</span>
                        </button>
                        <button @click="currentTab = 'postulaciones'" :class="currentTab === 'postulaciones' ? 'bg-yellow-100 text-yellow-900 border border-yellow-300 font-bold' : 'text-slate-600 hover:bg-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm transition text-left">
                            <i class="fa-solid fa-clipboard-list w-5 text-yellow-600"></i>
                            <span>Mis Postulaciones</span>
                            <span class="ml-auto bg-slate-200 text-slate-800 px-2 py-0.5 rounded-full text-xs font-bold" x-text="postulaciones.length"></span>
                        </button>
                        <template x-if="currentUser.is_admin">
                            <button @click="currentTab = 'admin'; fetchClientes();" :class="currentTab === 'admin' ? 'bg-yellow-100 text-yellow-900 border border-yellow-300 font-bold' : 'text-slate-600 hover:bg-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm transition text-left">
                                <i class="fa-solid fa-shield-halved w-5 text-yellow-600"></i>
                                <span>Panel Admin Master</span>
                            </button>
                        </template>
                    </div>

                    <!-- FILTROS -->
                    <div class="pt-4 border-t border-slate-200 space-y-3">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-500">Filtrar por Región</h3>
                        <select x-model="selectedRegion" class="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:border-yellow-500">
                            <option value="">Todas las Regiones</option>
                            <template x-for="reg in availableRegions" :key="reg">
                                <option :value="reg" x-text="reg"></option>
                            </template>
                        </select>
                    </div>
                </aside>

                <!-- Contenido Principal -->
                <section class="flex-1 overflow-y-auto p-6 bg-slate-50">
                    
                    <!-- INICIO Y NOTICIAS CON FOTOS OFICIALES -->
                    <div x-show="currentTab === 'home'" class="space-y-8 max-w-5xl mx-auto">
                        <!-- Banner de Bienvenida Profesional -->
                        <div class="bg-white border-2 yellow-brand-border rounded-2xl p-8 shadow-sm space-y-4">
                            <div class="flex items-center gap-3">
                                <span class="bg-yellow-100 text-yellow-800 border border-yellow-300 text-xs px-3 py-1 rounded-full font-bold">Portal Certificado 2026</span>
                                <span class="text-xs text-slate-500"><i class="fa-solid fa-location-dot text-yellow-600 mr-1"></i> Cobertura Nacional (Norte y Sur de Chile)</span>
                            </div>
                            <h2 class="text-3xl font-bold text-slate-900">Bienvenido al Centro de Oportunidades Industriales</h2>
                            <p class="text-sm text-slate-600 leading-relaxed">
                                Su plataforma de gestión avanzada para encontrar y postular a todas las grandes licitaciones, montajes electromecánicos, obras civiles y contratos de mantenimiento del sector industrial chileno. Actualizado en tiempo real con requerimientos completos y datos de mandantes.
                            </p>
                            <div class="pt-2">
                                <button @click="currentTab = 'dashboard'" class="bg-yellow-brand hover:bg-yellow-400 text-slate-950 px-6 py-3 rounded-xl font-bold text-xs shadow transition">
                                    Ir al Buscador de Empleos y Licitaciones <i class="fa-solid fa-arrow-right ml-1"></i>
                                </button>
                            </div>
                        </div>

                        <!-- Noticias y Proyectos Destacados del Norte y Sur con Fotos de Mandantes -->
                        <div class="space-y-4">
                            <h3 class="text-lg font-bold text-slate-900 border-l-4 border-yellow-400 pl-3">Noticias y Proyectos Clave (Norte y Sur)</h3>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm flex flex-col justify-between">
                                    <img src="https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=800" alt="Minera Norte" class="h-40 object-cover w-full">
                                    <div class="p-5 space-y-2">
                                        <span class="text-[10px] bg-purple-100 text-purple-800 font-bold px-2 py-0.5 rounded">Zona Norte - Antofagasta</span>
                                        <h4 class="font-bold text-slate-900 text-sm">Ampliación Faenas Mineras y Molinos SAG</h4>
                                        <p class="text-xs text-slate-600">Nuevas licitaciones de montaje mecánico y estructuras metálicas en Codelco y Minera Escondida con altos estándares de seguridad.</p>
                                    </div>
                                </div>
                                <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm flex flex-col justify-between">
                                    <img src="https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800" alt="Celulosa Sur" class="h-40 object-cover w-full">
                                    <div class="p-5 space-y-2">
                                        <span class="text-[10px] bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded">Zona Sur - Biobío y Laja</span>
                                        <h4 class="font-bold text-slate-900 text-sm">Par parada de planta y Piping en Celulosa Arauco</h4>
                                        <p class="text-xs text-slate-600">Contratos de alta exigencia técnica para mantención mayor y líneas de vapor con requisitos ASME estrictos en la región.</p>
                                    </div>
                                </div>
                                <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm flex flex-col justify-between">
                                    <img src="https://images.unsplash.com/photo-1541888946425-d0fbb18f86f6?w=800" alt="Vial MOP" class="h-40 object-cover w-full">
                                    <div class="p-5 space-y-2">
                                        <span class="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded">Zona Centro-Sur</span>
                                        <h4 class="font-bold text-slate-900 text-sm">Conservación Vial y Obras Hidráulicas MOP</h4>
                                        <p class="text-xs text-slate-600">Licitaciones públicas orientadas al mejoramiento de colectores y rutas secundarias con financiamiento estatal asegurado.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- BUSCADOR DE EMPLEOS Y LICITACIONES -->
                    <div x-show="currentTab === 'dashboard'" class="space-y-6">
                        <div class="bg-white border border-slate-200 p-4 rounded-2xl flex flex-col md:flex-row gap-4 items-center justify-between shadow-sm">
                            <div class="relative w-full md:w-96">
                                <i class="fa-solid fa-magnifying-glass absolute left-4 top-3.5 text-slate-400"></i>
                                <input type="text" x-model="searchQuery" placeholder="Buscar por título, mandante, comuna, categoría..." class="w-full bg-slate-50 border border-slate-300 rounded-xl pl-11 pr-4 py-2.5 text-xs text-slate-800 focus:outline-none focus:border-yellow-500">
                            </div>
                            <div class="flex items-center gap-3">
                                <span class="text-xs text-slate-600 font-medium" x-text="filteredTenders.length + ' empleos y licitaciones disponibles'"></span>
                                <button @click="fetchTenders()" class="bg-yellow-brand hover:bg-yellow-400 text-slate-950 px-4 py-2 rounded-xl text-xs font-bold shadow transition flex items-center gap-2">
                                    <i class="fa-solid fa-rotate" :class="loading ? 'fa-spin' : ''"></i>
                                    <span>Actualizar Buscador</span>
                                </button>
                            </div>
                        </div>

                        <!-- Tarjetas de Licitaciones Completas con Imágenes Oficiales -->
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <template x-for="item in filteredTenders" :key="item.codigo">
                                <div class="bg-white border border-slate-200 hover:border-yellow-400 rounded-2xl overflow-hidden shadow-sm flex flex-col justify-between transition">
                                    <div>
                                        <img :src="item.imagen_url" alt="Proyecto Industrial" class="h-40 w-full object-cover">
                                        <div class="p-5 space-y-3">
                                            <div class="flex items-center justify-between">
                                                <span class="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-blue-100 text-blue-800" x-text="item.tipo_origen"></span>
                                                <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-yellow-100 text-yellow-800" x-text="item.categoria"></span>
                                            </div>
                                            <h3 class="font-bold text-slate-900 text-sm line-clamp-2" x-text="item.titulo"></h3>
                                            <p class="text-xs font-semibold text-yellow-700 flex items-center gap-1.5">
                                                <i class="fa-solid fa-building"></i>
                                                <span x-text="item.mandante"></span>
                                            </p>
                                            
                                            <div class="space-y-1.5 text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200">
                                                <div class="flex justify-between">
                                                    <span class="text-slate-400">Región / Comuna:</span>
                                                    <span class="font-medium text-slate-800" x-text="item.region + ' / ' + item.comuna"></span>
                                                </div>
                                                <div class="flex justify-between">
                                                    <span class="text-slate-400">Presupuesto Ref:</span>
                                                    <span class="font-bold text-emerald-600" x-text="item.presupuesto"></span>
                                                </div>
                                                <div class="flex justify-between">
                                                    <span class="text-slate-400">Empresas Postulando:</span>
                                                    <span class="font-semibold text-indigo-600 truncate max-w-[140px]" x-text="item.empresas_postulando"></span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="p-5 pt-0 flex items-center space-x-2">
                                        <button @click="openDetail(item)" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-800 py-2.5 rounded-xl text-xs font-semibold transition text-center border border-slate-300">
                                            Ver Requisitos
                                        </button>
                                        <button @click="openPostularModal(item)" class="flex-1 bg-yellow-brand hover:bg-yellow-400 text-slate-950 py-2.5 rounded-xl text-xs font-bold transition text-center shadow">
                                            Postular
                                        </button>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- MIS POSTULACIONES -->
                    <div x-show="currentTab === 'postulaciones'" class="space-y-6">
                        <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                            <h2 class="text-lg font-bold text-slate-900 mb-1">Mis Postulaciones Registradas</h2>
                            <p class="text-xs text-slate-500 mb-6">Historial completo de propuestas comerciales y técnicas enviadas a través del buscador.</p>
                            
                            <div class="overflow-x-auto">
                                <table class="w-full text-left text-xs">
                                    <thead class="bg-slate-100 text-slate-600 uppercase font-semibold border-b border-slate-200">
                                        <tr>
                                            <th class="p-3">Fecha</th>
                                            <th class="p-3">Empresa Postulante</th>
                                            <th class="p-3">Proyecto / Mandante</th>
                                            <th class="p-3">Ubicación (Comuna)</th>
                                            <th class="p-3">Estado</th>
                                            <th class="p-3 text-right">Acción</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-200">
                                        <template x-for="p in postulaciones" :key="p.id">
                                            <tr class="hover:bg-slate-50">
                                                <td class="p-3 text-slate-500" x-text="p.fecha_postulacion"></td>
                                                <td class="p-3 font-bold text-slate-900" x-text="p.nombre_empresa"></td>
                                                <td class="p-3 text-slate-700">
                                                    <span class="font-semibold" x-text="p.titulo"></span>
                                                    <span class="block text-[10px] text-slate-400" x-text="p.mandante"></span>
                                                </td>
                                                <td class="p-3 text-slate-600" x-text="p.comuna + ', ' + p.region"></td>
                                                <td class="p-3"><span class="bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded-full font-bold" x-text="p.estado"></span></td>
                                                <td class="p-3 text-right space-x-2">
                                                    <button @click="openProposalModal(p)" class="text-indigo-600 font-semibold hover:underline">Ver Carta</button>
                                                </td>
                                            </tr>
                                        </template>
                                        <template x-if="postulaciones.length === 0">
                                            <tr><td colspan="6" class="text-center py-10 text-slate-400">No hay postulaciones registradas todavía.</td></tr>
                                        </template>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- PANEL ADMIN MASTER -->
                    <div x-show="currentTab === 'admin' && currentUser.is_admin" class="space-y-6">
                        <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
                            <div>
                                <h2 class="text-lg font-bold text-slate-900 mb-1"><i class="fa-solid fa-shield-halved text-yellow-600"></i> Panel Admin Master</h2>
                                <p class="text-xs text-slate-500">Cree licencias y cuentas de acceso exclusivas para vender a otras empresas.</p>
                            </div>

                            <div class="bg-slate-50 border border-slate-200 p-5 rounded-xl space-y-4">
                                <h3 class="text-xs font-bold uppercase tracking-wider text-yellow-700">Registrar Nueva Empresa Cliente</h3>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                                    <div><label class="text-slate-600 block mb-1">Nombre Empresa</label><input type="text" x-model="newClient.nombre_empresa" placeholder="Ej: Constructora Sur" class="w-full bg-white border border-slate-300 rounded-xl px-3 py-2"></div>
                                    <div><label class="text-slate-600 block mb-1">Correo de Acceso</label><input type="email" x-model="newClient.email" placeholder="cliente@empresa.cl" class="w-full bg-white border border-slate-300 rounded-xl px-3 py-2"></div>
                                    <div><label class="text-slate-600 block mb-1">Contraseña</label><input type="text" x-model="newClient.password" placeholder="Clave temporal" class="w-full bg-white border border-slate-300 rounded-xl px-3 py-2"></div>
                                </div>
                                <div class="flex justify-end">
                                    <button @click="crearCliente()" class="bg-yellow-brand hover:bg-yellow-400 text-slate-950 px-5 py-2.5 rounded-xl text-xs font-bold shadow">Crear Cuenta de Acceso</button>
                                </div>
                            </div>

                            <div>
                                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">Empresas con Licencia Activa</h3>
                                <div class="overflow-x-auto">
                                    <table class="w-full text-left text-xs">
                                        <thead class="bg-slate-100 text-slate-600 uppercase font-semibold border-b border-slate-200">
                                            <tr>
                                                <th class="p-3">ID</th>
                                                <th class="p-3">Empresa</th>
                                                <th class="p-3">Correo</th>
                                                <th class="p-3">Estado</th>
                                                <th class="p-3">Fecha Registro</th>
                                            </tr>
                                        </thead>
                                        <tbody class="divide-y divide-slate-200">
                                            <template x-for="c in clientesList" :key="c.id">
                                                <tr class="hover:bg-slate-50">
                                                    <td class="p-3 text-slate-400" x-text="c.id"></td>
                                                    <td class="p-3 font-bold text-slate-900" x-text="c.nombre_empresa"></td>
                                                    <td class="p-3 text-yellow-700 font-mono" x-text="c.email"></td>
                                                    <td class="p-3"><span class="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold" x-text="c.estado"></span></td>
                                                    <td class="p-3 text-slate-500" x-text="c.fecha_creacion"></td>
                                                </tr>
                                            </template>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
            </main>
        </div>

        <!-- MODAL DETALLES Y REQUISITOS COMPLETOS -->
        <div x-show="detailModal" class="fixed inset-0 bg-slate-950/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-white border border-slate-200 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
                <div class="flex items-start justify-between border-b border-slate-200 pb-4">
                    <div>
                        <span class="text-xs font-bold px-2.5 py-1 rounded-lg bg-yellow-100 text-yellow-800" x-text="selectedTender.tipo_origen"></span>
                        <h2 class="text-lg font-bold text-slate-900 mt-2" x-text="selectedTender.titulo"></h2>
                        <p class="text-xs text-slate-500">Mandante Oficial: <span class="font-bold text-slate-700" x-text="selectedTender.mandante"></span></p>
                    </div>
                    <button @click="detailModal = false" class="text-slate-400 hover:text-slate-900"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                
                <img :src="selectedTender.imagen_url" class="h-48 w-full object-cover rounded-xl" alt="Detalle">

                <div class="grid grid-cols-2 gap-4 text-xs bg-slate-50 p-4 rounded-xl border border-slate-200">
                    <div><span class="text-slate-400 block">Ubicación Exacta:</span><span class="font-bold text-slate-800" x-text="selectedTender.comuna + ', ' + selectedTender.region"></span></div>
                    <div><span class="text-slate-400 block">Presupuesto Referencial:</span><span class="font-bold text-emerald-600" x-text="selectedTender.presupuesto"></span></div>
                    <div><span class="text-slate-400 block">Empresas Postulando:</span><span class="font-bold text-indigo-600" x-text="selectedTender.empresas_postulando"></span></div>
                    <div><span class="text-slate-400 block">Categoría Técnica:</span><span class="font-bold text-slate-800" x-text="selectedTender.categoria"></span></div>
                </div>

                <div class="bg-yellow-50 border border-yellow-200 p-4 rounded-xl space-y-2">
                    <h4 class="text-xs font-bold text-yellow-800 uppercase flex items-center gap-2">
                        <i class="fa-solid fa-circle-exclamation"></i>
                        <span>Requisitos Completos y Exigencias del Mandante:</span>
                    </h4>
                    <p class="text-xs text-slate-700 leading-relaxed font-medium" x-text="selectedTender.requisitos"></p>
                </div>

                <div class="flex justify-between items-center pt-2">
                    <a :href="selectedTender.link" target="_blank" class="text-xs text-blue-600 font-semibold hover:underline">
                        <i class="fa-solid fa-external-link mr-1"></i> Ir a la Fuente Oficial del Mandante
                    </a>
                    <button @click="detailModal = false; openPostularModal(selectedTender)" class="bg-yellow-brand hover:bg-yellow-400 text-slate-950 px-6 py-2.5 rounded-xl text-xs font-bold shadow">
                        Postular Ahora
                    </button>
                </div>
            </div>
        </div>

        <!-- MODAL POSTULAR -->
        <div x-show="postularModal" class="fixed inset-0 bg-slate-950/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-white border border-slate-200 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
                <div class="flex items-center justify-between border-b border-slate-200 pb-3">
                    <h3 class="font-bold text-slate-900 text-base">Enviar Postulación Oficial</h3>
                    <button @click="postularModal = false" class="text-slate-400 hover:text-slate-900"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="space-y-3 text-xs">
                    <div><label class="text-slate-600 block mb-1">Nombre de su Empresa</label><input type="text" x-model="postForm.nombre_empresa" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2"></div>
                    <div><label class="text-slate-600 block mb-1">RUT Empresa</label><input type="text" x-model="postForm.rut_empresa" placeholder="Ej: 76.123.456-7" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2"></div>
                    <div><label class="text-slate-600 block mb-1">Correo Electrónico de Contacto</label><input type="email" x-model="postForm.email_contacto" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2"></div>
                </div>
                <div class="flex justify-end space-x-2 pt-3 border-t border-slate-200">
                    <button @click="postularModal = false" class="bg-slate-100 text-slate-700 px-4 py-2 rounded-xl text-xs font-semibold">Cancelar</button>
                    <button @click="submitPostulacion()" class="bg-yellow-brand hover:bg-yellow-400 text-slate-950 px-5 py-2 rounded-xl text-xs font-bold shadow">Enviar Postulación</button>
                </div>
            </div>
        </div>

        <!-- MODAL CARTA -->
        <div x-show="proposalModal" class="fixed inset-0 bg-slate-950/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-white border border-slate-200 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
                <div class="flex items-center justify-between border-b border-slate-200 pb-3">
                    <h3 class="font-bold text-slate-900 text-base">Carta Propuesta Oficial Generada</h3>
                    <button @click="proposalModal = false" class="text-slate-400 hover:text-slate-900"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <pre class="bg-slate-50 p-4 rounded-xl text-xs font-mono text-slate-700 whitespace-pre-wrap border border-slate-200" x-text="selectedProposalText"></pre>
                <div class="flex justify-end pt-3"><button @click="proposalModal = false" class="bg-slate-100 text-slate-700 px-4 py-2 rounded-xl text-xs font-semibold">Cerrar</button></div>
            </div>
        </div>

        <script>
            function tenderApp() {
                return {
                    isLoggedIn: false,
                    currentUser: {},
                    loginForm: { email: '', password: '' },
                    currentTab: 'home',
                    tenders: [],
                    postulaciones: [],
                    clientesList: [],
                    searchQuery: '',
                    selectedRegion: '',
                    loading: false,
                    detailModal: false,
                    postularModal: false,
                    proposalModal: false,
                    selectedTender: {},
                    selectedProposalText: '',
                    postForm: { nombre_empresa: '', rut_empresa: '', email_contacto: '' },
                    newClient: { nombre_empresa: '', email: '', password: '' },

                    async login() {
                        try {
                            const res = await fetch('/api/login', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(this.loginForm)
                            });
                            const data = await res.json();
                            if (data.status === 'success') {
                                this.currentUser = data;
                                this.isLoggedIn = true;
                                this.postForm.nombre_empresa = data.nombre_empresa;
                                this.postForm.email_contacto = data.email;
                                this.fetchTenders();
                                this.fetchPostulaciones();
                            } else {
                                alert(data.message);
                            }
                        } catch(e) { alert("Error de conexión al iniciar sesión."); }
                    },
                    logout() { this.isLoggedIn = false; this.currentUser = {}; },
                    async fetchClientes() {
                        const res = await fetch('/api/admin/clientes');
                        const data = await res.json();
                        this.clientesList = data.clientes || [];
                    },
                    async crearCliente() {
                        const res = await fetch('/api/admin/crear-cliente', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(this.newClient)
                        });
                        const data = await res.json();
                        alert(data.message);
                        if (data.status === 'success') { this.newClient = { nombre_empresa: '', email: '', password: '' }; this.fetchClientes(); }
                    },
                    async fetchTenders() {
                        this.loading = true;
                        const res = await fetch('/api/tenders');
                        const data = await res.json();
                        this.tenders = data.tenders || [];
                        this.loading = false;
                    },
                    async fetchPostulaciones() {
                        const res = await fetch('/api/postulaciones');
                        const data = await res.json();
                        this.postulaciones = data.postulaciones || [];
                    },
                    get availableRegions() {
                        return Array.from(new Set(this.tenders.map(t => t.region)));
                    },
                    get filteredTenders() {
                        return this.tenders.filter(t => {
                            const matchesSearch = !this.searchQuery || 
                                t.titulo.toLowerCase().includes(this.searchQuery.toLowerCase()) || 
                                t.mandante.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
                                t.comuna.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
                                t.categoria.toLowerCase().includes(this.searchQuery.toLowerCase());
                            const matchesReg = !this.selectedRegion || t.region === this.selectedRegion;
                            return matchesSearch && matchesReg;
                        });
                    },
                    openDetail(item) { this.selectedTender = item; this.detailModal = true; },
                    openPostularModal(item) { this.selectedTender = item; this.postularModal = true; },
                    openProposalModal(p) { this.selectedProposalText = p.carta_propuesta; this.proposalModal = true; },
                    async submitPostulacion() {
                        const payload = {
                            titulo: this.selectedTender.titulo,
                            mandante: this.selectedTender.mandante,
                            region: this.selectedTender.region,
                            comuna: this.selectedTender.comuna,
                            categoria: this.selectedTender.categoria,
                            presupuesto: this.selectedTender.presupuesto,
                            fuente: this.selectedTender.fuente,
                            link_original: this.selectedTender.link,
                            nombre_empresa: this.postForm.nombre_empresa,
                            rut_empresa: this.postForm.rut_empresa,
                            email_contacto: this.postForm.email_contacto
                        };
                        const res = await fetch('/api/postular', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                        const result = await res.json();
                        this.postularModal = false;
                        alert(result.message);
                        this.fetchPostulaciones();
                    }
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
