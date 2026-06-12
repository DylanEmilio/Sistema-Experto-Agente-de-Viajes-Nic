from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'sistema_experto_viajes_secreto'

# ==========================================
# 1. CONFIGURACIÓN DE LA BASE DE DATOS
# ==========================================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///viajes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# 2. MODELOS DE LA BASE DE DATOS (TABLAS)
# ==========================================
class Destino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    motivacion = db.Column(db.String(50), nullable=False)
    social = db.Column(db.String(50), nullable=False)
    actividad = db.Column(db.String(50), nullable=False)
    alojamiento = db.Column(db.String(50), nullable=False)
    clima = db.Column(db.String(50), nullable=False)
    cultura = db.Column(db.String(50), nullable=False)
    presupuesto = db.Column(db.String(50), nullable=False)
    costo = db.Column(db.Integer, nullable=False)
    desc = db.Column(db.Text, nullable=False)

class Consulta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    motivacion_buscada = db.Column(db.String(50))
    clima_buscado = db.Column(db.String(50))
    presupuesto_buscado = db.Column(db.String(50))
    destino_recomendado = db.Column(db.String(100))
    puntos = db.Column(db.Float)  # Cambiado a Float para guardar el porcentaje

# ==========================================
# 3. MOTOR DE INFERENCIA (TOP 3 Y MATCH %)
# ==========================================
def evaluar_destino(datos):
    if not datos:
        return []
        
    motivacion = datos.get('motivacion')
    clima = datos.get('clima')
    
    if motivacion in [None, '', 'Selecciona una opción'] or clima in [None, '', 'Selecciona una opción']:
        return []

    # El puntaje perfecto si todas las variables hacen match
    MAX_PUNTOS = 68.0 
    
    destinos_db = Destino.query.all()
    resultados_evaluacion = []

    for d in destinos_db:
        puntos = 0
        
        # 1. Reglas de Peso Pesado
        if datos.get('motivacion') == d.motivacion: puntos += 15
        if datos.get('cultura') == d.cultura: puntos += 15
        
        # 2. Reglas de Peso Medio
        if datos.get('clima') == d.clima: puntos += 10
        if datos.get('presupuesto') == d.presupuesto: puntos += 10
        if datos.get('alojamiento') == d.alojamiento: puntos += 8
        
        # 3. Reglas de Peso Ligero
        if datos.get('social') == d.social: puntos += 5
        if datos.get('actividad') == d.actividad: puntos += 5

        # 4. Reglas Críticas (Penalizaciones)
        if datos.get('presupuesto') == 'Bajo' and d.presupuesto == 'Alto':
            puntos -= 30
        if datos.get('social') == 'Baja' and d.social in ['Alta', 'Muy Alta']:
            puntos -= 15

        # Lógica Difusa: Cálculo de porcentaje (evitando números negativos)
        porcentaje_crudo = (puntos / MAX_PUNTOS) * 100
        porcentaje_final = round(max(0, porcentaje_crudo), 1)

        resultados_evaluacion.append({
            "destino": d,
            "puntos": puntos,
            "porcentaje": porcentaje_final
        })
            
    # Ordenar la lista de mayor a menor según los puntos
    resultados_evaluacion.sort(key=lambda x: x['puntos'], reverse=True)
    
    # Extraer solo el Top 3
    top_3 = resultados_evaluacion[:3]
    
    # Formateo final para el frontend
    destinos_formateados = []
    for item in top_3:
        d = item["destino"]
        destinos_formateados.append({
            "nombre": d.nombre,
            "motivacion": d.motivacion,
            "social": d.social,
            "actividad": d.actividad,
            "alojamiento": d.alojamiento,
            "clima": d.clima,
            "cultura": d.cultura,
            "presupuesto": d.presupuesto,
            "costo": d.costo,
            "desc": d.desc,
            "porcentaje": item["porcentaje"]
        })
        
    return destinos_formateados

