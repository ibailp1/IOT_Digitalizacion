import sys
import subprocess
import threading

import inspect
import os

import queue
from multiprocessing.managers import SyncManager

import time
import json
from datetime import datetime, timedelta

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

import boto3

from flask import Flask, render_template, request, redirect, url_for, jsonify

MODO_SIMULACION_MQTT = True

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

cola_publicaciones_mqtt_entrantes = queue.Queue()
cola_publicaciones_mqtt_salientes = None

class MiManager(SyncManager): pass
MiManager.register("cola_publicaciones_mqtt_entrantes_del_cloud", callable=lambda: cola_publicaciones_mqtt_entrantes)
MiManager.register("cola_publicaciones_mqtt_entrantes_del_master")

PUERTO_LOCAL = 50002
PUERTO_REMOTO = 50001

manager_local = MiManager(address=("127.0.0.1", PUERTO_LOCAL), authkey=b"secreto")
def iniciar_servidor():
    server = manager_local.get_server()
    server.serve_forever()
threading.Thread(target=iniciar_servidor, daemon=True).start()

def imprimir_error(mensaje):
    caller_frame = inspect.currentframe().f_back
    nombre_archivo = os.path.basename(caller_frame.f_code.co_filename)
    numero_linea = caller_frame.f_lineno
    print(nombre_archivo + "(" + str(numero_linea) + "):")
    print(mensaje)

def limpieza_y_salida(codigo_de_salida):
    evento_terminar_proceso.set()
    poner_publicacion_mqtt_saliente_en_cola(None)
    sys.exit(codigo_de_salida)

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

def conectar_con_broker_simulado():
    global cola_publicaciones_mqtt_salientes
    cola_publicaciones_mqtt_salientes = None
    while cola_publicaciones_mqtt_salientes is None:
        try:
            manager_remoto = MiManager(address=("127.0.0.1", PUERTO_REMOTO), authkey=b"secreto")
            manager_remoto.connect()
            cola_publicaciones_mqtt_salientes = manager_remoto.cola_publicaciones_mqtt_entrantes_del_master()
            print("Conectado a la cola del vecino en puerto: " + str(PUERTO_REMOTO))
        except Exception as excepcion:
            imprimir_error("Error conectando a la cola del vecino.")
            print(excepcion)
        time.sleep(1)
    return True

def suscribirse_a_tema(mqtt_tema):

    global cliente_mqtt

    if MODO_SIMULACION_MQTT == True:
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

def poner_publicacion_mqtt_saliente_en_cola(payload):
    while True:
        try:
            cola_publicaciones_mqtt_salientes.put(payload)
            break
        except Exception as exception:
            print("Conexión perdida. Intentando reconectar...")
            print(exception)
            conectar_con_broker_simulado()
            time.sleep(1)
    print("Publicación saliente MQTT.")
    print(json.dumps(json.loads(payload.decode("utf-8")), indent=4))

def publicar_en_tema(mqtt_tema, payload):

    global cliente_mqtt

    if MODO_SIMULACION_MQTT == True:
        poner_publicacion_mqtt_saliente_en_cola(json.dumps(payload).encode("utf-8"))
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
        return conectar_con_broker_simulado()

    if MODO_SIMULACION_MQTT == False:
        return conectar_con_aws_iot_core()

def on_publish_received_AWS(publish_packet_data):
    global cola_publicaciones_mqtt_entrantes
    publish_packet = publish_packet_data.publish_packet
    cola_publicaciones_mqtt_entrantes.put(publish_packet.payload)

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
        imprimir_error("Recibido mensaje JSON en mal formato desde el cliente web.")
        return construir_json_respuesta("error", 500, "Comando con mal formato.", None)
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde el cliente web.")
        return construir_json_respuesta("error", 500, "Error inesperado en el lado del servidor.", None)

    if not codigo_mensaje == codigo_mensaje_comando_luces:
        imprimir_error("Recibido mensaje JSON en mal formato desde el cliente web.")
        return construir_json_respuesta("error", 500, "Comando con mal formato.", None)

    if publicar_en_tema(mqtt_tema_comando_luces, payload) == True:
        return construir_json_respuesta("success", 200, "Comando enviado.", None)
    else:
        return construir_json_respuesta("error", 500, "Error inesperado al enviar el comando.", None)

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

    publicar_en_tema(mqtt_tema_solicitud_estado_luces, payload)

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
    except json.JSONDecodeError as excepcion:
        imprimir_error("Recibido mensaje UTF-8 en mal formato desde AWS IOT Core.")
        print(excepcion)
        return False
    except Exception as excepcion:
        imprimir_error("Error inesperado al procesar el mensaje de UTF-8 recibido desde AWS IOT Core.")
        print(excepcion)
        return False

    try:
        payload = json.loads(payload_string)
    except json.JSONDecodeError as excepcion:
        imprimir_error("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        print(excepcion)
        return False
    except Exception as excepcion:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        print(excepcion)
        return False

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError as excepcion:
        imprimir_error("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        print(excepcion)
        return False
    except Exception as excepcion:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        print(excepcion)
        return False

    if codigo_mensaje == codigo_mensaje_datos_estado_luces:
        ultimo_estado_luces_recibido = cuerpo_mensaje
        for evento in clientes_esperando_estado_luces:
            evento.set()
        clientes_esperando_estado_luces.clear()
        return True

    if codigo_mensaje == codigo_mensaje_datos_telemetria:
        ultima_telemetria_recibida = cuerpo_mensaje
        for evento in clientes_esperando_telemetria:
            evento.set()
        clientes_esperando_telemetria.clear()
        return True

def manejar_eventos_cola_publicaciones_mqtt_entrantes():
    global cola_publicaciones_mqtt_entrantes
    while not evento_terminar_proceso.is_set():
        publicacion_mqtt = None
        try:
            publicacion_mqtt = cola_publicaciones_mqtt_entrantes.get(timeout=1)
        except queue.Empty:
            continue
        except Exception as excepcion:
            imprimir_error("Ha ocurrido un error inesperado en el momento de leer una publicación de MQTT recibida desde AWS IOT Core.")
            print(excepcion)
            continue
        if publicacion_mqtt is not None:
            procesar_publicacion_mqtt(publicacion_mqtt)
        cola_publicaciones_mqtt_entrantes.task_done()

if __name__ == "__main__":

    try:
        with open("../secretos/aws-endpoint-address.txt", 'r') as archivo:
            aws_iot_core_endpoint_address = archivo.readline()
    except Exception as excepcion:
        print("Error al leer el archivo.")
        printU(excepcion)
        limpieza_y_salida(1)

    if conectar_con_broker() == False:
        limpieza_y_salida(1)

    threading.Thread(
        target=manejar_eventos_cola_publicaciones_mqtt_entrantes,
        daemon=True
    ).start()

    app.run(host="0.0.0.0", port=5001)

    evento_terminar_proceso.set()
    cola_publicaciones_mqtt_entrantes.put(None)
