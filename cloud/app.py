import sys
import subprocess
import threading

import inspect
import os

import queue
from multiprocessing.managers import BaseManager

import queue
import json
from datetime import datetime, timedelta

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

import boto3

from flask import Flask, render_template, request, redirect, url_for, jsonify

CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE = 2
TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE = 5 # Segundos

aws_iot_core_endpoint_address=""

aws_iot_core_ruta_archivo_certificado="../secretos/casita-1.pem.crt"
aws_iot_core_ruta_archivo_llave_privada="../secretos/casita-1.private.pem.key"

mqtt_identificador_cliente="randal-studios"
mqtt_nombre_cosa="randal-casita-1"

mqtt_tema_datos_telemetria="datos/telemetria"
mqtt_tema_datos_estado_luces="datos/estado-luces"
mqtt_tema_solicitud_estado_luces="solicitud/estado-luces"
mqtt_tema_comando_luces="comando/luces"

codigo_mensaje_datos_telemetria="datos-telemetria"
codigo_mensaje_datos_estado_luces="datos-estado-luces"
codigo_mensaje_solicitud_estado_luces="solicitud-estado-luces"
codigo_mensaje_comando_luces="comando-luces"

nombre_tabla_datos_telemetria = "casita-datos-telemetria"

connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()

app = Flask(__name__)

cliente_mqtt = None
cliente_dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

clientes_esperando_telemetria = []
clientes_esperando_estado_luces = []

candado_clientes_esperando_telemetria = threading.Lock()
candado_clientes_esperando_estado_luces = threading.Lock()

ultimo_estado_luces_recibido = {}
ultima_telemetria_recibida = {}

evento_terminar_proceso = threading.Event()

cola_publicaciones_mqtt_salientes = queue.Queue()
cola_publicaciones_mqtt_entrantes = None

class MiManager(BaseManager): pass
MiManager.register("get_salientes", callable=lambda: cola_publicaciones_mqtt_salientes)
MiManager.register("get_entrantes", callable=lambda: cola_publicaciones_mqtt_entrantes)

PUERTO_LOCAL = 50002
PUERTO_REMOTO = 50001

manager_local = MiManager(address=("127.0.0.1", PUERTO_LOCAL), authkey=b"secreto")
manager_local.get_server().serve_forever(poll_interval=1)

def imprimir_error(mensaje):
    caller_frame = inspect.currentframe().f_back
    nombre_archivo = os.path.basename(caller_frame.f_code.co_filename)
    numero_linea = caller_frame.f_lineno
    print(nombre_archivo + "(" + str(numero_linea) + "):")
    print(mensaje)

def crear_cliente_mqtt():

    global cliente_mqtt

    if MODO_SIMULACION_MQTT == True:
        return True

    if MODO_SIMULACION_MQTT == False:
        try:
            cliente_mqtt = mqtt5_client_builder.mtls_from_path(
                endpoint=aws_iot_core_endpoint_address,
                cert_filepath=aws_iot_core_ruta_archivo_certificado,
                pri_key_filepath=aws_iot_core_ruta_archivo_llave_privada,
                on_publish_received=on_publish_received_AWS,
                on_lifecycle_stopped=on_lifecycle_stopped_AWS,
                on_lifecycle_attempting_connect=on_lifecycle_attempting_connect_AWS,
                on_lifecycle_connection_success=on_lifecycle_connection_success_AWS,
                on_lifecycle_connection_failure=on_lifecycle_connection_failure_AWS,
                on_lifecycle_disconnection=on_lifecycle_disconnection_AWS,
                client_id=mqtt_identificador_cliente)
            cliente_mqtt.start()
        except Exception as excepcion:
            imprimir_error("Error al crear cliente MQTT.")
            print(excepcion)
            return False
        return True

def suscribirse_a_tema(mqtt_tema):

    global cliente_mqtt
    global cola_publicaciones_mqtt_entrantes

    if MODO_SIMULACION_MQTT == True:
        if cola_publicaciones_mqtt_entrantes is None:
            try:
                manager_remoto = MiManager(address=("127.0.0.1", PUERTO_REMOTO), authkey=b"secreto")
                manager_remoto.connect()
                cola_publicaciones_mqtt_entrantes = manager_remoto.get_salientes()
                print("Conectado a la cola del vecino en puerto: " + PUERTO_REMOTO)
            except Exception as excepcion:
                imprimir_error("Error conectando a la cola del vecino.")
                print(excepcion)
                return False
        return True

    if MODO_SIMULACION_MQTT == False:
        try:
            subscribe_future = cliente_mqtt.subscribe(
            subscribe_packet=mqtt5.SubscribePacket(
                subscriptions = [
                mqtt5.Subscription(
                    topic_filter = mqtt_tema,
                    qos = mqtt5.QoS.AT_LEAST_ONCE
                )]
            ))
            suback = subscribe_future.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
        except Exception as excepcion:
            imprimir_error("Error al suscribirse al tema MQTT.")
            print(excepcion)
            print("Tema MQTT:")
            print(mqtt_tema)
        return

