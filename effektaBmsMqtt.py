import serial
import paho.mqtt.client as mqtt
import json 
from effekta_ax_test_class import EffektaConn
import _thread
from threading import Thread
import time
import datetime
 
 
#Globals
 
beVerbose = False
beVerboseEffekta = False
#beVerbose = True
#beVerboseEffekta = True

# Skript Start. Wenn autoInit dann wird StarteMitAkku ignoriert
StarteMitAkku = True
AutoInitWrMode = True


EffektaCmd = {}
#EffektaSerialNames = {"WR1" : '/dev/ttyUSB1'}
#EffektaSerialNames = {"WR1" : '/dev/ttyUSB1', "WR2" : '/dev/ttyUSB3'}

# usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0  usb-FTDI_USB_Serial_Converter_FT8X1284-if00-port0  usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0
EffektaSerialNames = {"WR1" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0', "WR2" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9HSILDS-if00-port0'}
#EffektaSerialNames = {}
#BmsSerial = '/dev/ttyUSB0'
BmsSerial = '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'
BattCurrent = 0.0 

VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
BattLeer = "PSDV43.0"
BattWiederEntladen = "PBDV48.0"


client = mqtt.Client() 

def mqttconnect():
    client.connect("192.168.178.38", 1883, 60) 
    client.loop_start()
    client.subscribe("PV/BMS/command")

def on_connect(client, userdata, flags, rc):
    
    # subscribe or resubscribe effektas
    for name in list(EffektaCmd.keys()):
        client.subscribe("PV/" + name + "/command")
    
    client.subscribe("PV/allWr/command")

    if beVerbose == True:
        print("MQTT Connected with result code " + str(rc))

def on_message(client, userdata, msg):
    global EffektaCmd
    global BmsWerte
    
    tempTopic = str(msg.topic)
    tempTopicList = tempTopic.split("/")
    
    # single Effekta commands
    if tempTopicList[1] in list(EffektaSerialNames.keys()) and tempTopicList[2] == "command":
        EffektaCmd[tempTopicList[1]].append(str(msg.payload.decode()))

    # all Effekta/Skript commands
    if tempTopicList[1] == "allWr" and tempTopicList[2] == "command":
        if str(msg.payload.decode()) == "WrAufAkku":
            schalteAlleWrAufAkku()
        if str(msg.payload.decode()) == "WrAufNetz":
            schalteAlleWrAufNetzOhneNetzLaden()
        if str(msg.payload.decode()) == "WrVerbraucherPVundNetz":
            schalteAlleWrVerbraucherPVundNetz();
        if str(msg.payload.decode()) == "AkkuschutzEin":
            BmsWerte["Akkuschutz"] = True
        if str(msg.payload.decode()) == "AkkuschutzAus":
            BmsWerte["Akkuschutz"] = False
    
    # get CompleteProduction from MQTT
    if tempTopicList[1] in list(EffektaSerialNames.keys()) and tempTopicList[2] == "CompleteProduction":
        EffektaCmd[tempTopicList[1]].append("CompleteProduction")    
        EffektaCmd[tempTopicList[1]].append(str(msg.payload.decode()))
        client.unsubscribe("PV/" + tempTopicList[1] + "/CompleteProduction")
    
        
def checkWerteSprung(newValue, oldValue, percent, min, max):

    if newValue == oldValue == 0:
        if beVerbose == True:
            print("wert wird nicht uebernommen")
        return False
        
    percent = percent * 0.01
    valuePercent = abs(oldValue) * percent
    
    minPercent = oldValue - valuePercent
    maxPercent = oldValue + valuePercent
    
    if min <= newValue <= max and not (minPercent < newValue < maxPercent):
        if beVerbose == True:
            print("wert wird uebernommen")
        return True
    else:
        if beVerbose == True:
            print("wert wird nicht uebernommen")
        return False
       
        

client.on_connect = on_connect
client.on_message = on_message


#serBMS.write(b'PwlLHC')
#serBMS.write(b'file')
#serBMS.write(b'vsoc 3550')
#serBMS.write(b'vsoc 3550')
#serBMS.write(b'sensor 200')


#serBMS.write(b'vbal 3550')
#serBMS.write(b'vbal 3500')
#serBMS.write(b'vvoll 3900')
#serBMS.write(b'start')



