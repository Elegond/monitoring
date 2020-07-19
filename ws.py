#!/usr/bin/python3
import math
import selectors
import sys
import asyncio
import json
import logging
import threading
import time
from os import system,name

import sensor
import websockets

logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)  # Logging für den websocket

USERS = set()  # liste aller websocket Clients
threadloops = True  # für die ganzen while True schleifen (main.py 134)
sleep = 2  # intervall zum überprüfen der werte

CPU = sensor.get_cpu()  # CPU List z.B. {"cpu": {"use": [21.4, 4.7, 12.5, 3.1, 3.1, 3.1, 6.2, 6.2], "enabled": true,
# "warning": 85, "critical": 95}}

MEM = sensor.get_memory()  # RAM List z.B. {"mem": {"total": ["31.96", "GB", "100.0"], "used": ["9.48", "GB",
# "29.7"], "free": ["22.48", "GB", "70.3"], "enabled": true, "warning": 85, "critical": 95}}

DISK = sensor.get_all_drives()  # Disk List z.B. {"speicher": {"C:\\": {"total": ["475.50", "GB", "100.0"], "used": [
# "409.64", "GB", "86.1"], "free": ["65.86", "GB", "13.9"], "enabled": true, "warning": 85, "critical": 95},
# "D:\\": {"total": ["232.89", "GB", "100.0"], "used": ["116.42", "GB", "50.0"], "free": ["116.47", "GB", "50.0"],
# "enabled": true, "warning": 85, "critical": 95}, "E:\\": {"enabled": false, "warning": 85, "critical": 95},
# "F:\\": {"total": ["232.85", "GB", "100.0"], "used": ["148.97", "MB", "0.1"], "free": ["232.70", "GB", "99.9"],
# "enabled": true, "warning": 85, "critical": 95}}}

### TIP: benutze https://www.jsonformatter.io/ um diesen Json Dump leichter zu lesen

# loops für die Websockets
## inklusive workaround für windows python 3.8
policy = asyncio.get_event_loop_policy()
policy._loop_factory = asyncio.SelectorEventLoop
selector = selectors.SelectSelector()
clientloop = asyncio.SelectorEventLoop(selector)

selector2 = selectors.SelectSelector()
serverloop = asyncio.SelectorEventLoop(selector2)


def clear():  # Löscht den Inhalt des Terminals
    system('cls' if name == 'nt' else 'clear')

def state_event():  # Gibt eine liste aus allen listen im Json format zurück
    return json.dumps(
        {**DISK, **CPU, **MEM, "sleep": sleep, "time": time.strftime('%d.%m.%Y %X')})


async def notify_state():  # Sendet an alle Websocket Clients die ausgabe von state_event()
    if USERS:
        message = state_event()
        await asyncio.wait([user.send(message) for user in USERS])


async def wbs(websocket, path):  # Websocket Server Funktion
    global sleep
    USERS.add(websocket)  # register Websocket Client
    try:
        await websocket.send(state_event())  # Sende aktuelle Stats
        async for message in websocket:  # Warte auf nachricht von Client
            data = json.loads(message)  # Json -> list
            if data["action"] == "refresh":  # Broadcast stats
                await notify_state()

            elif data["action"] == "enable":  # aktivieren von Einstellungen
                if data["target"] in sensor.cfg:
                    if not sensor.cfg[data["target"]]["enabled"]:
                        sensor.cfg = sensor.write_config(data["target"], "enabled", True)
                        time.sleep(1)
                        if data["target"] == 'CPU':
                            cputhread = ActionThread(1, "CPU", 1)
                            cputhread.daemon = True
                            cputhread.start()
                        elif data["target"] == "MEM":
                            memthread = ActionThread(1, "MEM", 1)
                            memthread.daemon = True
                            memthread.start()
                await notify_state()

            elif data["action"] == "disable":  # deaktivieren von Einstellungen
                if data["target"] in sensor.cfg:
                    sensor.cfg = sensor.write_config(data["target"], "enabled", "False")
                await notify_state()

            elif data["action"] == "set":  # setzen von Werten in den Einstellungen *** UNTESTED ***
                if data["target"] in sensor.cfg:
                    if data["var"] in sensor.cfg[data["target"]]:
                        sensor.cfg = sensor.write_config(data["target"], data["var"], data["val"])
                await notify_state()

            elif data["action"] == "sleepplus":  # ändern des intervalls zum überprüfen der werte
                sleep += 1
                await notify_state()

            elif data["action"] == "sleepminus":  # ändern des intervalls zum überprüfen der werte
                if sleep < 2:
                    sleep = 2
                sleep -= 1
                await notify_state()

            else:
                print("error", data)
                logging.error("unsupported event: {}", data)

    finally:
        USERS.remove(websocket)  # unregister Websocket Client


