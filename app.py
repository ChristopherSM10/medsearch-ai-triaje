from flask import Flask, render_template_string, request, redirect, url_for
import heapq

app = Flask(__name__)

# =====================================================================
# 1. BASE DE CONOCIMIENTO CLÍNICO (Sistema de Triaje Manchester)
# =====================================================================
SINTOMAS_DB = {
    "Paro cardiorrespiratorio / Inconsciente": (10, "N1 - Reanimación (Rojo)", "Sala de Choque"),
    "Dolor torácico agudo / Posible infarto": (20, "N2 - Emergencia (Naranja)", "Unidad Coronaria"),
    "Dificultad respiratoria severa": (22, "N2 - Emergencia (Naranja)", "Inhaloterapia / Choque"),
    "Traumatismo craneoencefálico / Fractura": (35, "N3 - Urgencia (Amarillo)", "Traumatología"),
    "Dolor abdominal intenso / Apendicitis": (45, "N3 - Urgencia (Amarillo)", "Cirugía General"),
    "Fiebre alta (>39°C) con deshidratación": (60, "N4 - Prioritario (Verde)", "Consultorio Urgencias"),
    "Herida superficial / Esguince leve": (80, "N5 - No Urgente (Azul)", "Curaciones / Consulta"),
    "Dolor de garganta / Resfriado común": (90, "N5 - No Urgente (Azul)", "Consulta Externa")
}

PACIENTES_INICIALES = [
    ("Carlos Mendoza", 58, "Dolor torácico agudo / Posible infarto", 91, 118, 12),
    ("Sofía Ramírez", 24, "Herida superficial / Esguince leve", 98, 78, 35),
    ("Mateo López", 72, "Dificultad respiratoria severa", 86, 125, 5),
    ("Ana Torres", 31, "Fiebre alta (>39°C) con deshidratación", 96, 102, 20),
    ("Luis Herrera", 19, "Traumatismo craneoencefálico / Fractura", 95, 110, 8),
    ("Elena Ruiz", 42, "Dolor de garganta / Resfriado común", 99, 74, 45),
]

# =====================================================================
# 2. MOTOR DE BÚSQUEDA HEURÍSTICA: BEST-FIRST SEARCH
# =====================================================================
class NodoPaciente:
    def __init__(self, pid, nombre, edad, sintoma, spo2, fc, min_espera):
        self.pid = pid
        self.nombre = nombre
        self.edad = edad
        self.sintoma = sintoma
        self.spo2 = spo2
        self.fc = fc
        self.min_espera = min_espera
        self.nivel_txt = SINTOMAS_DB[sintoma][1]
        self.area_destino = SINTOMAS_DB[sintoma][2]
        self.h_score, self.desglose = self.calcular_heuristica()

    def calcular_heuristica(self):
        riesgo_base = SINTOMAS_DB[self.sintoma][0]
        penalizacion_signos = 0.0
        factores = []

        if self.spo2 < 90:
            penalizacion_signos -= 18.0
            factores.append(f"Hipoxia SpO₂ {self.spo2}% (-18)")
        elif self.spo2 < 94:
            penalizacion_signos -= 8.0
            factores.append(f"SpO₂ baja {self.spo2}% (-8)")

        if self.fc > 120 or self.fc < 50:
            penalizacion_signos -= 12.0
            factores.append(f"FC crítica {self.fc} lpm (-12)")
        elif self.fc > 100:
            penalizacion_signos -= 5.0
            factores.append(f"Taquicardia {self.fc} lpm (-5)")

        factor_edad = 0.0
        if self.edad >= 65 or self.edad <= 5:
            factor_edad = -7.0
            factores.append(f"Edad vulnerable {self.edad}a (-7)")

        factor_espera = -(self.min_espera * 0.25)
        if self.min_espera > 0:
            factores.append(f"Espera {self.min_espera}m (-{self.min_espera * 0.25:.1f})")

        h_final = max(1.0, round(riesgo_base + penalizacion_signos + factor_edad + factor_espera, 2))
        explicacion = f"Base: {riesgo_base} pts | " + (" + ".join(factores) if factores else "Signos estables")
        return h_final, explicacion

    def __lt__(self, otro):
        return self.h_score < otro.h_score


