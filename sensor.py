#!/usr/bin/python
import psutil
import shutil, time
from configparser import ConfigParser


def short_byte(byte, total=1, end=0):  # Verkürzt die angegebenen Bytes zu einer Lesbareren größe
    while byte > 1024 and end < 5:
        end = end + 1
        byte = byte / 1024
    return [str('{:1.2f}'.format(byte)),
            "KiB" if end == 1 else "MiB" if end == 2 else "GiB" if end == 3 else "TiB" if end == 4 else "PiB" if end == 5 else "",
            '{:1.1f}'.format(100 if total == 1 else (byte * (1024 ** end) / (total / 100)))]
    # Gibt [Anzahl, Einheit, Prozent] zurück z.B. [0] = 125 [1] = "GB" [2] = 50


def get_drive(path):  # Gibt die auslastung der Festplatte als list zurück
    return {"total": short_byte(shutil.disk_usage(path).total), "used":
        short_byte(shutil.disk_usage(path).used, shutil.disk_usage(path).total), "free":
                short_byte(shutil.disk_usage(path).total - shutil.disk_usage(path).used, shutil.disk_usage(path).total)}
                ## um wiedersprüchliche daten zu vermeiden benutze ich nicht disk_usage(path).free
                ## mit z.B. EXT4 bekommt man mit u


def get_all_drives():  # Gibt eine liste mit allen festplatten und deren auslastung zurück (Beispiel in ws.py)
    global cfg
    speicher = {}
    for i in psutil.disk_partitions():
        if str(i[0]).find('loop') == -1 and str(i[3]).find('cd'):  # verhindert bestimmte typen von Geräten
            if str(i[0]) in cfg:
                if cfg[str(i[0])]["enabled"]:
                    speicher.update({str(i[0]): {**get_drive(i[1]), **cfg[i[0]]}})
                else:
                    speicher.update({str(i[0]): {**cfg[str(i[0])]}})
            else:
                cfg = read_config(config())
                return get_all_drives()
    return {"speicher": speicher}


def get_memory():  # Gibt die aktuelle auslastung des Arbeitzspeichers zurück
    global cfg
    return {"mem": {"total": short_byte(psutil.virtual_memory().total),
                    "used": short_byte(psutil.virtual_memory().used, psutil.virtual_memory().total),
                    "free": short_byte(psutil.virtual_memory().free, psutil.virtual_memory().total),
                    **cfg["MEM"]}}


def get_cpu():  # Gibt die aktuelle auslastung der CPU zurück
    global cfg
    return {"cpu": {"use": psutil.cpu_percent(1, True), **cfg["CPU"]}}


def config():
    parser = ConfigParser()
    config = ["smtp", "ws", "log", "CPU", "MEM"]  # Liste mit allen Sectionen in der Config

    for disk in psutil.disk_partitions():  # Fügt alle Festplatten als Section in die Config Liste ein
        if str(disk[0]).find('loop') == -1 and str(disk[3]).find('cd'):
            config.append(disk[0])

    ### Listen mit Standard werten für die Einstellungen
    default = {"enabled": "True", "warning": "85", "critical": "95"}
    defaultws = {"ip": "127.0.0.1", "port": "8080"}
    defaultlog = {"enabled": "True", "file": "log.txt"}
    defaultsmtp = {"enabled": "False", "sender": "mail@email.de","receiver": "mail@email.de", "server": "smtp.email.de", "password": "1234",
                   "port": "25",
                   "ssl": "False"}
    ###

    parser.read("settings.ini")  # Liest die alte Config Datei ein
    for section in config:  # überprüft alle Sectionen
        if section in parser.sections():  # überprüft vorhandene Section auf fehlende werte
            for var in defaultws if section == "ws" else defaultsmtp if section == "smtp" else defaultlog if section == "log" else default:
                if var not in parser[section]:  # Setzt fehlende Werte auf den Standard wert
                    parser.set(section, var,
                               defaultws[var] if section == "ws" else defaultsmtp[var] if section == "smtp" else
                               defaultlog[var] if section == "log" else
                               default[var])
        else:  # Erstellt Section wenn nicht vorhanden und setzt alle Standard werte
            parser.add_section(section)
            for var in defaultws if section == "ws" else defaultsmtp if section == "smtp" else defaultlog if section == "log" else default:
                parser.set(section, var,
                           defaultws[var] if section == "ws" else defaultsmtp[var] if section == "smtp" else defaultlog[
                               var] if section == "log" else default[
                               var])

    with open('settings.ini', 'w') as configfile:  # Speichert alle Änderungen
        parser.write(configfile)
    return parser


def read_config(parser):  # Erstellt eine Liste aus der kompletten Config
    rcfg = {}
    for section in parser.sections():
        tmp = {}
        for var in parser[section]:
            val = parser[section][var]
            if var == "warning" or var == "critical" or var == "port":  # Versucht zahlen als Zahl zu speichern
                try:
                    val = int(val)
                except:
                    print("Error invalid setting: " + var + " = " + val)
                    val = 0
            elif var == "enabled":  # Versucht Booleans als Boolean zu speichern
                try:
                    val = parser.getboolean(section, var)
                except:
                    print("Error invalid setting: " + var + " = " + val)
                    val = False
            tmp.update({var: val})
        rcfg.update({section: tmp})
    return rcfg  # Gibt die ausgelesene als Liste zurück


