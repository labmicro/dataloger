import paho.mqtt.client as mqtt
from time import sleep

client = mqtt.Client(
    client_id="myPy", transport="tcp", protocol=mqtt.MQTTv311, clean_session=True
)
# client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
# client.tls_insecure_set(True)
# client.connect("test.mosquitto.org", port=8883, keepalive=60)

client.connect("test.mosquitto.org", port=1883, keepalive=60)
client.loop_start()

# properties = Properties(PacketTypes.PUBLISH)
# properties.MessageExpiryInterval = 30
client.publish("lea/ozono", "Cedalo Mosquitto is awesome")

sleep(2)