class MotorTriajeBestFirst:
    def __init__(self):
        self.frontera = []
        self.atendidos = []
        self.logs = []
        self.contador_id = 1
        for p in PACIENTES_INICIALES:
            self.agregar_paciente(*p, registrar_log=False)
        self.logs.insert(0, "Sistema inicializado con 6 pacientes en la frontera de búsqueda.")

    def agregar_paciente(self, nombre, edad, sintoma, spo2, fc, min_espera=0, registrar_log=True):
        nodo = NodoPaciente(self.contador_id, nombre, edad, sintoma, spo2, fc, min_espera)
        self.contador_id += 1
        heapq.heappush(self.frontera, nodo)
        if registrar_log:
            self.logs.insert(0, f"[INSERTAR] {nodo.nombre} -> h(n)={nodo.h_score} ({nodo.desglose})")
        return nodo

    def expandir_siguiente(self):
        if not self.frontera:
            return None
        paciente = heapq.heappop(self.frontera)
        self.atendidos.append(paciente)
        self.logs.insert(0, f"[EXPANDIR MEJOR NODO] {paciente.nombre} atendido (h(n)={paciente.h_score}) -> {paciente.area_destino}")
        return paciente

    def avanzar_tiempo(self, minutos=15):
        actualizados = []
        for nodo in self.frontera:
            nodo.min_espera += minutos
            nodo.h_score, nodo.desglose = nodo.calcular_heuristica()
            actualizados.append(nodo)
        heapq.heapify(actualizados)
        self.frontera = actualizados
        self.logs.insert(0, f"[TIEMPO +{minutos}m] Heurística h(n) recalculada para todos los nodos en espera.")