def write_config(section, var, val):  # Schreibt einen wert in die Config
    global cfg
    log_event(section, 8, "set " + var + " = " + str(val))  # Schreibt die Änderung in die Logdatei
    parser = config()
    if section not in parser.sections():
        parser.add_section(section)
    parser.set(section, var, str(val))  # Setzt den neuen Wert
    with open('settings.ini', 'w') as configfile:  # Speichert
        parser.write(configfile)
    log_event(section, 8, "settet " + var + " = " + str(val))  # Schreibt die Änderung in die Logdatei
    cfg.clear()
    cfg = read_config(config())  # Setzt die cfg liste neu


def log_event(triger, state, val):  # Schreibt die logdatie und/oder sendet die mail basierent aut den aktuellen Status
    t = time.strftime('%d.%m.%Y %X')  # Timestamp
    # state
    # 0 - OK
    # 1 - warnung
    # 2 - critical
    # 3 - warnung ack
    # 4 - critical ack
    # 8 - SETTINGS INFO
    # 9 - SYSTEM INFO
    if state == 0:
        msg = "INFO - " + t + " - " + triger + " load under " + str(val) + "%"
        write_log(msg)  # Schreibt in den Log
        mail(msg, msg)  # Sendet eine mail
        return 0
    elif state == 1:
        msg = "WARNING - " + t + " - " + triger + " load over " + str(val) + "%"
        write_log(msg)
        mail(msg, msg)
        return 3  # Gibt acknowledged Wert zurück um doppelte logs zu verhindern
    elif state == 2:
        msg = "CRITICAL - " + t + " - " + triger + " load over " + str(val) + "%"
        write_log(msg)
        mail(msg, msg)
        return 4  # Gibt acknowledged Wert zurück um doppelte logs zu verhindern
    elif state == 8:
        write_log("SETTINGS - " + t + " - " + triger + " " + str(val))
    elif state == 9:
        write_log("INFO - " + t + " - " + triger + " " + str(val))
    return state


def check_for_log(target, last):  # überprüft ob ein sensor die schwellwerte überschritten hat
    if cfg[target]["critical"] <= last:
        if state[target] == 0 or state[target] == 1:
            state[target] = log_event(target, 2, last)  # Speichert den acknowledged Wert ab

    elif cfg[target]["warning"] <= last:
        if state[target] == 0 or state[target] == 2:
            state[target] = log_event(target, 1, last)
    else:
        if state[target] == 3 or state[target] == 4:
            state[target] = log_event(target, 0, last)


def check_for_log_console(target):  # Gibt ein String mit einer ensprechenden Nachricht zurück
    try:
        if state[target] == 2 or state[target] == 4:
            return "CRITICAL"
        elif state[target] == 1 or state[target] == 3:
            return "WARNING"
        else:
            return ""
    except:
        state.update({target: 0})
        return check_for_log_console(target)

def mail(warnung, betreff):  # Versendet mails
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    if cfg["smtp"]["enabled"]:  # Versendet mails wenn die aktiviert sind
        try:
            context = ssl.create_default_context()
            if cfg["smtp"]["ssl"]:
                if cfg["smtp"]["port"] == 587:
                    server = smtplib.SMTP(cfg["smtp"]["server"], cfg["smtp"]["port"])
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                else:
                    server = smtplib.SMTP_SSL(cfg["smtp"]["server"], cfg["smtp"]["port"])
            else:
                server = smtplib.SMTP(cfg["smtp"]["server"], cfg["smtp"]["port"])
            if not cfg["smtp"]["password"] == "":
                server.login(cfg["smtp"]["sender"], cfg["smtp"]["password"])
            nachricht = MIMEMultipart("alternative")
            part1 = MIMEText(warnung, "plain")
            # part2 = MIMEText(html, "html")
            nachricht.attach(part1)
            # nachricht.attach(part2)
            nachricht["Subject"] = betreff
            nachricht["From"] = cfg["smtp"]["sender"]
            nachricht["To"] = cfg["smtp"]["receiver"]
            server.sendmail(cfg["smtp"]["sender"], cfg["smtp"]["receiver"], nachricht.as_string())
            server.quit()
        except Exception as e:
            write_log(
                "CRITICAL - " + time.strftime('%d.%m.%Y %X') + " - SMTP MAIL " + str(e))
            print(e)


def write_log(msg):  # Schreibt in die log datei falls eingeschaltet
    if cfg["log"]["enabled"]:
        try:
            f = open(cfg["log"]["file"], "a")
            f.write(msg + "\n")
            f.close()
        except:
            f = open(cfg["log"]["file"], "w+")
            f.write(msg + "\n")
            f.close()


try:
    cfg = read_config(config())  # Erstes setzen der cfg liste
except Exception as e:
    print("Configfile error: " + str(e))
    f = open("settings.ini", "w")
    f.write("\n")
    f.close()
    cfg = read_config(config())

state = {"CPU": 0, "MEM": 0}  # Erstellen der liste zum abspeichern des status von den Sensoren
for d in get_all_drives()["speicher"]:
    state.update({d: 0})