def publicar_en_tema(mqtt_tema, payload):

    global cliente_mqtt

    if MODO_SIMULACION_MQTT == True:
        cola_publicaciones_mqtt_salientes.put(payload)
        return True

    if MODO_SIMULACION_MQTT == False:

        objeto_futuro_publicacion = cliente_mqtt.publish(mqtt5.PublishPacket(
            topic=mqtt_tema,
            payload=json.dumps(payload),
            qos=mqtt5.QoS.AT_LEAST_ONCE
        ))

        for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE):
            numero_intento += 1
            try:
                objeto_futuro_publicacion.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
                return False
            except concurrent.futures.TimeoutError:
                imprimir_error("Intento fallido número " + str(numero_intento) + " al conectar con AWS IOT Core.")
                if numero_intento == CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE:
                    imprimir_error("Se agotó el tiempo de espera al publicar en AWS IOT Core.")
                    print(excepcion)
                    return False
                print(excepcion)
                continue
            except Exception:
                imprimir_error("Error inesperado al conectar con AWS IOT Core.")
                print(excepcion)
                return False
        return True

def conectar_con_aws_iot_core():

    if crear_cliente_mqtt() == False: return False

    if not connection_success_event.wait(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE):
        imprimir_error("Tiempo de espera agotado en el intento de conexión con AWS.")
        return False

    if suscribirse_a_tema(mqtt_tema_datos_estado_luces) == False: return False
    if suscribirse_a_tema(mqtt_tema_datos_telemetria) == False: return False

    return True

def conectar_con_broker():

    if MODO_SIMULACION_MQTT == True:
        return True

    if MODO_SIMULACION_MQTT == False:
        return conectar_con_aws_iot_core()

def on_publish_received_AWS(publish_packet_data):
    global cola_publicaciones_mqtt
    publish_packet = publish_packet_data.publish_packet
    cola_publicaciones_mqtt.put(publish_packet.payload)

def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    stopped_event.set()
    print("Se ha detenido el ciclo de vida de la conexión con AWS IOT Core.")

def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Intento de conexión con AWS IOT Core.")


def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    connection_success_event.set()
    print("Conexión lograda con AWS IOT Core.")

def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Conexión fallida con AWS IOT Core.")
    print(lifecycle_connection_failure.exception)

def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Conexión perdida con AWS IOT Core.")
    if lifecycle_disconnect_data.disconnect_packet:
        print("Código del motivo de la desconexión: " + lifecycle_disconnect_data.disconnect_packet.reason_code)

def construir_json_respuesta(estatus, codigo, mensaje, datos):
    return jsonify({
        "status": estatus,
        "code": codigo,
        "message": mensaje,
        "data": datos
    })

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/obtener-telemetria-durante-las-ultimas-24-horas", methods=["GET"])
def obtener_telemetria_durante_las_ultimas_24_horas():
    datos_telemetria = obtener_datos_dynamodb_durante_las_ultimas_24_horas(nombre_tabla_datos_telemetria)
    return jsonify(datos_telemetria)

