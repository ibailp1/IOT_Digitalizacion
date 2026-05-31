import sys
import threading
import selectors
import serial

import inspect
import os

import queue
from multiprocessing.managers import BaseManager

import time
import json

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

MODO_SIMULACION_MQTT = True

RUTA_DISPOSITIVO_PUERTO_SERIAL = '/dev/ttyACM0' 
TASA_DE_BAUDIOS_DEL_PUERTO_SERIAL = 9600 # Baud rate

CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL = 3
TIEMPO_ESPERA_ENTRE_INTENTOS_CONEXION_PUERTO_SERIAL = 1 # Segundos

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

connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()

cliente_mqtt = None

evento_terminar_proceso = threading.Event()

cola_publicaciones_mqtt_salientes = queue.Queue()
cola_publicaciones_mqtt_entrantes = None

class MiManager(BaseManager): pass
MiManager.register("get_salientes", callable=lambda: cola_publicaciones_mqtt_salientes)
MiManager.register("get_entrantes", callable=lambda: cola_publicaciones_mqtt_entrantes)

PUERTO_LOCAL = 50001
PUERTO_REMOTO = 50002

manager_local = MiManager(address=("127.0.0.1", PUERTO_LOCAL), authkey=b"secreto")
manager_local.get_server().serve_forever(poll_interval=1)

# Libero estos recursos antes de cerrar el programa.
class Recursos:
    selector = None
    descriptor_serial = None
recursos = Recursos()

def limpieza_y_salida(codigo_de_salida):

    if recursos.selector is not None:
        try:
            recursos.selector.close()
        except Exception:
            pass

    if recursos.descriptor_serial is not None:
        if recursos.descriptor_serial.is_open:
            try:
                recursos.descriptor_serial.close()
            except Exception:
                pass

    evento_terminar_proceso.set()
    cola_publicaciones_mqtt_salientes.put(None)
    sys.exit(codigo_de_salida)

def imprimir_error(mensaje):
    caller_frame = inspect.currentframe().f_back
    nombre_archivo = os.path.basename(caller_frame.f_code.co_filename)
    numero_linea = caller_frame.f_lineno
    print(nombre_archivo + "(" + str(numero_linea) + "):")
    print(mensaje)

def conectar_con_puerto_serial():
    for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL):
        numero_intento += 1
        try:
            recursos.descriptor_serial = serial.Serial(RUTA_DISPOSITIVO_PUERTO_SERIAL, TASA_DE_BAUDIOS_DEL_PUERTO_SERIAL, timeout=1)
            recursos.descriptor_serial.flushInput()
            return True
        except serial.SerialException:
            imprimir_error("Intento fallido número " + str(numero_intento) + " al conectar con el puerto serial.")
            if numero_intento == CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL:
                imprimir_error("Puerto serial no encontrado. Revisa la configuración.")
                print(excepcion)
                return
            print(excepcion)
            time.sleep(TIEMPO_ESPERA_ENTRE_INTENTOS_CONEXION_PUERTO_SERIAL)
            continue
        except Exception:
            return "Error inesperado al conectar con el puerto serial."

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

    if suscribirse_a_tema(mqtt_tema_comando_luces) == False: return False
    if suscribirse_a_tema(mqtt_tema_solicitud_estado_luces) == False: return False

    return True

def conectar_con_broker():

    if MODO_SIMULACION_MQTT == True:
        return True

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

def enviar_comando(comando):
    comando = (comando + "\n").encode("utf-8")
    if not recursos.descriptor_serial.is_open:
        try:
            recursos.descriptor_serial.write(comando)
        except serial.SerialException:
            print("No se ha escrito el comando al puerto serial debido a un error.")
            return False
        except Exception:
            imprimir_error("Error inesperado al escribir el comando al puerto serial.")
            return False

