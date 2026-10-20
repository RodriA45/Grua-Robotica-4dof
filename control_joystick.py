"""
=============================================================================
CONTROL DE GRÚA ROBÓTICA (4 GDL) CON JOYSTICK USB O TECLADO
=============================================================================
Características principales:
    - Soporte plug-and-play para cualquier joystick USB (PlayStation o genérico).
    - Detección automática en caliente (conectar/desconectar joystick en vivo).
    - Si NO hay joystick conectado: MODO TECLADO ACTIVO con interfaz visual interactiva.
    - Reconexión automática con el Arduino UNO (sin congelar la ventana).
    - Control incremental suave: al soltar la palanca o tecla, la grúa se queda fija.
    - Zona muerta (Deadzone) del 20% para anular drift en palancas desgastadas.
    - Modo Simulación si el Arduino no está enchufado (ideal para que el profesor pruebe en casa).
=============================================================================
"""

import os
import sys
import time
import serial
import serial.tools.list_ports
import pygame


def resource_path(relative_path):
    """Obtiene la ruta absoluta a recursos, compatible con PyInstaller y entorno dev."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==========================================
# CONFIGURACIÓN GENERAL Y LÍMITES DE SEGURIDAD
# ==========================================
BAUD_RATE = 9600
DEADZONE = 0.20        # Filtra palancas con holgura o drift (20%)
SEND_INTERVAL = 0.04   # Envía datos al Arduino cada 40 ms (25 veces por segundo)
REINTENTO_SERIAL = 2.0 # Segundos entre reintentos para detectar Arduino enchufado

# Límites angulares para cada servo (en grados)
LIMITES = {
    "base":   {"min": 0.0,  "max": 180.0, "inicial": 90.0, "vel": 50.0},
    "hombro": {"min": 20.0, "max": 160.0, "inicial": 90.0, "vel": 45.0},
    "codo":   {"min": 20.0, "max": 160.0, "inicial": 90.0, "vel": 45.0},
    "pinza":  {"min": 15.0, "max": 115.0, "inicial": 90.0, "vel": 70.0},
}

# Inversión de ejes según el montaje mecánico
INVERTIR = {
    "base":   False,
    "hombro": True,
    "codo":   False,
    "pinza":  False,
}


def buscar_puerto_arduino():
    """Busca automáticamente un Arduino o conversor USB-Serial."""
    puertos = list(serial.tools.list_ports.comports())
    if not puertos:
        return None

    for p in puertos:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(k in desc or k in mfg for k in ["arduino", "ch340", "ch341", "cp210", "ftdi", "usb serial"]):
            return p.device

    return puertos[0].device


class ControladorGrua:
    def __init__(self):
        self.angles = {
            "base":   LIMITES["base"]["inicial"],
            "hombro": LIMITES["hombro"]["inicial"],
            "codo":   LIMITES["codo"]["inicial"],
            "pinza":  LIMITES["pinza"]["inicial"],
        }
        self.modo_rapido = False
        self.arduino = None
        self.port_name = None
        self.ultimo_intento_conexion = 0.0
        self.intentar_conexion()

    def intentar_conexion(self):
        """Intenta conectarse al Arduino de forma no bloqueante."""
        ahora = time.time()
        if ahora - self.ultimo_intento_conexion < REINTENTO_SERIAL:
            return
        self.ultimo_intento_conexion = ahora

        puerto = buscar_puerto_arduino()
        if puerto:
            try:
                self.arduino = serial.Serial(puerto, BAUD_RATE, timeout=0.05)
                self.port_name = puerto
                time.sleep(1.5)  # Esperar reinicio de Arduino al abrir Serial
                print(f"[OK] Conectado a Arduino en {puerto}")
            except Exception:
                self.arduino = None
                self.port_name = None
        else:
            self.arduino = None
            self.port_name = None

    def home(self):
        """Vuelve todos los servos a la posición neutral."""
        for k in self.angles:
            self.angles[k] = LIMITES[k]["inicial"]
        self.enviar_a_arduino()

    def aplicar_movimiento(self, d_base, d_hombro, d_codo, d_pinza, dt):
        """Actualiza incrementalmente los ángulos con velocidad suave."""
        mult = 1.7 if self.modo_rapido else 1.0

        deltas = {
            "base":   d_base   * (-1.0 if INVERTIR["base"] else 1.0),
            "hombro": d_hombro * (-1.0 if INVERTIR["hombro"] else 1.0),
            "codo":   d_codo   * (-1.0 if INVERTIR["codo"] else 1.0),
            "pinza":  d_pinza  * (-1.0 if INVERTIR["pinza"] else 1.0),
        }

        for servo, val in deltas.items():
            if abs(val) > 0.001:
                paso = val * LIMITES[servo]["vel"] * mult * dt
                nuevo = self.angles[servo] + paso
                self.angles[servo] = max(LIMITES[servo]["min"], min(LIMITES[servo]["max"], nuevo))

    def enviar_a_arduino(self):
        """Envía el comando serie en formato <B,H,C,P>."""
        if not self.arduino or not self.arduino.is_open:
            return

        b = int(round(self.angles["base"]))
        h = int(round(self.angles["hombro"]))
        c = int(round(self.angles["codo"]))
        p = int(round(self.angles["pinza"]))

        linea = f"<{b},{h},{c},{p}>\n"
        try:
            self.arduino.write(linea.encode('ascii'))
        except Exception:
            self.arduino = None
            self.port_name = None


def procesar_eje(valor):
    """Aplica zona muerta para evitar drift de palancas desgastadas."""
    if abs(valor) < DEADZONE:
        return 0.0
    signo = 1.0 if valor > 0 else -1.0
    escalado = (abs(valor) - DEADZONE) / (1.0 - DEADZONE)
    return signo * escalado


# ==========================================
# INTERFAZ GRÁFICA Y BUCLE PRINCIPAL
# ==========================================
def main():
    # Asignar App ID explícito a Windows para que la barra de tareas muestre nuestro icono
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("grua.robotica.controlador.1.0")
    except Exception:
        pass

    pygame.init()
    pygame.joystick.init()

    # IMPORTANTE: En Pygame para Windows, set_icon DEBE llamarse ANTES de set_mode
    icono_path = resource_path(os.path.join("assets", "icono.png"))
    if os.path.exists(icono_path):
        try:
            icono_surf = pygame.image.load(icono_path)
            pygame.display.set_icon(icono_surf)
        except Exception:
            pass

    ANCHO, ALTO = 940, 660
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Panel de Control - Grúa Robótica (4 GDL)")


    reloj = pygame.time.Clock()
    fuente_titulo = pygame.font.SysFont("Segoe UI, Arial", 23, bold=True)
    fuente_sub = pygame.font.SysFont("Segoe UI, Arial", 15)
    fuente_mono = pygame.font.SysFont("Consolas, Courier", 14)
    fuente_bold = pygame.font.SysFont("Segoe UI, Arial", 14, bold=True)
    fuente_tecla = pygame.font.SysFont("Consolas, Arial", 13, bold=True)

    controlador = ControladorGrua()

    # Detectar joystick inicial
    joystick = None
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        print(f"[JOYSTICK] Detectado: {joystick.get_name()}")

    ultimo_envio = time.time()
    ejecutando = True

    # Paleta de colores
    COLOR_BG       = (18, 22, 31)
    COLOR_PANEL    = (27, 34, 48)
    COLOR_ACCENT   = (38, 132, 255)
    COLOR_ORANGE   = (255, 138, 43)
    COLOR_GREEN    = (46, 204, 113)
    COLOR_TEXT     = (240, 243, 246)
    COLOR_MUTED    = (130, 145, 165)
    COLOR_WARN     = (241, 196, 15)
    COLOR_KEY_OFF  = (40, 48, 66)
    COLOR_KEY_ON   = (38, 180, 100)

    while ejecutando:
        dt = reloj.tick(60) / 1000.0  # Delta time en segundos

        # Reintento de conexión automática si Arduino no está conectado
        if not controlador.arduino:
            controlador.intentar_conexion()

        # 1. Eventos
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                ejecutando = False

            elif evento.type == pygame.JOYDEVICEADDED:
                if joystick is None:
                    joystick = pygame.joystick.Joystick(evento.device_index)
                    joystick.init()
                    print(f"[JOYSTICK CONECTADO] {joystick.get_name()}")

            elif evento.type == pygame.JOYDEVICEREMOVED:
                if joystick is not None and evento.instance_id == joystick.get_instance_id():
                    print("[JOYSTICK DESCONECTADO]")
                    joystick = None

            elif evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ejecutando = False
                elif evento.key == pygame.K_h:
                    controlador.home()
                elif evento.key == pygame.K_v:
                    controlador.modo_rapido = not controlador.modo_rapido

        # 2. Lectura de Joystick
        d_base = 0.0
        d_hombro = 0.0
        d_codo = 0.0
        d_pinza = 0.0

        stick_izq = [0.0, 0.0]
        stick_der = [0.0, 0.0]
        botones_presionados = []

        if joystick:
            num_axes = joystick.get_numaxes()
            if num_axes > 0:
                raw_x = joystick.get_axis(0)
                stick_izq[0] = raw_x
                d_base = procesar_eje(raw_x)

            if num_axes > 1:
                raw_y = joystick.get_axis(1)
                stick_izq[1] = raw_y
                d_hombro = -procesar_eje(raw_y)

            if num_axes >= 3:
                eje_codo_idx = 3 if num_axes >= 4 else 2
                raw_codo = joystick.get_axis(eje_codo_idx)
                stick_der[1] = raw_codo
                d_codo = -procesar_eje(raw_codo)

                eje_der_x = 2 if eje_codo_idx == 3 else 4
                if num_axes > eje_der_x:
                    stick_der[0] = joystick.get_axis(eje_der_x)

            num_botones = joystick.get_numbuttons()
            for b in range(num_botones):
                if joystick.get_button(b):
                    botones_presionados.append(b)

            # Botones de Pinza y Home
            if 0 in botones_presionados or 4 in botones_presionados:
                d_pinza = -1.0  # Cerrar
            elif 1 in botones_presionados or 5 in botones_presionados:
                d_pinza = 1.0   # Abrir

            if 3 in botones_presionados:  # Triángulo
                controlador.home()

            if joystick.get_numhats() > 0:
                hat = joystick.get_hat(0)
                if hat[0] != 0:
                    d_base += float(hat[0]) * 0.7
                if hat[1] != 0:
                    d_codo += float(hat[1]) * 0.7

        # 3. Lectura de Teclado (Funciona siempre, haya o no joystick)
        teclas = pygame.key.get_pressed()
        tecla_activa = {}

        # Base (Giro)
        if teclas[pygame.K_LEFT] or teclas[pygame.K_a]:
            d_base = -1.0
            tecla_activa["base_izq"] = True
        if teclas[pygame.K_RIGHT] or teclas[pygame.K_d]:
            d_base = 1.0
            tecla_activa["base_der"] = True

        # Hombro (Subir / Bajar)
        if teclas[pygame.K_UP] or teclas[pygame.K_w]:
            d_hombro = 1.0
            tecla_activa["hombro_arr"] = True
        if teclas[pygame.K_DOWN] or teclas[pygame.K_s]:
            d_hombro = -1.0
            tecla_activa["hombro_abj"] = True

        # Codo (Extender / Recoger)
        if teclas[pygame.K_q] or teclas[pygame.K_PAGEUP] or teclas[pygame.K_i]:
            d_codo = 1.0
            tecla_activa["codo_ext"] = True
        if teclas[pygame.K_e] or teclas[pygame.K_PAGEDOWN] or teclas[pygame.K_k]:
            d_codo = -1.0
            tecla_activa["codo_rec"] = True

        # Pinza (Abrir / Cerrar)
        if teclas[pygame.K_SPACE] or teclas[pygame.K_o]:
            d_pinza = 1.0
            tecla_activa["pinza_abr"] = True
        if teclas[pygame.K_RETURN] or teclas[pygame.K_c] or teclas[pygame.K_p]:
            d_pinza = -1.0
            tecla_activa["pinza_cer"] = True

        if teclas[pygame.K_h]:
            tecla_activa["home"] = True

        # 4. Actualizar posiciones de la grúa
        controlador.aplicar_movimiento(d_base, d_hombro, d_codo, d_pinza, dt)

        # 5. Enviar periódicamente a Arduino
        ahora = time.time()
        if ahora - ultimo_envio >= SEND_INTERVAL:
            ultimo_envio = ahora
            controlador.enviar_a_arduino()

        # ==========================================
        # RENDERIZADO VISUAL
        # ==========================================
        pantalla.fill(COLOR_BG)

        # Header superior
        pygame.draw.rect(pantalla, COLOR_PANEL, (0, 0, ANCHO, 80))
        txt_titulo = fuente_titulo.render("Grúa Robótica (4 GDL) - Panel de Control", True, COLOR_TEXT)
        pantalla.blit(txt_titulo, (25, 14))

        # Estado del Arduino
        if controlador.arduino and controlador.arduino.is_open:
            txt_estado = fuente_sub.render(f"● ARDUINO CONECTADO [{controlador.port_name}]", True, COLOR_GREEN)
        else:
            txt_estado = fuente_sub.render("▲ MODO SIMULACIÓN (Arduino desconectado - Reconectando automáticamente...)", True, COLOR_WARN)
        pantalla.blit(txt_estado, (25, 48))

        # Indicador de modo / velocidad
        modo_txt = "MODO: RÁPIDO [V]" if controlador.modo_rapido else "MODO: PRECISIÓN [V]"
        txt_modo = fuente_mono.render(modo_txt, True, COLOR_ORANGE if controlador.modo_rapido else COLOR_MUTED)
        pantalla.blit(txt_modo, (ANCHO - txt_modo.get_width() - 25, 48))

        # ------------------------------------------
        # PANEL IZQUIERDO: BARRAS DE LOS 4 SERVOS
        # ------------------------------------------
        pygame.draw.rect(pantalla, COLOR_PANEL, (25, 100, 480, 535), border_radius=10)
        lbl_servos = fuente_titulo.render("Ángulos de Servomotores", True, COLOR_TEXT)
        pantalla.blit(lbl_servos, (45, 115))

        servos_info = [
            ("Base (Giro Horizontal)", "base",   "Pin 9",  (52, 152, 219)),
            ("Hombro (Brazo Inferior)", "hombro", "Pin 10", (46, 204, 113)),
            ("Codo (Brazo Superior)",   "codo",   "Pin 11", (241, 196, 15)),
            ("Pinza (Apertura)",        "pinza",  "Pin 6",  (231, 76, 60)),
        ]

        y_offset = 165
        for nombre, clave, pin, color_barra in servos_info:
            val_actual = controlador.angles[clave]
            lim_min = LIMITES[clave]["min"]
            lim_max = LIMITES[clave]["max"]
            porcentaje = (val_actual - lim_min) / (lim_max - lim_min)

            txt_n = fuente_bold.render(f"{nombre} - {pin}", True, COLOR_TEXT)
            txt_deg = fuente_mono.render(f"{val_actual:5.1f}° [{int(lim_min)}°-{int(lim_max)}°]", True, COLOR_MUTED)
            pantalla.blit(txt_n, (45, y_offset))
            pantalla.blit(txt_deg, (480 - txt_deg.get_width(), y_offset))

            bar_x, bar_y, bar_w, bar_h = 45, y_offset + 25, 440, 26
            pygame.draw.rect(pantalla, (40, 48, 66), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
            ancho_activo = max(10, int(bar_w * porcentaje))
            pygame.draw.rect(pantalla, color_barra, (bar_x, bar_y, ancho_activo, bar_h), border_radius=6)

            cx = bar_x + int(bar_w * ((90.0 - lim_min) / (lim_max - lim_min)))
            pygame.draw.line(pantalla, (255, 255, 255), (cx, bar_y - 2), (cx, bar_y + bar_h + 2), 2)

            y_offset += 86

        # Botón / Instrucción Home
        btn_home_txt = fuente_mono.render("[H] Centrar Posición (Home 90°)", True, COLOR_ORANGE)
        pantalla.blit(btn_home_txt, (45, 595))

        # ------------------------------------------
        # PANEL DERECHO: JOYSTICK O TECLADO
        # ------------------------------------------
        pygame.draw.rect(pantalla, COLOR_PANEL, (530, 100, 385, 535), border_radius=10)

        def dibujar_tecla(x, y, w, h, etiqueta, activa):
            color = COLOR_KEY_ON if activa else COLOR_KEY_OFF
            borde = COLOR_GREEN if activa else (60, 72, 95)
            pygame.draw.rect(pantalla, color, (x, y, w, h), border_radius=6)
            pygame.draw.rect(pantalla, borde, (x, y, w, h), width=2, border_radius=6)
            txt = fuente_tecla.render(etiqueta, True, (255, 255, 255) if activa else COLOR_TEXT)
            pantalla.blit(txt, (x + (w - txt.get_width()) // 2, y + (h - txt.get_height()) // 2))

        if joystick is not None:
            # === CASO A: JOYSTICK CONECTADO ===
            lbl_joy = fuente_titulo.render("Joystick Conectado", True, COLOR_GREEN)
            pantalla.blit(lbl_joy, (550, 115))
            txt_njoy = fuente_sub.render(joystick.get_name(), True, COLOR_ACCENT)
            pantalla.blit(txt_njoy, (550, 142))

            # Dibujar palancas analógicas
            def dibujar_stick(cx, cy, valor_x, valor_y, etiqueta_x, etiqueta_y):
                radio_base = 45
                pygame.draw.circle(pantalla, (40, 48, 66), (cx, cy), radio_base)
                pygame.draw.circle(pantalla, COLOR_MUTED, (cx, cy), radio_base, 1)
                pygame.draw.circle(pantalla, (55, 65, 85), (cx, cy), int(radio_base * DEADZONE), 1)

                pos_x = cx + int(valor_x * radio_base)
                pos_y = cy + int(valor_y * radio_base)
                pygame.draw.line(pantalla, COLOR_MUTED, (cx, cy), (pos_x, pos_y), 2)
                pygame.draw.circle(pantalla, COLOR_ACCENT, (pos_x, pos_y), 11)

                lbl1 = fuente_mono.render(etiqueta_x, True, COLOR_MUTED)
                lbl2 = fuente_mono.render(etiqueta_y, True, COLOR_MUTED)
                pantalla.blit(lbl1, (cx - lbl1.get_width() // 2, cy + radio_base + 8))
                pantalla.blit(lbl2, (cx - lbl2.get_width() // 2, cy + radio_base + 24))

            dibujar_stick(630, 235, stick_izq[0], stick_izq[1], "Stick Izq (Base)", "Arriba/Abj (Hombro)")
            dibujar_stick(810, 235, stick_der[0], stick_der[1], "Stick Der (Codo)", "Arriba/Abj")

            lbl_btn = fuente_bold.render("Botones presionados:", True, COLOR_TEXT)
            pantalla.blit(lbl_btn, (550, 335))
            txt_b = ", ".join(f"B{b}" for b in botones_presionados) if botones_presionados else "Ninguno"
            pantalla.blit(fuente_mono.render(txt_b, True, COLOR_GREEN if botones_presionados else COLOR_MUTED), (550, 360))

            pygame.draw.line(pantalla, (45, 55, 75), (550, 395), (890, 395), 1)
            guia_joy = [
                ("Stick Izq X:", "Girar Base"),
                ("Stick Izq Y:", "Subir / Bajar Hombro"),
                ("Stick Der Y:", "Extender / Recoger Codo"),
                ("Botón X / L1:", "Cerrar Pinza"),
                ("Botón O / R1:", "Abrir Pinza"),
                ("Triángulo / [H]:", "Home (90°)"),
                ("Nota:", "También puedes usar el teclado"),
            ]
            gy = 410
            for c1, c2 in guia_joy:
                pantalla.blit(fuente_bold.render(c1, True, COLOR_ORANGE), (550, gy))
                pantalla.blit(fuente_sub.render(c2, True, COLOR_TEXT), (680, gy))
                gy += 23

        else:
            # === CASO B: SIN JOYSTICK -> MODO TECLADO ACTIVO CON TECLAS INTERACTIVAS ===
            lbl_joy = fuente_titulo.render("Modo Teclado Activo", True, COLOR_WARN)
            pantalla.blit(lbl_joy, (550, 115))
            txt_aviso = fuente_sub.render("Sin joystick detectado. ¡Usa las teclas!", True, COLOR_MUTED)
            pantalla.blit(txt_aviso, (550, 142))

            # Fila 1: Base
            pantalla.blit(fuente_bold.render("1. BASE (Giro):", True, COLOR_TEXT), (550, 185))
            dibujar_tecla(700, 178, 48, 32, "◄ A", tecla_activa.get("base_izq", False))
            dibujar_tecla(755, 178, 48, 32, "D ►", tecla_activa.get("base_der", False))
            dibujar_tecla(810, 178, 48, 32, "◄ / ►", tecla_activa.get("base_izq", False) or tecla_activa.get("base_der", False))

            # Fila 2: Hombro
            pantalla.blit(fuente_bold.render("2. HOMBRO (Subir):", True, COLOR_TEXT), (550, 235))
            dibujar_tecla(720, 228, 60, 32, "▲ / W", tecla_activa.get("hombro_arr", False))
            dibujar_tecla(790, 228, 60, 32, "▼ / S", tecla_activa.get("hombro_abj", False))

            # Fila 3: Codo
            pantalla.blit(fuente_bold.render("3. CODO (Extender):", True, COLOR_TEXT), (550, 285))
            dibujar_tecla(720, 278, 60, 32, "Q / I", tecla_activa.get("codo_ext", False))
            dibujar_tecla(790, 278, 60, 32, "E / K", tecla_activa.get("codo_rec", False))

            # Fila 4: Pinza
            pantalla.blit(fuente_bold.render("4. PINZA (Abrir/Cerrar):", True, COLOR_TEXT), (550, 335))
            dibujar_tecla(550, 365, 160, 34, "ESPACIO (Abrir)", tecla_activa.get("pinza_abr", False))
            dibujar_tecla(720, 365, 160, 34, "ENTER / C (Cerrar)", tecla_activa.get("pinza_cer", False))

            # Fila 5: Funciones adicionales
            pygame.draw.line(pantalla, (45, 55, 75), (550, 420), (890, 420), 1)
            pantalla.blit(fuente_bold.render("Accesos Rápidos:", True, COLOR_ORANGE), (550, 435))
            dibujar_tecla(550, 465, 150, 32, "Tecla [ H ] : Home 90°", tecla_activa.get("home", False))
            dibujar_tecla(715, 465, 165, 32, "Tecla [ V ] : Velocidad", controlador.modo_rapido)

            txt_plug = fuente_sub.render("💡 Si enchufas un joystick USB ahora,", True, COLOR_ACCENT)
            txt_plug2 = fuente_sub.render("el programa lo detecta automáticamente.", True, COLOR_MUTED)
            pantalla.blit(txt_plug, (550, 525))
            pantalla.blit(txt_plug2, (550, 548))

        pygame.display.flip()

    if controlador.arduino and controlador.arduino.is_open:
        controlador.arduino.close()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
