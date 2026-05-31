import sys
import subprocess
import threading

import queue
import json
from datetime import datetime, timedelta

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

import boto3

from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

aws_iot_core_endpoint="a2xyhr7rc9cefs-ats.iot.us-east-1.amazonaws.com"

aws_iot_core_ruta_archivo_certificado="../cert/casita-1.pem.crt"
aws_iot_core_ruta_archivo_llave_privada="../cert/casita-1.private.pem.key"

mqtt_identificador_cliente="randal"
mqtt_nombre_dispositivo="casita-1"

mqtt_tema_datos_telemetria="datos/telemetria"
mqtt_tema_datos_estado_luces="datos/estado-luces"
mqtt_tema_solicitud_estado_luces="solicitud/estado-luces"
mqtt_tema_comando_luces="comando/luces"

codigo_mensaje_datos_telemetria="datos-telemetria"
codigo_mensaje_datos_estado_luces="datos-estado-luces"
codigo_mensaje_solicitud_estado_luces="solicitud-estado-luces"
codigo_mensaje_comando_luces="comando-luces"

nombre_tabla_datos_telemetria = "datos-telemetria"

connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()

mqtt_client_aws_iot_core = None
aws_iot_core_estado_conexion_activa = False
TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE = 5 # Segundos
    
mqtt_client_dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

cola_publicaciones_mqtt = queue.Queue()
evento_terminar_proceso = threading.Event()

clientes_esperando_telemetria = []
clientes_esperando_estado_luces = []

ultimo_estado_luces_recibido = {}
ultima_telemetria_recibida = {}

def conectar_con_aws_iot_core():

    global mqtt_client_aws_iot_core, aws_iot_core_estado_conexion_activa

    # Creation of MQTT5 mqtt_client_aws_iot_core using mutual TLS via X509 Certificate and Private Key
    mqtt_client_aws_iot_core = mqtt5_client_builder.mtls_from_path(
        endpoint=aws_iot_core_endpoint,
        cert_filepath=aws_iot_core_ruta_archivo_certificado,
        pri_key_filepath=aws_iot_core_ruta_archivo_llave_privada,
        on_publish_received=on_publish_received_AWS,
        on_lifecycle_stopped=on_lifecycle_stopped_AWS,
        on_lifecycle_attempting_connect=on_lifecycle_attempting_connect_AWS,
        on_lifecycle_connection_success=on_lifecycle_connection_success_AWS,
        on_lifecycle_connection_failure=on_lifecycle_connection_failure_AWS,
        on_lifecycle_disconnection=on_lifecycle_disconnection_AWS,
        client_id=mqtt_identificador_cliente)
    mqtt_client_aws_iot_core.start()

    if not connection_success_event.wait(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE):
        return "Tiempo de espera agotado en el intento de conexión con AWS."

    try:

        mqtt_tema = mqtt_tema_datos_estado_luces
        subscribe_future = mqtt_client_aws_iot_core.subscribe(
        subscribe_packet=mqtt5.SubscribePacket(
            subscriptions = [
            mqtt5.Subscription(
                topic_filter = mqtt_tema,
                qos = mqtt5.QoS.AT_LEAST_ONCE
            )]
        ))
        suback = subscribe_future.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)

        mqtt_tema = mqtt_tema_datos_telemetria
        subscribe_future = mqtt_client_aws_iot_core.subscribe(
        subscribe_packet=mqtt5.SubscribePacket(
            subscriptions = [
            mqtt5.Subscription(
                topic_filter = mqtt_tema,
                qos = mqtt5.QoS.AT_LEAST_ONCE
            )]
        ))
        suback = subscribe_future.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
    
    except Exception:
        return "Error al suscribirse al tema MQTT: " + mqtt_tema

    aws_iot_core_estado_conexion_activa = True
    return None

def on_publish_received_AWS(publish_packet_data):
    global cola_publicaciones_mqtt
    publish_packet = publish_packet_data.publish_packet
    cola_publicaciones_mqtt.put(publish_packet.payload)

def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    stopped_event.set()
    print("Se ha detenido el ciclo de vida de la conexión con AWS IOT Core.\n")

def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Intento de conexión con AWS IOT Core.")


def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    global aws_iot_core_estado_conexion_activa
    connack_packet = lifecycle_connect_success_data.connack_packet
    connection_success_event.set()
    aws_iot_core_estado_conexion_activa = True
    print("Conexión lograda con AWS IOT Core.")

def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    global aws_iot_core_estado_conexion_activa
    aws_iot_core_estado_conexion_activa = False
    print("Conexión fallida con AWS IOT Core.")

def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    global aws_iot_core_estado_conexion_activa
    aws_iot_core_estado_conexion_activa = False
    print("Conexión perdida con AWS IOT Core.")

@app.route("/")
def index():

    datos_telemetria = obtener_datos_dynamodb_durante_las_ultimas_24_horas(nombre_tabla_datos_telemetria)

    return render_template(
        "index.html",
        datos_telemetria = datos_telemetria
    )

