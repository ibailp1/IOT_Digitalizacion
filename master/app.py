import sys
import threading
import selectors
import serial

import time
import json

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

# --- Serial Communication Setup ---
# NOTE: Please replace '/dev/ttyACM0' with the correct serial port for your Arduino.
# On Raspberry Pi, it is typically /dev/ttyACM0 or /dev/ttyUSB0.
# You can find the correct port by checking the output of `dmesg | grep tty` after plugging in your Arduino.

RUTA_DISPOSITIVO_PUERTO_SERIAL = '/dev/ttyACM0' 
TASA_DE_BAUDIOS_DEL_PUERTO_SERIAL = 9600 # Baud rate

CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL = 3
TIEMPO_ESPERA_ENTRE_INTENTOS_CONEXION_PUERTO_SERIAL = 1 # Segundos

# Events and properties for AWS used within callbacks to progress sample
connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()
endpoint_AWS="a2xyhr7rc9cefs-ats.iot.us-east-1.amazonaws.com"
cert_filepath_AWS="cert/Casa1.cert.pem"
pri_key_filepath_AWS="cert/Casa1.private.key"
aws_client_id="basicPubSub"
aws_device_name="Casa1"
message_topic_commands_AWS="command"
message_topic_telemetry_AWS="telemetry"
client = None
aws_iot_connected = False
TIMEOUT_CONNECT_AWS = 100

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

    sys.exit(codigo_de_salida)

def conectar_con_puerto_serial():
    for numero_intento in range(CANTIDAD_INTENTOS_CONEXION_PUERTO_SERIAL):
        try:
            recursos.descriptor_serial = serial.Serial(RUTA_DISPOSITIVO_PUERTO_SERIAL, TASA_DE_BAUDIOS_DEL_PUERTO_SERIAL, timeout=1)
            recursos.descriptor_serial.flushInput()
        except serial.SerialException:
            print("Intento fallido número " + str(numero_intento) + " al conectar con el puerto serial.")
            time.sleep(TIEMPO_ESPERA_ENTRE_INTENTOS_CONEXION_PUERTO_SERIAL)
        except Exception:
            print("Error al conectar con el puerto serial.")
            limpieza_y_salida(1)
    print("Puerto serial no encontrado. Revisa la configuración.")
    limpieza_y_salida(1)

# Connection to AWS
def conectar_con_aws():

    global client, aws_iot_connected

    # Create MQTT5 client using mutual TLS via X509 Certificate and Private Key
    client = mqtt5_client_builder.mtls_from_path(
        endpoint=endpoint_AWS,
        cert_filepath=cert_filepath_AWS,
        pri_key_filepath=pri_key_filepath_AWS,
        on_publish_received=on_publish_received_AWS,
        on_lifecycle_stopped=on_lifecycle_stopped_AWS,
        on_lifecycle_attempting_connect=on_lifecycle_attempting_connect_AWS,
        on_lifecycle_connection_success=on_lifecycle_connection_success_AWS,
        on_lifecycle_connection_failure=on_lifecycle_connection_failure_AWS,
        on_lifecycle_disconnection=on_lifecycle_disconnection_AWS,
        client_id=aws_client_id)
    
    # Start the client, instructing the client to desire a connected state. The client will try to 
    # establish a connection with the provided settings. If the client is disconnected while in this 
    # state it will attempt to reconnect automatically.

    client.start()

    if not connection_success_event.wait(TIMEOUT_CONNECT_AWS):
        raise TimeoutError("Tiempo de espera agotado en el intento de conexión con AWS.")


    # Subscribe 
    subscribe_future = client.subscribe(
    subscribe_packet=mqtt5.SubscribePacket(
        subscriptions = [
        mqtt5.Subscription(
            topic_filter = message_topic_commands_AWS,
            qos = mqtt5.QoS.AT_LEAST_ONCE
        )]
    ))
    suback = subscribe_future.result(TIMEOUT_CONNECT_AWS)
    print("Suback received with reason code:{}\n".format(suback.reason_codes))

    aws_iot_connected = True