def parsear_comando_cliente_web(cuerpo_mensaje):

    if "luz-roja" in cuerpo_mensaje:

        if "encendida" in cuerpo_mensaje["luz-roja"]:

            if cuerpo_mensaje["luz-roja"]["encendida"] == True:
                comando = "encender luz roja"
                return comando

            if cuerpo_mensaje["luz-roja"]["encendida"] == False:
                comando = "apagar luz roja"
                return comando

        return None

    if "luz-amarilla" in cuerpo_mensaje:

        if "encendida" in cuerpo_mensaje["luz-amarilla"]:

            if cuerpo_mensaje["luz-amarilla"]["encendida"] == True:
                comando = "encender luz amarilla"
                return comando

            if cuerpo_mensaje["luz-amarilla"]["encendida"] == False:
                comando = "apagar luz amarilla"
                return comando

        return None

    if "luz-verde" in cuerpo_mensaje:

        if "encendida" in cuerpo_mensaje["luz-verde"]:

            if cuerpo_mensaje["luz-verde"]["encendida"] == True:
                comando = "encender luz verde"
                return comando

            if cuerpo_mensaje["luz-verde"]["encendida"] == False:
                comando = "apagar luz verde"
                return comando

        return None

    if "luz-puerta" in cuerpo_mensaje:

        if "encendida" in cuerpo_mensaje["luz-puerta"]:

            if cuerpo_mensaje["luz-puerta"]["encendida"] == True:
                comando = "encender luz puerta"
                return comando

            if cuerpo_mensaje["luz-puerta"]["encendida"] == False:
                comando = "apagar luz puerta"
                return comando

        return None

    if "luz-rgb" in cuerpo_mensaje:

        if "encendida" in cuerpo_mensaje["luz-rgb"]:

            if cuerpo_mensaje["luz-rgb"]["encendida"] == True:
                comando = "encender luz rgb"
                return comando

            if cuerpo_mensaje["luz-rgb"]["encendida"] == False:
                comando = "apagar luz rgb"
                return comando

        if "color" in cuerpo_mensaje["luz-rgb"]:
            try:
                int(cuerpo_mensaje["luz-rgb"]["color"], 16)
            except ValueError:
                return None
            comando = "cambiar color luz rgb " + cuerpo_mensaje["luz-rgb"]["color"]
            return comando

        return None

    return None

@app.route("/enviar-comando", methods=["POST"])
def enviar_comando():

    try:
        payload = request.get_json()
    except Exception:
        imprimir_error("Error inesperado al leer JSON del cliente.")
        return construir_json_respuesta("error", 500, "Error inesperado en el lado del servidor.", None)

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError:
        print("Recibido mensaje JSON en mal formato desde el cliente web.")
        return construir_json_respuesta("error", 500, "Comando con mal formato.", None)
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde el cliente web.")
        return construir_json_respuesta("error", 500, "Error inesperado en el lado del servidor.", None)

    if not codigo_mensaje == codigo_mensaje_comando_luces:
        print("Recibido mensaje JSON en mal formato desde el cliente web.")
        return construir_json_respuesta("error", 500, "Comando con mal formato.", None)

    comando = parsear_comando_cliente_web(cuerpo_mensaje)
    if comando is None:
        print("Recibido mensaje JSON en mal formato desde el cliente web.")
        return construir_json_respuesta("error", 500, "Comando con mal formato.", None)

    objeto_futuro_publicacion = cliente_mqtt.publish(mqtt5.PublishPacket(
        topic=mqtt_tema_comando_luces,
        payload=json.dumps(payload),
        qos=mqtt5.QoS.AT_LEAST_ONCE
    ))

    for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE):
        numero_intento += 1
        try:
            objeto_futuro_publicacion.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
            return construir_json_respuesta("success", 200, "Comando enviado a la casita.", None)
        except concurrent.futures.TimeoutError:
            print("Intento fallido número " + str(numero_intento) + " al conectar con AWS IOT Core.")
            if numero_intento == CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE:
                return construir_json_respuesta("error", 500, "No hay conexión con la casita.", None)
            continue
        except Exception:
            imprimir_error("Error inesperado al conectar con AWS IOT Core.")
            return construir_json_respuesta("error", 500, "No hay conexión con la casita.", None)

def obtener_datos_dynamodb_durante_las_ultimas_24_horas(nombre_tabla):
    global cliente_dynamodb
    
    ahora = datetime.now()
    hace_24_horas = ahora - timedelta(hours=24)

    end_ts = int(ahora.timestamp())
    start_ts = int(hace_24_horas.timestamp())

    response = cliente_dynamodb.Table(nombre_tabla).scan(
        FilterExpression="#ts BETWEEN :start AND :end",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={
            ":start": start_ts,
            ":end": end_ts
        }
    )
    
    return response.get("Items", [])

