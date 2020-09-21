import serial
import paho.mqtt.client as mqtt
import json 
from effekta_ax_test_class import EffektaConn
import _thread
from threading import Thread
import time
import datetime
from Wetterbericht import getSonnenStunden
from Secret import getPassMqtt
from Secret import getUserMqtt
from Secret import getPassBMS

#import Wetterbericht
 
 
#Globals
 
beVerbose = False
beVerboseEffekta = False
#beVerbose = True
#beVerboseEffekta = True

# Skript Start. Wenn autoInit dann wird StarteMitAkku ignoriert
StarteMitAkku = True
AutoInitWrMode = True


#EffektaSerialNames = {"WR1" : '/dev/ttyUSB1'}
#EffektaSerialNames = {"WR1" : '/dev/ttyUSB1', "WR2" : '/dev/ttyUSB3'}

# usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0  usb-FTDI_USB_Serial_Converter_FT8X1284-if00-port0  usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0

EffektaData = {"WR1" : {"Serial" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0'}, "WR2" : {"Serial" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9HSILDS-if00-port0'}}

#EffektaSerialNames = {"WR1" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0', "WR2" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9HSILDS-if00-port0'}

#BmsSerial = '/dev/ttyUSB0'
BmsSerial = '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'

VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
BattLeer = "PSDV43.0"
BattWiederEntladen = "PBDV48.0"