def procesar_serial(descriptor_selector, codigo_evento_selector):

    try:
        linea_de_texto = descriptor_selector.readline().decode('utf-8').strip()
    except UnicodeDecodeError as excepcion:
        imprimir_error("Error de formato UTF-8 al procesar el mensaje del Arduino.")
        print(excepcion)
        return False
    except Exception as excepcion:
        imprimir_error("Error inesperado al procesar el mensaje del Arduino.")
        print(excepcion)
        return False

    if not linea_de_texto: return False
    
    try:
        estado_arduino = json.loads(linea_de_texto)
    except json.JSONDecodeError as excepcion:
        imprimir_error("Error de formato JSON al procesar el mensaje del Arduino.")
        print(excepcion)
        print("Línea de texto:")
        print(linea_de_texto)
        return False
    except Exception as excepcion:
        imprimir_error("Error inesperado al procesar el mensaje del Arduino.")
        print(excepcion)
        print("Línea de texto:")
        print(linea_de_texto)
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
        mqtt_tema = mqtt_tema_datos_estado_luces

    if codigo_mensaje == codigo_mensaje_datos_telemetria:
        mqtt_tema = mqtt_tema_datos_telemetria
        cuerpo_mensaje["identificador-cliente-nombre-dispositivo"] = mqtt_identificador_cliente + "-" + mqtt_nombre_cosa
        
        ahora = datetime.now()
        cuerpo_mensaje["timestamp-formato-unix"] = ahora.timestamp()

        timestamp_legible = ahora.strftime("%Y-%m-%d %H:%M:%S")
        cuerpo_mensaje["timestamp-textual"] = timestamp_legible

    publicar_en_tema(mqtt_tema, payload)

def procesar_publicacion_mqtt(publicacion_mqtt):

    try:
        payload_string = publicacion_mqtt.decode("utf-8")
    except json.JSONDecodeError:
        print("Recibido mensaje UTF-8 en mal formato desde AWS IOT Core.")
        return False
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de UTF-8 recibido desde AWS IOT Core.")
        return False

    try:
        payload = json.loads(payload_string)
    except json.JSONDecodeError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return False
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        return False

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return False
    except Exception:
        imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
        return False

    if codigo_mensaje == codigo_mensaje_comando_luces:
        # El servidor web pone la string que espera el Arduino
        # Se evita gran trabajo de parseo en la Raspberry
        enviar_comando(cuerpo_mensaje)
        return False

    if codigo_mensaje == codigo_mensaje_solicitud_estado_luces:
        try:
            if cuerpo_mensaje["luz-roja"]:
                comando = "estado luz roja"
                enviar_comando(comando)

            if cuerpo_mensaje["luz-amarilla"]:
                comando = "estado luz amarilla"
                enviar_comando(comando)

            if cuerpo_mensaje["luz-verde"]:
                comando = "estado luz verde"
                enviar_comando(comando)

            if cuerpo_mensaje["luz-puerta"]:
                comando = "estado luz puerta"
                enviar_comando(comando)

            if cuerpo_mensaje["luz-rgb"]:
                comando = "estado luz rgb"
                enviar_comando(comando)

        except KeyError:
            print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
            return False

        except Exception:
            imprimir_error("Error inesperado al procesar el mensaje de JSON recibido desde AWS IOT Core.")
            return False

        return False

def manejar_eventos_cola_publicaciones_mqtt_entrantes():
    global cola_publicaciones_mqtt_entrantes
    while not evento_terminar_proceso.is_set():
        publicacion_mqtt = None
        try:
            publicacion_mqtt = cola_publicaciones_mqtt_entrantes.get(timeout=1)
        except queue.Empty:
            continue
        except Exception:
            print("Ha ocurrido un error inesperado en el momento de leer una publicación de MQTT recibida desde AWS IOT Core.")
            continue
        if publicacion_mqtt is not None:
            procesar_publicacion_mqtt(publicacion_mqtt)
        cola_publicaciones_mqtt_entrantes.task_done()

if __name__ == '__main__':

    with open("../secretos/aws-endpoint-address.txt", 'r') as archivo:
        aws_iot_core_endpoint_address = archivo.readline()

    mensaje_error_conexion_puerto_serial = conectar_con_puerto_serial()
    if mensaje_error_conexion_puerto_serial is not None:
        print(mensaje_error_conexion_puerto_serial)
        limpieza_y_salida(1)

    mensaje_error_conexion_aws_iot_core = conectar_con_aws_iot_core()
    if mensaje_error_conexion_aws_iot_core is not None:
        print(mensaje_error_conexion_aws_iot_core)
        limpieza_y_salida(1)

    threading.Thread(
        target=manejar_eventos_cola_publicaciones_mqtt_entrantes,
        daemon=True
    ).start()

    # Registro del selector
    recursos.selector = selectors.DefaultSelector()
    recursos.selector.register(recursos.descriptor_serial, selectors.EVENT_READ, procesar_serial)
    
    try:
        while True:
            # Se duerme hasta que el Arduino escribe algo
            for key, mask in recursos.selector.select():
                key.data(key.fileobj, mask)
    except KeyboardInterrupt:
        # Si se termina el programa desde la consola pulsando una combinación de teclas
        limpieza_y_salida(0)
    except Exception as excepcion:
        imprimir_error("Error inesperado al esperar eventos del puerto serial.")
        print(excepcion)
        limpieza_y_salida(1)

    limpieza_y_salida(0)