motor = MotorTriajeBestFirst()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MedSearch AI — Triaje con Best-First Search</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f1f5f9; margin: 0; color: #1e293b; }
        header { background: #0f172a; color: white; padding: 16px 28px; display: flex; justify-content: space-between; align-items: center; }
        header h1 { margin: 0; font-size: 1.3rem; color: #38bdf8; }
        header span { color: #cbd5e1; font-weight: normal; font-size: 0.95rem; }
        .badge { background: #1e293b; color: #38bdf8; padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; }
        .container { display: grid; grid-template-columns: 330px 1fr; gap: 20px; padding: 20px 28px; }
        .card { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 18px; }
        label { display: block; font-size: 0.85rem; color: #475569; margin-top: 10px; font-weight: 600; }
        input, select { width: 100%; padding: 8px; margin-top: 4px; border: 1px solid #cbd5e1; border-radius: 5px; box-sizing: border-box; }
        .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
        button { width: 100%; padding: 10px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 12px; font-size: 0.9rem; }
        .btn-blue { background: #0284c7; color: white; }
        .btn-green { background: #10b981; color: white; }
        .btn-gray { background: #e2e8f0; color: #1e293b; }
        .btn-light { background: #f8fafc; color: #64748b; border: 1px solid #cbd5e1; }
        .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
        .kpi { background: white; border: 1px solid #cbd5e1; border-top: 4px solid #0284c7; border-radius: 6px; padding: 12px; }
        .kpi small { color: #64748b; font-weight: bold; font-size: 0.75rem; }
        .kpi div { font-size: 1.2rem; font-weight: bold; margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
        th { background: #0f172a; color: white; padding: 10px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #e2e8f0; }
        tbody tr.fila-paciente { cursor: pointer; transition: background 0.15s; }
        tbody tr.fila-paciente:hover { filter: brightness(0.95); }
        tr.critico { background: #fee2e2; color: #991b1b; }
        tr.urgente { background: #fef3c7; color: #92400e; }
        .inspector { background: #e0f2fe; border: 1px solid #bae6fd; padding: 12px; border-radius: 6px; margin: 14px 0; font-size: 0.9rem; color: #0c4a6e; font-weight: 600; }
        .alerta-prioridad { display: none; background: #fef2f2; border: 1px solid #ef4444; border-left: 5px solid #dc2626; color: #991b1b; padding: 12px 16px; border-radius: 6px; margin-bottom: 14px; font-size: 0.9rem; font-weight: 600; }
        .log { background: #0f172a; color: #e2e8f0; font-family: monospace; padding: 14px; border-radius: 6px; height: 130px; overflow-y: auto; font-size: 0.85rem; }
        @media (max-width: 900px) { .container { grid-template-columns: 1fr; } .kpis { grid-template-columns: 1fr 1fr; } }
    </style>
</head>
<body>
<header>
    <h1>🏥 MedSearch AI <span>| Triaje mediante Búsqueda Primero el Mejor (Best-First Search)</span></h1>
    <div class="badge">Estructura: Min-Heap O(log n)</div>
</header>
<div class="container">
    <div class="card">
        <h3 style="margin-top:0; font-size:0.95rem;">1. INGRESO DE NUEVO PACIENTE</h3>
        <form action="/agregar" method="POST">
            <label>Nombre completo:</label>
            <input type="text" name="nombre" value="Roberto Gómez" required>
            <label>Motivo de consulta / Síntoma:</label>
            <select name="sintoma">
                {% for s in sintomas %}
                <option value="{{ s }}" {% if loop.index == 2 %}selected{% endif %}>{{ s }}</option>
                {% endfor %}
            </select>
            <div class="row3">
                <div><label>Edad</label><input type="number" name="edad" value="68" required></div>
                <div><label>SpO₂ (%)</label><input type="number" name="spo2" value="89" required></div>
                <div><label>Frec. Card.</label><input type="number" name="fc" value="122" required></div>
            </div>
            <button type="submit" class="btn-blue">+ Insertar Nodo en Frontera</button>
        </form>
        <hr style="margin: 18px 0; border: 0; border-top: 1px solid #e2e8f0;">
        <h3 style="font-size:0.95rem;">2. CONTROL DE EXPANSIÓN</h3>
        <form action="/atender" method="POST"><button type="submit" class="btn-green">▶ Atender Siguiente (Menor h(n))</button></form>
        <form action="/tiempo" method="POST"><button type="submit" class="btn-gray">⏱ Simular +15 min de Espera</button></form>
        <form action="/reiniciar" method="POST"><button type="submit" class="btn-light">↺ Reiniciar Simulación</button></form>
    </div>

    <div>
        <div id="banner-alerta" class="alerta-prioridad"></div>

        <div class="kpis">
            <div class="kpi"><small>NODOS EN FRONTERA</small><div>{{ frontera|length }} pacientes</div></div>
            <div class="kpi" style="border-top-color:#ef4444;"><small>SIGUIENTE A EXPANDIR</small><div>{{ frontera[0].nombre if frontera else 'Sala libre' }}</div></div>
            <div class="kpi" style="border-top-color:#f59e0b;"><small>MENOR COSTO h(n)</small><div>{{ frontera[0].h_score ~ ' pts' if frontera else '--' }}</div></div>
            <div class="kpi" style="border-top-color:#10b981;"><small>NODOS EXPANDIDOS</small><div>{{ atendidos|length }} atendidos</div></div>
        </div>

        <div class="card">
            <h3 style="margin-top:0; font-size:0.95rem;">Frontera de Búsqueda Activa (Haz clic en un paciente para inspeccionar)</h3>
            <table>
                <thead>
                    <tr><th>Turno</th><th>h(n)</th><th>Paciente</th><th>Edad</th><th>Síntoma Principal</th><th>SpO₂ / FC</th><th>Espera</th><th>Clasificación</th></tr>
                </thead>
                <tbody>
                    {% for n in frontera %}
                    <tr class="fila-paciente {% if n.h_score <= 25 %}critico{% elif n.h_score <= 50 %}urgente{% endif %}"
                        onclick="seleccionarPaciente({{ loop.index }}, '{{ n.nombre }}', '{{ n.h_score }}', '{{ n.desglose }}', '{{ frontera[0].nombre }}', '{{ frontera[0].h_score }}')">
                        <td><strong>#{{ loop.index }}</strong></td>
                        <td><strong>{{ "%.1f"|format(n.h_score) }}</strong></td>
                        <td>{{ n.nombre }}</td>
                        <td>{{ n.edad }}a</td>
                        <td>{{ n.sintoma }}</td>
                        <td>{{ n.spo2 }}% / {{ n.fc }}</td>
                        <td>{{ n.min_espera }}m</td>
                        <td>{{ n.nivel_txt }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            {% if atendidos %}
            <h3 style="margin-top:20px; font-size:0.95rem;">Historial de Nodos Expandidos (Atendidos)</h3>
            <table>
                <thead><tr><th>Orden</th><th>h(n) Final</th><th>Paciente</th><th>Síntoma</th><th>Área Asignada</th></tr></thead>
                <tbody>
                    {% for a in atendidos %}
                    <tr><td>#{{ loop.index }}</td><td>{{ "%.1f"|format(a.h_score) }} pts</td><td>{{ a.nombre }}</td><td>{{ a.sintoma }}</td><td><strong>{{ a.area_destino }}</strong></td></tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
        </div>

        <div class="inspector" id="texto-inspector">
            🔍 INSPECTOR HEURÍSTICO:
            {% if frontera %}
                Prioridad #1: {{ frontera[0].nombre }} → h(n) = {{ frontera[0].h_score }} ({{ frontera[0].desglose }})
            {% else %}
                Sin pacientes pendientes en la frontera de búsqueda.
            {% endif %}
        </div>

        <div class="log">
            <div style="color:#38bdf8; font-weight:bold; margin-bottom:6px;">BITÁCORA DE EJECUCIÓN — BEST-FIRST SEARCH</div>
            {% for l in logs %}
                <div>&gt; {{ l }}</div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
function seleccionarPaciente(turno, nombre, hScore, desglose, primeroNombre, primeroH) {
    const inspector = document.getElementById("texto-inspector");
    const banner = document.getElementById("banner-alerta");

    inspector.innerHTML = `🔍 INSPECTOR HEURÍSTICO: ${nombre} (Turno #${turno}) → h(n) = ${hScore} pts (${desglose})`;

    if (turno > 1) {
        const mensaje = `⚠️ RESTRICCIÓN DE PRIORIDAD (BEST-FIRST SEARCH):\n\n` +
                        `Seleccionaste a ${nombre} (Turno #${turno}, h(n) = ${hScore} pts).\n` +
                        `No puede ser atendido todavía: primero se deben atender los pacientes que están antes por su mayor prioridad clínica (iniciando con ${primeroNombre}, h(n) = ${primeroH} pts).`;
        banner.style.display = "block";
        banner.innerText = `⚠️ Atención bloqueada para ${nombre} (Turno #${turno}): Primero se deben atender los pacientes que están antes por su prioridad heurística (Turno #1: ${primeroNombre} con h(n) = ${primeroH} pts).`;
        alert(mensaje);
    } else {
        banner.style.display = "none";
    }
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    frontera_ordenada = sorted(motor.frontera)
    return render_template_string(
        HTML_TEMPLATE,
        frontera=frontera_ordenada,
        atendidos=motor.atendidos,
        logs=motor.logs,
        sintomas=list(SINTOMAS_DB.keys())
    )

@app.route("/agregar", methods=["POST"])
def agregar():
    motor.agregar_paciente(
        request.form.get("nombre", "Paciente").strip(),
        int(request.form.get("edad", 30)),
        request.form.get("sintoma"),
        int(request.form.get("spo2", 98)),
        int(request.form.get("fc", 80)),
        min_espera=0
    )
    return redirect(url_for("index"))

@app.route("/atender", methods=["POST"])
def atender():
    motor.expandir_siguiente()
    return redirect(url_for("index"))

@app.route("/tiempo", methods=["POST"])
def tiempo():
    motor.avanzar_tiempo(15)
    return redirect(url_for("index"))

@app.route("/reiniciar", methods=["POST"])
def reiniciar():
    global motor
    motor = MotorTriajeBestFirst()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)