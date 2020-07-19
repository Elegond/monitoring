#!/usr/bin/python3
# -*- coding: utf-8 -*-
import math

import checklib  # überprüft ob alle libs installiert sind
import time
import sys, os

import sensor
import ws
import shutil

checklib.CHECK_OK()  # um mein import zu behalten

if len(sys.argv) > 1:
    if sys.argv[1] == "help":
        print("HELP!!!11")
        exit(0)


def terminal_size(w=True):  ### gibt die größe des Terminals aus
    (tw, th) = shutil.get_terminal_size((80, 20))
    return tw if w else th


def show_progress_bar(completed, total,
                      bar_length):  # Gibt eine progressbar aus um die Auslastung Prozentual anzuzeigen
    bar_length_unit_value = (total / bar_length)
    completed_bar_part = math.ceil(completed / bar_length_unit_value)
    progress = ""
    if os.name == "nt":  # unterschiedliche zeichen bei Windows und Linux
        for ia in range(1, completed_bar_part):
            progress += "▒" if ia % 2 == 1 else "▓"
        if completed_bar_part == 0:
            remaining = " " * (bar_length - 1)
        else:
            remaining = " " * (bar_length - completed_bar_part)
    else:
        for ia in range(1, completed_bar_part):
            progress += "▒" if ia % 2 == 1 else "▓"
        if completed_bar_part == 0:
            remaining = "░" * (bar_length - 1)
        else:
            remaining = "░" * (bar_length - completed_bar_part)
    percent_done = "%.2f" % ((completed / total) * 100)
    print(f'[{progress}{remaining}] {percent_done}%', end='\n')





### Starten aller notwändigen Threads
webs = 'ws://' + sensor.cfg["ws"]["ip"] + ":" + str(sensor.cfg["ws"]["port"])
wsthread = ws.ActionThread(1, "WEBSOCK", 1)
wsthread.daemon = True
wsthread.start()

sendthread = ws.ActionThread(1, "SEND", 1)
sendthread.daemon = True
sendthread.start()
cputhread = ws.ActionThread(1, "CPU", 1)
cputhread.daemon = True
cputhread.start()
memthread = ws.ActionThread(1, "MEM", 1)
memthread.daemon = True
memthread.start()
diskthread = ws.ActionThread(1, "DISK", 1)
diskthread.daemon = True
diskthread.start()

## Log eintrag zum hochfaren
sensor.log_event("SYSTEM", 9, "Startup complete")


def menu_monitor():  # Funktion zum anzeigen der aktuellen werte
    while ws.threadloops:
        ws.clear()
        space = " " * (int(terminal_size() / 2) - 5)

        dis = False  ## überprüft ob eine festplatte aktiv ist
        for disk in ws.DISK["speicher"]:
            if ws.DISK["speicher"][disk]["enabled"]:
                dis = True

        if ws.CPU["cpu"]["enabled"]:
            print(space + "   CPU " + sensor.check_for_log_console("CPU"))
            ## Gibt die gesammte CPU last in einem Balken aus wenn das Terminal zu klein ist
            if terminal_size(False) < (len(ws.CPU["cpu"]["use"]) + 1 + (2 if ws.MEM["mem"]["enabled"] else 0) + (
                    ((len(ws.DISK["speicher"]) * 2) + 1) if dis else 0) + 8):
                i = 0
                for cpu in ws.CPU["cpu"]["use"]:
                    i += cpu
                show_progress_bar(i / len(ws.CPU["cpu"]["use"]), 100, terminal_size() - 10)
            else:  ## Gibt alle CPU Kerne aus
                for cpu in ws.CPU["cpu"]["use"]:
                    show_progress_bar(cpu, 100, terminal_size() - 10)

        if ws.MEM["mem"]["enabled"]:  ## Gibt die RAM Auslastung aus
            print(space + "   RAM " + sensor.check_for_log_console("MEM"))
            show_progress_bar(float(ws.MEM["mem"]["used"][2]), 100, terminal_size() - 10)

        if dis:  ## Gibt die Festplatten auslastung aus
            print(space + " Storage")
            for disk in ws.DISK["speicher"]:
                if ws.DISK["speicher"][disk]["enabled"]:
                    print(disk + " " + sensor.check_for_log_console(disk))
                    show_progress_bar(float(ws.DISK["speicher"][disk]["used"][2]), 100, terminal_size() - 10)

        ## zusätzliche Infos
        print("\nActiv Webinterface User:", str(len(ws.USERS) - 1) if not len(ws.USERS) == 0 else "0")
        print("Webinsterface: http://monitor.saretzki.work")
        print("Websocket:     " + webs)
        print("\nPress CTRL+C to get to the Menu")
        time.sleep(0.9)


### Schleife zum darstellen des Menüs im Terminal
while ws.threadloops:
    try:
        ## Gibt die Aktuellen werte im Terminal aus
        menu_monitor()
    except KeyboardInterrupt:  # zum unterbrechen der Monitor Funktion
        while True:  ## Menü schleife
            ws.clear()
            print("Menu")
            print(" 1) Monitor\n 2) Settings\n 0) Exit")
            input_char = input("Input: ")
            if input_char == '0':  # shutdown option  | etwas buggy
                ws.clear()
                sensor.log_event("SYSTEM", 9,
                                 "Shutting down")
                print("Shutting down")
                ws.threadloops = False
                exit(0)
            elif input_char == '1':  # Monitor option
                break
            elif input_char == '2':  # Settings option
                inp = ""
                while True:  ## Einstellungsschleife
                    ws.clear()
                    print("Settings")
                    i = 0
                    for s in sensor.cfg:  # Schleife um alle einstellungen im Terminal auszugeben
                        i += 1
                        print(" " + str(i) + ") " + s, "[-]" if inp == str(i) else "[+]")
                        if inp == str(i):
                            ia = 0
                            for v in sensor.cfg[s]:
                                ia += 1
                                print("   0" + str(ia) + ") " + v + ": " + str(sensor.cfg[s][v]))
                    inpold = inp
                    print("\n 0) Back")
                    inp = input("Input: ")
                    ib = 0
                    update = []
                    if inp == "0":  # Zurück
                        break
                    for s in sensor.cfg:  # schleife zu zu überprüfen welche Option geändert werden soll
                        ib += 1
                        if inpold == str(ib):
                            ia = 0
                            if len(inp) == 1:
                                continue
                            for v in sensor.cfg[s]:
                                ia += 1
                                if inp == str("0" + str(ia)):
                                    update.append(s)
                                    update.append(v)
                                    update.append(
                                        str(not sensor.cfg[s][v]) if isinstance(sensor.cfg[s][v], bool) else input(
                                            "Neuer Wert: "))
                            inp = inpold
                            inpold = ""
                    if not update == []:  # ändern der einstellungen
                        # update besteht aus section, option, value (z.B. [0] = CPU, [1] = warning, [2] = 85)
                        sensor.write_config(update[0], update[1], update[2])
                        if update[1] == "enabled" and update[2]:
                            if update[0] == "CPU":
                                cputhread = ws.ActionThread(1, "CPU", 1)
                                cputhread.daemon = True
                                cputhread.start()
                            elif update[0] == "MEM":
                                memthread = ws.ActionThread(1, "MEM", 1)
                                memthread.daemon = True
                                memthread.start()
                    inp = "" if inp == inpold else inp  # speichern des alten input Wertes

                continue
