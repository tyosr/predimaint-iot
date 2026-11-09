import json
import logging
import threading
import paho.mqtt.client as mqtt
from pydantic import ValidationError
from app.application.services import MeasurementInput
from app.infrastructure.database import SessionLocal
from app.infrastructure.repository import SqlMeasurementRepository
from app.settings import settings

logger = logging.getLogger(__name__)


class MqttIngestor:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="predimaint-backend")
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.thread = None

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe("predimaint/+/telemetry", qos=1)
            client.subscribe("predimaint/+/status", qos=1)
            logger.info("Abonné aux topics PrediMaint")
        else:
            logger.error("Connexion MQTT refusée: %s", reason_code)

    def on_message(self, client, userdata, message):
        parts = message.topic.split("/")
        if len(parts) != 3 or parts[0] != "predimaint": return
        machine_id, kind = parts[1], parts[2]
        db = SessionLocal()
        try:
            if kind == "status":
                from app.infrastructure.models import MachineRow
                machine = db.get(MachineRow, machine_id)
                if machine:
                    machine.status = "online" if message.payload.decode(errors="replace") == "online" else "offline"
                    db.commit()
                return
            data = MeasurementInput.model_validate(json.loads(message.payload))
            SqlMeasurementRepository(db).receive(machine_id, data)
        except (ValueError, LookupError, ValidationError, json.JSONDecodeError) as exc:
            logger.warning("Message MQTT ignoré (%s): %s", message.topic, exc)
            db.rollback()
        except Exception:
            logger.exception("Erreur de traitement MQTT (%s)", message.topic)
            db.rollback()
        finally:
            db.close()

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        self.client.loop_forever()

    def stop(self):
        self.client.disconnect()