async def send(self):  ### Erstellt ein Websocket Client der den Websocket Server Broadcasts machen lässt
    async with websockets.connect('ws://' + sensor.cfg["ws"]["ip"] + ':' + str(sensor.cfg["ws"]["port"])) as websocket:
        while True:
            await websocket.send(json.dumps({"action": "refresh"}))
            if not threadloops:
                await websocket.close(0, "")
                break
            await asyncio.sleep(sleep)


class ActionThread(threading.Thread):  ### Klasse für die Threads
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter

    def run(self):
        global threadloops
        if self.name == "CPU":  # CPU Thread
            global CPU
            while threadloops:
                try:
                    if not sensor.cfg["CPU"]["enabled"]:  # Wenn der Sensor abgeschaltet ist wird der Thread beended
                        CPU = {"cpu": {"enabled": False}}
                        break

                    CPU = sensor.get_cpu()  # Setzt die aktuellen werte in die liste
                    i = 0
                    for cpu in CPU["cpu"]["use"]:
                        i += cpu
                    last = i / len(CPU["cpu"]["use"])
                    sensor.check_for_log("CPU", round(last, 2))  # überprüft ob die CPU insgesammt über einen der
                    # Alert werte liegt

                except:
                    if sensor.cfg is None:  # wenn die Config nicht richtig geladen ist muss sie gesetzt werden
                        sensor.cfg = sensor.read_config(sensor.config())

                time.sleep(sleep - 1)  # Die CPU braucht 1 Sekunde um die Last zu messen deswegen wird -1 gerechnet

        elif self.name == "MEM":  # RAM Thread
            global MEM
            while threadloops:
                try:
                    if not sensor.cfg["MEM"]["enabled"]:  # Wenn der Sensor abgeschaltet ist wird der Thread beended
                        MEM = {"mem": {"enabled": False}}
                        break
                    MEM = sensor.get_memory()  # Setzt die aktuellen werte in die liste
                    sensor.check_for_log("MEM", round(MEM["mem"]["used"], 2))  # überprüft ob die auslastung über einen
                    # der Alert werte liegt
                except:
                    if sensor.cfg is None:
                        sensor.cfg = sensor.read_config(sensor.config())

                time.sleep(sleep)

        elif self.name == "DISK":  # Disk Thread
            global DISK
            while threadloops:
                try:
                    DISK = sensor.get_all_drives()  # Setzt die aktuellen werte in die liste
                    for d in DISK["speicher"]:
                        sensor.check_for_log(d, round(float(DISK["speicher"][d]["used"][2]), 2))  # überprüft ob die
                        # auslastung über einen der Alert werte liegt
                except:
                    if sensor.cfg is None:
                        sensor.cfg = sensor.read_config(sensor.config())
                time.sleep(sleep)

        elif self.name == "SEND":  # Websocket Client Thread ( siehe def send() )
            global clientloop
            time.sleep(3)
            while threadloops:
                try:
                    ### Bugfix für windows 3.8 eventloop in thread
                    selector = selectors.SelectSelector()
                    clientloop = asyncio.SelectorEventLoop(selector)
                    asyncio.set_event_loop(clientloop)
                    ###
                    asyncio.get_event_loop().run_until_complete(send(self))  # Startet den Websocket Client
                except Exception as e:
                    if not "code = 1006" in str(e):
                        sensor.log_event("WEBSOCKET Client", 9,
                                         "Client Killed " + str(e))  # Schreibt eventuelle errors in die logdatei
                    time.sleep(1)

        elif self.name == "WEBSOCK":  # Websocket Server Thread
            global serverloop
            time.sleep(1)
            while threadloops:
                try:
                    ### Bugfix für windows 3.8 eventloop in thread
                    selector = selectors.SelectSelector()
                    serverloop = asyncio.SelectorEventLoop(selector)
                    asyncio.set_event_loop(serverloop)
                    ###

                    # schreibt die websocket Server adresse in den Log
                    sensor.log_event("WEBSOCKET", 9,
                                     'ws://' + sensor.cfg["ws"]["ip"] + ":" + str(sensor.cfg["ws"]["port"]))

                    start_server = websockets.serve(wbs, sensor.cfg["ws"]["ip"], sensor.cfg["ws"]["port"])

                    asyncio.get_event_loop().run_until_complete(start_server)  # Startet den Websocket Server
                    asyncio.get_event_loop().run_forever()
                except Exception as e:
                    sensor.log_event("WEBSOCKET", 9,
                                     "Server Killed " + str(e))  # Schreibt eventuelle errors in die logdatei
                    if "Errno 10048" in str(e) or "Errno 98" in str(e) or "already in use" in str(e):  ### Error wenn das Tool Zweimal gestartet wird
                        threadloops = False
                        serverloop.stop()
                        clientloop.stop()
                        time.sleep(3)
                        clear()
                        print("Websocket already in use\n\n"+ str(e))
                        input("\nPress Enter to Close")
                        sys.exit(0)
                    time.sleep(1)