@app.route("/solicitar-estado-luces")
def solicitar_estado_luces():
    global clientes_esperando_estado_luces, candado_clientes_esperando_estado_luces

    payload = {
        "cabeza-mensaje": {
            "codigo-mensaje": "solicitud-estado-luces"
        },
        "cuerpo-mensaje": {
            "luz-roja": True,
            "luz-amarilla": True,
            "luz-verde": True,
            "luz-puerta": True,
            "luz-rgb": True
        }
    }

    objeto_futuro_publicacion = cliente_mqtt.publish(mqtt5.PublishPacket(
        topic=mqtt_tema_solicitud_estado_luces,
        payload=json.dumps(payload),
        qos=mqtt5.QoS.AT_LEAST_ONCE
    ))

    for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE):
        numero_intento += 1
        try:
            objeto_futuro_publicacion.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
            break
        except concurrent.futures.TimeoutError:
            print("Intento fallido número " + str(numero_intento) + " al conectar con AWS IOT Core.")
            if numero_intento == CANTIDAD_INTENTOS_CONEXION_AWS_IOT_CORE:
                print("Se agotó el tiempo de espera al publicar en AWS IOT Core.")
                return construir_json_respuesta("error", 500, "No hay conexión con la casita.", None)
            continue
        except Exception:
            imprimir_error("Error inesperado al conectar con AWS IOT Core.")
            return construir_json_respuesta("error", 500, "No hay conexión con la casita.", None)

    evento = threading.Event()
    with candado_clientes_esperando_estado_luces:
        clientes_esperando_estado_luces.append(evento)
    senalizado = evento.wait(timeout = 5)
    
    with candado_clientes_esperando_estado_luces:
        if evento in clientes_esperando_estado_luces:
            clientes_esperando_estado_luces.remove(evento)
            
    if senalizado:
        return construir_json_respuesta("success", 200, "Se ha procesado la solicitud.", ultimo_estado_luces_recibido)
    else:
        return construir_json_respuesta("success", 200, "Se ha procesado la solicitud.", None)

@app.route("/esperar-telemetria", methods=["GET"])
def esperar_telemetria():
    global clientes_esperando_telemetria, candado_clientes_esperando_telemetria

    evento = threading.Event()
    with candado_clientes_esperando_telemetria:
        clientes_esperando_telemetria.append(evento)
    senalizado = evento.wait(timeout = 5)
    
    with candado_clientes_esperando_telemetria:
        if evento in clientes_esperando_telemetria:
            clientes_esperando_telemetria.remove(evento)
            
    if senalizado:
        return json.dumps(ultima_telemetria_recibida)
    else:
        return json.dumps(None)

def procesar_publicacion_mqtt(publicacion_mqtt):

    try:
        payload_string = publicacion_mqtt.decode("utf-8")
    except json.JSONDecodeError:
        print("Recibido mensaje UTF-8 en mal formato desde AWS IOT Core.")
        return
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de UTF-8 recibido desde AWS IOT Core.")
        return

    try:
        payload = json.loads(payload_string)
    except json.JSONDecodeError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        return

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        return

    if codigo_mensaje == codigo_mensaje_datos_estado_luces:
        ultimo_estado_luces_recibido = cuerpo_mensaje
        for evento in clientes_esperando_estado_luces:
            evento.set()
        clientes_esperando_estado_luces.clear()
        return

    if codigo_mensaje == codigo_mensaje_datos_telemetria:
        ultima_telemetria_recibida = cuerpo_mensaje
        for evento in clientes_esperando_telemetria:
            evento.set()
        clientes_esperando_telemetria.clear()
        return

def manejar_eventos_cola_publicaciones_mqtt():
    global cola_publicaciones_mqtt
    while not evento_terminar_proceso.is_set():
        publicacion_mqtt = None
        try:
            publicacion_mqtt = cola_publicaciones_mqtt.get(timeout=1)
        except queue.Empty:
            continue
        except Exception:
            print("Ha ocurrido un error inesperado en el momento de leer una publicación de MQTT recibida desde AWS IOT Core.")
            continue
        if publicacion_mqtt is not None:
            procesar_publicacion_mqtt(publicacion_mqtt)
        cola_publicaciones_mqtt.task_done()

if __name__ == "__main__":

    with open("../secretos/aws-endpoint-address.txt", 'r') as archivo:
        aws_iot_core_endpoint_address = archivo.readline()

    mensaje_error_conexion_aws_iot_core = conectar_con_aws_iot_core()
    if mensaje_error_conexion_aws_iot_core is not None:
        print(mensaje_error_conexion_aws_iot_core)
        sys.exit(1)

    threading.Thread(
        target=manejar_eventos_cola_publicaciones_mqtt,
        daemon=True
    ).start()

    app.run(host="0.0.0.0", port=5001)

    evento_terminar_proceso.set()
    cola_publicaciones_mqtt.put(None)
