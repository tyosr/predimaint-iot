"""PrediMaint ESP32 firmware for the user's confirmed GPIO wiring."""
import json
import time
import machine
import network
import dht
from machine import Pin

CONFIG_PATH = "config.json"

try:
    from umqtt.simple import MQTTClient
except ImportError:
    raise RuntimeError("Module umqtt.simple manquant. Installez-le depuis Thonny ou le firmware.")


def load_config():
    with open(CONFIG_PATH, "r") as file:
        return json.load(file)


def connect_wifi(config):
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        print("Wi-Fi déjà connecté:", wlan.ifconfig()[0])
        return wlan
    # MicroPython can retain a failed/connecting radio state across soft resets.
    try:
        wlan.disconnect()
    except Exception:
        pass
    try:
        wlan.active(False)
        time.sleep_ms(300)
    except Exception:
        pass
    wlan.active(True)
    wlan.connect(config["wifi_ssid"], config["wifi_password"])
    deadline = time.time() + 25
    while not wlan.isconnected() and time.time() < deadline:
        time.sleep_ms(250)
    if not wlan.isconnected():
        raise OSError("Connexion Wi-Fi impossible")
    print("Wi-Fi connecté:", wlan.ifconfig()[0])
    return wlan


def connect_mqtt(config):
    machine_id = config["machine_id"]
    client = MQTTClient(
        # The ACL uses the client ID to restrict the ESP32 to its own topic.
        client_id=machine_id.encode(),
        server=config["mqtt_host"], port=config.get("mqtt_port", 1883),
        user=config.get("mqtt_username") or None,
        password=config.get("mqtt_password") or None,
        keepalive=30,
    )
    status_topic = ("predimaint/%s/status" % machine_id).encode()
    client.set_last_will(status_topic, b"offline", retain=True, qos=1)
    client.connect()
    client.publish(status_topic, b"online", retain=True, qos=1)
    return client


class Sensors:
    def __init__(self, config):
        self.config = config
        self.dht_sensor = dht.DHT22(Pin(config.get("dht_pin", 27)))
        self.vibration = Pin(config.get("vibration_pin", 16), Pin.IN)
        self.active_level = config.get("vibration_active_level", 1)
        self.adc = machine.ADC(Pin(config.get("acs_pin", 34)))
        self.adc.atten(machine.ADC.ATTN_11DB)
        self.adc.width(machine.ADC.WIDTH_12BIT)
        self.last_edge_ms = time.ticks_ms()
        self.edge_count = 0
        self.window_start = time.ticks_ms()
        self.current_source = config.get("current_mode", "simulated")
        if self.current_source not in ("simulated", "hardware"):
            raise ValueError("current_mode doit être 'simulated' ou 'hardware'")
        # HW-072 is a digital comparator output, not a calibrated accelerometer.
        irq_trigger = Pin.IRQ_RISING if self.active_level else Pin.IRQ_FALLING
        self.vibration.irq(trigger=irq_trigger, handler=self._on_vibration)

    def _on_vibration(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_edge_ms) > 30:
            self.edge_count += 1
            self.last_edge_ms = now

    def read(self):
        temp, humidity = None, None
        try:
            self.dht_sensor.measure()
            temp, humidity = self.dht_sensor.temperature(), self.dht_sensor.humidity()
        except Exception as exc:
            if not self.config.get("simulate_missing_sensors", False):
                print("Erreur DHT22:", exc)
            else:
                temp, humidity = 24.0, 55.0
        now = time.ticks_ms()
        elapsed_ms = max(time.ticks_diff(now, self.window_start), 1)
        irq_state = machine.disable_irq()
        edges = self.edge_count
        self.edge_count, self.window_start = 0, now
        machine.enable_irq(irq_state)
        rate = edges * 1000.0 / elapsed_ms
        current = self.read_current() if self.current_source == "hardware" else 0.0
        return {
            "temperature": temp,
            "humidity": humidity,
            "vibration_rate": round(rate, 3),
            "vibration_edges": edges,
            "current_rms": current,
            "current_source": self.current_source,
        }

    def read_current(self):
        # Enable only after the 10k/20k divider is installed and ADC voltage is verified.
        # 300 ms window approximates 15 periods at 50 Hz; RMS is relative to
        # the calibrated no-current offset. Keep sampling close to 1 kHz.
        sensor_v_per_a = self.config.get("current_sensitivity_v_per_a", 0.185)
        offset = self.config.get("current_offset_v", 1.67)
        compensation = self.config.get("divider_compensation", 1.5)
        sum_squares = 0.0
        samples = 0
        started = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), started) < 300:
            adc_v = self.adc.read() * 3.3 / 4095.0
            module_out_v = adc_v * compensation
            delta_a = (module_out_v - offset) / sensor_v_per_a
            sum_squares += delta_a * delta_a
            samples += 1
            time.sleep_ms(1)
        return round((sum_squares / max(samples, 1)) ** 0.5, 3)


def main():
    config = load_config()
    sensors = Sensors(config)
    seq = 0
    client = None
    while True:
        try:
            if not network.WLAN(network.STA_IF).isconnected():
                connect_wifi(config)
            if client is None:
                client = connect_mqtt(config)
            try:
                values = sensors.read()
                if values["temperature"] is None or values["humidity"] is None:
                    print("Mesure DHT invalide; publication ignorée")
                else:
                    seq += 1
                    payload = {"seq": seq}
                    payload.update(values)
                    topic = ("predimaint/%s/telemetry" % config["machine_id"]).encode()
                    client.publish(topic, json.dumps(payload), qos=1)
                    print("Publié:", payload)
            except Exception as exc:
                print("Erreur acquisition/publication:", exc)
                try:
                    client.disconnect()
                except Exception:
                    pass
                client = None
        except Exception as exc:
            print("Erreur connexion:", exc)
            client = None
            time.sleep(3)
        time.sleep(max(2, config.get("publish_interval_s", 5)))


main()