def schalteAlleWrAufAkku():
    global EffektaCmd
    for i in list(EffektaSerialNames.keys()):
        EffektaCmd[i].append(BattLeer)    # Batt undervoltage
        EffektaCmd[i].append(BattWiederEntladen)   # redischarge voltage
        EffektaCmd[i].append(VerbraucherAkku)       # load prio 00=Netz, 02=Batt
        EffektaCmd[i].append("PCP03")       # charge prio 02=Netz und pv, 03=pv
    BmsWerte["WrMode"] = VerbraucherAkku
    BmsWerte["WrEntladeFreigabe"] = True
    BmsWerte["WrNetzladen"] = False
        
def schalteAlleWrNetzLadenAus():
    # Funktion ok, wr schaltet netzladen aus
    global EffektaCmd
    for i in list(EffektaSerialNames.keys()):
        EffektaCmd[i].append("PCP03")       # charge prio 02=Netz und pv, 03=pv    
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrNetzLadenEin():
    # Funktion ok, wr schaltet netzladen ein
    global EffektaCmd
    for i in list(EffektaSerialNames.keys()):
        EffektaCmd[i].append("PCP02")       # charge prio 02=Netz und pv, 03=pv    
    BmsWerte["WrNetzladen"] = True

def schalteAlleWrVerbraucherPVundNetz():
    # Funktion noch nicht getestet
    global EffektaCmd
    for i in list(EffektaSerialNames.keys()):
        EffektaCmd[i].append(BattLeer)    # Batt undervoltage
        EffektaCmd[i].append(BattWiederEntladen)   # redischarge voltage
        EffektaCmd[i].append(VerbraucherPVundNetz)       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
    BmsWerte["WrMode"] = VerbraucherPVundNetz
    BmsWerte["WrEntladeFreigabe"] = True

def schalteAlleWrAufNetzOhneNetzLaden():
    # Diese Funktion ist dazu da, um den Akku zu schonen wenn lange schlechtes wetter ist und zu wenig PV leistung kommt sodass die Verbraucher versorgt werden können
    global EffektaCmd
    for i in list(EffektaSerialNames.keys()):
        EffektaCmd[i].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
        EffektaCmd[i].append(BattLeer)    # Batt undervoltage
        EffektaCmd[i].append(BattWiederEntladen)   # redischarge voltage
        EffektaCmd[i].append("PCP03")       # charge prio 02=Netz und pv, 03=pv
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrAufNetz():
    # Test:
    # funktion aufrufen, wr schaltet dann auf netz, netz ausschalten, wr schaltet auf akku, akku entladen <48V, wr schaltet komplett ab, strom aus akku: 0A
    # ergebnis ok
    # wr schaltet sofort auf netz wenn zusätzlich dann der netz ausfällt schaltet er wieder auf batt bis diese <48V hat
    # bei wieder einschaltetn läd er mit netz wenn kein pv da ist. wenn pv dann kommt läd er damit zusätzlich
    global EffektaCmd
    for i in list(EffektaSerialNames.keys()):
        EffektaCmd[i].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt
        EffektaCmd[i].append("PBDV52.0")   # redischarge voltage
        EffektaCmd[i].append("PSDV48.0")    # Batt undervoltage
        EffektaCmd[i].append("MUCHGC002")   # Netz Ladestrom
        EffektaCmd[i].append("PCP02")       # charge prio 02=Netz und pv, 03=pv
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = True

