import json
import subprocess
import threading
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

app = Flask(__name__)

# Properties for connecting to AWSIOTCore

connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()
endpoint_AWS="a2xyhr7rc9cefs-ats.iot.us-east-1.amazonaws.com"
cert_filepath_AWS="cert/Control.cert.pem"
pri_key_filepath_AWS="cert/Control.private.key"
clientId_AWS="Control"
message_topic_commands_AWS="command"
client = None
iot_connected = False
TIMEOUT_CONNECT_AWS = 100

# Connection to AWS
def connect_to_aws():

    global client, iot_connected

    # Create MQTT5 client using mutual TLS via X509 Certificate and Private Key
    print("==== Creating MQTT5 Client ====\n")
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
        client_id=clientId_AWS)
    
    # Start the client, instructing the client to desire a connected state. The client will try to 
    # establish a connection with the provided settings. If the client is disconnected while in this 
    # state it will attempt to reconnect automatically.
    print("==== Starting client ====")
    client.start()

    # We await the `on_lifecycle_connection_success` callback to be invoked.
    if not connection_success_event.wait(TIMEOUT_CONNECT_AWS):
        raise TimeoutError("Connection timeout")

    iot_connected = True

# Callback when any IOT PUB is received
def on_publish_received_AWS(publish_packet_data):
    publish_packet = publish_packet_data.publish_packet
    print("==== Received message from topic '{}': {} ====\n".format(
        publish_packet.topic, publish_packet.payload.decode('utf-8')))

# Callback for the lifecycle event Stopped
def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped\n")
    stopped_event.set()


# Callback for lifecycle event Attempting Connect
def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Lifecycle Connection Attempt\nConnecting to endpoint: '{}' with client ID'{}'".format(
        endpoint_AWS, clientId_AWS))


# Callback for the lifecycle event Connection Success
def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    print("Lifecycle Connection Success with reason code:{}\n".format(
        repr(connack_packet.reason_code)))
    connection_success_event.set()


# Callback for the lifecycle event Connection Failure
def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Lifecycle Connection Failure with exception:{}".format(
        lifecycle_connection_failure.exception))


# Callback for the lifecycle event Disconnection
def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Lifecycle Disconnected with reason code:{}".format(
        lifecycle_disconnect_data.disconnect_packet.reason_code if lifecycle_disconnect_data.disconnect_packet else "None"))


@app.route("/")
def index():

    try:
        with open("../datos.json") as f:
            data = json.load(f)
        items = data.get("Items", [])
    except (FileNotFoundError, json.JSONDecodeError):
        items = []

    # Al haber solo una casa, la definimos directamente
    houses = ["Casa1"]
    selected_house = "Casa1"

    timestamps = []
    temperature = []
    humidity = []
    distance = []

    today = datetime.now().date()

    for item in items:
        # Ya no saltamos por casa porque asumimos que todos los datos son de nuestra única casa
        if item["house"]["S"] != selected_house:
            continue

        payload = item.get("payload", {}).get("M", {})

        # Timestamp
        ts_str = payload.get("timestamp", {}).get("N")
        if not ts_str:
            continue  # saltar si no hay timestamp
        ts = int(ts_str)
        dt = datetime.fromtimestamp(ts)

        # Filtrar solo datos de hoy
        if dt.date() != today:
            continue

        timestamps.append(dt.strftime("%d/%m %H:%M:%S"))

        # Temperatura
        temp_raw = payload.get("temperature", {}).get("S")
        if temp_raw:
            temp = float(temp_raw.replace("C", ""))
        else:
            temp = None
        temperature.append(temp)

        # Humedad
        hum_raw = payload.get("humidity", {}).get("S")
        if hum_raw:
            hum = float(hum_raw.replace("%", ""))
        else:
            hum = None
        humidity.append(hum)

        # Distancia
        dist_raw = payload.get("distance", {}).get("S")
        if dist_raw:
            dist = float(dist_raw.replace(" cm", ""))
        else:
            dist = None
        distance.append(dist)

    return render_template(
        "index.html",
        timestamps=timestamps,
        temperature=temperature,
        humidity=humidity,
        distance=distance,
        houses=houses,
        selected_house=selected_house
    )

@app.route("/send", methods=["POST"])
def send():

    import json

    message = request.form.get("message")
    house = request.form.get("house")

    try:
        # Convertir string → dict
        data = json.loads(message)

        # Inyectar house
        data["house"] = house

        # Volver a string JSON listo para enviar
        final_message = json.dumps(data)

        # We send json message to IOTCore AWS
        if iot_connected:
            print(f"JSON enviado a IoT: '{message_topic_commands_AWS}': {final_message}")
            publish_future = client.publish(
                mqtt5.PublishPacket(
                    topic=message_topic_commands_AWS,
                    payload=final_message,
                    qos=mqtt5.QoS.AT_LEAST_ONCE
                )
            )

            publish_completion_data = publish_future.result(TIMEOUT_CONNECT_AWS)
            print("PubAck received with {}\n".format(repr(publish_completion_data.puback.reason_code)))


    except Exception as e:
        print("Error procesando JSON:", e)

    if house:
        return redirect(url_for("index", house=house))
    else:
        return redirect(url_for("index"))

@app.route("/refresh")
def refresh():

    print("Entro en refresh")
    house = request.form.get("house")
    
    now = datetime.now()

    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = start_of_day + timedelta(days=1)

    start_ts = int(start_of_day.timestamp())
    end_ts = int(end_of_day.timestamp())

    command = f"""aws dynamodb scan \
    --table-name telemetry \
    --filter-expression "#ts BETWEEN :start AND :end" \
    --expression-attribute-names '{{"#ts":"timestamp"}}' \
    --expression-attribute-values '{{":start":{{"N":"{start_ts}"}},":end":{{"N":"{end_ts}"}}}}' \
    --output json > ../datos.json"""

    print("Comando ejecutado:")
    print(command)

    subprocess.run(command, shell=True)

    return redirect(url_for("index", house=house))

if __name__ == "__main__":

    # Cnnect to AWS IOTCOre
    try:
        connect_to_aws()
        print("Connected to AWS IoT")

    except Exception as e:
        print("Error conectando IOTCore: ", str(e))

    app.run(host="0.0.0.0", port=5001)