# ==========================================
# 4. RUTA PRINCIPAL (PATRÓN PRG)
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def inicio():
    if request.method == 'POST':
        datos = request.form
        top_destinos = evaluar_destino(datos)
        
        if len(top_destinos) > 0:
            try:
                dias = int(datos.get('dias', 3))
            except ValueError:
                dias = 3
                
            session['ofertas'] = []
            for dest in top_destinos:
                session['ofertas'].append({
                    "destino": dest,
                    "dias": dias,
                    "total_estimado": dest['costo'] * dias,
                    "porcentaje_match": dest['porcentaje']
                })

            # Guardar en base de datos la opción #1 como referencia de auditoría
            mejor_destino = top_destinos[0]
            nuevo_log = Consulta(
                motivacion_buscada=datos.get('motivacion', 'No especificó'),
                clima_buscado=datos.get('clima', 'No especificó'),
                presupuesto_buscado=datos.get('presupuesto', 'No especificó'),
                destino_recomendado=mejor_destino['nombre'],
                puntos=mejor_destino['porcentaje']
            )
            db.session.add(nuevo_log)
            db.session.commit()
        
        return redirect(url_for('inicio'))
        
    ofertas = session.pop('ofertas', None)
    return render_template('index.html', ofertas=ofertas)

# ==========================================
# 5. EJECUCIÓN E INICIALIZACIÓN AUTOMÁTICA
# ==========================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  
        
        if Destino.query.first() is None:
            destinos_iniciales = [
                {
                    "nombre": "Corn Island (Caribe)", "motivacion": "Relajación", "social": "Baja", "actividad": "Baja",
                    "alojamiento": "Hotel Boutique", "clima": "Cálido Húmedo", "cultura": "Afro-caribeña", "presupuesto": "Alto", 
                    "costo": 150, "desc": "Playas turquesas de arena blanca y marisco fresco. Un retiro exclusivo y silencioso."
                },
                {
                    "nombre": "Isla de Ometepe", "motivacion": "Aventura", "social": "Media", "actividad": "Alta",
                    "alojamiento": "Eco-lodge", "clima": "Cálido", "cultura": "Indígena", "presupuesto": "Bajo", 
                    "costo": 40, "desc": "Naturaleza pura. Dos imponentes volcanes en medio del Gran Lago de Nicaragua."
                },
                {
                    "nombre": "Granada", "motivacion": "Cultura", "social": "Alta", "actividad": "Media",
                    "alojamiento": "Hotel Colonial", "clima": "Cálido", "cultura": "Hispánica", "presupuesto": "Medio", 
                    "costo": 75, "desc": "La Gran Sultana. Arquitectura colonial, paseos en volanta e isletas históricas."
                },
                {
                    "nombre": "San Juan del Sur", "motivacion": "Fiesta/Social", "social": "Muy Alta", "actividad": "Media",
                    "alojamiento": "Hostal", "clima": "Cálido Seco", "cultura": "Moderna", "presupuesto": "Medio", 
                    "costo": 85, "desc": "La meca del surf en el Pacífico. Excelente ambiente nocturno y playas dinámicas."
                },
                {
                    "nombre": "Selva Negra (Matagalpa)", "motivacion": "Naturaleza", "social": "Baja", "actividad": "Alta",
                    "alojamiento": "Cabaña", "clima": "Fresco", "cultura": "Cafetalera", "presupuesto": "Medio", 
                    "costo": 65, "desc": "Clima de montaña exquisito. Podrás disfrutar de tours de café y senderos privados."
                },
                {
                    "nombre": "León", "motivacion": "Historia", "social": "Alta", "actividad": "Media",
                    "alojamiento": "Hostal", "clima": "Muy Cálido", "cultura": "Revolucionaria", "presupuesto": "Bajo", 
                    "costo": 45, "desc": "Cuna de la Revolución y poetas. Ideal para visitar la Catedral y hacer volcano boarding."
                }
            ]
            
            for d in destinos_iniciales:
                nuevo_destino = Destino(
                    nombre=d["nombre"], motivacion=d["motivacion"], social=d["social"],
                    actividad=d["actividad"], alojamiento=d["alojamiento"], clima=d["clima"],
                    cultura=d["cultura"], presupuesto=d["presupuesto"], costo=d["costo"], desc=d["desc"]
                )
                db.session.add(nuevo_destino)
                
            db.session.commit()
            print("¡Base de datos viajes.db generada y poblada con éxito!")

    app.run(debug=True)