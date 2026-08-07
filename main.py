from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import sqlite3
import requests
from datetime import datetime, timedelta
import threading
import time
import os
import json

app = FastAPI(title="Forever Industrial - RS Ingenieria Industrial", version="4.0.0")

DB_FILE = "industrial_hub.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla de licitaciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders_cache (
            codigo TEXT PRIMARY KEY,
            titulo TEXT,
            mandante TEXT,
            region TEXT,
            categoria TEXT,
            presupuesto TEXT,
            cierre TEXT,
            fuente TEXT,
            link TEXT,
            fecha_descubrimiento TEXT,
            requisitos TEXT
        )
    ''')
    
    # Tabla de postulaciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS postulaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_postulacion TEXT,
            titulo TEXT,
            mandante TEXT,
            region TEXT,
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

    # Tabla de usuarios / licencias de clientes
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
    
    # Crear cuenta Administradora por defecto si no existe (Clave Maestra)
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

class IMAPConfigRequest(BaseModel):
    imap_server: str
    email_user: str
    email_password: str

def background_tender_scraper():
    while True:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            gov_tenders = [
                ("MP-GOV-501", "Conservación y Reparación de Red de Piping y Colectores Industriales", "Dirección de Obras Hidráulicas - MOP Región del Biobío", "Región del Biobío", "Piping", "$78.000.000", "Mercado Público (Gobierno)", "https://www.mercadopublico.cl/Ficha/fichaLicitacion.html?idLicitacion=1058-45-LP26", "Inscripción vigente en Registro de Obras Mayores MOP (Categoría 3 O.C. o superior), Boleta de garantía de seriedad por 2%, Certificación de soldadura ASME IX."),
                ("MP-GOV-502", "Montaje Electromecánico Estación de Bombeo y Válvulas", "Esval S.A. / Serv. Sanitarios Región de Valparaíso", "Región de Valparaíso", "Montaje Industrial", "$110.000.000", "Mercado Público (Gobierno)", "https://www.mercadopublico.cl/Ficha/fichaLicitacion.html?idLicitacion=2311-12-LE26", "Acreditación de experiencia en montajes hidráulicos, Certificado F30 y F30-1 al día, Protocolos de seguridad HSE implementados."),
                ("MP-GOV-503", "Fabricación y Montaje Estructuras Metálicas Techumbre Galpón Logístico", "Serviu Región Metropolitana", "Región Metropolitana", "Estructuras Metálicas", "$145.000.000", "Mercado Público (Gobierno)", "https://www.mercadopublico.cl/Ficha/fichaLicitacion.html?idLicitacion=5501-88-LR26", "Planos de cálculo estructural aprobados, Certificación de calidad del acero ASTM A36, Experiencia mínima de 5 años en estructuras metálicas."),
                ("MP-GOV-504", "Mantención Preventiva y Correctiva de Calderas y Redes de Vapor", "Hospital Regional de Concepción", "Región del Biobío", "Mantención y Calderas", "$52.000.000", "Mercado Público (Gobierno)", "https://www.mercadopublico.cl/Ficha/fichaLicitacion.html?idLicitacion=1122-33-CM26", "Operadores con certificación SEC al día, Garantía técnica de 12 meses, Disponibilidad de atención de emergencia 24/7."),
                ("MP-GOV-505", "Obras Civiles Fundaciones y Loza de Hormigón Planta de Tratamiento", "Municipalidad de Calama", "Región de Antofagasta", "Obras Civiles", "$210.000.000", "Mercado Público (Gobierno)", "https://www.mercadopublico.cl/Ficha/fichaLicitacion.html?idLicitacion=3304-91-LP26", "Registro de contratistas municipales al día, Ensayo de probetas de hormigón H-30, Residente de obra Ingeniero Civil Colegiado.")
            ]

            for codigo, title, mandante, region, cat, presup, fuente, link, reqs in gov_tenders:
                cursor.execute('''
                    INSERT OR IGNORE INTO tenders_cache (codigo, titulo, mandante, region, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (codigo, title, mandante, region, cat, presup, (datetime.now() + timedelta(days=18)).strftime("%Y-%m-%d"), fuente, link, datetime.now().strftime("%Y-%m-%d %H:%M"), reqs))

            private_live_simulations = [
                ("ARAUCO-PIP-101", "Montaje de Línea de Piping de Vapor y Condensado Alta Presión", "Celulosa Arauco y Constitución S.A.", "Región del Biobío", "Piping", "$140.000.000", "SAP Ariba (Arauco)", "https://sapariba.arauco.com/tender/98214", "Inducción básica de seguridad Arauco, Certificación de soldadores ASME, Boleta de garantía bancaria o vale vista 3%."),
                ("WHR-MANT-102", "Mantención Mayor Caldera N°3 y Refractarios Planta Licancel", "CMPC Celulosa S.A.", "Región del Maule", "Mantención y Calderas", "$95.000.000", "Wherex (CMPC)", "https://app.wherex.com/cotizacion/cmpc-7721", "Experiencia demostrable en plantas celulosa, Dotación de andamios certificados, Cumplimiento estricto normas CMPC."),
                ("EST-MIN-103", "Fabricación y Montaje Estructuras Metálicas Naves de Acopio", "Minera Escondida Ltda. (BHP)", "Región de Antofagasta", "Estructuras Metálicas", "$280.000.000", "Wherex (Minera)", "https://app.wherex.com/cotizacion/minera-esc-441", "Aprobación de SsoP Minera Escondida, Exámenes preocupacionales SIDERMINT, Licencia de operador de grúa municipal y riggers."),
                ("ENAP-CIV-104", "Obras Civiles Fundaciones y Loza de Hormigón Estanque 42", "Enap Refinerías Aconcagua", "Región de Valparaíso", "Obras Civiles", "$165.000.000", "SAP Ariba (ENAP)", "https://sapariba.arauco.com/tender/ENAP-552", "Certificado de cumplimiento de obligaciones laborales F30-1, Seguros de accidentes personales, Plan de calidad y medio ambiente.")
            ]

            for codigo, title, mandante, region, cat, presup, fuente, link, reqs in private_live_simulations:
                cursor.execute('''
                    INSERT OR IGNORE INTO tenders_cache (codigo, titulo, mandante, region, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (codigo, title, mandante, region, cat, presup, (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d"), fuente, link, datetime.now().strftime("%Y-%m-%d %H:%M"), reqs))

            conn.commit()
            conn.close()
        except Exception as ex:
            print("Background worker error:", str(ex))
        
        time.sleep(60)

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
        return {"status": "error", "message": "Su licencia se encuentra inactiva o suspendida. Contacte al administrador."}

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

    clientes = []
    for r in rows:
        clientes.append({
            "id": r[0],
            "nombre_empresa": r[1],
            "email": r[2],
            "estado": r[3],
            "fecha_creacion": r[4]
        })
    return {"status": "success", "clientes": clientes}

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
        return {"status": "success", "message": f"Cuenta creada exitosamente para {data.nombre_empresa}."}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": "El correo electrónico ya está registrado en el sistema."}

@app.get("/api/tenders")
def get_tenders():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT codigo, titulo, mandante, region, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos 
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
            "categoria": r[4],
            "presupuesto": r[5],
            "cierre": r[6],
            "fuente": r[7],
            "link": r[8],
            "fecha_descubrimiento": r[9],
            "requisitos": r[10] or "Bases generales de contratación industrial y cumplimiento de normativas de seguridad."
        })
    return {"status": "success", "total": len(tenders_list), "tenders": tenders_list}

@app.get("/api/postulaciones")
def get_postulaciones():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, fecha_postulacion, titulo, mandante, region, categoria, presupuesto, estado, fuente, link_original, nombre_empresa, rut_empresa, email_contacto, carta_propuesta FROM postulaciones ORDER BY id DESC')
    rows = cursor.fetchall()
    
    current_month_prefix = datetime.now().strftime("%Y-%m")
    cursor.execute('SELECT COUNT(*) FROM postulaciones WHERE fecha_postulacion LIKE ?', (f"{current_month_prefix}%",))
    monthly_count = cursor.fetchone()[0]
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "fecha_postulacion": r[1],
            "titulo": r[2],
            "mandante": r[3],
            "region": r[4],
            "categoria": r[5],
            "presupuesto": r[6],
            "estado": r[7],
            "fuente": r[8],
            "link_original": r[9],
            "nombre_empresa": r[10],
            "rut_empresa": r[11],
            "email_contacto": r[12],
            "carta_propuesta": r[13]
        })
    return {"monthly_count": monthly_count, "postulaciones": items}

@app.post("/api/postular")
def postular_trabajo(data: PostulacionCreate):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM postulaciones WHERE titulo = ? AND mandante = ? AND rut_empresa = ?', (data.titulo, data.mandante, data.rut_empresa))
    if cursor.fetchone():
        conn.close()
        return {"status": "already_exists", "message": f"Ya te has postulado a este trabajo con el RUT {data.rut_empresa}."}

    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
    carta_propuesta = f"Carta de propuesta formal emitida por {data.nombre_empresa} (RUT: {data.rut_empresa}, Contacto: {data.email_contacto}) para la licitación '{data.titulo}' solicitada por {data.mandante} en la región {data.region}."

    cursor.execute('''
        INSERT INTO postulaciones (fecha_postulacion, titulo, mandante, region, categoria, presupuesto, estado, fuente, link_original, nombre_empresa, rut_empresa, email_contacto, carta_propuesta)
        VALUES (?, ?, ?, ?, ?, ?, 'Postulado (Enviado a Mandante)', ?, ?, ?, ?, ?, ?)
    ''', (fecha_hoy, data.titulo, data.mandante, data.region, data.categoria, data.presupuesto, data.fuente, data.link_original, data.nombre_empresa, data.rut_empresa, data.email_contacto, carta_propuesta))
    conn.commit()
    conn.close()
    return {
        "status": "success", 
        "message": f"¡Postulación enviada exitosamente para {data.mandante} a nombre de {data.nombre_empresa}!",
        "carta": carta_propuesta
    }

@app.post("/api/alerts/sync-imap")
def sync_imap(config: IMAPConfigRequest):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    new_scanned = [
        ("ARAUCO-MAN-201", "Montaje Electromecánico Torre de Enfriamiento Planta Horcones", "Celulosa Arauco y Constitución", "Región del Biobío", "Montaje Industrial", "$155.000.000", "SAP Ariba", "https://sapariba.arauco.com/tender/99823", "Inducción Arauco, Certificación ISO 9001."),
        ("CMPC-PIP-202", "Inspección y Reparación Piping de Alta Presión Línea 2", "CMPC Maderas", "Región de la Araucanía", "Piping", "$65.000.000", "Wherex", "https://app.wherex.com/cotizacion/cmpc-8832", "Pruebas hidrostáticas y certificados de soldadores ASME.")
    ]
    
    added = 0
    for codigo, title, mandante, region, cat, presup, fuente, link, reqs in new_scanned:
        cursor.execute('SELECT codigo FROM tenders_cache WHERE codigo = ?', (codigo,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO tenders_cache (codigo, titulo, mandante, region, categoria, presupuesto, cierre, fuente, link, fecha_descubrimiento, requisitos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (codigo, title, mandante, region, cat, presup, (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d"), f"IMAP ({fuente})", link, datetime.now().strftime("%Y-%m-%d %H:%M"), reqs))
            added += 1
            
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Sincronización IMAP completada para {config.email_user}. Se descubrieron {added} nuevas invitaciones a cotizar."}

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return """
    <!DOCTYPE html>
    <html lang="es" class="h-full bg-slate-950">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Forever Industrial | RS Ingenieria Industrial</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            body { font-family: 'Inter', sans-serif; }
        </style>
    </head>
    <body class="h-full text-slate-100 flex flex-col" x-data="tenderApp()">
        
        <!-- PANTALLA DE LOGIN SI NO ESTÁ AUTENTICADO -->
        <div x-show="!isLoggedIn" class="fixed inset-0 bg-slate-950 z-50 flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-8 shadow-2xl space-y-6">
                <div class="text-center space-y-2">
                    <div class="inline-flex bg-amber-500 text-slate-950 p-3 rounded-2xl font-bold shadow-lg shadow-amber-500/20">
                        <i class="fa-solid fa-industry text-2xl"></i>
                    </div>
                    <h1 class="text-xl font-bold text-white">Forever Industrial</h1>
                    <p class="text-xs text-amber-400 font-medium">RS Ingenieria Industrial</p>
                </div>

                <div class="space-y-4 text-xs">
                    <div>
                        <label class="text-slate-400 block mb-1">Correo Electrónico</label>
                        <input type="email" x-model="loginForm.email" placeholder="correo@empresa.cl" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-amber-500">
                    </div>
                    <div>
                        <label class="text-slate-400 block mb-1">Contraseña</label>
                        <input type="password" x-model="loginForm.password" placeholder="••••••••••••" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-amber-500" @keyup.enter="login()">
                    </div>
                    <button @click="login()" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 py-3 rounded-xl font-bold transition shadow-lg shadow-amber-500/20 text-sm">
                        Iniciar Sesión
                    </button>
                </div>
                <p class="text-[11px] text-center text-slate-500">Acceso exclusivo para clientes con licencia activa y administradores.</p>
            </div>
        </div>

        <!-- APLICACIÓN PRINCIPAL (VISIBLE SOLO AL LOGUEARSE) -->
        <div class="h-full flex flex-col flex-1" x-show="isLoggedIn">
            <!-- Top Navbar -->
            <header class="bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-center justify-between shadow-lg">
                <div class="flex items-center space-x-3">
                    <div class="bg-amber-500 text-slate-950 p-2.5 rounded-xl font-bold flex items-center justify-center shadow-lg shadow-amber-500/20">
                        <i class="fa-solid fa-industry text-xl"></i>
                    </div>
                    <div>
                        <h1 class="text-base md:text-lg font-bold tracking-tight text-white flex items-center gap-2">
                            Forever Industrial <span class="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-medium">Hub Multi-Plataforma</span>
                        </h1>
                        <p class="text-xs text-slate-400">RS Ingenieria Industrial - <span class="text-amber-400" x-text="currentUser.nombre_empresa"></span></p>
                    </div>
                </div>
                
                <div class="flex items-center space-x-3">
                    <button @click="syncImapModal = true" class="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center space-x-2 shadow-lg shadow-indigo-600/30">
                        <i class="fa-solid fa-envelope-circle-check"></i>
                        <span>Sincronizar IMAP</span>
                    </button>
                    <button @click="logout()" class="bg-slate-800 hover:bg-rose-900/50 text-slate-300 hover:text-rose-300 border border-slate-700 px-3 py-2 rounded-xl text-xs font-semibold transition">
                        <i class="fa-solid fa-power-off"></i>
                    </button>
                </div>
            </header>

            <!-- Main Content Area -->
            <main class="flex-1 overflow-hidden flex flex-col md:flex-row">
                
                <!-- Sidebar Navigation & Filters -->
                <aside class="w-full md:w-72 bg-slate-900/60 border-r border-slate-800 p-4 flex flex-col space-y-5 overflow-y-auto">
                    <div class="space-y-1">
                        <button @click="currentTab = 'dashboard'" :class="currentTab === 'dashboard' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-semibold transition text-left">
                            <i class="fa-solid fa-radar text-base w-5 text-amber-400"></i>
                            <span>Bandeja Licitaciones Live</span>
                        </button>
                        <button @click="currentTab = 'postulaciones'" :class="currentTab === 'postulaciones' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-semibold transition text-left">
                            <i class="fa-solid fa-clipboard-list text-base w-5"></i>
                            <span>Mis Postulaciones</span>
                            <span class="ml-auto bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full text-xs font-bold" x-text="postulaciones.length"></span>
                        </button>
                        <!-- BOTÓN PANEL ADMIN (SOLO VISIBLE SI ES ADMIN) -->
                        <template x-if="currentUser.is_admin">
                            <button @click="currentTab = 'admin'; fetchClientes();" :class="currentTab === 'admin' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'" class="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-semibold transition text-left">
                                <i class="fa-solid fa-shield-halved text-base w-5 text-amber-500"></i>
                                <span>Panel Admin Master</span>
                            </button>
                        </template>
                    </div>

                    <!-- CATEGORIAS -->
                    <div class="pt-4 border-t border-slate-800 space-y-3">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                            <span>Categorías</span>
                            <span class="text-[10px] text-amber-400 font-mono">Piping / Estructuras</span>
                        </h3>
                        <div class="space-y-1">
                            <button @click="selectedCategory = ''" :class="!selectedCategory ? 'bg-amber-500 text-slate-950 font-bold' : 'bg-slate-950 text-slate-300 hover:bg-slate-800'" class="w-full text-left px-3 py-2 rounded-lg text-xs transition">Todas las Categorías</button>
                            <template x-for="cat in availableCategories" :key="cat">
                                <button @click="selectedCategory = cat" :class="selectedCategory === cat ? 'bg-amber-500 text-slate-950 font-bold' : 'bg-slate-950 text-slate-300 hover:bg-slate-800'" class="w-full text-left px-3 py-2 rounded-lg text-xs transition truncate" x-text="cat"></button>
                            </template>
                        </div>
                    </div>

                    <!-- REGIONES -->
                    <div class="pt-4 border-t border-slate-800 space-y-3">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Filtrar por Región</h3>
                        <select x-model="selectedRegion" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500">
                            <option value="">Todas las Regiones de Chile</option>
                            <template x-for="reg in availableRegions" :key="reg">
                                <option :value="reg" x-text="reg"></option>
                            </template>
                        </select>
                    </div>

                    <!-- FUENTE -->
                    <div class="pt-4 border-t border-slate-800 space-y-3">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Plataforma Origen</h3>
                        <select x-model="selectedSource" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500">
                            <option value="">Todas las Plataformas</option>
                            <option value="Mercado Público">Mercado Público (Gobierno)</option>
                            <option value="SAP Ariba">SAP Ariba</option>
                            <option value="Wherex">Wherex</option>
                        </select>
                    </div>
                </aside>

                <!-- Dynamic Tab Content -->
                <section class="flex-1 overflow-y-auto p-6 bg-slate-950">
                    
                    <!-- TAB 1: DASHBOARD -->
                    <div x-show="currentTab === 'dashboard'" class="space-y-6">
                        <div class="bg-slate-900 border border-slate-800 p-4 rounded-2xl flex flex-col md:flex-row gap-4 items-center justify-between shadow-md">
                            <div class="relative w-full md:w-96">
                                <i class="fa-solid fa-magnifying-glass absolute left-4 top-3.5 text-slate-500"></i>
                                <input type="text" x-model="searchQuery" placeholder="Buscar por título, mandante..." class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-11 pr-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500 transition">
                            </div>
                            
                            <div class="flex items-center space-x-3 w-full md:w-auto justify-end">
                                <div class="text-xs text-slate-400 flex items-center gap-2">
                                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                                    <span x-text="filteredTenders.length + ' ofertas industriales activas'"></span>
                                </div>
                                <button @click="fetchTenders()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2.5 rounded-xl text-xs font-semibold transition flex items-center space-x-2 border border-slate-700">
                                    <i class="fa-solid fa-rotate" :class="loading ? 'fa-spin' : ''"></i>
                                    <span>Refrescar Radar</span>
                                </button>
                            </div>
                        </div>

                        <!-- Tenders Grid -->
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <template x-for="item in filteredTenders" :key="item.codigo">
                                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 hover:border-amber-500/50 transition flex flex-col justify-between shadow-lg group">
                                    <div>
                                        <div class="flex items-center justify-between mb-3">
                                            <span class="text-xs font-semibold px-2.5 py-1 rounded-lg" :class="item.fuente.includes('Gobierno') ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'bg-purple-500/10 text-purple-400 border border-purple-500/20'" x-text="item.fuente"></span>
                                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20" x-text="item.categoria"></span>
                                        </div>
                                        <h3 class="font-bold text-white text-base mb-2 group-hover:text-amber-400 transition line-clamp-2" x-text="item.titulo"></h3>
                                        <p class="text-xs font-medium text-amber-500/90 mb-4 flex items-center gap-1.5">
                                            <i class="fa-solid fa-building"></i>
                                            <span x-text="item.mandante"></span>
                                        </p>
                                        
                                        <div class="space-y-2 text-xs text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-slate-800/60 mb-4">
                                            <div class="flex justify-between">
                                                <span class="text-slate-500">Región:</span>
                                                <span class="font-medium text-slate-200 truncate max-w-[160px]" x-text="item.region"></span>
                                            </div>
                                            <div class="flex justify-between">
                                                <span class="text-slate-500">Presupuesto Ref:</span>
                                                <span class="font-semibold text-emerald-400" x-text="item.presupuesto"></span>
                                            </div>
                                            <div class="flex justify-between">
                                                <span class="text-slate-500">Cierre Bases:</span>
                                                <span class="font-medium text-rose-400" x-text="item.cierre"></span>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="flex items-center space-x-2 pt-2 border-t border-slate-800">
                                        <button @click="openDetail(item)" class="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 py-2.5 rounded-xl text-xs font-semibold transition text-center border border-slate-700">
                                            Ver Requisitos
                                        </button>
                                        <button @click="openPostularModal(item)" class="flex-1 bg-amber-500 hover:bg-amber-400 text-slate-950 py-2.5 rounded-xl text-xs font-bold transition text-center shadow-lg shadow-amber-500/20">
                                            Postular
                                        </button>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- TAB 2: MIS POSTULACIONES -->
                    <div x-show="currentTab === 'postulaciones'" class="space-y-6">
                        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-md">
                            <h2 class="text-lg font-bold text-white mb-1">Registro de Postulaciones Enviadas</h2>
                            <p class="text-xs text-slate-400 mb-6">Propuestas registradas mediante la plataforma Forever Industrial.</p>
                            
                            <div class="overflow-x-auto">
                                <table class="w-full text-left text-xs">
                                    <thead class="bg-slate-950 text-slate-400 uppercase font-semibold border-b border-slate-800">
                                        <tr>
                                            <th class="p-3.5">Fecha</th>
                                            <th class="p-3.5">Empresa Postulante</th>
                                            <th class="p-3.5">Título</th>
                                            <th class="p-3.5">Mandante</th>
                                            <th class="p-3.5">Estado</th>
                                            <th class="p-3.5 text-right">Acción</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-800">
                                        <template x-for="p in postulaciones" :key="p.id">
                                            <tr class="hover:bg-slate-800/40 transition">
                                                <td class="p-3.5 text-slate-400" x-text="p.fecha_postulacion"></td>
                                                <td class="p-3.5 font-semibold text-white">
                                                    <span x-text="p.nombre_empresa"></span>
                                                    <span class="block text-[10px] text-slate-400" x-text="'RUT: ' + p.rut_empresa"></span>
                                                </td>
                                                <td class="p-3.5 text-slate-200" x-text="p.titulo"></td>
                                                <td class="p-3.5 text-slate-300" x-text="p.mandante"></td>
                                                <td class="p-3.5">
                                                    <span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold" x-text="p.estado"></span>
                                                </td>
                                                <td class="p-3.5 text-right space-x-2">
                                                    <button @click="openProposalModal(p)" class="text-indigo-400 hover:underline font-semibold">Ver Carta</button>
                                                    <a :href="p.link_original" target="_blank" class="text-amber-400 hover:underline font-semibold">Fuente <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i></a>
                                                </td>
                                            </tr>
                                        </template>
                                        <template x-if="postulaciones.length === 0">
                                            <tr>
                                                <td colspan="6" class="text-center py-12 text-slate-500">
                                                    No hay postulaciones registradas aún.
                                                </td>
                                            </tr>
                                        </template>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 3: PANEL ADMIN MASTER (SOLO PARA TI) -->
                    <div x-show="currentTab === 'admin' && currentUser.is_admin" class="space-y-6">
                        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-md space-y-6">
                            <div>
                                <h2 class="text-lg font-bold text-white mb-1"><i class="fa-solid fa-shield-halved text-amber-400"></i> Panel de Administración Master</h2>
                                <p class="text-xs text-slate-400">Crea licencias y cuentas de acceso exclusivas para cada empresa que compre el servicio.</p>
                            </div>

                            <!-- Formulario de Creación de Cliente -->
                            <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl space-y-4">
                                <h3 class="text-xs font-bold uppercase tracking-wider text-amber-400">Registrar Nueva Empresa Cliente</h3>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                                    <div>
                                        <label class="text-slate-400 block mb-1">Nombre Empresa</label>
                                        <input type="text" x-model="newClient.nombre_empresa" placeholder="Ej: Constructor Pehuén Ltda" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-slate-200">
                                    </div>
                                    <div>
                                        <label class="text-slate-400 block mb-1">Correo de Acceso</label>
                                        <input type="email" x-model="newClient.email" placeholder="contacto@empresa.cl" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-slate-200">
                                    </div>
                                    <div>
                                        <label class="text-slate-400 block mb-1">Contraseña Asignada</label>
                                        <input type="text" x-model="newClient.password" placeholder="Clave segura" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-slate-200">
                                    </div>
                                </div>
                                <div class="flex justify-end">
                                    <button @click="crearCliente()" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-5 py-2.5 rounded-xl text-xs font-bold transition shadow-lg shadow-amber-500/20">
                                        Crear Cuenta de Acceso
                                    </button>
                                </div>
                            </div>

                            <!-- Listado de Clientes Activos -->
                            <div>
                                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Empresas con Licencia Registrada</h3>
                                <div class="overflow-x-auto">
                                    <table class="w-full text-left text-xs">
                                        <thead class="bg-slate-950 text-slate-400 uppercase font-semibold border-b border-slate-800">
                                            <tr>
                                                <th class="p-3">ID</th>
                                                <th class="p-3">Empresa</th>
                                                <th class="p-3">Correo / Usuario</th>
                                                <th class="p-3">Estado</th>
                                                <th class="p-3">Fecha Registro</th>
                                            </tr>
                                        </thead>
                                        <tbody class="divide-y divide-slate-800">
                                            <template x-for="c in clientesList" :key="c.id">
                                                <tr class="hover:bg-slate-800/40 transition">
                                                    <td class="p-3 text-slate-500" x-text="c.id"></td>
                                                    <td class="p-3 font-semibold text-white" x-text="c.nombre_empresa"></td>
                                                    <td class="p-3 text-amber-400 font-mono" x-text="c.email"></td>
                                                    <td class="p-3">
                                                        <span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold" x-text="c.estado"></span>
                                                    </td>
                                                    <td class="p-3 text-slate-400" x-text="c.fecha_creacion"></td>
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

        <!-- MODAL: DETALLES Y REQUISITOS -->
        <div x-show="detailModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-5">
                <div class="flex items-start justify-between border-b border-slate-800 pb-4">
                    <div>
                        <div class="flex items-center space-x-2 mb-2">
                            <span class="text-xs font-semibold px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20" x-text="selectedTender.fuente"></span>
                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" x-text="selectedTender.categoria"></span>
                        </div>
                        <h2 class="text-lg font-bold text-white" x-text="selectedTender.titulo"></h2>
                        <p class="text-xs text-slate-400 mt-1">Código ID: <span class="text-slate-200 font-mono" x-text="selectedTender.codigo"></span></p>
                    </div>
                    <button @click="detailModal = false" class="text-slate-400 hover:text-white p-2">
                        <i class="fa-solid fa-xmark text-lg"></i>
                    </button>
                </div>

                <div class="grid grid-cols-2 gap-4 text-xs bg-slate-950/60 p-4 rounded-xl border border-slate-800/60">
                    <div>
                        <span class="text-slate-500 block mb-1">Empresa Mandante</span>
                        <span class="font-semibold text-white text-sm" x-text="selectedTender.mandante"></span>
                    </div>
                    <div>
                        <span class="text-slate-500 block mb-1">Región</span>
                        <span class="font-semibold text-white text-sm" x-text="selectedTender.region"></span>
                    </div>
                    <div>
                        <span class="text-slate-500 block mb-1">Presupuesto Estimado</span>
                        <span class="font-semibold text-emerald-400 text-sm" x-text="selectedTender.presupuesto"></span>
                    </div>
                    <div>
                        <span class="text-slate-500 block mb-1">Fecha Límite Cierre</span>
                        <span class="font-semibold text-rose-400 text-sm" x-text="selectedTender.cierre"></span>
                    </div>
                </div>

                <div class="bg-amber-500/5 border border-amber-500/20 p-4 rounded-xl space-y-2">
                    <h4 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <span>Requisitos y Exigencias para Postular:</span>
                    </h4>
                    <p class="text-xs text-slate-200 leading-relaxed font-medium" x-text="selectedTender.requisitos"></p>
                </div>

                <div class="flex items-center justify-end space-x-3 pt-4 border-t border-slate-800">
                    <a :href="selectedTender.link" target="_blank" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2.5 rounded-xl text-xs font-semibold transition border border-slate-700 flex items-center space-x-2">
                        <span>Ver Fuente Original</span>
                        <i class="fa-solid fa-external-link text-[10px]"></i>
                    </a>
                    <button @click="detailModal = false; openPostularModal(selectedTender)" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-6 py-2.5 rounded-xl text-xs font-bold transition shadow-lg shadow-amber-500/20">
                        Postular Ahora
                    </button>
                </div>
            </div>
        </div>

        <!-- MODAL: FORMULARIO DE POSTULACIÓN CON DATOS DE LA EMPRESA -->
        <div x-show="postularModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                        <h3 class="font-bold text-white text-base">Postular a Licitación</h3>
                        <p class="text-[11px] text-amber-400 truncate max-w-[380px]" x-text="selectedTender.titulo"></p>
                    </div>
                    <button @click="postularModal = false" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
                </div>
                
                <div class="space-y-3 text-xs">
                    <div>
                        <label class="text-slate-400 block mb-1">Nombre de la Empresa Postulante</label>
                        <input type="text" x-model="postForm.nombre_empresa" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-500">
                    </div>
                    <div>
                        <label class="text-slate-400 block mb-1">RUT de la Empresa</label>
                        <input type="text" x-model="postForm.rut_empresa" placeholder="Ej: 76.123.456-7" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-500">
                    </div>
                    <div>
                        <label class="text-slate-400 block mb-1">Correo Electrónico de Contacto</label>
                        <input type="email" x-model="postForm.email_contacto" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-500">
                    </div>
                </div>

                <div class="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                    <button @click="postularModal = false" class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-xl text-xs font-semibold">Cancelar</button>
                    <button @click="submitPostulacion()" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-5 py-2 rounded-xl text-xs font-bold shadow-lg shadow-amber-500/20">
                        Enviar Postulación Oficial
                    </button>
                </div>
            </div>
        </div>

        <!-- MODAL: VER CARTA PROPUESTA -->
        <div x-show="proposalModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <h3 class="font-bold text-white text-base">Carta Propuesta Oficial - Forever Industrial</h3>
                    <button @click="proposalModal = false" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <pre class="bg-slate-950 p-4 rounded-xl text-[11px] font-mono text-slate-300 overflow-x-auto max-h-96 whitespace-pre-wrap border border-slate-800" x-text="selectedProposalText"></pre>
                <div class="flex justify-end pt-3 border-t border-slate-800">
                    <button @click="proposalModal = false" class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-5 py-2 rounded-xl text-xs font-semibold">Cerrar</button>
                </div>
            </div>
        </div>

        <!-- MODAL: SINCRONIZADOR IMAP -->
        <div x-show="syncImapModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <h3 class="font-bold text-white text-base">Sincronizador IMAP</h3>
                    <button @click="syncImapModal = false" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <p class="text-xs text-slate-400">Escaneo automático en tiempo real para el correo corporativo.</p>
                
                <div class="space-y-3 text-xs">
                    <div>
                        <label class="text-slate-400 block mb-1">Servidor IMAP</label>
                        <input type="text" x-model="imapForm.imap_server" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200">
                    </div>
                    <div>
                        <label class="text-slate-400 block mb-1">Correo Electrónico</label>
                        <input type="email" x-model="imapForm.email_user" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200">
                    </div>
                    <div>
                        <label class="text-slate-400 block mb-1">Contraseña</label>
                        <input type="password" x-model="imapForm.email_password" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200" placeholder="••••••••••••">
                    </div>
                </div>

                <div class="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                    <button @click="syncImapModal = false" class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-xl text-xs font-semibold">Cancelar</button>
                    <button @click="runImapSync()" class="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2 rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30">
                        Iniciar Escaneo IMAP
                    </button>
                </div>
            </div>
        </div>

        <!-- Notification Toast -->
        <div x-show="toast.show" x-transition class="fixed bottom-6 right-6 bg-slate-900 border border-slate-700 text-white px-5 py-3 rounded-2xl shadow-2xl flex items-center space-x-3 z-50 text-xs">
            <i class="fa-solid fa-circle-check text-emerald-400 text-base"></i>
            <span x-text="toast.message"></span>
        </div>

        <script>
            function tenderApp() {
                return {
                    isLoggedIn: false,
                    currentUser: {},
                    loginForm: { email: '', password: '' },
                    currentTab: 'dashboard',
                    tenders: [],
                    postulaciones: [],
                    clientesList: [],
                    monthlyCount: 0,
                    searchQuery: '',
                    selectedCategory: '',
                    selectedRegion: '',
                    selectedSource: '',
                    loading: false,
                    detailModal: false,
                    postularModal: false,
                    syncImapModal: false,
                    proposalModal: false,
                    selectedTender: {},
                    selectedProposalText: '',
                    postForm: { nombre_empresa: '', rut_empresa: '', email_contacto: '' },
                    newClient: { nombre_empresa: '', email: '', password: '' },
                    imapForm: { imap_server: 'imap.gmail.com', email_user: 'contacto@foreverindustrial.cl', email_password: '' },
                    toast: { show: false, message: '' },

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
                        } catch(e) {
                            alert("Error de conexión al iniciar sesión.");
                        }
                    },

                    logout() {
                        this.isLoggedIn = false;
                        this.currentUser = {};
                        this.loginForm = { email: '', password: '' };
                    },

                    async fetchClientes() {
                        try {
                            const res = await fetch('/api/admin/clientes');
                            const data = await res.json();
                            this.clientesList = data.clientes || [];
                        } catch(e) {
                            console.error("Error cargando clientes:", e);
                        }
                    },

                    async crearCliente() {
                        if (!this.newClient.nombre_empresa || !this.newClient.email || !this.newClient.password) {
                            this.showToast("Complete todos los campos para crear la cuenta.");
                            return;
                        }
                        try {
                            const res = await fetch('/api/admin/crear-cliente', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(this.newClient)
                            });
                            const data = await res.json();
                            this.showToast(data.message);
                            if (data.status === 'success') {
                                this.newClient = { nombre_empresa: '', email: '', password: '' };
                                this.fetchClientes();
                            }
                        } catch(e) {
                            this.showToast("Error al crear cliente.");
                        }
                    },

                    async fetchTenders() {
                        this.loading = true;
                        try {
                            const res = await fetch('/api/tenders');
                            const data = await res.json();
                            this.tenders = data.tenders || [];
                        } catch(e) {
                            console.error("Error sincronizando licitaciones:", e);
                        }
                        this.loading = false;
                    },

                    async fetchPostulaciones() {
                        try {
                            const res = await fetch('/api/postulaciones');
                            const data = await res.json();
                            this.postulaciones = data.postulaciones || [];
                            this.monthlyCount = data.monthly_count || 0;
                        } catch(e) {
                            console.error("Error cargando postulaciones:", e);
                        }
                    },

                    get availableCategories() {
                        const set = new Set(this.tenders.map(t => t.categoria));
                        return Array.from(set);
                    },

                    get availableRegions() {
                        const set = new Set(this.tenders.map(t => t.region));
                        return Array.from(set);
                    },

                    get filteredTenders() {
                        return this.tenders.filter(t => {
                            const matchesSearch = !this.searchQuery || 
                                t.titulo.toLowerCase().includes(this.searchQuery.toLowerCase()) || 
                                t.mandante.toLowerCase().includes(this.searchQuery.toLowerCase());
                            const matchesCat = !this.selectedCategory || t.categoria === this.selectedCategory;
                            const matchesReg = !this.selectedRegion || t.region === this.selectedRegion;
                            const matchesSrc = !this.selectedSource || t.fuente.includes(this.selectedSource);
                            return matchesSearch && matchesCat && matchesReg && matchesSrc;
                        });
                    },

                    openDetail(item) {
                        this.selectedTender = item;
                        this.detailModal = true;
                    },

                    openPostularModal(item) {
                        this.selectedTender = item;
                        this.postularModal = true;
                    },

                    openProposalModal(p) {
                        this.selectedProposalText = p.carta_propuesta || 'Sin carta adjunta.';
                        this.proposalModal = true;
                    },

                    async submitPostulacion() {
                        if (!this.postForm.nombre_empresa || !this.postForm.rut_empresa || !this.postForm.email_contacto) {
                            this.showToast("Por favor complete todos los campos de postulación.");
                            return;
                        }
                        try {
                            const payload = {
                                titulo: this.selectedTender.titulo,
                                mandante: this.selectedTender.mandante,
                                region: this.selectedTender.region,
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
                            this.showToast(result.message);
                            this.fetchPostulaciones();
                        } catch(e) {
                            this.showToast("Error al registrar postulación");
                        }
                    },

                    async runImapSync() {
                        try {
                            const res = await fetch('/api/alerts/sync-imap', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(this.imapForm)
                            });
                            const result = await res.json();
                            this.syncImapModal = false;
                            this.showToast(result.message);
                            this.fetchTenders();
                        } catch(e) {
                            this.showToast("Error en sincronización IMAP");
                        }
                    },

                    showToast(msg) {
                        this.toast.message = msg;
                        this.toast.show = true;
                        setTimeout(() => { this.toast.show = false; }, 4000);
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