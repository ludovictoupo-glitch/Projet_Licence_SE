#!/bin/bash

IFACE="wlan0"
SSID="dobot"
PASSWORD="000rasp000"

sudo nmcli con delete dobot-fix 2>/dev/null

sudo nmcli con add type wifi \
    ifname "$IFACE" \
    con-name dobot-fix \
    ssid "$SSID"

sudo nmcli con modify dobot-fix \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD" \
    connection.autoconnect yes \
    ipv4.method manual \
    ipv4.addresses 192.168.137.57/24 \
    ipv4.gateway 192.168.137.1 \
    ipv4.dns "8.8.8.8 1.1.1.1"

sudo nmcli con up dobot-fix

echo "Connecté à $SSID avec IP fixe 192.168.137.57"