def parsear_comando_cliente_web():

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

    global mqtt_client_aws_iot_core, aws_iot_core_estado_conexion_activa

    if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500

    try:
        payload = request.get_json()
    except Exception:
        print("Error inesperado al leer JSON del cliente.")
        return

    if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError:
        print("Recibido mensaje JSON en mal formato desde el cliente web.")
        return
    except Exception:
        print("Error inesperado al procesar el mensaje de JSON recibido desde el cliente web.")
        return

    if not codigo_mensaje == codigo_mensaje_comando_luces:
        print("Recibido mensaje JSON en mal formato desde el cliente web.")
        return

    if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500

    comando = parsear_comando_cliente_web(cuerpo_mensaje)
    if comando is None:
        print("Recibido mensaje JSON en mal formato desde el cliente web.")
        return

    if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500

    objeto_futuro_publicacion = mqtt_client_aws_iot_core.publish(mqtt5.PublishPacket(
        topic=mqtt_tema_comando_luces,
        payload=json.dumps(payload),
        qos=mqtt5.QoS.AT_LEAST_ONCE
    ))

    for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL):
        if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500
        numero_intento += 1
        try:
            objeto_futuro_publicacion.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
            return "Solicitud enviada al Master correctamente", 200
        except concurrent.futures.TimeoutError:
            print("Intento fallido número " + str(numero_intento) + " al conectar con AWS IOT Core.")
            if numero_intento == CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL:
                print("Se agotó el tiempo de espera al publicar en AWS IOT Core.")
                return
            continue
        except Exception:
            print("Error inesperado al conectar con AWS IOT Core.")
            return

def obtener_datos_dynamodb_durante_las_ultimas_24_horas(nombre_tabla):

    global mqtt_client_dynamodb
    
    ahora = datetime.now()
    hace_24_horas = ahora - timedelta(hours=24)

    end_ts = int(ahora.timestamp())
    start_ts = int(hace_24_horas.timestamp())

    response = mqtt_client_dynamodb.scan(
        TableName=nombre_tabla,
        FilterExpression="#ts BETWEEN :start AND :end",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={
            ":start": {"N": str(start_ts)},
            ":end": {"N": str(end_ts)}
        }
    )
    
    return response.get("Items", [])

@app.route("/solicitar-estado-luces")
def solicitar_estado_luces():
    global clientes_esperando_estado_luces

    if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500

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

    if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500

    objeto_futuro_publicacion = mqtt_client_aws_iot_core.publish(mqtt5.PublishPacket(
        topic=mqtt_tema_solicitud_estado_luces,
        payload=json.dumps(payload),
        qos=mqtt5.QoS.AT_LEAST_ONCE
    ))

    for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL):
        if not aws_iot_core_estado_conexion_activa: return "Error: Cliente IoT no conectado", 500
        numero_intento += 1
        try:
            objeto_futuro_publicacion.result(TIEMPO_ESPERA_CONEXION_AWS_IOT_CORE)
            break
        except concurrent.futures.TimeoutError:
            print("Intento fallido número " + str(numero_intento) + " al conectar con AWS IOT Core.")
            if numero_intento == CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL:
                print("Se agotó el tiempo de espera al publicar en AWS IOT Core.")
                return
            continue
        except Exception:
            print("Error inesperado al conectar con AWS IOT Core.")
            return

    evento = threading.Event()
    with lock:
        clientes_esperando_estado_luces.append(evento)
    senalizado = evento.wait(timeout = 5)
    
    with lock:
        if evento in clientes_esperando_estado_luces:
            clientes_esperando_estado_luces.remove(evento)
            
    if senalizado:
        return json.dumps(ultimo_estado_luces_recibido)
    else:
        return json.dumps(None)

@app.route("/esperar-telemetria")
def esperar_telemetria():
    global clientes_esperando_telemetria

    evento = threading.Event()
    with lock:
        clientes_esperando_telemetria.append(evento)
    senalizado = evento.wait(timeout = 5)
    
    with lock:
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
        print("Error inesperado al procesar el mensaje de UTF-8 recibido desde AWS IOT Core.")
        return

    try:
        payload = json.loads(payload_string)
    except json.JSONDecodeError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return
    except Exception:
        print("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        return

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return
    except Exception:
        print("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
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
        try:
            publicacion_mqtt = cola_publicaciones_mqtt.get(timeout=1)
            if publicacion_mqtt is None:
                cola_publicaciones_mqtt.task_done()
                continue
            procesar_publicacion_mqtt(publicacion_mqtt)
        except queue.Empty:
            pass
        except Exception:
            print("Ha ocurrido un error inesperado en el momento de leer una publicación de MQTT recibida desde AWS IOT Core.")
            pass
        cola_publicaciones_mqtt.task_done()

if __name__ == "__main__":

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
