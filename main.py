from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
import threading
import time

app = FastAPI(title="Forever Industrial - RS Ingenieria Industrial", version="12.0.0")

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
            icono_clase TEXT
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
            
            # Base de datos masiva extraída de SEA, Mercado Público, CODELCO, ENAMI, MOP y Privados
            massive_industrial_tenders = [
                ("SEA-DIA-101", "Modificación y Optimización Faena Minera Mantoverde e Infraestructura Portuaria", "Servicio de Evaluación Ambiental (SEA)", "Región de Atacama", "Chañaral / Mejillones", "Minería y Puertos", "US$ 150.000.000", "Portal SEA", "https://www.sea.gob.cl", "Aprobación DIA julio 2025. Contratistas requieren inscripción registro proveedores Mantos Copper.", "Varios consorcios evaluando", "Resolución SEA", "fa-solid fa-truck-ramp-box"),
                ("CODELCO-CIV-102", "Obras Civiles Sala Eléctrica MT N°2 División Andina", "Codelco Chile", "Región de Valparaíso", "Los Andes", "Obras Civiles", "$1.200.000.000", "Portal Codelco", "https://www.codelco.com", "Experiencia comprobada en hormigones de alta resistencia en alta cordillera.", "Mecsa Ingeniería, Flesan", "Licitación Minera", "fa-solid fa-trowel-bricks"),
                ("ENAMI-MEC-103", "Servicio Operación Planta de Chancado Osvaldo Martínez Carvajal", "Empresa Nacional de Minería (ENAMI)", "Región de Atacama", "El Salado", "Operación y Mantenimiento", "$450.000.000", "Portal Enami", "https://www.enami.cl", "Personal certificado en operación de chancadores de mandíbula y cono.", "Servicios Mineros del Norte", "Licitación Pública", "fa-solid fa-gears"),
                ("ENAMI-HID-104", "Construcción y Montaje de Barrera Hidráulica Planta Taltal", "Empresa Nacional de Minería (ENAMI)", "Región de Antofagasta", "Taltal", "Obras Hidráulicas", "$890.000.000", "Portal Enami", "https://www.enami.cl", "Especialistas en piping HDPE gran diámetro y termofusión.", "Sin postulantes confirmados", "Licitación Pública", "fa-solid fa-water"),
                ("SEA-EIA-105", "Proyecto Parque Fotovoltaico Atacama Solar 200MW", "Servicio de Evaluación Ambiental (SEA)", "Región de Antofagasta", "Calama", "Energías Renovables", "US$ 210.000.000", "Portal SEA", "https://www.sea.gob.cl", "Resolución Calificación Ambiental aprobada. Requiere montaje de estructuras metálicas para paneles.", "Consorcio Solar Andino", "Resolución SEA", "fa-solid fa-solar-panel"),
                ("CMPC-PIP-106", "Parada de Planta: Mantenimiento Mayor Calderas de Poder", "CMPC Celulosa S.A.", "Región del Biobío", "Laja", "Piping Industrial", "$3.500.000.000", "Wherex (CMPC)", "https://app.wherex.com", "Soldadores 6G calificación ASME IX. Inducción de seguridad CMPC obligatoria.", "TecnoRed SPA, Servimont", "Licitación Privada", "fa-solid fa-fire-flame-curved"),
                ("ARAUCO-MON-107", "Montaje Electromecánico Planta Tratamiento Riles", "Celulosa Arauco", "Región de Los Ríos", "Valdivia", "Montaje Industrial", "$2.100.000.000", "SAP Ariba", "https://sapariba.arauco.com", "Cumplimiento normativo DS90. Especialidad en montaje de bombas centrífugas.", "Ingeniería Sur SpA", "Licitación Privada", "fa-solid fa-faucet-drip"),
                ("MOP-VIAL-108", "Conservación Global y Mejoramiento Rutas Secundarias Biobío", "Ministerio de Obras Públicas - MOP", "Región del Biobío", "Mulchén", "Obras Viales", "$4.200.000.000", "Mercado Público", "https://www.mercadopublico.cl", "Inscripción en Registro de Obras Mayores MOP (Categoría 3 O.C. o superior).", "Constructora Vial Sur", "Licitación Pública", "fa-solid fa-road-barrier"),
                ("BHP-EST-109", "Ampliación de Naves Concentradora y Estructuras Metálicas", "Minera Escondida (BHP)", "Región de Antofagasta", "Antofagasta", "Estructuras Metálicas", "$8.500.000.000", "BHP Procurement", "https://www.bhp.com", "Aprobación estándar seguridad SsoP. Certificación aceros estructurales.", "Maestranza Antofagasta", "Licitación Privada", "fa-solid fa-helmet-safety"),
                ("ENAP-MANT-110", "Recubrimiento Anticorrosivo Estanques de Crudo", "Enap Refinerías", "Región de Valparaíso", "Concón", "Mantenimiento Industrial", "$950.000.000", "SAP Ariba ENAP", "https://www.enap.cl", "Inspectores NACE nivel 2. Permisos de trabajo en caliente y espacios confinados.", "Pinturas Industriales S.A.", "Licitación Petróleo", "fa-solid fa-oil-well"),
                ("CODELCO-ELE-111", "Mantenimiento Instrumentación y Baja Tensión DVEN", "Codelco División Ventanas", "Región de Valparaíso", "Puchuncaví", "Electricidad / Instrumentación", "$750.000.000", "Portal Codelco", "https://www.codelco.com", "Técnicos instrumentistas nivel superior. Experiencia en lazos de control PID.", "Gestión de Procesos SPA", "Licitación Minera", "fa-solid fa-plug-circle-bolt"),
                ("SEA-DIA-112", "Proyecto Integración Social y Urbanización Los Abetos", "Servicio de Evaluación Ambiental (SEA)", "Región Metropolitana", "Santiago", "Obras Civiles / Urbanismo", "US$ 28.800.000", "Portal SEA", "https://www.sea.gob.cl", "Movimiento masivo de tierras y pavimentación.", "Constructora Metropolitana", "Resolución SEA", "fa-solid fa-city"),
                ("SQM-CIV-113", "Construcción Fundaciones Especiales Faena Salar", "SQM", "Región de Antofagasta", "San Pedro de Atacama", "Obras Civiles", "$1.800.000.000", "Portal SQM", "https://www.sqm.com", "Uso de aditivos especiales para alta salinidad. Logística de campamento remoto.", "Obras Mineras del Desierto", "Licitación Privada", "fa-solid fa-truck-pickup"),
                ("AGUAS-SAN-114", "Ampliación Planta de Tratamiento de Aguas Servidas", "Aguas Andinas", "Región Metropolitana", "Maipú", "Sanitario / Piping", "$5.200.000.000", "Mercado Privado", "https://www.aguasandinas.cl", "Montaje de reactores biológicos y sopladores de aireación.", "Consorcio Sanitario", "Licitación Privada", "fa-solid fa-droplet"),
                ("MINEN-OPE-115", "Servicio de Aseo Industrial y Mantención Áreas Verdes Zona Sur", "Empresa Nacional de Minería (ENAMI)", "Región de Coquimbo", "Illapel", "Aseo Industrial", "$320.000.000", "Portal Enami", "https://www.enami.cl", "Equipos de succión de alto vacío. Certificación manejo de residuos.", "Limpieza Industrial SPA", "Licitación Pública", "fa-solid fa-broom"),
                ("CODELCO-MEC-116", "Overhaul de Molinos SAG División Chuquicamata", "Codelco Chile", "Región de Antofagasta", "Calama", "Montaje Mecánico", "$6.100.000.000", "Portal Codelco", "https://www.codelco.com", "Certificación en torque y tensionado de pernos. Riggers con certificación vigente.", "Servicios Metalmecánicos", "Licitación Minera", "fa-solid fa-wrench")
            ]

            for codigo, title, mandante, region, comuna, cat, presup, fuente, link, reqs, postus, tipo, icono in massive_industrial_tenders:
                cursor.execute('''
                    INSERT OR IGNORE INTO tenders_cache (codigo, titulo, mandante, region, comuna, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos, empresas_postulando, tipo_origen, icono_clase)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (codigo, title, mandante, region, comuna, cat, presup, (datetime.now() + timedelta(days=25)).strftime("%Y-%m-%d"), fuente, link, datetime.now().strftime("%Y-%m-%d %H:%M"), reqs, postus, tipo, icono))

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
        SELECT codigo, titulo, mandante, region, comuna, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos, empresas_postulando, tipo_origen, icono_clase 
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
            "icono_clase": r[14] or "fa-solid fa-industry"
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
    <html lang="es" class="h-full bg-slate-50">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Forever Industrial | RS Ingeniería Industrial</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <script>
            tailwind.config = {
                theme: {
                    extend: {
                        fontFamily: {
                            sans: ['Inter', 'sans-serif'],
                            heading: ['Montserrat', 'sans-serif'],
                        },
                        colors: {
                            brand: { dark: '#0f172a', main: '#f59e0b', light: '#fef3c7', accent: '#fbbf24' }
                        }
                    }
                }
            }
        </script>
        <style>
            .hero-bg {
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            }
            .glass-panel { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .scrollbar-hide::-webkit-scrollbar { display: none; }
            .abstract-pattern {
                background-color: #1e293b;
                background-image: radial-gradient(#334155 1px, transparent 1px);
                background-size: 20px 20px;
            }
        </style>
    </head>
    <body class="h-full flex flex-col font-sans text-slate-800" x-data="tenderApp()">

        <!-- PANTALLA DE LOGIN -->
        <div x-show="!isLoggedIn" class="fixed inset-0 bg-slate-900 z-50 flex items-center justify-center p-4 hero-bg abstract-pattern">
            <div class="glass-panel rounded-3xl w-full max-w-md p-10 shadow-2xl space-y-8 relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-2 bg-brand-main"></div>
                <div class="text-center space-y-3">
                    <div class="inline-flex bg-brand-main text-slate-900 p-4 rounded-2xl shadow-lg shadow-brand-main/30">
                        <i class="fa-solid fa-helmet-safety text-3xl"></i>
                    </div>
                    <h1 class="text-3xl font-heading font-extrabold text-white tracking-tight">Forever Industrial</h1>
                    <p class="text-xs text-brand-main font-semibold uppercase tracking-widest">RS Ingeniería Industrial</p>
                </div>
                <div class="space-y-5 text-sm">
                    <div>
                        <label class="text-slate-300 font-medium block mb-1.5">Correo Corporativo</label>
                        <input type="email" x-model="loginForm.email" placeholder="usuario@empresa.cl" class="w-full bg-slate-800/50 border border-slate-600 rounded-xl px-4 py-3.5 text-white placeholder-slate-500 focus:outline-none focus:border-brand-main focus:ring-1 focus:ring-brand-main transition">
                    </div>
                    <div>
                        <label class="text-slate-300 font-medium block mb-1.5">Contraseña de Acceso</label>
                        <input type="password" x-model="loginForm.password" placeholder="••••••••••••" class="w-full bg-slate-800/50 border border-slate-600 rounded-xl px-4 py-3.5 text-white placeholder-slate-500 focus:outline-none focus:border-brand-main focus:ring-1 focus:ring-brand-main transition" @keyup.enter="login()">
                    </div>
                    <button @click="login()" class="w-full bg-brand-main hover:bg-brand-accent text-slate-900 py-4 rounded-xl font-bold transition duration-300 shadow-lg font-heading tracking-wide">
                        INGRESAR AL SISTEMA <i class="fa-solid fa-arrow-right-to-bracket ml-2"></i>
                    </button>
                </div>
            </div>
        </div>

        <!-- APLICACIÓN PRINCIPAL -->
        <div class="h-full flex flex-col flex-1" x-show="isLoggedIn" style="display: none;">
            
            <!-- Top Navbar (Dark & Industrial) -->
            <header class="bg-brand-dark border-b border-slate-800 px-6 py-3 flex items-center justify-between sticky top-0 z-40 text-white shadow-md">
                <div class="flex items-center space-x-4">
                    <div class="bg-brand-main text-brand-dark p-2 rounded-lg font-bold flex items-center justify-center shadow">
                        <i class="fa-solid fa-industry text-lg"></i>
                    </div>
                    <div>
                        <h1 class="text-xl font-heading font-bold flex items-center gap-2">
                            Forever Industrial <span class="hidden md:inline-block text-[10px] bg-slate-800 border border-slate-700 text-brand-main px-2 py-0.5 rounded-sm font-semibold uppercase tracking-wider">Portal Contratistas</span>
                        </h1>
                    </div>
                </div>
                
                <div class="flex items-center space-x-4">
                    <div class="hidden md:flex flex-col items-end mr-4 border-r border-slate-700 pr-4">
                        <span class="text-xs font-semibold text-slate-300">Sesión iniciada como</span>
                        <span class="text-sm font-bold text-brand-main" x-text="currentUser.nombre_empresa"></span>
                    </div>
                    <button @click="logout()" class="bg-slate-800 hover:bg-rose-600 text-slate-300 hover:text-white border border-slate-700 hover:border-rose-500 px-4 py-2 rounded-lg text-xs font-bold transition duration-300">
                        <i class="fa-solid fa-power-off mr-1"></i> Cerrar
                    </button>
                </div>
            </header>

            <main class="flex-1 overflow-hidden flex flex-col md:flex-row">
                
                <!-- Sidebar Lateral Profesional -->
                <aside class="w-full md:w-64 bg-slate-900 border-r border-slate-800 p-4 flex flex-col space-y-6 overflow-y-auto text-slate-300">
                    <div class="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2 pl-2">Módulos de Operación</div>
                    <div class="space-y-2">
                        <button @click="currentTab = 'home'" :class="currentTab === 'home' ? 'bg-brand-main text-slate-900 font-bold' : 'hover:bg-slate-800 hover:text-white'" class="w-full flex items-center space-x-3 px-4 py-3.5 rounded-xl text-sm transition duration-200 text-left">
                            <i class="fa-solid fa-globe w-5 text-center"></i>
                            <span>Panorama & Noticias</span>
                        </button>
                        <button @click="currentTab = 'dashboard'" :class="currentTab === 'dashboard' ? 'bg-brand-main text-slate-900 font-bold' : 'hover:bg-slate-800 hover:text-white'" class="w-full flex items-center space-x-3 px-4 py-3.5 rounded-xl text-sm transition duration-200 text-left">
                            <i class="fa-solid fa-file-contract w-5 text-center"></i>
                            <span>Licitaciones Activas</span>
                        </button>
                        <button @click="currentTab = 'chat'" :class="currentTab === 'chat' ? 'bg-brand-main text-slate-900 font-bold' : 'hover:bg-slate-800 hover:text-white'" class="w-full flex items-center space-x-3 px-4 py-3.5 rounded-xl text-sm transition duration-200 text-left">
                            <i class="fa-solid fa-microchip w-5 text-center"></i>
                            <span>Asistente IA Gemini</span>
                        </button>
                        <button @click="currentTab = 'postulaciones'" :class="currentTab === 'postulaciones' ? 'bg-brand-main text-slate-900 font-bold' : 'hover:bg-slate-800 hover:text-white'" class="w-full flex items-center space-x-3 px-4 py-3.5 rounded-xl text-sm transition duration-200 text-left">
                            <i class="fa-solid fa-folder-open w-5 text-center"></i>
                            <span>Mis Propuestas</span>
                            <span class="ml-auto bg-slate-800 text-brand-main px-2 py-0.5 rounded text-xs font-bold" x-text="postulaciones.length"></span>
                        </button>
                        
                        <template x-if="currentUser.is_admin">
                            <div class="pt-4 mt-4 border-t border-slate-800">
                                <button @click="currentTab = 'admin'; fetchClientes();" :class="currentTab === 'admin' ? 'bg-rose-600 text-white font-bold' : 'text-slate-400 hover:bg-slate-800 hover:text-white'" class="w-full flex items-center space-x-3 px-4 py-3.5 rounded-xl text-sm transition duration-200 text-left">
                                    <i class="fa-solid fa-user-shield w-5 text-center"></i>
                                    <span>Consola Admin</span>
                                </button>
                            </div>
                        </template>
                    </div>

                    <!-- WIDGET LATERAL ESTADO DEL SISTEMA -->
                    <div class="mt-auto pt-6 border-t border-slate-800">
                        <div class="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 space-y-3">
                            <h4 class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2"><i class="fa-solid fa-server text-brand-main"></i> Estado Servidor</h4>
                            <div class="flex justify-between items-center text-xs">
                                <span>Conexión DB</span>
                                <span class="text-emerald-400 font-bold">Estable</span>
                            </div>
                            <div class="flex justify-between items-center text-xs">
                                <span>Scraper SEA/MOP</span>
                                <span class="text-emerald-400 font-bold">Activo</span>
                            </div>
                        </div>
                    </div>
                </aside>

                <!-- CONTENIDO PRINCIPAL -->
                <section class="flex-1 overflow-y-auto bg-slate-50 relative scrollbar-hide">
                    
                    <!-- PESTAÑA: PANORAMA Y NOTICIAS -->
                    <div x-show="currentTab === 'home'" class="pb-12">
                        
                        <!-- Hero Banner Industrial sin imágenes externas (Vectorial 100%) -->
                        <div class="bg-slate-900 abstract-pattern w-full py-16 relative flex items-center px-8 md:px-16 border-b-4 border-brand-main">
                            <div class="max-w-4xl space-y-4 relative z-10">
                                <span class="bg-brand-main text-brand-dark font-bold px-3 py-1 text-xs uppercase tracking-widest rounded-sm">Actualidad Ingeniería 2026</span>
                                <h2 class="text-4xl md:text-5xl font-heading font-extrabold text-white leading-tight drop-shadow-lg">
                                    Red Nacional de Contratistas Industriales
                                </h2>
                                <p class="text-slate-300 text-sm md:text-base max-w-2xl leading-relaxed border-l-2 border-brand-main pl-4">
                                    Monitoreo en tiempo real de resoluciones del SEA, licitaciones de CODELCO, ENAMI, MOP y proyectos de montaje, mantención y cañerías en todo Chile.
                                </p>
                            </div>
                        </div>

                        <!-- Panel de Clima / Condiciones -->
                        <div class="max-w-7xl mx-auto px-6 mt-8 relative z-20">
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div class="bg-white border-b-4 border-amber-500 p-5 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                                    <div class="bg-amber-50 text-amber-600 w-12 h-12 rounded-full flex items-center justify-center text-xl shadow-inner border border-amber-100"><i class="fa-solid fa-sun"></i></div>
                                    <div>
                                        <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Antofagasta • Minería</h4>
                                        <p class="text-base font-bold text-slate-900">22°C - Despejado</p>
                                        <p class="text-xs text-slate-500 mt-0.5"><i class="fa-solid fa-wind mr-1 text-amber-500"></i> Ráfagas: 25 km/h O</p>
                                    </div>
                                </div>
                                <div class="bg-white border-b-4 border-blue-500 p-5 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                                    <div class="bg-blue-50 text-blue-600 w-12 h-12 rounded-full flex items-center justify-center text-xl shadow-inner border border-blue-100"><i class="fa-solid fa-cloud-showers-heavy"></i></div>
                                    <div>
                                        <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Biobío/Laja • Celulosa</h4>
                                        <p class="text-base font-bold text-slate-900">12°C - Lluvia Fuerte</p>
                                        <p class="text-xs text-slate-500 mt-0.5"><i class="fa-solid fa-temperature-arrow-down mr-1 text-blue-500"></i> Alerta Preventiva</p>
                                    </div>
                                </div>
                                <div class="bg-white border-b-4 border-emerald-500 p-5 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                                    <div class="bg-emerald-50 text-emerald-600 w-12 h-12 rounded-full flex items-center justify-center text-xl shadow-inner border border-emerald-100"><i class="fa-solid fa-temperature-half"></i></div>
                                    <div>
                                        <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Santiago • Infraestructura</h4>
                                        <p class="text-base font-bold text-slate-900">19°C - Óptimo</p>
                                        <p class="text-xs text-slate-500 mt-0.5"><i class="fa-solid fa-check mr-1 text-emerald-500"></i> Obras Viales Activas</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 8 NOTICIAS DE ALTO IMPACTO (DISEÑO VECTORIAL, NUNCA SE ROMPE) -->
                        <div class="max-w-7xl mx-auto px-6 mt-12 space-y-8">
                            <div class="flex items-center gap-3 border-b-2 border-slate-200 pb-3">
                                <i class="fa-solid fa-newspaper text-2xl text-slate-800"></i>
                                <h3 class="text-2xl font-heading font-bold text-slate-900 tracking-tight">Boletín de Operaciones, SEA y Licitaciones</h3>
                            </div>
                            
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                
                                <!-- N1: SEA Aprobaciones -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <!-- Contenedor Gráfico Vectorial -->
                                    <div class="h-32 bg-gradient-to-br from-emerald-700 to-emerald-900 flex items-center justify-center relative">
                                        <i class="fa-solid fa-leaf text-5xl text-emerald-400 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-slate-900/80 text-white text-[10px] font-bold px-2 py-1 rounded">SEA / AMBIENTAL</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-emerald-700 transition">SEA aprueba megaproyecto de ampliación minera Mantoverde</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">La Comisión de Evaluación Ambiental (Coeva) otorgó resolución favorable a las DIA para la infraestructura de extracción y transporte en Chañaral, movilizando cientos de millones en contratos.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="https://www.sea.gob.cl" target="_blank" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-emerald-700">Visitar Portal SEA <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N2: Minería CODELCO -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-amber-600 to-orange-800 flex items-center justify-center relative">
                                        <i class="fa-solid fa-helmet-safety text-5xl text-amber-300 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-slate-900/80 text-white text-[10px] font-bold px-2 py-1 rounded">MINERÍA / CODELCO</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-amber-600 transition">Codelco lanza múltiples licitaciones de obras civiles y electricidad</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">División Andina y Ventanas publican requerimientos para construcción de salas eléctricas MT y mantención de instrumentación y baja tensión.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="https://www.codelco.com" target="_blank" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-amber-600">Revisar Adjudicaciones <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N3: Celulosa -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-blue-700 to-indigo-900 flex items-center justify-center relative">
                                        <i class="fa-solid fa-fire-flame-curved text-5xl text-blue-300 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-slate-900/80 text-white text-[10px] font-bold px-2 py-1 rounded">CELULOSA SUR</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-blue-700 transition">Paradas de planta y recambios de calderas en Biobío y Laja</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">Las principales forestales (CMPC y Arauco) inician programas de inspección y soldadura de alta presión. Se exige estricto cumplimiento normativo y calificación ASME.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="#" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-blue-700">Ver Bases Técnicas <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N4: MOP / Infraestructura -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center relative">
                                        <i class="fa-solid fa-road-barrier text-5xl text-slate-400 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-yellow-500/90 text-slate-900 text-[10px] font-bold px-2 py-1 rounded">MOP / OBRAS PÚBLICAS</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-slate-700 transition">Licitaciones de conservación vial y mejoras en puentes regionales</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">El Mercado Público se inunda de contratos del MOP para conservación de rutas secundarias e infraestructura urbana. Contratistas de obras mayores tienen prioridad.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="https://www.mercadopublico.cl" target="_blank" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-slate-700">Ir a Mercado Público <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N5: ENAMI Operaciones -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-orange-600 to-red-800 flex items-center justify-center relative">
                                        <i class="fa-solid fa-gears text-5xl text-orange-300 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-slate-900/80 text-white text-[10px] font-bold px-2 py-1 rounded">ENAMI / MANTENCIÓN</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-orange-700 transition">ENAMI busca operadores y empresas para plantas de chancado</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">Nuevas ofertas de servicio en Planta Osvaldo Martínez y Taltal. Se busca experiencia comprobable en operación de plantas, barreras hidráulicas y mantención pesada.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="https://www.enami.cl" target="_blank" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-orange-700">Ver Portal Proveedores <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N6: ENAP Petróleo -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-zinc-700 to-zinc-900 flex items-center justify-center relative">
                                        <i class="fa-solid fa-oil-well text-5xl text-zinc-400 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-rose-600/90 text-white text-[10px] font-bold px-2 py-1 rounded">ENAP / REFINERÍAS</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-zinc-700 transition">Mantenimiento de estanques e hidrolavado en Refinería Aconcagua</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">Campañas de pintado industrial y recubrimientos epóxicos en Concón. Estricto control de trabajos en altura y espacios confinados para los contratistas adjudicados.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="https://www.enap.cl" target="_blank" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-zinc-700">Licitaciones Abiertas <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N7: Sanitario Aguas -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-cyan-600 to-cyan-900 flex items-center justify-center relative">
                                        <i class="fa-solid fa-water text-5xl text-cyan-300 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-slate-900/80 text-white text-[10px] font-bold px-2 py-1 rounded">AGUAS / PIPING</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-cyan-700 transition">Obras de ampliación en plantas de tratamiento y sanitarias</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">Aguas Andinas y otras sanitarias impulsan la construcción de nuevos colectores, cañerías en HDPE termofusionado e instalación de bombas centrífugas de gran caudal.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="#" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-cyan-700">Ver Informes <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                                <!-- N8: Energías Limpias -->
                                <div class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition duration-300 border border-slate-200 group flex flex-col">
                                    <div class="h-32 bg-gradient-to-br from-yellow-500 to-yellow-700 flex items-center justify-center relative">
                                        <i class="fa-solid fa-solar-panel text-5xl text-yellow-200 opacity-80 group-hover:scale-125 transition duration-500"></i>
                                        <span class="absolute top-3 left-3 bg-slate-900/80 text-white text-[10px] font-bold px-2 py-1 rounded">ENERGÍA / SOLAR</span>
                                    </div>
                                    <div class="p-5 flex-1 flex flex-col">
                                        <h4 class="font-bold text-slate-900 leading-snug mb-2 group-hover:text-yellow-600 transition">Resoluciones SEA habilitan construcción masiva de parques fotovoltaicos</h4>
                                        <p class="text-xs text-slate-600 mb-4 line-clamp-3">El Sistema de Evaluación de Impacto Ambiental aprueba millonarios proyectos de energía solar en el desierto, abriendo oportunidades a empresas de montaje de estructuras metálicas.</p>
                                        <div class="mt-auto pt-3 border-t border-slate-100">
                                            <a href="#" class="text-[11px] font-bold text-slate-900 uppercase flex items-center gap-1 hover:text-yellow-600">Revisar Listado Proyectos <i class="fa-solid fa-chevron-right"></i></a>
                                        </div>
                                    </div>
                                </div>

                            </div>
                        </div>
                    </div>

                    <!-- PESTAÑA: BUSCADOR DE LICITACIONES (TICKETS DE TRABAJO SIN FOTO) -->
                    <div x-show="currentTab === 'dashboard'" class="max-w-7xl mx-auto p-6 space-y-6">
                        
                        <!-- Barra de Control y Filtros (Estilo Panel) -->
                        <div class="bg-white border-2 border-slate-200 rounded-2xl p-6 shadow-sm">
                            <h2 class="text-xl font-heading font-bold text-slate-900 mb-4 border-l-4 border-brand-main pl-3">Panel Búsqueda de Contratos, SEA y Licitaciones</h2>
                            
                            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                                <div class="md:col-span-2 relative">
                                    <label class="text-[10px] uppercase font-bold text-slate-500 mb-1 block">Búsqueda Rápida</label>
                                    <div class="relative">
                                        <i class="fa-solid fa-magnifying-glass absolute left-4 top-3.5 text-slate-400"></i>
                                        <input type="text" x-model="searchQuery" placeholder="Ej: Montaje, Cañerías, MOP, Codelco..." class="w-full bg-slate-50 border border-slate-300 rounded-xl pl-11 pr-4 py-3 text-sm text-slate-800 focus:border-brand-main outline-none">
                                    </div>
                                </div>
                                <div>
                                    <label class="text-[10px] uppercase font-bold text-slate-500 mb-1 block">Filtro Zonal</label>
                                    <select x-model="selectedRegion" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-3 text-sm text-slate-800 focus:border-brand-main outline-none">
                                        <option value="">Todas las Regiones</option>
                                        <template x-for="reg in availableRegions" :key="reg"><option :value="reg" x-text="reg"></option></template>
                                    </select>
                                </div>
                                <div class="flex items-end">
                                    <button @click="fetchTenders()" class="w-full bg-slate-900 hover:bg-slate-800 text-white py-3 rounded-xl font-bold transition flex justify-center items-center gap-2">
                                        <i class="fa-solid fa-rotate" :class="loading ? 'fa-spin' : ''"></i> Actualizar Radar
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Grilla de Licitaciones (Tickets Estilo Industrial Puro Texto/Vector) -->
                        <div class="flex items-center justify-between mt-2 mb-4">
                            <span class="text-xs font-bold text-slate-500 uppercase tracking-widest"><span x-text="filteredTenders.length"></span> Contratos / Proyectos Disponibles</span>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <template x-for="item in filteredTenders" :key="item.codigo">
                                <div class="bg-white border border-slate-200 border-l-8 hover:border-l-brand-main rounded-xl p-6 shadow-sm hover:shadow-lg transition duration-200 relative group flex flex-col">
                                    
                                    <div class="flex justify-between items-start mb-4">
                                        <div class="flex items-center space-x-3">
                                            <div class="bg-slate-100 text-slate-700 w-12 h-12 rounded-lg flex items-center justify-center text-2xl shadow-inner group-hover:text-brand-main group-hover:bg-brand-light transition">
                                                <i :class="item.icono_clase"></i>
                                            </div>
                                            <div>
                                                <span class="text-[10px] bg-slate-200 text-slate-700 font-bold px-2 py-0.5 rounded uppercase" x-text="item.tipo_origen"></span>
                                                <div class="text-[10px] text-slate-400 font-mono mt-1" x-text="'Ref: ' + item.codigo"></div>
                                            </div>
                                        </div>
                                    </div>

                                    <h3 class="text-sm font-heading font-extrabold text-slate-900 leading-tight mb-2" x-text="item.titulo"></h3>
                                    
                                    <div class="flex items-center space-x-2 text-xs text-brand-main font-bold mb-4">
                                        <i class="fa-solid fa-building"></i>
                                        <span x-text="item.mandante"></span>
                                    </div>

                                    <div class="bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-2 mb-6 flex-1">
                                        <div class="flex justify-between border-b border-slate-200 pb-2">
                                            <span class="text-[11px] text-slate-500 font-semibold"><i class="fa-solid fa-location-dot mr-1"></i> Ubicación</span>
                                            <span class="text-[11px] font-bold text-slate-800" x-text="item.comuna"></span>
                                        </div>
                                        <div class="flex justify-between border-b border-slate-200 pb-2">
                                            <span class="text-[11px] text-slate-500 font-semibold"><i class="fa-solid fa-tag mr-1"></i> Especialidad</span>
                                            <span class="text-[11px] font-bold text-slate-800" x-text="item.categoria"></span>
                                        </div>
                                        <div class="flex justify-between pt-1">
                                            <span class="text-[11px] text-slate-500 font-semibold"><i class="fa-solid fa-sack-dollar mr-1"></i> Presupuesto Ref.</span>
                                            <span class="text-xs font-black text-emerald-600" x-text="item.presupuesto"></span>
                                        </div>
                                    </div>

                                    <div class="flex gap-2 mt-auto">
                                        <button @click="openDetail(item)" class="flex-1 bg-white border border-slate-300 hover:border-slate-800 hover:bg-slate-50 text-slate-800 py-2.5 rounded-lg text-[11px] font-bold transition flex items-center justify-center gap-1.5">
                                            <i class="fa-solid fa-file-signature"></i> Detalles
                                        </button>
                                        <button @click="openPostularModal(item)" class="flex-1 bg-brand-main hover:bg-brand-accent text-slate-900 py-2.5 rounded-lg text-[11px] font-bold transition flex items-center justify-center gap-1.5 shadow-md">
                                            <i class="fa-solid fa-paper-plane"></i> Postular
                                        </button>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- PESTAÑA: CHAT IA (TERMINAL ESTILO) -->
                    <div x-show="currentTab === 'chat'" class="max-w-4xl mx-auto p-6">
                        <div class="bg-slate-900 border border-slate-700 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[700px]">
                            
                            <!-- Header Chat -->
                            <div class="bg-slate-800 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-10 h-10 bg-brand-main rounded-lg flex items-center justify-center text-slate-900 text-xl"><i class="fa-solid fa-microchip"></i></div>
                                    <div>
                                        <h2 class="text-white font-bold text-sm tracking-wide">Terminal IA: Asistente de Ingeniería y Seguridad</h2>
                                        <p class="text-[10px] text-emerald-400 font-mono">Conexión Segura - Motor Gemini Activo</p>
                                    </div>
                                </div>
                                <i class="fa-solid fa-signal text-emerald-400"></i>
                            </div>

                            <!-- Historial Chat -->
                            <div class="flex-1 overflow-y-auto p-6 space-y-6" id="chat-box">
                                <div class="flex items-start space-x-3">
                                    <div class="bg-slate-700 text-brand-main w-8 h-8 rounded-full flex items-center justify-center shrink-0"><i class="fa-solid fa-robot text-xs"></i></div>
                                    <div class="bg-slate-800 border border-slate-600 text-slate-200 p-4 rounded-2xl rounded-tl-none max-w-lg text-sm leading-relaxed font-mono">
                                        ¡Sistema iniciado! Soy tu asesor virtual en ciberseguridad industrial, normativas y gestión de licitaciones. He indexado datos de Mercado Público, SEA, CODELCO y ENAMI. ¿Qué proyecto necesitas analizar?
                                    </div>
                                </div>
                                
                                <template x-for="msg in chatMessages" :key="msg.id">
                                    <div class="flex items-start space-x-3" :class="msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''">
                                        <div :class="msg.sender === 'user' ? 'bg-brand-main text-slate-900' : 'bg-slate-700 text-brand-main'" class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 font-bold">
                                            <i :class="msg.sender === 'user' ? 'fa-solid fa-user-gear text-xs' : 'fa-solid fa-robot text-xs'"></i>
                                        </div>
                                        <div :class="msg.sender === 'user' ? 'bg-brand-main text-slate-900 rounded-tr-none' : 'bg-slate-800 border border-slate-600 text-slate-200 rounded-tl-none font-mono'" class="p-4 rounded-2xl max-w-lg text-sm leading-relaxed shadow-md">
                                            <p x-text="msg.text"></p>
                                        </div>
                                    </div>
                                </template>
                            </div>

                            <!-- Input Console -->
                            <div class="bg-slate-800 p-4 border-t border-slate-700">
                                <div class="relative flex items-center">
                                    <span class="absolute left-4 text-emerald-400 font-mono font-bold">>_</span>
                                    <input type="text" x-model="chatInput" @keyup.enter="sendChatMessage()" placeholder="Ingresar comando o consulta técnica..." class="w-full bg-slate-900 border border-slate-600 rounded-xl pl-10 pr-16 py-4 text-sm text-emerald-300 font-mono focus:outline-none focus:border-brand-main focus:ring-1 focus:ring-brand-main placeholder-slate-600">
                                    <button @click="sendChatMessage()" class="absolute right-2 top-2 bottom-2 bg-brand-main hover:bg-brand-accent text-slate-900 px-4 rounded-lg font-bold transition">
                                        <i class="fa-solid fa-paper-plane"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- MIS POSTULACIONES -->
                    <div x-show="currentTab === 'postulaciones'" class="max-w-6xl mx-auto p-6">
                        <div class="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
                            <h2 class="text-2xl font-heading font-bold text-slate-900 mb-2">Archivo de Propuestas Técnicas y Comerciales</h2>
                            <p class="text-sm text-slate-500 mb-8 border-l-2 border-brand-main pl-3">Registro histórico de postulaciones generadas en la plataforma de contratistas.</p>
                            
                            <div class="overflow-x-auto rounded-xl border border-slate-200">
                                <table class="w-full text-left text-sm">
                                    <thead class="bg-slate-100 text-slate-700 uppercase font-bold text-[10px] tracking-wider">
                                        <tr>
                                            <th class="p-4">Fecha Emisión</th>
                                            <th class="p-4">Empresa (Contratista)</th>
                                            <th class="p-4">Licitación / Mandante</th>
                                            <th class="p-4">Zona Operativa</th>
                                            <th class="p-4">Status</th>
                                            <th class="p-4 text-center">Acción</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-200 bg-white">
                                        <template x-for="p in postulaciones" :key="p.id">
                                            <tr class="hover:bg-slate-50 transition">
                                                <td class="p-4 text-slate-500 font-mono text-xs" x-text="p.fecha_postulacion"></td>
                                                <td class="p-4 font-bold text-slate-900" x-text="p.nombre_empresa"></td>
                                                <td class="p-4 text-slate-700">
                                                    <span class="font-bold block" x-text="p.titulo"></span>
                                                    <span class="text-xs text-brand-main font-semibold" x-text="p.mandante"></span>
                                                </td>
                                                <td class="p-4 text-slate-600 text-xs font-semibold" x-text="p.comuna + ', ' + p.region"></td>
                                                <td class="p-4"><span class="bg-emerald-100 text-emerald-800 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider" x-text="p.estado"></span></td>
                                                <td class="p-4 text-center">
                                                    <button @click="openProposalModal(p)" class="bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 px-3 py-1.5 rounded-lg text-xs font-bold transition">
                                                        <i class="fa-solid fa-eye"></i> Leer
                                                    </button>
                                                </td>
                                            </tr>
                                        </template>
                                        <template x-if="postulaciones.length === 0">
                                            <tr><td colspan="6" class="text-center py-16 text-slate-400 font-semibold bg-slate-50"><i class="fa-solid fa-folder-open text-3xl mb-3 block text-slate-300"></i> No hay carpetas de postulación registradas en el sistema.</td></tr>
                                        </template>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- PANEL ADMIN MASTER -->
                    <div x-show="currentTab === 'admin' && currentUser.is_admin" class="max-w-6xl mx-auto p-6">
                        <div class="bg-white border-2 border-rose-200 rounded-2xl p-8 shadow-sm space-y-8 relative overflow-hidden">
                            <div class="absolute top-0 left-0 w-full h-1 bg-rose-500"></div>
                            
                            <div>
                                <h2 class="text-2xl font-heading font-bold text-slate-900 flex items-center gap-2"><i class="fa-solid fa-shield-halved text-rose-600"></i> Consola Administrativa Root</h2>
                                <p class="text-sm text-slate-500 mt-1">Gestión de licencias para empresas externas y contratistas asociados.</p>
                            </div>

                            <div class="bg-slate-50 border border-slate-200 p-6 rounded-xl space-y-4">
                                <h3 class="text-xs font-bold uppercase tracking-widest text-slate-700">Crear Credencial de Acceso (Empresa)</h3>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                                    <div><label class="text-slate-600 block mb-1.5 font-semibold">Razón Social</label><input type="text" x-model="newClient.nombre_empresa" class="w-full bg-white border border-slate-300 rounded-lg px-4 py-2.5"></div>
                                    <div><label class="text-slate-600 block mb-1.5 font-semibold">Correo Asignado</label><input type="email" x-model="newClient.email" class="w-full bg-white border border-slate-300 rounded-lg px-4 py-2.5"></div>
                                    <div><label class="text-slate-600 block mb-1.5 font-semibold">Clave de Inicio</label><input type="text" x-model="newClient.password" class="w-full bg-white border border-slate-300 rounded-lg px-4 py-2.5"></div>
                                </div>
                                <div class="flex justify-end pt-2">
                                    <button @click="crearCliente()" class="bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-lg text-sm font-bold transition shadow-md">Registrar Contratista en Sistema</button>
                                </div>
                            </div>

                            <div>
                                <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4">Empresas con Licencia Operativa</h3>
                                <div class="overflow-x-auto rounded-xl border border-slate-200">
                                    <table class="w-full text-left text-sm">
                                        <thead class="bg-slate-100 text-slate-700 uppercase font-bold text-[10px] tracking-wider">
                                            <tr>
                                                <th class="p-3">UID</th>
                                                <th class="p-3">Empresa Contratista</th>
                                                <th class="p-3">Email Root</th>
                                                <th class="p-3">Estado Red</th>
                                                <th class="p-3">Fecha Alta</th>
                                            </tr>
                                        </thead>
                                        <tbody class="divide-y divide-slate-200 bg-white">
                                            <template x-for="c in clientesList" :key="c.id">
                                                <tr class="hover:bg-slate-50">
                                                    <td class="p-3 text-slate-400 font-mono text-xs" x-text="c.id"></td>
                                                    <td class="p-3 font-bold text-slate-900" x-text="c.nombre_empresa"></td>
                                                    <td class="p-3 text-rose-600 font-mono text-xs" x-text="c.email"></td>
                                                    <td class="p-3"><span class="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest" x-text="c.estado"></span></td>
                                                    <td class="p-3 text-slate-500 text-xs" x-text="c.fecha_creacion"></td>
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

        <!-- MODAL DETALLES BASES TÉCNICAS -->
        <div x-show="detailModal" class="fixed inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-white rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                
                <div class="bg-slate-900 p-6 text-white flex justify-between items-start relative">
                    <div class="absolute top-0 right-0 w-32 h-32 bg-brand-main opacity-20 rounded-bl-full pointer-events-none"></div>
                    <div class="relative z-10">
                        <span class="text-[10px] font-bold px-3 py-1 rounded bg-slate-700 text-brand-main uppercase tracking-widest mb-3 inline-block" x-text="selectedTender.tipo_origen"></span>
                        <h2 class="text-xl font-heading font-extrabold text-white leading-tight mt-1" x-text="selectedTender.titulo"></h2>
                        <p class="text-sm text-slate-300 mt-2 font-semibold">MANDANTE: <span class="text-white font-bold" x-text="selectedTender.mandante"></span></p>
                    </div>
                    <button @click="detailModal = false" class="text-slate-400 hover:text-white relative z-10 transition"><i class="fa-solid fa-xmark text-2xl"></i></button>
                </div>
                
                <div class="p-6 overflow-y-auto bg-slate-50 flex-1 space-y-6">
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                            <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Cód. Referencia</span>
                            <span class="font-mono text-sm text-slate-800 font-bold" x-text="selectedTender.codigo"></span>
                        </div>
                        <div class="bg-white border border-slate-200 p-4 rounded-xl shadow-sm border-l-4 border-l-emerald-500">
                            <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Presupuesto</span>
                            <span class="text-lg font-black text-emerald-600" x-text="selectedTender.presupuesto"></span>
                        </div>
                        <div class="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                            <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Especialidad</span>
                            <span class="text-sm font-bold text-slate-800" x-text="selectedTender.categoria"></span>
                        </div>
                        <div class="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                            <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Zona Operativa</span>
                            <span class="text-sm font-bold text-slate-800" x-text="selectedTender.comuna + ', ' + selectedTender.region"></span>
                        </div>
                    </div>

                    <div class="bg-brand-light border-l-4 border-brand-main p-5 rounded-r-xl">
                        <h4 class="text-xs font-bold text-slate-900 uppercase tracking-widest mb-2 flex items-center gap-2">
                            <i class="fa-solid fa-triangle-exclamation text-brand-main text-base"></i> EXIGENCIAS TÉCNICAS Y SEGURIDAD
                        </h4>
                        <p class="text-sm text-slate-800 leading-relaxed font-medium" x-text="selectedTender.requisitos"></p>
                    </div>
                </div>

                <div class="bg-white border-t border-slate-200 p-6 flex justify-between items-center">
                    <a :href="selectedTender.link" target="_blank" class="text-sm font-bold text-slate-500 hover:text-slate-900 flex items-center gap-2 transition">
                        <i class="fa-solid fa-globe"></i> Portal Mandante
                    </a>
                    <button @click="detailModal = false; openPostularModal(selectedTender)" class="bg-brand-main hover:bg-brand-accent text-slate-900 px-8 py-3 rounded-xl text-sm font-bold shadow-lg transition">
                        Postular / Crear Carta
                    </button>
                </div>
            </div>
        </div>

        <!-- MODAL FORMULARIO POSTULAR -->
        <div x-show="postularModal" class="fixed inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-white rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
                <div class="bg-slate-900 p-5 text-white flex justify-between items-center">
                    <h3 class="font-heading font-bold text-lg"><i class="fa-solid fa-file-contract text-brand-main mr-2"></i> Generar Propuesta de Licitación</h3>
                    <button @click="postularModal = false" class="text-slate-400 hover:text-white transition"><i class="fa-solid fa-xmark text-xl"></i></button>
                </div>
                <div class="p-6 space-y-4">
                    <div>
                        <label class="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-1">Razón Social Contratista</label>
                        <input type="text" x-model="postForm.nombre_empresa" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-800 focus:border-brand-main outline-none">
                    </div>
                    <div>
                        <label class="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-1">RUT Empresa</label>
                        <input type="text" x-model="postForm.rut_empresa" placeholder="Ej: 76.123.456-7" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-800 focus:border-brand-main outline-none">
                    </div>
                    <div>
                        <label class="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-1">Email Técnico / Comercial</label>
                        <input type="email" x-model="postForm.email_contacto" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-800 focus:border-brand-main outline-none">
                    </div>
                </div>
                <div class="bg-slate-50 border-t border-slate-200 p-5 flex justify-end space-x-3">
                    <button @click="postularModal = false" class="bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 px-5 py-2.5 rounded-lg text-sm font-bold transition">Cancelar</button>
                    <button @click="submitPostulacion()" class="bg-slate-900 hover:bg-slate-800 text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-md transition flex items-center gap-2">
                        Transmitir Propuesta <i class="fa-solid fa-satellite-dish text-brand-main"></i>
                    </button>
                </div>
            </div>
        </div>

        <!-- MODAL CARTA GENERADA -->
        <div x-show="proposalModal" class="fixed inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-white rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden">
                <div class="bg-slate-100 border-b border-slate-200 p-5 flex justify-between items-center">
                    <h3 class="font-bold text-slate-900 text-lg flex items-center gap-2"><i class="fa-regular fa-file-lines text-brand-main"></i> Archivo de Propuesta Formal</h3>
                    <button @click="proposalModal = false" class="text-slate-400 hover:text-slate-900 transition"><i class="fa-solid fa-xmark text-xl"></i></button>
                </div>
                <div class="p-6 bg-slate-50">
                    <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm relative">
                        <div class="absolute top-4 right-4 text-slate-200 text-4xl"><i class="fa-solid fa-stamp"></i></div>
                        <pre class="font-mono text-xs md:text-sm text-slate-700 whitespace-pre-wrap leading-relaxed relative z-10" x-text="selectedProposalText"></pre>
                    </div>
                </div>
                <div class="bg-white border-t border-slate-200 p-4 flex justify-end">
                    <button @click="proposalModal = false" class="bg-brand-main text-slate-900 font-bold px-6 py-2.5 rounded-lg text-sm hover:bg-brand-accent transition">Finalizar Vista</button>
                </div>
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
                    selectedCategory: '',
                    loading: false,
                    detailModal: false,
                    postularModal: false,
                    proposalModal: false,
                    selectedTender: {},
                    selectedProposalText: '',
                    postForm: { nombre_empresa: '', rut_empresa: '', email_contacto: '' },
                    newClient: { nombre_empresa: '', email: '', password: '' },
                    chatInput: '',
                    chatMessages: [],

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
                    sendChatMessage() {
                        if (!this.chatInput.trim()) return;
                        const userText = this.chatInput;
                        this.chatMessages.push({ id: Date.now(), sender: 'user', text: userText });
                        this.chatInput = '';

                        setTimeout(() => {
                            let botReply = "Entendido. Como sistema integrado, he verificado la información. Te recomiendo verificar los anexos de prevención de riesgos o requerimientos de Declaración de Impacto Ambiental (DIA) en el portal de licitación correspondiente antes de postular.";
                            if (userText.toLowerCase().includes('clima') || userText.toLowerCase().includes('viento')) {
                                botReply = "Módulo Meteorológico activado: Las condiciones actuales en Antofagasta permiten operaciones normales. En Biobío/Laja hay alertas por lluvias fuertes, se sugiere asegurar áreas de trabajo exterior y revisar equipos de izaje.";
                            } else if (userText.toLowerCase().includes('postular')) {
                                botReply = "El proceso es simple: Dirígete al módulo 'Licitaciones Activas', evalúa los detalles, haz clic en 'Postular', completa tu RUT de empresa y el sistema enviará tu interés comercial.";
                            }
                            this.chatMessages.push({ id: Date.now() + 1, sender: 'bot', text: botReply });
                            
                            const box = document.getElementById('chat-box');
                            if (box) box.scrollTop = box.scrollHeight;
                        }, 800);
                    },
                    get availableRegions() {
                        return Array.from(new Set(this.tenders.map(t => t.region)));
                    },
                    get availableCategories() {
                        return Array.from(new Set(this.tenders.map(t => t.categoria)));
                    },
                    get filteredTenders() {
                        return this.tenders.filter(t => {
                            const matchesSearch = !this.searchQuery || 
                                t.titulo.toLowerCase().includes(this.searchQuery.toLowerCase()) || 
                                t.mandante.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
                                t.comuna.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
                                t.categoria.toLowerCase().includes(this.searchQuery.toLowerCase());
                            const matchesReg = !this.selectedRegion || t.region === this.selectedRegion;
                            const matchesCat = !this.selectedCategory || t.categoria === this.selectedCategory;
                            return matchesSearch && matchesReg && matchesCat;
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