BmsWerte = {"AkkuStrom": 0.0, "Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "AkkuProz": 0, "Ladephase": "none", "BmsEntladeFreigabe":True, "WrEntladeFreigabe":True, "WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":""}

EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False

def GetAndSendBmsData():
    global BattCurrent

    sendeMqtt = False
    lastLine = False
    # Wir lesen alle Zeilen der Serial parsen nach Schlüsselwörten und holen uns die Werte raus.
    # Es kann sein, dass Übertragungsfehler auftreten, in dem Fall fängt das das try except bez die Prüfung des Wertebereichs ab.
    x = serBMS.readline()
    y = x.split()
    for i in y:
        if i == b'Strom':
            try:
                if checkWerteSprung(float(y[3]), BmsWerte["AkkuStrom"], 20, -1000, 1000):
                    sendeMqtt = True
                    BmsWerte["AkkuStrom"] = float(y[3])
                    BattCurrent = BmsWerte["AkkuStrom"]
            except:
                if beVerbose == True:
                    print("convertError")
            break
        if i == b'Kleinste':
            try:   
                if checkWerteSprung(float(y[2]), BmsWerte["Vmin"], 1, -1, 10):
                    sendeMqtt = True
                    BmsWerte["Vmin"] = float(y[2])
            except:
                if beVerbose == True:
                    print("convertError")
            break
        if i == b'Groeste':
            try:
                if checkWerteSprung(float(y[2]), BmsWerte["Vmax"], 1, -1, 10):
                    sendeMqtt = True
                    BmsWerte["Vmax"] = float(y[2])
            except:
                if beVerbose == True:
                    print("convertError")
            break
        if i == b'SOC':
            try:
                if checkWerteSprung(float(y[1]), BmsWerte["AkkuAh"], 5, -2000, 2000): 
                    sendeMqtt = True
                    BmsWerte["AkkuAh"] = float(y[1])
            except:
                if beVerbose == True:
                    print("convertError")
        if i == b'SOC':
            try:
                if checkWerteSprung(float(y[3]), BmsWerte["AkkuProz"], 1, -101, 101): 
                    sendeMqtt = True
                    BmsWerte["AkkuProz"] = float(y[3])
            except:
                if beVerbose == True:
                    print("convertError")
            break
        if i == b'Ladephase:':
            lastLine = True
            try:
                if BmsWerte["Ladephase"] != y[1].decode():
                    sendeMqtt = True
                BmsWerte["Ladephase"] = y[1].decode()
            except:
                if beVerbose == True:
                    print("convertError")
            break 
    
    
    if x == b'Rel fahren 1\r\n':
        if BmsWerte["BmsEntladeFreigabe"] == False:
            BmsWerte["BmsEntladeFreigabe"] = True
            sendeMqtt = True
    elif x == b'Rel fahren 0\r\n':
        if BmsWerte["BmsEntladeFreigabe"] == True:
            BmsWerte["BmsEntladeFreigabe"] = False
            sendeMqtt = True

    global AutoInitWrMode
    global EntladeFreigabeGesendet
    global NetzLadenAusGesperrt
    
    SkriptWerte = {}
    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
    
    if BmsWerte["Akkuschutz"]:
        SkriptWerte["schaltschwelleAkku"] = 60.0
        SkriptWerte["schaltschwellePvNetz"] = 40.0
        SkriptWerte["schaltschwelleNetz"] = 30.0
    else:
        SkriptWerte["schaltschwelleAkku"] = 45.0
        SkriptWerte["schaltschwellePvNetz"] = 30.0
        SkriptWerte["schaltschwelleNetz"] = 15.0
        
    # Wenn init gesetzt ist und das BMS einen Akkuwert gesendet hat dann stellen wir einen Initial Zustand der Wr her
    if AutoInitWrMode == True and BmsWerte["AkkuProz"] > 0:
        AutoInitWrMode = False
        if 0 < BmsWerte["AkkuProz"] < SkriptWerte["schaltschwelleNetzLadenaus"]:
            if beVerbose == True:
                print("Autoinit: Schalte auf Netz mit Laden")
            schalteAlleWrAufNetzOhneNetzLaden()
            schalteAlleWrNetzLadenEin()    
        elif SkriptWerte["schaltschwelleNetzLadenaus"] <= BmsWerte["AkkuProz"] < SkriptWerte["schaltschwellePvNetz"]:
            schalteAlleWrAufNetzOhneNetzLaden()
            if beVerbose == True:
                print("Autoinit: Schalte auf Netz ohne Laden")            
        elif SkriptWerte["schaltschwellePvNetz"] <= BmsWerte["AkkuProz"] < SkriptWerte["schaltschwelleAkku"]:
            schalteAlleWrVerbraucherPVundNetz()  
            if beVerbose == True:
                print("Autoinit: Schalte auf PV und Netz")            
        elif BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleAkku"]:
            schalteAlleWrAufAkku()
            if beVerbose == True:
                print("Autoinit: Schalte auf Akku")            
        
    # Wir setzen den Error bei 100 prozent zurück. In der Hoffunng dass nicht immer 100 prozent vom BMS kommen dieses fängt aber bei einem Neustart bei 0 proz an.
    if BmsWerte["AkkuProz"] >= 100.0:
        BmsWerte["Error"] = False
        
    if BmsWerte["BmsEntladeFreigabe"] == True and BmsWerte["Error"] == False:
        EntladeFreigabeGesendet = False
        # Wenn der Akku wieder über die schaltschwelleAkku ist dann wird er wieder Tag und Nacht genutzt
        if not BmsWerte["WrMode"] == VerbraucherAkku and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleAkku"]:
            schalteAlleWrAufAkku()
            BmsWerte["Akkuschutz"] = False
            sendeMqtt = True
            if beVerbose == True:
                print("Schalte alle WR auf Akku")
        # Wenn der Akku über die schaltschwellePvNetz ist dann geben wir den Akku wieder frei wenn PV verfügbar ist. PV (Tag), Netz (Nacht)
        elif BmsWerte["WrMode"] == VerbraucherNetz and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
            # Hier wird explizit nur geschalten wenn der WR auf VerbraucherNetz steht damit der Zweig nur reagiert wenn der Akku leer war und voll wird 
            schalteAlleWrNetzLadenAus()
            schalteAlleWrVerbraucherPVundNetz()
            NetzLadenAusGesperrt = False
            sendeMqtt = True
            if beVerbose == True:
                print("Schalte alle WR Verbraucher PV und Netz")
        # Wenn die Verbraucher auf PV (Tag) und Netz (Nacht) geschaltet wurden und der Akku wieder unter die schaltschwelleNetz fällt dann wird auf Netz geschaltet
        elif BmsWerte["WrMode"] == VerbraucherPVundNetz and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetz"]:
            schalteAlleWrAufNetzOhneNetzLaden()
            BmsWerte["Akkuschutz"] = True
            sendeMqtt = True
            if beVerbose == True:
                print("Schalte alle WR Netz ohne laden")
        # Wenn das Netz Laden durch eine Unterspannungserkennung eingeschaltet wurde schalten wir es aus wenn der Akku wieder 10% hat
        elif BmsWerte["WrNetzladen"] == True and NetzLadenAusGesperrt == False and BmsWerte["AkkuProz"] > SkriptWerte["schaltschwelleNetzLadenaus"]:
            schalteAlleWrNetzLadenAus()
            sendeMqtt = True
            if beVerbose == True:
                print("Schalte alle WR Netz laden aus")
        elif BmsWerte["WrNetzladen"] == False and BmsWerte["Akkuschutz"] == True and BmsWerte["AkkuProz"] < (SkriptWerte["schaltschwelleNetzLadenaus"] - 2):
            schalteAlleWrNetzLadenEin()
            sendeMqtt = True
            if beVerbose == True:
                print("Schalte alle WR Netz laden ein")
    elif EntladeFreigabeGesendet == False:
        EntladeFreigabeGesendet = True
        schalteAlleWrAufNetz()
        # Falls der Akkustand zu hoch ist würde nach einer Abschaltung das Netzladen gleich wieder abgeschaltet werden das wollen wir verhindern
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
            NetzLadenAusGesperrt = True
        # wir setzen einen error weil das nicht plausibel ist und wir hin und her schalten sollte die freigabe wieder kommen
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
            Bmswerte["Error"] = True
        sendeMqtt = True
        if beVerbose == True:
            print("Schalte alle WR auf Netz mit laden")

    if sendeMqtt == True: 
        sendeMqtt = False
        try: 
            client.publish("PV/BMS/istwerte", json.dumps(BmsWerte))
            client.publish("PV/Skript/istwerte", json.dumps(SkriptWerte))
            if beVerbose == True:
                print(BmsWerte)
        except:
            if beVerbose == True:
                print("mqtt konnte nicht gesendet werden")
        
    if beVerbose == True:
        print(x)

    return lastLine



def GetAndSendEffektaData(name, serial, beVerbose):

    EffektaWerte = {"timeStamp": 0, "Netzspannung": 0, "AcOutPowerW": 0, "PvPower": 0, "BattChargCurr": 0, "BattDischargCurr": 0, "ActualMode": "", "DailyProduction": 0.0, "CompleteProduction": 0, "DailyCharge": 0.0, "DailyDischarge": 0.0}
    
    global BattCurrent
    global EffektaCmd
    sendeMqtt = False
    
    WR = EffektaConn(name, serial, beVerbose)
    effekta_Query_Cycle = 20
    writeErrors = 0
    tempDailyProduction = 0.0
    battEnergyCycle = 8 
    timestampbattEnergyCycle = 0
    tempDailyDischarge = 0.0
    tempDailyCharge = 0.0
    #print(WR.getEffektaData("QPIRI"))
    
    while(1):
        if EffektaWerte["timeStamp"] + effekta_Query_Cycle < time.time():
            EffektaWerte["timeStamp"] = time.time()
            EffekaQPIGS = WR.getEffektaData("QPIGS") # Device general status parameters inquiry
            ActualMode = WR.getEffektaData("QMOD")

            if len(ActualMode) > 0:
                if EffektaWerte["ActualMode"] != ActualMode:
                    sendeMqtt = True
                    EffektaWerte["ActualMode"] = ActualMode
            if len(EffekaQPIGS) > 0:
                (Netzspannung, Netzfrequenz, AcOutSpannung, AcOutFrequenz, AcOutPowerVA, AcOutPowerW, AcOutLoadProz, BusVoltage, BattVoltage, BattChargCurr, BattCapazity, InverterTemp, PvCurrent, PvVoltage, BattVoltageSCC, BattDischargCurr, DeviceStatus1, BattOffset, EeVersion, PvPower, DeviceStatus2) = EffekaQPIGS.split()
                if checkWerteSprung(EffektaWerte["Netzspannung"], int(float(Netzspannung)), 3, -1, 10000):
                    EffektaWerte["Netzspannung"] = int(float(Netzspannung))
                    sendeMqtt = True                
                if checkWerteSprung(EffektaWerte["AcOutPowerW"], int(AcOutPowerW), 10, -1, 10000):
                    EffektaWerte["AcOutPowerW"] = int(AcOutPowerW)
                    sendeMqtt = True
                if checkWerteSprung(EffektaWerte["PvPower"], int(PvPower), 10, -1, 10000):
                    EffektaWerte["PvPower"] = int(PvPower)
                    sendeMqtt = True
                if checkWerteSprung(EffektaWerte["BattChargCurr"], int(BattChargCurr), 10, -1, 10000):
                    EffektaWerte["BattChargCurr"] = int(BattChargCurr)
                    sendeMqtt = True
                if checkWerteSprung(EffektaWerte["BattDischargCurr"], int(BattDischargCurr), 10, -1, 10000):
                    EffektaWerte["BattDischargCurr"] = int(BattDischargCurr)
                    sendeMqtt = True
                
            tempDailyProduction = tempDailyProduction + (int(PvPower) * effekta_Query_Cycle / 60 / 60 / 1000)
            EffektaWerte["DailyProduction"] = round(tempDailyProduction, 2)
            
        if len(EffekaQPIGS) > 0:
            if timestampbattEnergyCycle + battEnergyCycle < time.time():
                timestampbattEnergyCycle = time.time()
                if BattCurrent > 0:
                    tempDailyCharge = tempDailyCharge  + ((float(BattVoltage) * BattCurrent) * battEnergyCycle / 60 / 60 / 1000)
                    EffektaWerte["DailyCharge"] = round(tempDailyCharge, 2)         
                elif BattCurrent < 0:
                    tempDailyDischarge = tempDailyDischarge  + ((float(BattVoltage) * abs(BattCurrent)) * battEnergyCycle / 60 / 60 / 1000)
                    EffektaWerte["DailyDischarge"] = round(tempDailyDischarge, 2)     

        
        now = datetime.datetime.now()
        if now.hour == 23:
            if EffektaWerte["DailyProduction"] > 0.0:
                EffektaWerte["CompleteProduction"] = EffektaWerte["CompleteProduction"] + round(EffektaWerte["DailyProduction"])
                EffektaWerte["DailyProduction"] = 0.0
                tempDailyProduction = 0.0
            EffektaWerte["DailyDischarge"] = 0.0
            tempDailyDischarge = 0.0
            EffektaWerte["DailyCharge"] = 0.0
            tempDailyCharge = 0.0
            
        
        # sende Kommandos aus der EffektaCmd Liste. Wenn das Kommando erfolreich gesendet wurde löschen wir es sofort ansonsten probieren wir es noch
        # weitere 9 mal und geben dann einen Error per MQTT zurück
        if len(EffektaCmd[WR.EffektaName()]) > 0:
            # QuickFix damit CompleteProduction empfangen werden kann.
            if EffektaCmd[WR.EffektaName()][0] == "CompleteProduction":
                EffektaWerte["CompleteProduction"] = int(EffektaCmd[WR.EffektaName()][1])
                del EffektaCmd[WR.EffektaName()][1]
                del EffektaCmd[WR.EffektaName()][0]
            else:
                if WR.setEffektaData(EffektaCmd[WR.EffektaName()][0]):
                    writeErrors = 0
                    del EffektaCmd[WR.EffektaName()][0]
                    # Timestamp faken damit er gleich ausliest wenn keine Kommandos mehr zu senden sind
                    if len(EffektaCmd[WR.EffektaName()]) == 0:
                        EffektaWerte["timeStamp"] = EffektaWerte["timeStamp"] - effekta_Query_Cycle
                else:
                    writeErrors += 1
                    if writeErrors >= 10:
                        writeErrors = 0
                        del EffektaCmd[WR.EffektaName()][0]
                        topic = "PV/" + WR.EffektaName() + "/errors"
                        try: 
                            client.publish(topic, "Error cannot send command to %s" %WR.EffektaName())
                        except:
                            if beVerbose == True:
                                print("mqtt konnte nicht gesendet werden")

        if sendeMqtt == True: 
            sendeMqtt = False
            try: 
                topic = "PV/" + WR.EffektaName() + "/istwerte"
                client.publish(topic, json.dumps(EffektaWerte))
                topic = "PV/" + WR.EffektaName() + "/CompleteProduction"
                client.publish(topic, str(EffektaWerte["CompleteProduction"]), retain=True)
                if beVerbose == True:
                    print(EffektaWerte)
                    print(topic)
            except:
                if beVerbose == True:
                    print("mqtt konnte nicht gesendet werden")
    
    

# Efferkta Namens Liste anlegen damit die on_connect() sich auf die Namen subscriben kann
for name in list(EffektaSerialNames.keys()):
    EffektaCmd[name] = []

mqttconnect()

# Init Threads for Effektas
for name in list(EffektaSerialNames.keys()):
    t = Thread(target=GetAndSendEffektaData, args=(name, EffektaSerialNames[name], beVerboseEffekta,))
    t.start()
    client.subscribe("PV/" + name + "/CompleteProduction")

# Warten bis CompleteProduction per MQTT kommt weil es kann mit schalteAlleWrAufAkku() oder schalteAlleWrAufNetz() konflikte geben
time.sleep(1)

serBMS = serial.Serial(BmsSerial, 9600)  # open serial port

#serBMS.write(b'PwlLHC')
#serBMS.write(b'vsoc 3300')
#serBMS.write(b'vsoc 3530')

#serBMS.write(b'vleer2750')
#serBMS.write(b'cap260') # 267 ware es auch schon

#serBMS.write(b'file')

# Initial Zustand manuell herstellen damit das Umschalten bei leerem und voll werdenden Akku funktioniert
if not AutoInitWrMode:
    if StarteMitAkku:
        schalteAlleWrAufAkku()
        if beVerbose == True:
            print("ManualInit: schalte auf Akku")    
    else:
        schalteAlleWrAufNetzOhneNetzLaden()
        if beVerbose == True:
            print("ManualInit: schalte auf Netz ohne Laden")    
        
if beVerbose == True:
    print("starte main loop")

while 1:
    try:
        GetAndSendBmsData()
    except:
        if beVerbose == True:
            print("BMS read error. Init Serial again!")
        try:
            serBMS.close()  
            serBMS.open()  
            #del serBMS
            #serBMS = serial.Serial(BmsSerial, 9600)
        except:
            if beVerbose == True:
                print("BMS reInit Serial failed!")        
        
 