$ErrorActionPreference = "Stop"

$allowedPublish = 'mosquitto_pub -h localhost -p 1883 -i demo-machine -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -q 1 -t predimaint/demo-machine/telemetry -m ''{"seq":999,"temperature":24,"humidity":55,"vibration_rate":0,"vibration_edges":0,"current_rms":0,"current_source":"simulated"}'''
& docker compose exec -T mosquitto sh -c $allowedPublish
if ($LASTEXITCODE -ne 0) {
    throw "Publication sur le topic propre à la machine refusée (code $LASTEXITCODE). Vérifie les services et le .env."
}
Write-Host "OK : publication du client demo-machine autorisée."

$forbiddenPublish = 'mosquitto_pub -h localhost -p 1883 -i autre-machine -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -q 1 -t predimaint/demo-machine/telemetry -m ''{"seq":1000,"temperature":24,"humidity":55,"vibration_rate":0,"vibration_edges":0,"current_rms":0,"current_source":"simulated"}'''
& docker compose exec -T mosquitto sh -c $forbiddenPublish
if ($LASTEXITCODE -eq 0) {
    throw "ÉCHEC : l'ACL a laissé autre-machine publier dans predimaint/demo-machine/telemetry."
}
Write-Host "OK : publication croisée refusée par l'ACL."