def on_publish_received_AWS(publish_packet_data):

    publish_packet = publish_packet_data.publish_packet

    try:
        payload_string = publish_packet.payload.decode("utf-8")
    except json.JSONDecodeError:
        print("Recibido mensaje UTF-8 en mal formato desde AWS IOT Core.")
        return
    except Exception:
        print("Error inesperado.")
        return

    try:
        payload = json.loads(payload_string)
    except json.JSONDecodeError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return
    except Exception:
        print("Error inesperado.")
        return

    try:
        cabeza_mensaje = payload["cabeza-mensaje"]
        cuerpo_mensaje = payload["cuerpo-mensaje"]
        codigo_mensaje = cabeza_mensaje["codigo-mensaje"]
    except KeyError:
        print("Recibido mensaje JSON en mal formato desde AWS IOT Core.")
        return
    except Exception:
        print("Error inesperado.")
        return

    if codigo_mensaje == "comando":
        comando = cuerpo_mensaje
        enviar_comando(comando)
        return

    if codigo_mensaje == "solicitud-estado":
        print("NO IMPLEMENTADO")
        return

# Callback for the lifecycle event Stopped
def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped\n")
    stopped_event.set()


# Callback for lifecycle event Attempting Connect
def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Lifecycle Connection Attempt\nConnecting to endpoint: '{}' with client ID'{}'".format(
        endpoint_AWS, aws_client_id))


# Callback for the lifecycle event Connection Success
def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    print("Lifecycle Connection Success with reason code:{}\n".format(
        repr(connack_packet.reason_code)))
    connection_success_event.set()
    aws_iot_connected = True

# Callback for the lifecycle event Connection Failure
def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Lifecycle Connection Failure with exception:{}".format(
        lifecycle_connection_failure.exception))
    aws_iot_connected = False

# Callback for the lifecycle event Disconnection
def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Lifecycle Disconnected with reason code:{}".format(
        lifecycle_disconnect_data.disconnect_packet.reason_code if lifecycle_disconnect_data.disconnect_packet else "None"))
    aws_iot_connected = False

def enviar_comando(comando):
    comando = (comando + "\n").encode("utf-8")
    if not recursos.descriptor_serial.is_open:
        try:
            recursos.descriptor_serial.write(comando)
        except serial.SerialException:
            print("No se ha escrito el comando al puerto serial debido a un error.")
            return
        except Exception:
            print("Error inesperado.")
            return

def procesar_serial(descriptor_selector, codigo_evento_selector):

    if not aws_iot_connected: return

    try:
        linea_de_texto = file_obj.readline().decode('utf-8').strip()
    except UnicodeDecodeError:
        return
    except Exception:
        print("Error inesperado.")
        limpieza_y_salida(1)

    if not linea_de_texto: return
    
    try:
        estado_arduino = json.loads(linea_de_texto)
    except json.JSONDecodeError:
        return
    except Exception:
        print("Error inesperado.")
        return

    if not aws_iot_connected: return

    payload = {
        "house": aws_device_name,
        "timestamp": int(time.time()),
        "estado": estado_arduino
    }

    try:
        client.publish(mqtt5.PublishPacket(
            topic=message_topic_telemetry_AWS,
            payload=json.dumps(payload),
            qos=mqtt5.QoS.AT_LEAST_ONCE
        )).result(TIMEOUT_CONNECT_AWS)
    except concurrent.futures.TimeoutError:
        print("Se agotó el tiempo de espera al publicar en AWS.")
        return
    except Exception:
        print("Error inesperado.")
        return

if __name__ == '__main__':

    conectar_con_puerto_serial()

    try:
        conectar_con_aws()
    except Exception as excepcion:
        print("Error de conexión con AWS.")
        return

    # Solicita el estado de las luces al Arduino
    enviar_comando("estado luces")

    # Registro del selector
    recursos.selector = selectors.DefaultSelector()
    recursos.selector.register(recursos.descriptor_serial, selectors.EVENT_READ, procesar_serial)
    
    try:
        while True:
            # Se duerme hasta que el Arduino escribe algo
            for key, mask in selector.select():
                key.data(key.fileobj, mask)
    except KeyboardInterrupt:
        # Si se termina el programa desde la consola pulsando una combinación de teclas
        limpieza_y_salida(0)
    finally:
        recursos.selector.close()