BattCurrent = 0.0     # BattCurrent updated with higher frequency
InitAkkuProz = -1
BmsWerte = {"AkkuStrom": BattCurrent, "Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "AkkuProz": InitAkkuProz, "Ladephase": "none", "BmsEntladeFreigabe":True, "WrEntladeFreigabe":True, "WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":""}

SkriptWerte = {}


client = mqtt.Client() 

def myPrint(msg):
    temp = msg.split()
    if "Info:" in temp or "Error:" in temp:
        try:
            client.publish("PV/Skript/Info", msg)
        except:
            myPrint("mqtt konnte nicht gesendet werden")
    if beVerbose:
        print(msg)

def mqttconnect():

    client.username_pw_set(getUserMqtt(),getPassMqtt())
    client.connect( "192.168.178.38" , 1883 , 60 ) 
    client.loop_start() 
    client.subscribe("PV/BMS/command") 

def on_connect(client, userdata, flags, rc):
    global EffektaData
    
    # subscribe or resubscribe effektas
    for name in list(EffektaData.keys()):
        client.subscribe("PV/" + name + "/command")
    
    client.subscribe("PV/allWr/command")

    myPrint("MQTT Connected with result code " + str(rc))

def on_message(client, userdata, msg):
    global EffektaData
    global BmsWerte
    
    tempTopic = str(msg.topic)
    tempTopicList = tempTopic.split("/")
    
    # single Effekta commands
    if tempTopicList[1] in list(EffektaData.keys()) and tempTopicList[2] == "command":
        EffektaData[tempTopicList[1]]["EffektaCmd"].append(str(msg.payload.decode()))

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
        if str(msg.payload.decode()) == "NetzLadenAus":
            schalteAlleWrNetzLadenAus()
        if str(msg.payload.decode()) == "NetzLadenEin":
            schalteAlleWrNetzLadenEin()
    
    # get CompleteProduction from MQTT
    if tempTopicList[1] in list(EffektaData.keys()) and tempTopicList[2] == "CompleteProduction":
        EffektaData[tempTopicList[1]]["EffektaCmd"].append("CompleteProduction")    
        EffektaData[tempTopicList[1]]["EffektaCmd"].append(str(msg.payload.decode()))
        client.unsubscribe("PV/" + tempTopicList[1] + "/CompleteProduction")
    
        
def checkWerteSprung(newValue, oldValue, percent, min, max):
    
    # Diese Funktion prüft, dass der neue Wert innerhalb der angegebenen min max Grenzen und ausserhalb der angegebenen Prozent Grenze
    # Diese Funktion wird verwendet um kleine Wertsprünge rauszu Filtern und Werte Grenzen einzuhalten

    if newValue == oldValue == 0:
        myPrint("wert wird nicht uebernommen")
        return False
        
    percent = percent * 0.01
    valuePercent = abs(oldValue) * percent
    
    minPercent = oldValue - valuePercent
    maxPercent = oldValue + valuePercent
    
    if min <= newValue <= max and not (minPercent < newValue < maxPercent):
        myPrint("wert wird uebernommen")
        return True
    else:
        myPrint("wert wird nicht uebernommen")
        return False
       
def checkWerteSprungMaxJump(newValue, oldValue, jump):
    # Diese Funktion prüft, dass sich der neue Wert innerhalb des angegebenen Sprung befindet.
    # Diese Funktion wird verwendet um Ausreißer raus zu Filtern
    
    if newValue == oldValue == 0:
        myPrint("wert wird nicht uebernommen")
        return False
    
    minValue = oldValue - jump
    maxValue = oldValue + jump
    
    if (minValue < newValue < maxValue):
        myPrint("wert wird uebernommen")
        return True
    else:
        myPrint("wert wird nicht uebernommen")
        return False  

client.on_connect = on_connect
client.on_message = on_message

def schalteAlleWrAufAkku():
    global EffektaData
    global BmsWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(BattLeer)    # Batt undervoltage
        EffektaData[i]["EffektaCmd"].append(BattWiederEntladen)   # redischarge voltage
        #EffektaData[i]["EffektaCmd"].append("PDJ")       # PowerSaving disable PDJJJ
        EffektaData[i]["EffektaCmd"].append(VerbraucherAkku)       # load prio 00=Netz, 02=Batt
        EffektaData[i]["EffektaCmd"].append("PCP03")       # charge prio 02=Netz und pv, 03=pv
    BmsWerte["WrMode"] = VerbraucherAkku
    BmsWerte["WrEntladeFreigabe"] = True
    BmsWerte["WrNetzladen"] = False
        
def schalteAlleWrNetzLadenAus():
    # Funktion ok, wr schaltet netzladen aus
    global EffektaData
    global BmsWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append("PCP03")       # charge prio 02=Netz und pv, 03=pv    
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrNetzLadenEin():
    # Funktion ok, wr schaltet netzladen ein
    global EffektaData
    global BmsWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append("PCP02")       # charge prio 02=Netz und pv, 03=pv    
    BmsWerte["WrNetzladen"] = True

def schalteAlleWrVerbraucherPVundNetz():
    # Funktion noch nicht getestet
    global EffektaData
    global BmsWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(BattLeer)    # Batt undervoltage
        EffektaData[i]["EffektaCmd"].append(BattWiederEntladen)   # redischarge voltage
        #EffektaData[i]["EffektaCmd"].append("PDJ")       # PowerSaving disable PDJJJ
        EffektaData[i]["EffektaCmd"].append(VerbraucherPVundNetz)       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
    BmsWerte["WrMode"] = VerbraucherPVundNetz
    BmsWerte["WrEntladeFreigabe"] = True

def schalteAlleWrAufNetzOhneNetzLaden():
    # Diese Funktion ist dazu da, um den Akku zu schonen wenn lange schlechtes wetter ist und zu wenig PV leistung kommt sodass die Verbraucher versorgt werden können
    global EffektaData
    global BmsWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
        EffektaData[i]["EffektaCmd"].append(BattLeer)    # Batt undervoltage
        EffektaData[i]["EffektaCmd"].append(BattWiederEntladen)   # redischarge voltage
        EffektaData[i]["EffektaCmd"].append("PCP03")       # charge prio 02=Netz und pv, 03=pv
        #EffektaData[i]["EffektaCmd"].append("PEJ")       # PowerSaving enable PEJJJ
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrAufNetzMitNetzladen():
    # Test:
    # funktion aufrufen, wr schaltet dann auf netz, netz ausschalten, wr schaltet auf akku, akku entladen <48V, wr schaltet komplett ab, strom aus akku: 0A
    # ergebnis ok
    # wr schaltet sofort auf netz wenn zusätzlich dann der netz ausfällt schaltet er wieder auf batt bis diese <48V hat
    # bei wieder einschaltetn läd er mit netz wenn kein pv da ist. wenn pv dann kommt läd er damit zusätzlich
    global EffektaData
    global BmsWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt
        EffektaData[i]["EffektaCmd"].append("PBDV52.0")   # redischarge voltage
        EffektaData[i]["EffektaCmd"].append("PSDV48.0")    # Batt undervoltage
        EffektaData[i]["EffektaCmd"].append("MUCHGC002")   # Netz Ladestrom
        EffektaData[i]["EffektaCmd"].append("PCP02")       # charge prio 02=Netz und pv, 03=pv
        #EffektaData[i]["EffektaCmd"].append("PEJ")       # PowerSaving enable PEJJJ
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = True

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
                myPrint("convertError")
            break
        if i == b'Kleinste':
            try:   
                if checkWerteSprung(float(y[2]), BmsWerte["Vmin"], 1, -1, 10):
                    sendeMqtt = True
                    BmsWerte["Vmin"] = float(y[2])
            except:
                myPrint("convertError")
            break
        if i == b'Groeste':
            try:
                if checkWerteSprung(float(y[2]), BmsWerte["Vmax"], 1, -1, 10):
                    sendeMqtt = True
                    BmsWerte["Vmax"] = float(y[2])
            except:
                myPrint("convertError")
            break
        if i == b'SOC':
            try:
                if checkWerteSprung(float(y[1]), BmsWerte["AkkuAh"], 5, -2000, 2000): 
                    sendeMqtt = True
                    BmsWerte["AkkuAh"] = float(y[1])
            except:
                myPrint("convertError")
        if i == b'SOC':
            try:
                if BmsWerte["AkkuProz"] == InitAkkuProz:
                    if checkWerteSprung(float(y[3]), BmsWerte["AkkuProz"], 1, -101, 101): 
                        sendeMqtt = True
                        BmsWerte["AkkuProz"] = float(y[3])
                else:
                    if checkWerteSprung(float(y[3]), BmsWerte["AkkuProz"], 1, -101, 101) and checkWerteSprungMaxJump(float(y[3]), BmsWerte["AkkuProz"], 10): 
                        sendeMqtt = True
                        BmsWerte["AkkuProz"] = float(y[3])
            except:
                myPrint("convertError")
            break
        if i == b'Ladephase:':
            lastLine = True
            try:
                if BmsWerte["Ladephase"] != y[1].decode():
                    sendeMqtt = True
                BmsWerte["Ladephase"] = y[1].decode()
            except:
                myPrint("convertError")
            break 
    
    
    if x == b'Rel fahren 1\r\n':
        if BmsWerte["BmsEntladeFreigabe"] == False:
            BmsWerte["BmsEntladeFreigabe"] = True
            sendeMqtt = True
    elif x == b'Rel fahren 0\r\n':
        if BmsWerte["BmsEntladeFreigabe"] == True:
            BmsWerte["BmsEntladeFreigabe"] = False
            sendeMqtt = True
            
    if sendeMqtt == True: 
        sendeMqtt = False
        try: 
            client.publish("PV/BMS/istwerte", json.dumps(BmsWerte))
            myPrint(BmsWerte)
        except:
            myPrint("mqtt konnte nicht gesendet werden")
        
    myPrint(x)

    return lastLine

def autoInitInverter():
    global SkriptWerte
    global BmsWerte

    if 0 < BmsWerte["AkkuProz"] < SkriptWerte["schaltschwelleNetzLadenaus"]:
        myPrint("Autoinit: Schalte auf Netz mit Laden")
        schalteAlleWrAufNetzOhneNetzLaden()
        schalteAlleWrNetzLadenEin()    
    elif SkriptWerte["schaltschwelleNetzLadenaus"] <= BmsWerte["AkkuProz"] < SkriptWerte["schaltschwellePvNetz"]:
        schalteAlleWrAufNetzOhneNetzLaden()
        myPrint("Autoinit: Schalte auf Netz ohne Laden")            
    elif SkriptWerte["schaltschwellePvNetz"] <= BmsWerte["AkkuProz"] < SkriptWerte["schaltschwelleAkku"]:
        schalteAlleWrVerbraucherPVundNetz()  
        myPrint("Autoinit: Schalte auf PV und Netz")            
    elif BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleAkku"]:
        schalteAlleWrAufAkku()
        myPrint("Autoinit: Schalte auf Akku")    


EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False

def setInverterMode(wetterDaten):
    global SkriptWerte
    global BmsWerte
    global AutoInitWrMode
    global EntladeFreigabeGesendet
    global NetzLadenAusGesperrt
    
    now = datetime.datetime.now()
    sendeMqtt = False
    
    #SOC Schaltschwellen
    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
    SkriptWerte["schaltschwelleNetzLadenein"] = 7.0
    SkriptWerte["MinSoc"] = 10.0
    SkriptWerte["verbrauchNachtAkku"] = 25.0
    SkriptWerte["verbrauchNachtNetz"] = 3.0
    
    if BmsWerte["Akkuschutz"]:
        SkriptWerte["schaltschwelleAkku"] = 60.0
        SkriptWerte["schaltschwellePvNetz"] = 40.0
        SkriptWerte["schaltschwelleNetz"] = 30.0
    else:
        SkriptWerte["schaltschwelleAkku"] = 45.0
        SkriptWerte["schaltschwellePvNetz"] = 20.0
        SkriptWerte["schaltschwelleNetz"] = 15.0
        
    # Wetter Sonnenstunden Schaltschwellen
    SkriptWerte["wetterSchaltschwelleNetz"] = 6
        
    # Wenn init gesetzt ist und das BMS einen Akkuwert gesendet hat dann stellen wir einen Initial Zustand der Wr her
    if AutoInitWrMode == True and BmsWerte["AkkuProz"] != InitAkkuProz:
        AutoInitWrMode = False
        autoInitInverter()
        sendeMqtt = True
        
    # Wir setzen den Error bei 100 prozent zurück. In der Hoffunng dass nicht immer 100 prozent vom BMS kommen dieses fängt aber bei einem Neustart bei 0 proz an.
    if BmsWerte["AkkuProz"] >= 100.0:
        BmsWerte["Error"] = False
    
    # Wir prüfen als erstes ob die Freigabe vom BMS da ist und kein Akkustand Error vorliegt
    if BmsWerte["BmsEntladeFreigabe"] == True and BmsWerte["Error"] == False:
            # Wir wollen abschätzen ob wir auf Netz schalten müssen dazu soll abends geprüft werden ob noch genug energie für die Nacht zur verfügung steht
            # Dazu wird geprüft wie das Wetter (Sonnenstunden) am nächsten Tag ist und dementsprechend früher oder später umgeschaltet.
            # Wenn das Wetter am nächsten Tag schlecht ist macht es keinen Sinn den Akku leer zu machen und dann im Falle einer Unterspannung vom Netz laden zu müssen.
            # Die Prüfung ist nur Abends aktiv da man unter Tags eine andere Logig haben möchte.
        #now = datetime.datetime.now()
        if now.hour >= 17 and now.hour < 23:
        #if Zeit >= 17 and Zeit < 23:
            if "Tag_1" in wetterDaten:
                if wetterDaten["Tag_1"] != None:
                    if wetterDaten["Tag_1"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"]:
                    # Wir wollen den Akku schonen weil es nichts bringt wenn wir ihn leer machen
                        if BmsWerte["AkkuProz"] < (SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"]):
                            if BmsWerte["WrMode"] == VerbraucherAkku:
                                BmsWerte["Akkuschutz"] = True
                                sendeMqtt = True
                                schalteAlleWrAufNetzOhneNetzLaden()
                                myPrint("Info: Sonne morgen < %ih -> schalte auf Netz." %SkriptWerte["wetterSchaltschwelleNetz"])
                else:
                    myPrint("Info: Keine Wetterdaten")
        elif now.hour >= 8:
        #elif Zeit >= 8:
            # Ab hier beginnnt der Teil der die Anlage stufenweise wieder auf Akkubetrieb schaltet 
            # dieser Teil soll Tagsüber aktiv sein das macht Nachts keinen Sinn weil der Akkustand nicht steigt
            EntladeFreigabeGesendet = False
            # Wenn der Akku wieder über die schaltschwelleAkku ist dann wird er wieder Tag und Nacht genutzt
            if not BmsWerte["WrMode"] == VerbraucherAkku and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleAkku"]:
                schalteAlleWrAufAkku()
                BmsWerte["Akkuschutz"] = False
                sendeMqtt = True
                myPrint("Info: Schalte alle WR auf Akku")
            # Wenn der Akku über die schaltschwellePvNetz ist dann geben wir den Akku wieder frei wenn PV verfügbar ist. PV (Tag), Netz (Nacht)
            elif BmsWerte["WrMode"] == VerbraucherNetz and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
                # Hier wird explizit nur geschalten wenn der WR auf VerbraucherNetz steht damit der Zweig nur reagiert wenn der Akku leer war und voll wird 
                schalteAlleWrNetzLadenAus()
                schalteAlleWrVerbraucherPVundNetz()
                NetzLadenAusGesperrt = False
                sendeMqtt = True
                myPrint("Info: Schalte alle WR Verbraucher PV und Netz")
        # Ab hier beginnt der Teil der die Anlage auf  Netz schaltet sowie das Netzladen ein und aus schaltet
        # Wir schalten auf Netz wenn der min Soc unterschritten wird
        if BmsWerte["WrMode"] == VerbraucherAkku and BmsWerte["AkkuProz"] <= SkriptWerte["MinSoc"]:
            schalteAlleWrAufNetzOhneNetzLaden()
            sendeMqtt = True
            myPrint("Schalte alle WR Netz ohne laden. MinSOC.")
            myPrint("Info: MinSoc %iP erreicht -> schalte auf Netz." %SkriptWerte["MinSoc"])
        # Wenn das Netz Laden durch eine Unterspannungserkennung eingeschaltet wurde schalten wir es aus wenn der Akku wieder 10% hat
        elif BmsWerte["WrNetzladen"] == True and NetzLadenAusGesperrt == False and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
            schalteAlleWrNetzLadenAus()
            sendeMqtt = True
            myPrint("Schalte alle WR Netz laden aus")
            myPrint("Info: NetzLadenaus %iP erreicht -> schalte Laden aus." %SkriptWerte["schaltschwelleNetzLadenaus"])
        # Wenn die Verbraucher auf PV (Tag) und Netz (Nacht) geschaltet wurden und der Akku wieder unter die schaltschwelleNetz fällt dann wird auf Netz geschaltet
        elif BmsWerte["WrMode"] == VerbraucherPVundNetz and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetz"]:
            schalteAlleWrAufNetzOhneNetzLaden()
            sendeMqtt = True
            myPrint("Info: Schalte auf Netz")
        elif BmsWerte["WrMode"] != VerbraucherAkku and BmsWerte["WrNetzladen"] == False and BmsWerte["Akkuschutz"] == False and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetzLadenaus"] and BmsWerte["AkkuProz"] > 0.0:
            BmsWerte["Akkuschutz"] = True
            sendeMqtt = True
            myPrint("Schalte Akkuschutz ein")
            myPrint("Info: %iP erreicht -> schalte Akkuschutz ein." %SkriptWerte["schaltschwelleNetzLadenaus"])
        elif BmsWerte["WrNetzladen"] == False and BmsWerte["Akkuschutz"] == True and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetzLadenein"]:
            schalteAlleWrNetzLadenEin()
            sendeMqtt = True
            myPrint("Info: Schalte Netz mit laden")
    elif EntladeFreigabeGesendet == False:
        EntladeFreigabeGesendet = True
        schalteAlleWrAufNetzMitNetzladen()
        # Falls der Akkustand zu hoch ist würde nach einer Abschaltung das Netzladen gleich wieder abgeschaltet werden das wollen wir verhindern
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
            # Wenn eine Unterspannnung SOC > schaltschwelleNetzLadenaus ausgelöst wurde dann stimmt mit dem SOC etwas nicht der wird bei schaltschwelle PVNEtz wieder zurück gesetzt
            NetzLadenAusGesperrt = True
            BmsWerte["Akkuschutz"] = True
            sendeMqtt = True
            myPrint("Error: Ladestand weicht ab")
        # wir setzen einen error weil das nicht plausibel ist und wir hin und her schalten sollte die freigabe wieder kommen
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
            BmsWerte["Error"] = True
            myPrint("Error: Ladestand nicht plausibel")
        sendeMqtt = True
        myPrint("Info: Schalte auf Netz mit laden")

    if sendeMqtt == True: 
        sendeMqtt = False
        try: 
            client.publish("PV/BMS/istwerte", json.dumps(BmsWerte))
            client.publish("PV/Skript/istwerte", json.dumps(SkriptWerte))
            myPrint(BmsWerte)
        except:
            myPrint("mqtt konnte nicht gesendet werden")


def GetAndSendEffektaData(name, serial, beVerbose):

    
    global BattCurrent
    global EffektaData
    sendeMqtt = False
    
    WR = EffektaConn(name, serial, beVerbose)
    
    EffektaData[WR.EffektaName()]["EffektaWerte"] = {"timeStamp": 0, "Netzspannung": 0, "AcOutPowerW": 0, "PvPower": 0, "BattChargCurr": 0, "BattDischargCurr": 0, "ActualMode": "", "DailyProduction": 0.0, "CompleteProduction": 0, "DailyCharge": 0.0, "DailyDischarge": 0.0}
    
    effekta_Query_Cycle = 20
    writeErrors = 0
    tempDailyProduction = 0.0
    battEnergyCycle = 8 
    timestampbattEnergyCycle = 0
    tempDailyDischarge = 0.0
    tempDailyCharge = 0.0
    #print(WR.getEffektaData("QPIRI"))
    
    while(1):
        if EffektaData[WR.EffektaName()]["EffektaWerte"]["timeStamp"] + effekta_Query_Cycle < time.time():
            EffektaData[WR.EffektaName()]["EffektaWerte"]["timeStamp"] = time.time()
            EffekaQPIGS = WR.getEffektaData("QPIGS") # Device general status parameters inquiry
            ActualMode = WR.getEffektaData("QMOD")

            if len(ActualMode) > 0:
                if EffektaData[WR.EffektaName()]["EffektaWerte"]["ActualMode"] != ActualMode:
                    sendeMqtt = True
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["ActualMode"] = ActualMode
            if len(EffekaQPIGS) > 0:
                (Netzspannung, Netzfrequenz, AcOutSpannung, AcOutFrequenz, AcOutPowerVA, AcOutPowerW, AcOutLoadProz, BusVoltage, BattVoltage, BattChargCurr, BattCapazity, InverterTemp, PvCurrent, PvVoltage, BattVoltageSCC, BattDischargCurr, DeviceStatus1, BattOffset, EeVersion, PvPower, DeviceStatus2) = EffekaQPIGS.split()
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["Netzspannung"], int(float(Netzspannung)), 3, -1, 10000):
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["Netzspannung"] = int(float(Netzspannung))
                    sendeMqtt = True                
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["AcOutPowerW"], int(AcOutPowerW), 10, -1, 10000):
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["AcOutPowerW"] = int(AcOutPowerW)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["PvPower"], int(PvPower), 10, -1, 10000):
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["PvPower"] = int(PvPower)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["BattChargCurr"], int(BattChargCurr), 10, -1, 10000):
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["BattChargCurr"] = int(BattChargCurr)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["BattDischargCurr"], int(BattDischargCurr), 10, -1, 10000):
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["BattDischargCurr"] = int(BattDischargCurr)
                    sendeMqtt = True
                
            tempDailyProduction = tempDailyProduction + (int(PvPower) * effekta_Query_Cycle / 60 / 60 / 1000)
            EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyProduction"] = round(tempDailyProduction, 2)
            
        if len(EffekaQPIGS) > 0:
            if timestampbattEnergyCycle + battEnergyCycle < time.time():
                timestampbattEnergyCycle = time.time()
                if BattCurrent > 0:
                    tempDailyCharge = tempDailyCharge  + ((float(BattVoltage) * BattCurrent) * battEnergyCycle / 60 / 60 / 1000)
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyCharge"] = round(tempDailyCharge, 2)         
                elif BattCurrent < 0:
                    tempDailyDischarge = tempDailyDischarge  + ((float(BattVoltage) * abs(BattCurrent)) * battEnergyCycle / 60 / 60 / 1000)
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyDischarge"] = round(tempDailyDischarge, 2)     

        
        now = datetime.datetime.now()
        if now.hour == 23:
            if EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyProduction"] > 0.0:
                EffektaData[WR.EffektaName()]["EffektaWerte"]["CompleteProduction"] = EffektaData[WR.EffektaName()]["EffektaWerte"]["CompleteProduction"] + round(EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyProduction"])
                EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyProduction"] = 0.0
                tempDailyProduction = 0.0
            EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyDischarge"] = 0.0
            tempDailyDischarge = 0.0
            EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyCharge"] = 0.0
            tempDailyCharge = 0.0
            
        
        # sende Kommandos aus der EffektaCmd Liste. Wenn das Kommando erfolreich gesendet wurde löschen wir es sofort ansonsten probieren wir es noch
        # weitere 9 mal und geben dann einen Error per MQTT zurück
        if len(EffektaData[WR.EffektaName()]["EffektaCmd"]) > 0:
            # QuickFix damit CompleteProduction empfangen werden kann.
            if EffektaData[WR.EffektaName()]["EffektaCmd"][0] == "CompleteProduction":
                EffektaData[WR.EffektaName()]["EffektaWerte"]["CompleteProduction"] = int(EffektaData[WR.EffektaName()]["EffektaCmd"][1])
                del EffektaData[WR.EffektaName()]["EffektaCmd"][1]
                del EffektaData[WR.EffektaName()]["EffektaCmd"][0]
            else:
                stateMsg = ""
                cmd = EffektaData[WR.EffektaName()]["EffektaCmd"][0]
                if WR.setEffektaData(EffektaData[WR.EffektaName()]["EffektaCmd"][0]):
                    writeErrors = 0
                    stateMsg = "Send cmd %s to %s. Ok."
                    del EffektaData[WR.EffektaName()]["EffektaCmd"][0]
                    # Timestamp faken damit er gleich ausliest wenn keine Kommandos mehr zu senden sind
                    if len(EffektaData[WR.EffektaName()]["EffektaCmd"]) == 0:
                        EffektaData[WR.EffektaName()]["EffektaWerte"]["timeStamp"] = EffektaData[WR.EffektaName()]["EffektaWerte"]["timeStamp"] - effekta_Query_Cycle
                else:
                    writeErrors += 1
                    stateMsg = "Send cmd %s to %s. Retry."
                    if writeErrors >= 10:
                        writeErrors = 0
                        stateMsg = "Send cmd %s to %s. Error."
                        myPrint("Error: send cmd %s to %s" %(cmd, WR.EffektaName()))
                        del EffektaData[WR.EffektaName()]["EffektaCmd"][0]
                try: 
                    client.publish("PV/" + WR.EffektaName() + "/cmdState", stateMsg %(cmd, WR.EffektaName()))
                except:
                    myPrint("mqtt konnte nicht gesendet werden")
                        

        if sendeMqtt == True: 
            sendeMqtt = False
            try: 
                topic = "PV/" + WR.EffektaName() + "/istwerte"
                client.publish(topic, json.dumps(EffektaData[WR.EffektaName()]["EffektaWerte"]))
                topic = "PV/" + WR.EffektaName() + "/CompleteProduction"
                client.publish(topic, str(EffektaData[WR.EffektaName()]["EffektaWerte"]["CompleteProduction"]), retain=True)
                myPrint(EffektaData[WR.EffektaName()]["EffektaWerte"])
                myPrint(topic)
            except:
                myPrint("mqtt konnte nicht gesendet werden")
    
    
def handleWeather(wetterdaten):
    publishWeather = False
    initWeather = False
    now = datetime.datetime.now()
    if "lastrequest" not in wetterdaten:
        wetterdaten["lastrequest"] = 0
        initWeather = True
        
    # Wir wollen das Wetter um 15 und um 6 Uhr holen
    if (now.hour == 15 and wetterdaten["lastrequest"] != 15) or (now.hour == 6 and wetterdaten["lastrequest"] != 6) or initWeather:
        wetterdaten["lastrequest"] = now.hour
        publishWeather = True
        try:
            wetterdaten.update(getSonnenStunden())
            #tempWetter = getSonnenStunden()
            #wetterdaten.update( (k,v) for k,v in tempWetter.items() if v is not None)
        except:
            myPrint("Info: Wetter Daten konnten nicht geholt werden!")
            
    # Wenn der Tag_1 dem aktuellen Tag entspricht dann müssen wir die Tage um eins verrutschen
    # wir fragen zurest ab ob der key vorhanden ist denn es kann sein dass das Dict leer ist.
    if "Tag_1" in wetterdaten: 
        tempDate = wetterdaten["Tag_1"]["Datum"].split(".")
        if now.day == int(tempDate[0]):
            publishWeather = True
            if "Tag_1" in wetterdaten:
                wetterDaten["Tag_0"] = wetterDaten["Tag_1"]
            if "Tag_2" in wetterdaten:
                wetterDaten["Tag_1"] = wetterDaten["Tag_2"]
            if "Tag_3" in wetterdaten:
                wetterDaten["Tag_2"] = wetterDaten["Tag_3"]
            # Wir füllen von hinten mit None auf
            wetterDaten["Tag_4"] = None
            wetterDaten["Tag_3"] = wetterDaten["Tag_4"]
            
    if publishWeather:
        try: 
            topic = "PV/Wetter"
            client.publish(topic, json.dumps(wetterdaten), retain = True)           
        except:
            myPrint("Wetter Daten konnten nicht gesendet werden") 
            
    return wetterdaten



mqttconnect()

# Init Threads and globals for Effektas
for name in list(EffektaData.keys()):
    EffektaData[name]["EffektaCmd"] = []
    t = Thread(target=GetAndSendEffektaData, args=(name, EffektaData[name]["Serial"], beVerboseEffekta,))
    t.start()
    client.subscribe("PV/" + name + "/CompleteProduction")

# Warten bis CompleteProduction per MQTT kommt weil es kann mit schalteAlleWrAufAkku() oder schalteAlleWrAufNetzMitNetzladen() konflikte geben
time.sleep(1)

serBMS = serial.Serial(BmsSerial, 9600)  # open serial port

#serBMS.write(b'vsoc 3300')
#serBMS.write(b'vsoc 3530')

#serBMS.write(b'vleer2750')
#serBMS.write(b'cap260') # 267 ware es auch schon

#serBMS.write(b'file')

#serBMS.write(b'file')
#serBMS.write(b'vsoc 3550')
#serBMS.write(b'vsoc 3550')
#serBMS.write(b'sensor 200')


#serBMS.write(b'vbal 3550')
#serBMS.write(b'vbal 3500')
#serBMS.write(b'vvoll 3900')
#serBMS.write(b'start')


# Initial Zustand manuell herstellen damit das Umschalten bei leerem und voll werdenden Akku funktioniert
if not AutoInitWrMode:
    if StarteMitAkku:
        schalteAlleWrAufAkku()
        myPrint("ManualInit: schalte auf Akku")    
    else:
        schalteAlleWrAufNetzOhneNetzLaden()
        myPrint("ManualInit: schalte auf Netz ohne Laden")    
        
myPrint("starte main loop")

wetterdaten = {}

while 1:
    
    try:
        GetAndSendBmsData()
    except:
        myPrint("BMS read error. Init Serial again!")
        try:
            serBMS.close()  
            serBMS.open()  
        except:
            myPrint("BMS reInit Serial failed!")        
    
    setInverterMode(wetterdaten)
    
    wetterdaten = handleWeather(wetterdaten)
    

