import serial
import paho.mqtt.client as mqtt
import json 
from effekta_ax_class import EffektaConn
import _thread
from threading import Thread
import time
import datetime
from Wetterbericht import getSonnenStunden
from Secret import getPassMqtt
from Secret import getUserMqtt
from Secret import getPassBMS
 
 
# Globals
# Define a emty string if not used

# Serielle Schnittstellen der Wechselrichter Soc Monitore und BMS
EffektaData = {"WR1" : {"Serial" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0'}, "WR2" : {"Serial" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9HSILDS-if00-port0'}}
BmsSerial = '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'
SocMonitorSerial = "/dev/serial/by-path/platform-20980000.usb-usb-0:1.3.4:1.0-port0"
UsbRelSerial = "/dev/serial/by-path/platform-20980000.usb-usb-0:1.2:1.0-port0"

# MqttBrokerIp
MqttBrokerIp = "192.168.178.38"

#Effekta Parameter die mit diesem Skript verstellt werden
BattLeer = "PSDV43.0"
BattWiederEntladen = "PBDV48.0"
NetzSchnellLadestrom = "MUCHGC030"
NetzErhaltungsLadestrom = "MUCHGC002"


# Skript Start. Wenn autoInit dann wird StarteMitAkku ignoriert. 
# Autoinit holt sich die letzten Daten vom mqtt Server. Wenn nicht verfügbar wird per SOC entschieden.
# StarteMitAkku = True und AutoInitWrMode = False dann wird die Anlage mit Akkubetrieb gestartet/umgeschaltet
StarteMitAkku = True
AutoInitWrMode = True


#Ausfuehrlich Skript Ausgabe zum debuggen
beVerbose = False
beVerboseEffekta = False
#beVerbose = True
#beVerboseEffekta = True




# Interne Konstanten und Variablen
VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
InitAkkuProz = -1
BmsWerte = {"Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "Ladephase": "none", "BmsEntladeFreigabe":True}
SkriptWerte = {"WrNetzladen":False, "Akkuschutz":False, "RussiaMode": False, "Error":False, "WrMode":"", "SkriptMode":"Auto", "PowerSaveMode":False, "schaltschwelleAkku":100.0, "schaltschwelleNetz":20.0, "schaltschwelleAkkuTollesWetter":20.0, "schaltschwelleAkkuRussia":100.0, "schaltschwelleNetzRussia":80.0, "schaltschwelleAkkuSchlechtesWetter":45.0, "schaltschwelleNetzSchlechtesWetter":30.0}
setableSkriptWerte = ["schaltschwelleAkkuTollesWetter", "schaltschwelleAkkuRussia", "schaltschwelleNetzRussia", "schaltschwelleAkkuSchlechtesWetter", "schaltschwelleNetzSchlechtesWetter", "SkriptMode"]
EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False

client = mqtt.Client() 

# Topics
DiscoveryTopicSensor = "homeassistant/sensor/config" 



def myPrint(msg):
    if beVerbose:
        print(msg)
    temp = msg.split()
    if "Info:" in temp or "Error:" in temp or "Autoinit:" in temp:
        try:
            client.publish("PV/Skript/AllMsg", msg)
            client.publish("PV/Skript/%s"%temp[0].replace(":",""), msg)
        except:
            if beVerbose:
                print("myPrint: mqtt konnte nicht gesendet werden")
                
def sendeSkriptDaten():
    global SkriptWerte
        
    try: 
        client.publish("PV/Skript/istwerte", json.dumps(SkriptWerte), retain=True)
    except:
        myPrint("sendeSkriptDaten: mqtt konnte nicht gesendet werden")

def mqttconnect():
    client.username_pw_set(getUserMqtt(),getPassMqtt())
    client.connect( MqttBrokerIp , 1883 , 60 ) 
    client.loop_start() 
    
def mqttconnectWaitAndRetry():
    for i in range(10):
        try: 
            mqttconnect()
            return
        except:
            time.sleep(100)
    return

def on_connect(client, userdata, flags, rc):
    global EffektaData
    
    # subscribe or resubscribe effektas
    for name in list(EffektaData.keys()):
        client.subscribe("PV/" + name + "/command")
        client.subscribe("PV/" + name + "/request")
    
    client.subscribe("PV/allWr/command")
    client.subscribe("PV/BMS/command")
    
    myPrint("MQTT Connected with result code " + str(rc))

def on_message(client, userdata, msg):
    global EffektaData
    global SkriptWerte
    global AutoInitWrMode
    
    tempTopic = str(msg.topic)
    tempTopicList = tempTopic.split("/")
    tempMsg = str(msg.payload.decode())
    
    # Beim Skriptstart und AutoInitWrMode = True abonieren wir das Topic PV/Skript/istwerte wo wir die eigenen Istwerte abgelegt haben.
    # So können wir mit den alten Werten weitermachen
    if tempTopicList[1] == "Skript" and tempTopicList[2] == "istwerte":
        SkriptWerte.update(json.loads(tempMsg))
        AutoInitWrMode = False
        client.unsubscribe("PV/Skript/istwerte")
        
    # single Effekta commands
    # Topic z.B.: Wr1/command
    if tempTopicList[1] in list(EffektaData.keys()) and tempTopicList[2] == "command":
        EffektaData[tempTopicList[1]]["EffektaCmd"].append(tempMsg)
    
    # Effekta requests
    # Topic z.B.: Wr1/request
    if tempTopicList[1] in list(EffektaData.keys()) and tempTopicList[2] == "request":
        EffektaData[tempTopicList[1]]["query"]["cmd"] = tempMsg
        EffektaData[tempTopicList[1]]["query"]["getValue"] = True
        
    # all Effekta/Skript commands
    if tempTopicList[1] == "allWr":
        # Topic z.B.: allWr/command
        if tempTopicList[2] == "command":
            if tempMsg == "WrAufAkku":
                schalteAlleWrAufAkku()
            elif tempMsg == "WrAufNetz":
                schalteAlleWrAufNetzOhneNetzLaden()
            elif tempMsg == "AkkuschutzEin":
                SkriptWerte["Akkuschutz"] = True
                passeSchaltschwellenAn()
                sendeSkriptDaten()
            elif tempMsg == "AkkuschutzAus":
                SkriptWerte["Akkuschutz"] = False
                passeSchaltschwellenAn()
                sendeSkriptDaten()
            elif tempMsg == "RussiaModeEin":
                SkriptWerte["RussiaMode"] = True
                passeSchaltschwellenAn()
                sendeSkriptDaten()
            elif tempMsg == "RussiaModeAus":
                SkriptWerte["RussiaMode"] = False
                passeSchaltschwellenAn()
                sendeSkriptDaten()
            elif tempMsg == "NetzLadenAus":
                schalteAlleWrNetzLadenAus()
            elif tempMsg == "NetzLadenEin":
                schalteAlleWrNetzLadenEin()
            elif tempMsg == "NetzSchnellLadenEin":
                schalteAlleWrNetzSchnellLadenEin()
            elif tempMsg == "socResetMaxAndHold":
                SocMonitorWerte["Commands"].append(tempMsg)
            elif tempMsg == "PowerSaveEin":    
                SkriptWerte["PowerSaveMode"] = True
                sendeSkriptDaten()
            elif tempMsg == "PowerSaveAus":    
                SkriptWerte["PowerSaveMode"] = False 
                sendeSkriptDaten()       
            elif tempMsg in ["PDb", "PEb"]:
                for i in list(EffektaData.keys()):
                    EffektaData[i]["EffektaCmd"].append(tempMsg)   
        elif tempTopicList[2] == "value":
            # Topic z.B.: allWr/value/schaltschwelleAkkuTollesWetter
            if tempTopicList[3] in setableSkriptWerte:
                SkriptWerte[tempTopicList[3]] = tempMsg
                sendeSkriptDaten()
            
            
    # Beim Skriptstart abonieren wir das Topic PV/WRxx/CompleteProduction wo wir die eigenen Istwerte abgelegt haben.
    # So können wir mit den alten Werten weitermachen.
    if tempTopicList[1] in list(EffektaData.keys()) and tempTopicList[2] == "CompleteProduction":
        EffektaData[tempTopicList[1]]["EffektaCmd"].append("CompleteProduction")    
        EffektaData[tempTopicList[1]]["EffektaCmd"].append(tempMsg)
        client.unsubscribe("PV/" + tempTopicList[1] + "/CompleteProduction")
    
        
def checkWerteSprung(newValue, oldValue, percent, min, max, minAbs = 0):
    
    # Diese Funktion prüft, dass der neue Wert innerhalb der angegebenen min max Grenzen und ausserhalb der angegebenen Prozent Grenze
    # Diese Funktion wird verwendet um kleine Wertsprünge rauszu Filtern und Werte Grenzen einzuhalten

    if newValue == oldValue == 0:
        #myPrint("wert wird nicht uebernommen")
        return False
        
    percent = percent * 0.01
    valuePercent = abs(oldValue) * percent
    
    if valuePercent < minAbs:
        valuePercent = minAbs
        
    minPercent = oldValue - valuePercent
    maxPercent = oldValue + valuePercent
    
    if min <= newValue <= max and not (minPercent < newValue < maxPercent):
        #myPrint("wert wird uebernommen")
        return True
    else:
        #myPrint("wert wird nicht uebernommen")
        return False
       
def checkWerteSprungMaxJump(newValue, oldValue, jump):
    # Diese Funktion prüft, dass sich der neue Wert innerhalb des angegebenen Sprung befindet.
    # Diese Funktion wird verwendet um Ausreißer raus zu Filtern
    
    if newValue == oldValue == 0:
        #myPrint("wert wird nicht uebernommen")
        return False
    
    minValue = oldValue - jump
    maxValue = oldValue + jump
    
    if (minValue < newValue < maxValue):
        #myPrint("wert wird uebernommen")
        return True
    else:
        #myPrint("wert wird nicht uebernommen")
        return False  

client.on_connect = on_connect
client.on_message = on_message

"""
schalteAlleWrAufAkku()              Schaltet alle Wr auf Akku, setzt die Unterspannungserkennung des Wr ausser Kraft
schalteAlleWrNetzLadenAus()         Schaltet das Laden auf PV
schalteAlleWrNetzLadenEin()         Schaltet das Laden auf PV+Netz, schaltet die Verbraucher auf Netz, setzt den Netz Ladstrom auf NetzErhaltungsLadestrom
schalteAlleWrNetzSchnellLadenEin()  Schaltet das Laden auf PV+Netz, schaltet die Verbraucher auf Netz, setzt den Netz Ladstrom auf NetzSchnellLadestrom, schaltet das Skript auf Manuell
schalteAlleWrAufNetzOhneNetzLaden() Schaltet alle Wr auf Netz, setzt die Unterspannungserkennung des Wr ausser Kraft
schalteAlleWrAufNetzMitNetzladen()  Schaltet alle Wr auf Netz, setzt die Unterspannungserkennung des Wr auf aktiv
"""

def schalteAlleWrAufAkku():
    global EffektaData
    global SkriptWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(BattLeer)    # Batt undervoltage
        EffektaData[i]["EffektaCmd"].append(BattWiederEntladen)   # redischarge voltage
        #EffektaData[i]["EffektaCmd"].append("PDj")       # PowerSaving disable PDJJJ
        EffektaData[i]["EffektaCmd"].append(VerbraucherAkku)       # load prio 00=Netz, 02=Batt
        EffektaData[i]["EffektaCmd"].append("PCP03")       # charge prio 02=Netz und pv, 03=pv
        
    SkriptWerte["WrMode"] = VerbraucherAkku
    SkriptWerte["WrNetzladen"] = False
    sendeSkriptDaten()
        
def schalteAlleWrNetzLadenAus():
    # Funktion ok, wr schaltet netzladen aus
    global EffektaData
    global SkriptWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append("PCP03")       # charge prio 02=Netz und pv, 03=pv    
        
    SkriptWerte["WrNetzladen"] = False
    sendeSkriptDaten()

def schalteAlleWrNetzLadenEin():
    # Funktion ok, wr schaltet netzladen ein
    global EffektaData
    global SkriptWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append("PCP02")       # charge prio 02=Netz und pv, 03=pv 
        EffektaData[i]["EffektaCmd"].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt
        EffektaData[i]["EffektaCmd"].append(NetzErhaltungsLadestrom)   # Netz Ladestrom  
        
    SkriptWerte["WrNetzladen"] = True
    sendeSkriptDaten()

def schalteAlleWrNetzSchnellLadenEin():
    # Funktion ok, wr schaltet netzladen ein
    global EffektaData
    global SkriptWerte
    

    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append("PCP02")       # charge prio 02=Netz und pv, 03=pv 
        EffektaData[i]["EffektaCmd"].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt
        EffektaData[i]["EffektaCmd"].append(NetzSchnellLadestrom)   # Netz Ladestrom 
        
    SkriptWerte["WrNetzladen"] = True
    # Wir müssen hier auf Manuell schalten damit das Skrip nich gleich zurückschaltet
    SkriptWerte["SkriptMode"] = "Manual"
    SkriptWerte["WrMode"] = VerbraucherNetz
    sendeSkriptDaten()
    myPrint("Info: Schnellladen vom Netz wurde aktiviert!")
    myPrint("Info: Die Anlage wurde auf manuell gestellt!")
    

def schalteAlleWrAufNetzOhneNetzLaden():
    # Diese Funktion ist dazu da, um den Akku zu schonen wenn lange schlechtes wetter ist und zu wenig PV leistung kommt sodass die Verbraucher versorgt werden können
    global EffektaData
    global SkriptWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
        EffektaData[i]["EffektaCmd"].append(BattLeer)    # Batt undervoltage
        EffektaData[i]["EffektaCmd"].append(BattWiederEntladen)   # redischarge voltage
        EffektaData[i]["EffektaCmd"].append("PCP03")       # charge prio 02=Netz und pv, 03=pv
        #EffektaData[i]["EffektaCmd"].append("PEj")       # PowerSaving enable PEJJJ
        
    SkriptWerte["WrMode"] = VerbraucherNetz
    SkriptWerte["WrNetzladen"] = False
    sendeSkriptDaten()

def schalteAlleWrAufNetzMitNetzladen():
    # Diese Funktion setzt den Wr in einen Modus wo er auch selbst die Unterspannung überwacht. Sollten wir diese erreichen schaltet er komplett ab.
    # Dies ist nötig wenn die Anlage aufgrund tiefer entladung auf Netz geschaltet wurde.
    # Test:
    # funktion aufrufen, wr schaltet dann auf netz, netz ausschalten, wr schaltet auf akku, akku entladen <48V, wr schaltet komplett ab, strom aus akku: 0A
    # ergebnis ok
    # wr schaltet sofort auf netz wenn zusätzlich dann der netz ausfällt schaltet er wieder auf batt bis diese <48V hat
    # bei wieder einschaltetn läd er mit netz wenn kein pv da ist. wenn pv dann kommt läd er damit zusätzlich
    global EffektaData
    global SkriptWerte
    
    for i in list(EffektaData.keys()):
        EffektaData[i]["EffektaCmd"].append(VerbraucherNetz)       # load prio 00=Netz, 02=Batt
        EffektaData[i]["EffektaCmd"].append("PBDV52.0")   # redischarge voltage auf Grösste Spannugn setzen
        EffektaData[i]["EffektaCmd"].append("PSDV48.0")    # Batt undervoltage auf Grösste Spannugn setzen
        EffektaData[i]["EffektaCmd"].append(NetzErhaltungsLadestrom)   # Netz Ladestrom
        EffektaData[i]["EffektaCmd"].append("PCP02")       # charge prio 02=Netz und pv, 03=pv
        #EffektaData[i]["EffektaCmd"].append("PEj")       # PowerSaving enable PEJJJ
        
    SkriptWerte["WrMode"] = VerbraucherNetz
    SkriptWerte["WrNetzladen"] = True
    sendeSkriptDaten()

def sendDiscoveryHomeAssistant():
    """
    https://www.home-assistant.io/docs/mqtt/discovery/
    topic "homeassistant/binary_sensor/garden/config" 
    message '{"name": "garden", "device_class": "motion", "state_topic": "homeassistant/binary_sensor/garden/state"}'
    """
    templateMsgSensor = {"topic":"", "name": "", "value_template":"{{ value_json.%s | int }}", "unit_of_measurement ":""}
    
    # send Effekta Sensor templates to Homeassistant
    # EffektaData[WR.EffektaName()]["EffektaWerte"] = {"timeStamp": 0, "Netzspannung": 0, "AcOutSpannung": 0, "AcOutPowerW": 0, "PvPower": 0, "BattChargCurr": 0, "BattDischargCurr": 0, "ActualMode": "", "DailyProduction": 0.0, "CompleteProduction": 0, "DailyCharge": 0.0, "DailyDischarge": 0.0, "BattCapacity": 0, "DeviceStatus2": "", "BattVoltage": 0.0}
    for wr in list(EffektaData.keys()):
        wrTopic = ("PV/" + wr + "/istwerte")
        for key in EffektaData[wr]:
            templateMsgSensor["topic"] = wrTopic
            templateMsgSensor["name"] = key + " " + wr
            templateMsgSensor["value_template"] = templateMsgSensor["value_template"]%key
            if "Power" in key:
                einheit = "W"
            elif "Curr" in key:
                einheit = "A"
            elif "Daily" in key or "Produ" in key:
                einheit = "KWh"
            elif "Spannung" in key:
                einheit = "V"
            else:
                einheit = ""
            templateMsgSensor["unit_of_measurement"] = einheit
            try: 
                client.publish(DiscoveryTopicSensor, templateMsgSensor)
            except:
                myPrint("SocMonitor mqtt konnte nicht gesendet werden")            
        

def getGlobalEffektaData():
    
    globalEffektaData = {"FloatingModeOr" : False, "OutputVoltageHighOr" : False, "InputVoltageAnd" : True, "OutputVoltageHighAnd" : True, "OutputVoltageLowAnd" : True, "ErrorPresentOr" : False}
    
    for name in list(EffektaData.keys()):
        floatmode = list(EffektaData[name]["EffektaWerte"]["DeviceStatus2"])
        # prüfen ob schon Parameter abgefragt wurden
        if len(floatmode) > 0:
            if floatmode[0] == "1":
                globalEffektaData["FloatingModeOr"] = True    
            if float(EffektaData[name]["EffektaWerte"]["Netzspannung"]) < 210.0:
                globalEffektaData["InputVoltageAnd"] = False    
            if float(EffektaData[name]["EffektaWerte"]["AcOutSpannung"]) < 210.0:
                globalEffektaData["OutputVoltageHighAnd"] = False 
            if float(EffektaData[name]["EffektaWerte"]["AcOutSpannung"]) > 25.0:
                globalEffektaData["OutputVoltageLowAnd"] = False
                globalEffektaData["OutputVoltageHighOr"] = True
            if EffektaData[name]["EffektaWerte"]["ActualMode"] == "F":
                globalEffektaData["ErrorPresentOr"] = True
                
    return globalEffektaData

SocMonitorWerte = {"Commands":[], "Ah":-1, "Currentaktuell":0, "Current":0, "Prozent":InitAkkuProz, "FloatingMode": False}

def GetSocData():
    global SocMonitorWerte

    # b'Current A -1.92\r\n'
    # b'SOC Ah 258\r\n'
    # b'SOC <upper Bytes!!!> mAsec 931208825\r\n'
    # b'SOC Prozent 99\r\n'
    
    # supported commands: "config, socResetMax, socResetMin, socResetMaxAndHold, releaseMaxSocHold, setSocToValue"
    
    serialSocMonitor = serial.Serial(SocMonitorSerial, 115200, timeout=4)
    
    sendeMqtt = False
    resetSocSended = False
    
    #SocMonitorWerte["Commands"].append("setSocToValue")
    #SocMonitorWerte["Commands"].append("50")
    
    while 1:
                    
        tempglobalEffektaData = getGlobalEffektaData()
        
        SocMonitorWerte["FloatingMode"] = tempglobalEffektaData["FloatingModeOr"]
        
        if SocMonitorWerte["FloatingMode"] == True and resetSocSended == False:
            resetSocSended = True
            # Wir setzen den Soc Monitor auf 100% 
            SocMonitorWerte["Commands"].append("socResetMaxAndHold")
            # Wir schreiben gleich 100 in den Akkustand um einen fehlerhaften Schaltvorgang aufgrund des aktuellen Akkustandes zu verhindern
            SocMonitorWerte["Prozent"] = 100 
            serialSocMonitor.reset_input_buffer()
            myPrint("Info: Akku voll.")
            
        if SocMonitorWerte["FloatingMode"] == False and resetSocSended == True:
            resetSocSended = False

        
        try:
            x = serialSocMonitor.readline()
        #timebeg = time.time()
        #x = ""
        #while 1:
        #    serChar = serialSocMonitor.read()
        #    x = x + serChar.decode()
        #    if serChar == b"/n" or (time.time() > (timebeg + timeoutRead)):
        #        break         
        except:
            myPrint("Error: SocMonitor Serial error. Init Serial again!")
            try:
                myPrint("Error: SocMonitor Serial reInit!")
                serialSocMonitor.close()  
                serialSocMonitor.open()  
            except:
                myPrint("Error: SocMonitor reInit Serial failed!")  
                time.sleep(100)

        try:
            y = x.split()
            for i in y:
                if i == b'Current' and y[1] == b'A':
                    if checkWerteSprung(float(y[2].decode()), SocMonitorWerte["Current"], 20, -200, 200, 5) or sendeMqtt:
                        sendeMqtt = True  
                        SocMonitorWerte["Current"] = float(y[2].decode())
                    SocMonitorWerte["Currentaktuell"] = float(y[2].decode())
                elif i == b'Prozent':
                    if checkWerteSprung(int(y[2].decode()), SocMonitorWerte["Prozent"], 1, -1, 101) or sendeMqtt:
                        sendeMqtt = True  
                    # Wenn wir einen Akkustan haben und der SOC Monitor neu gestartet wurde dann schicken wir den Wert
                    if SocMonitorWerte["Prozent"] != InitAkkuProz and int(y[2].decode()) == 0 and SocMonitorWerte["Prozent"] != int(y[2].decode()):
                        SocMonitorWerte["Commands"].append("setSocToValue")
                        SocMonitorWerte["Commands"].append(str(SocMonitorWerte["Prozent"]))
                        myPrint("Error: SocMonitor hatte unerwartet den falschen Wert! Alt: %i, Neu: %i" %(int(y[2].decode()),SocMonitorWerte["Prozent"]))
                    else:
                        SocMonitorWerte["Prozent"] = int(y[2].decode())  
                    # Todo folgende Zeile entfernen und serial vernünftig lösen (zu langsam)
                    serialSocMonitor.reset_input_buffer()
                elif i == b'Ah':
                    if checkWerteSprung(float(y[2].decode()), SocMonitorWerte["Ah"], 1, -1, 500, 10) or sendeMqtt:
                        sendeMqtt = True                        
                        SocMonitorWerte["Ah"] = float(y[2].decode())  
        except:
            myPrint("Error: SocMonitor Convert Data failed!")

        if sendeMqtt == True: 
            sendeMqtt = False
            try: 
                # Workaround damit der Strom auf der PV Anzeige richtig angezeigt wird
                temp = {}
                temp["AkkuStrom"] = SocMonitorWerte["Current"]
                temp["AkkuProz"] = SocMonitorWerte["Prozent"]
                client.publish("PV/PvAnzeige/istwerte", json.dumps(temp))
                # publish alle SOC Daten
                client.publish("PV/SocMonitor/istwerte", json.dumps(SocMonitorWerte))
            except:
                myPrint("SocMonitor mqtt konnte nicht gesendet werden")

        if len(SocMonitorWerte["Commands"]):
            tempcmd = SocMonitorWerte["Commands"][0]
            cmd = tempcmd.encode('utf-8')
            cmd = cmd + b'\n'
            try:
                if serialSocMonitor.write(cmd):
                    del SocMonitorWerte["Commands"][0]
            except:
                myPrint("Error: SocMonitor Commands konnten nicht gesendet werden. Command wird verworfen.")
                del SocMonitorWerte["Commands"][0]
                
        #myPrint(x)

def GetAndSendBmsData():
    global BmsWerte
    
    serBMS = serial.Serial(BmsSerial, 9600, timeout=4)  # open serial port
    
    while 1:
        sendeMqtt = False
        lastLine = False
        # Wir lesen alle Zeilen der Serial parsen nach Schlüsselwörten und holen uns die Werte raus.
        # Es kann sein, dass Übertragungsfehler auftreten, in dem Fall fängt das das try except bez die Prüfung des Wertebereichs ab.
        try:
            x = serBMS.readline()
            y = x.split()           
        except:
            myPrint("BMS read error. Init Serial again!")
            try:
                serBMS.close()  
                serBMS.open()  
            except:
                myPrint("BMS reInit Serial failed!")
            time.sleep(100)                
        for i in y:
    #        if i == b'Strom':
    #            try:
    #                if checkWerteSprung(float(y[3]), BmsWerte["AkkuStrom"], 20, -1000, 1000):
    #                    sendeMqtt = True
    #                    BmsWerte["AkkuStrom"] = float(y[3])
    #                    BattCurrent = BmsWerte["AkkuStrom"]
    #            except:
    #                myPrint("convertError")
    #            break
            if i == b'Kleinste':
                try:   
                    if checkWerteSprung(float(y[2]), BmsWerte["Vmin"], 1, -1, 10) or sendeMqtt:
                        sendeMqtt = True
                        BmsWerte["Vmin"] = float(y[2])
                except:
                    myPrint("convertError")
                break
            if i == b'Groeste':
                try:
                    if checkWerteSprung(float(y[2]), BmsWerte["Vmax"], 1, -1, 10) or sendeMqtt:
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
            #if i == b'SOC':
            #    try:
            #        if BmsWerte["AkkuProz"] == InitAkkuProz:
            #            if checkWerteSprung(float(y[3]), BmsWerte["AkkuProz"], 1, -101, 101): 
            #                sendeMqtt = True
            #                BmsWerte["AkkuProz"] = float(y[3])
            #        else:
            #            if checkWerteSprung(float(y[3]), BmsWerte["AkkuProz"], 1, -101, 101) and checkWerteSprungMaxJump(float(y[3]), BmsWerte["AkkuProz"], 10): 
            #                sendeMqtt = True
            #                BmsWerte["AkkuProz"] = float(y[3])
            #    except:
            #        myPrint("convertError")
            #    break
            if i == b'Ladephase:':
                lastLine = True
                # Todo folgende Zeile entfernen und serial vernünfti lösen (zu langsam)
                serBMS.reset_input_buffer()                
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
                myPrint("GetAndSendBmsData: mqtt konnte nicht gesendet werden")
            
        #myPrint(x)


def NetzUmschaltung():
    
    netzMode = "Netz"
    pvMode = "Pv"
    unknownMode = "unknownMode"
    modeError = "error"
    OutputVoltageError = "OutputVoltageError"
    relWr1 = b"Relay4 "
    relWr2 = b"Relay3 "
    relPvAus = b"Relay2 "
    relNetzAus = b"Relay1 "
    ein = b"1"
    aus = b"0"
    comandEnd = b"\n"
    
    aktualMode = None
    
    
    serUsbRel = serial.Serial(UsbRelSerial, 115200, timeout=4)  # open serial port
    # kurz warten damit das zurücklesen nicht zu schnell geht
    time.sleep(2)
    
    def warteAufAcOutHigh():
        i = 0
        while i < 100:
            tmpglobalEffektaData = getGlobalEffektaData()
            if tmpglobalEffektaData["OutputVoltageHighAnd"] == True:
                return True
            i += 1
            time.sleep(1)
        return False
        
    def schalteRelaisAufNetz():
        myPrint("Info: Schalte Netzumschaltung auf Netz.")
        try:
            serUsbRel.write(relNetzAus + aus + comandEnd)
            serUsbRel.write(relPvAus + ein + comandEnd)
            # warten bis Parameter geschrieben sind
            time.sleep(30)
            serUsbRel.write(relWr1 + aus + comandEnd)
            serUsbRel.write(relWr2 + aus + comandEnd)
            # warten bis keine Spannung mehr am ausgang anliegt damit der Schütz nicht wieder kurz anzieht
            time.sleep(500)
            tmpglobalEffektaData = getGlobalEffektaData()
            if tmpglobalEffektaData["OutputVoltageHighOr"] == True:
                # Durch das ruecksetzten von PowersaveMode schalten wir als nächstes wieder zurück auf PV. 
                # Wir wollen im Fehlerfall keinen inkonsistenten Schaltzustand der Anlage darum schalten wir die Umrichter nicht aus.
                SkriptWerte["PowerSaveMode"] = False
                sendeSkriptDaten()
                myPrint("Error: Wechselrichter konnte nicht abgeschaltet werden. Er hat nach Wartezeit immer noch Spannung am Ausgang! Die Automatische Netzumschaltung wurde deaktiviert.")
                # Wir setzen den Status bereits hier ohne Rücklesen damit das relPvAus nicht zurückgesetzt wird. (siehe zurücklesen der Relais Werte)
                return netzMode
            else:
                serUsbRel.write(relPvAus + aus + comandEnd)
                # kurz warten damit das zurücklesen nicht zu schnell geht
                time.sleep(0.5)
        except:
            myPrint("Error: UsbRel send Serial failed 1!")  
        return unknownMode

    def schalteRelaisAufPv():
        myPrint("Info: Schalte Netzumschaltung auf PV.")
        # warten bis Parameter geschrieben sind
        time.sleep(30)
        try:
            serUsbRel.write(relPvAus + ein + comandEnd)
            serUsbRel.write(relNetzAus + aus + comandEnd)
            serUsbRel.write(relWr1 + ein + comandEnd)
            serUsbRel.write(relWr2 + ein + comandEnd)
            if warteAufAcOutHigh():
                time.sleep(20)
                serUsbRel.write(relPvAus + aus + comandEnd) 
            else:
                myPrint("Error: Wartezeit zu lange. Keine Ausgangsspannung am WR erkannt.")
                #Wir schalten die Funktion aus
                SkriptWerte["PowerSaveMode"] = False
                sendeSkriptDaten()
                myPrint("Error: Die Automatische Netzumschaltung wurde deaktiviert.")
                serUsbRel.write(relWr1 + aus + comandEnd)
                serUsbRel.write(relWr2 + aus + comandEnd) 
                # warten bis keine Spannung mehr am ausgang anliegt damit der Schütz nicht wieder kurz anzieht
                time.sleep(500)
                serUsbRel.write(relPvAus + aus + comandEnd)
                return OutputVoltageError
            # kurz warten damit das zurücklesen nicht zu schnell geht
            time.sleep(0.5)
        except:
            myPrint("Error: UsbRel send Serial failed 2!") 
        return unknownMode
    
    aufNetzSchaltenErlaubt = True
    aufPvSchaltenErlaubt = True
        
    while 1:
        time.sleep(1)
        
        now = datetime.datetime.now()
        # Wir setzten den aktualMode au None damit neu gelesen wird. Das Relais kann so wieder auf den alten Wert gesetzt werden falls der USB ect getrennt wurde.
        if now.second == 1:
            aktualMode = None
        
        tmpglobalEffektaData = getGlobalEffektaData()
        if tmpglobalEffektaData["ErrorPresentOr"] == False:
            if SkriptWerte["PowerSaveMode"] == True:
                # Wir resetten die Variable einmal am Tag
                # Nach der Winterzeit von 21 - 22 Uhr
                if now.hour == 21:
                    aufNetzSchaltenErlaubt = True
                    aufPvSchaltenErlaubt = True
                # VerbraucherAkku -> schalten auf PV, VerbraucherNetz -> schalten auf Netz, VerbraucherPVundNetz -> zwischen 6-22 Uhr auf PV sonst Netz 
                if SkriptWerte["WrMode"] == VerbraucherAkku and aktualMode == netzMode:
                    aktualMode = schalteRelaisAufPv()
                elif SkriptWerte["WrMode"] == VerbraucherNetz and aufNetzSchaltenErlaubt == True and aktualMode == pvMode:
                    # Wir wollen nicht zu oft am Tag umschalten Maximal 2 mal auf Netz.
                    aufNetzSchaltenErlaubt = False
                    # prüfen ob alle WR vom Netz versorgt werden
                    if tmpglobalEffektaData["InputVoltageAnd"] == True:
                        aktualMode = schalteRelaisAufNetz()
                        time.sleep(2)
            elif aktualMode == netzMode and aufPvSchaltenErlaubt == True:
                # Wir resetten die Variable hier auch damit man durch aus und einchalten von PowerSaveMode das Umschalten auf Netz wieder frei gibt.
                aufNetzSchaltenErlaubt = True
                aktualMode = schalteRelaisAufPv()    
                if aktualMode == OutputVoltageError:
                    aufPvSchaltenErlaubt = False
        elif aktualMode == pvMode:
            aktualMode = schalteRelaisAufNetz()
        
        if aktualMode == unknownMode or aktualMode == None:
            if aktualMode == None:
                meldeStatus = False
            else:
                meldeStatus = True
        
            relays = {"Relay1": "unknown", "Relay2": "unknown", "Relay3": "unknown", "Relay4": "unknown"}
            zeilen = []
            try:
                serUsbRel.reset_input_buffer()
                serUsbRel.write(b"getIO\n")
                # Die nächsten 8 Zeilen lesen
                for i in range(8):
                    zeilen.append("")
                    zeilen[i] = serUsbRel.readline()
            except:
                myPrint("Error: UsbRel Serial error. Init Serial again!")
                try:
                    myPrint("Error: UsbRel Serial reInit.")
                    serUsbRel.close()  
                    serUsbRel.open() 
                    time.sleep(10)
                except:
                    myPrint("Error: UsbRel reInit Serial failed!") 
                    time.sleep(200)
            try:
                for i in zeilen:            
                    y = i.split()  
                    if i == b"RelayLock 1\r\n":
                        serUsbRel.write(b"RelayLock 0\n")
                        myPrint("Info: UsbRel Lock released.") 
                    if len(y) > 0:
                        if y[0].decode() in relays:
                            relays[y[0].decode()] = y[1].decode()
            except:
                myPrint("Error: UsbRel convert Data failed!")
            
            if relays == {"Relay1": "0", "Relay2": "0", "Relay3": "0", "Relay4": "0"}:
                aktualMode = netzMode
            elif relays == {"Relay1": "0", "Relay2": "0", "Relay3": "1", "Relay4": "1"}:
                aktualMode = pvMode
            elif relays["Relay3"] == "1" and relays["Relay4"] == "1":
                myPrint("Error: UsbRel Inconsistent State! Set relNetzAus and relPvAus to off and try again reading state")
                try:
                    serUsbRel.write(relNetzAus + aus + comandEnd)
                    serUsbRel.write(relPvAus + aus + comandEnd)
                    aktualMode = unknownMode
                except:
                    myPrint("Error: UsbRel send Serial failed 3!")                  
            elif relays == {"Relay1": "unknown", "Relay2": "unknown", "Relay3": "unknown", "Relay4": "unknown"}:
                aktualMode = unknownMode
            else:
                aktualMode = modeError

            if meldeStatus == True:
                myPrint("Info: Die Netz Umschaltung steht jetzt auf %s"%aktualMode)
            
            if aktualMode == modeError:
                time.sleep(20)
                aktualMode = unknownMode
                myPrint("Error: UsbRel set all to off and try again reading state")
                try:
                    serUsbRel.write(relNetzAus + aus + comandEnd)
                    serUsbRel.write(relPvAus + aus + comandEnd)
                    serUsbRel.write(relWr1 + aus + comandEnd)
                    serUsbRel.write(relWr2 + aus + comandEnd)
                    time.sleep(0.5)
                except:
                    myPrint("Error: UsbRel send Serial failed 4!")           


def autoInitInverter():

    if 0 < SocMonitorWerte["Prozent"] < SkriptWerte["schaltschwelleNetzLadenaus"]:
        myPrint("Autoinit: Schalte auf Netz mit Laden")
        schalteAlleWrAufNetzOhneNetzLaden()
        schalteAlleWrNetzLadenEin()    
    elif SkriptWerte["schaltschwelleNetzLadenaus"] <= SocMonitorWerte["Prozent"] < SkriptWerte["schaltschwelleNetzSchlechtesWetter"]:
        schalteAlleWrAufNetzOhneNetzLaden()
        myPrint("Autoinit: Schalte auf Netz ohne Laden")                     
    elif SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleAkkuSchlechtesWetter"]:
        schalteAlleWrAufAkku()
        myPrint("Autoinit: Schalte auf Akku")    
        

def passeSchaltschwellenAn():
    global SkriptWerte

    #SOC Schaltschwellen in Prozent
    SkriptWerte["schaltschwelleNetzLadenaus"] = 11.0
    SkriptWerte["schaltschwelleNetzLadenein"] = 6.0
    SkriptWerte["MinSoc"] = 10.0
    SkriptWerte["SchaltschwelleAkkuTollesWetter"] = 20.0
    SkriptWerte["AkkuschutzAbschalten"] = SkriptWerte["schaltschwelleAkkuSchlechtesWetter"] + 15.0
    # todo Automatisch ermitteln
    SkriptWerte["verbrauchNachtAkku"] = 25.0
    SkriptWerte["verbrauchNachtNetz"] = 3.0
    
    # Russia Mode hat Vorrang ansonsten entscheiden wir je nach Wetter (Akkuschutz)
    if SkriptWerte["RussiaMode"]:
        # Wir wollen die Schaltschwellen nur übernehmen wenn diese plausibel sind
        if SkriptWerte["schaltschwelleNetzRussia"] < SkriptWerte["schaltschwelleAkkuRussia"]:
            if SkriptWerte["schaltschwelleAkku"] != SkriptWerte["schaltschwelleAkkuRussia"]:
                sendeMqtt = True
            SkriptWerte["schaltschwelleAkku"] = SkriptWerte["schaltschwelleAkkuRussia"]
            SkriptWerte["schaltschwelleNetz"] = SkriptWerte["schaltschwelleNetzRussia"]
    else:
        if SkriptWerte["Akkuschutz"]:
            # Wir wollen die Schaltschwellen nur übernehmen wenn diese plausibel sind
            if SkriptWerte["schaltschwelleNetzSchlechtesWetter"] < SkriptWerte["schaltschwelleAkkuSchlechtesWetter"]:        
                if SkriptWerte["schaltschwelleAkku"] != SkriptWerte["schaltschwelleAkkuSchlechtesWetter"]:
                    sendeMqtt = True
                SkriptWerte["schaltschwelleAkku"] = SkriptWerte["schaltschwelleAkkuSchlechtesWetter"]
                SkriptWerte["schaltschwelleNetz"] = SkriptWerte["schaltschwelleNetzSchlechtesWetter"]
        else:
            # Wir wollen die Schaltschwellen nur übernehmen wenn diese plausibel sind
            if SkriptWerte["MinSoc"] < SkriptWerte["schaltschwelleAkkuTollesWetter"]:        
                if SkriptWerte["schaltschwelleAkku"] != SkriptWerte["schaltschwelleAkkuTollesWetter"]:
                    sendeMqtt = True
                SkriptWerte["schaltschwelleAkku"] = SkriptWerte["schaltschwelleAkkuTollesWetter"]
                SkriptWerte["schaltschwelleNetz"] = SkriptWerte["MinSoc"]
        
    # Wetter Sonnenstunden Schaltschwellen
    SkriptWerte["wetterSchaltschwelleNetz"] = 6    # Einheit Sonnnenstunden


def setInverterMode(wetterDaten):
    global SkriptWerte
    global AutoInitWrMode
    global EntladeFreigabeGesendet
    global NetzLadenAusGesperrt
    
    now = datetime.datetime.now()
    sendeMqtt = False
    
    passeSchaltschwellenAn()
    
    # Wenn init gesetzt ist und das BMS einen Akkuwert gesendet hat dann stellen wir einen Initial Zustand der Wr her
    if AutoInitWrMode == True and SocMonitorWerte["Prozent"] != InitAkkuProz:
        AutoInitWrMode = False
        autoInitInverter()
        sendeMqtt = True
        
    # Wir setzen den Error bei 100 prozent zurück. In der Hoffunng dass nicht immer 100 prozent vom BMS kommen dieses fängt aber bei einem Neustart bei 0 proz an.
    if SocMonitorWerte["Prozent"] >= 100.0:
        SkriptWerte["Error"] = False
    
    # Wir prüfen als erstes ob die Freigabe vom BMS da ist und kein Akkustand Error vorliegt
    if BmsWerte["BmsEntladeFreigabe"] == True and SkriptWerte["Error"] == False:
        # Wir wollen erst prüfen ob das skript automatisch schalten soll.
        if SkriptWerte["SkriptMode"] == "Auto":
            # Wir wollen abschätzen ob wir auf Netz schalten müssen dazu soll abends geprüft werden ob noch genug energie für die Nacht zur verfügung steht
            # Dazu wird geprüft wie das Wetter (Sonnenstunden) am nächsten Tag ist und dementsprechend früher oder später umgeschaltet.
            # Wenn das Wetter am nächsten Tag schlecht ist macht es keinen Sinn den Akku leer zu machen und dann im Falle einer Unterspannung vom Netz laden zu müssen.
            # Die Prüfung ist nur Abends aktiv da man unter Tags eine andere Logig haben möchte.
            # In der Sommerzeit löst now.hour = 17 um 18 Uhr aus, In der Winterzeit dann um 17 Uhr
            if now.hour >= 17 and now.hour < 23:
            #if Zeit >= 17 and Zeit < 23:
                if "Tag_1" in wetterDaten:
                    if wetterDaten["Tag_1"] != None:
                        if wetterDaten["Tag_1"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"]:
                        # Wir wollen den Akku schonen weil es nichts bringt wenn wir ihn leer machen
                            if SocMonitorWerte["Prozent"] < (SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"]):
                                if SkriptWerte["WrMode"] == VerbraucherAkku:
                                    # todo ist das so sinnvoll. Bestand
                                    schalteAlleWrAufNetzOhneNetzLaden()
                                    SkriptWerte["Akkuschutz"] = True
                                    myPrint("Info: Sonne morgen < %ih -> schalte auf Netz." %SkriptWerte["wetterSchaltschwelleNetz"])
                    else:
                        myPrint("Error: Keine Wetterdaten!")
            # In der Sommerzeit löst now.hour = 17 um 18 Uhr aus, In der Winterzeit dann um 17 Uhr
            if now.hour >= 12 and now.hour < 23:
            #if Zeit >= 17 and Zeit < 23:
                if "Tag_0" in wetterDaten and "Tag_1" in wetterDaten:
                    if wetterDaten["Tag_0"] != None and wetterDaten["Tag_1"] != None:
                        if wetterDaten["Tag_0"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"] and wetterDaten["Tag_1"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"]:
                        # Wir wollen den Akku schonen weil es nichts bringt wenn wir ihn leer machen
                            if SocMonitorWerte["Prozent"] < (SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"]):
                                if SkriptWerte["WrMode"] == VerbraucherAkku:
                                    # todo ist das so sinnvoll. Bestand
                                    schalteAlleWrAufNetzOhneNetzLaden()
                                    SkriptWerte["Akkuschutz"] = True
                                    myPrint("Info: Sonne heute und morgen < %ih -> schalte auf Netz." %SkriptWerte["wetterSchaltschwelleNetz"])
                    else:
                        myPrint("Error: Keine Wetterdaten!")
            
            passeSchaltschwellenAn()
            
            # todo SkriptWerte["Akkuschutz"] = False Über Wetter?? Was ist mit "Error: Ladestand weicht ab"
            if SocMonitorWerte["Prozent"] >= SkriptWerte["AkkuschutzAbschalten"]:
                SkriptWerte["Akkuschutz"] = False
                
            if SkriptWerte["WrMode"] == VerbraucherAkku:
                if SocMonitorWerte["Prozent"] <= SkriptWerte["MinSoc"]:
                    schalteAlleWrAufNetzOhneNetzLaden()
                    myPrint("Info: MinSOC %iP erreicht -> schalte auf Netz." %SkriptWerte["MinSoc"])                 
                elif SocMonitorWerte["Prozent"] <= SkriptWerte["schaltschwelleNetz"]:
                    schalteAlleWrAufNetzOhneNetzLaden()
                    myPrint("Info: %iP erreicht -> schalte auf Netz." %SkriptWerte["schaltschwelleNetz"])  
            elif SkriptWerte["WrMode"] == VerbraucherNetz:
                if SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleAkku"]:
                    schalteAlleWrAufAkku()
                    NetzLadenAusGesperrt = False
                    myPrint("Info: %iP erreicht -> Schalte auf Akku"  %SkriptWerte["schaltschwelleAkku"])
            # Wr Mode nicht bekannt
            else:
                schalteAlleWrAufNetzOhneNetzLaden()
                myPrint("Error: WrMode nicht bekannt! Schalte auf Netz")

            # Wenn Akkuschutz an ist und schaltschwelle NetzLadenEin erreicht ist dann laden wir vom Netz
            if SkriptWerte["WrNetzladen"] == False and SkriptWerte["Akkuschutz"] == True and SocMonitorWerte["Prozent"] <= SkriptWerte["schaltschwelleNetzLadenein"]:
                schalteAlleWrNetzLadenEin()
                myPrint("Info: Schalte auf Netz mit laden")       
                
            # Wenn das Netz Laden durch eine Unterspannungserkennung eingeschaltet wurde schalten wir es aus wenn der Akku wieder 10% hat
            if SkriptWerte["WrNetzladen"] == True and NetzLadenAusGesperrt == False and SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
                schalteAlleWrNetzLadenAus()
                myPrint("Info: NetzLadenaus %iP erreicht -> schalte Laden aus." %SkriptWerte["schaltschwelleNetzLadenaus"])            
            
            
#            # Ab hier beginnnt der Teil der die Anlage stufenweise wieder auf Akkubetrieb schaltet 
#            # Wenn der Akku wieder über die schaltschwelleAkku ist dann wird er wieder Tag und Nacht genutzt
#            if not SkriptWerte["WrMode"] == VerbraucherAkku and SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleAkku"]:
#                SkriptWerte["Akkuschutz"] = False
#                passeSchaltschwellenAn()
#                schalteAlleWrAufAkku()
#                myPrint("Info: Schalte auf Akku")
#            # Wenn der Akku über die schaltschwellePvNetz ist dann geben wir den Akku wieder frei wenn PV verfügbar ist. PV (Tag), Netz (Nacht)
#            elif SkriptWerte["WrMode"] == VerbraucherNetz and SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwellePvNetz"]:
#                # Hier wird explizit nur geschalten wenn der WR auf VerbraucherNetz steht damit der Zweig nur reagiert wenn der Akku leer war und voll wird 
#                schalteAlleWrNetzLadenAus()
#                NetzLadenAusGesperrt = False
#                schalteAlleWrVerbraucherPVundNetz()
#                myPrint("Info: Schalte auf PV und Netzbetrieb")
#                
#                
#            # Ab hier beginnt der Teil der die Anlage auf  Netz schaltet sowie das Netzladen ein und aus schaltet
#            # Wir schalten auf Netz wenn der min Soc unterschritten wird
#            if SkriptWerte["WrMode"] == VerbraucherAkku and SocMonitorWerte["Prozent"] <= SkriptWerte["MinSoc"]:
#                schalteAlleWrAufNetzOhneNetzLaden()
#                myPrint("Info: MinSoc %iP erreicht -> schalte auf Netz." %SkriptWerte["MinSoc"])
#            # Wenn das Netz Laden durch eine Unterspannungserkennung eingeschaltet wurde schalten wir es aus wenn der Akku wieder 10% hat
#            elif SkriptWerte["WrNetzladen"] == True and NetzLadenAusGesperrt == False and SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
#                schalteAlleWrNetzLadenAus()
#                myPrint("Info: NetzLadenaus %iP erreicht -> schalte Laden aus." %SkriptWerte["schaltschwelleNetzLadenaus"])
#            # Wenn die Verbraucher auf PV (Tag) und Netz (Nacht) geschaltet wurden und der Akku wieder unter die schaltschwelleNetz fällt dann wird auf Netz geschaltet
#            elif SkriptWerte["WrMode"] == VerbraucherPVundNetz and SocMonitorWerte["Prozent"] <= SkriptWerte["schaltschwelleNetz"]:
#                schalteAlleWrAufNetzOhneNetzLaden()
#                myPrint("Info: Schalte auf Netz")
#            # Wenn wir 
#            elif SkriptWerte["WrMode"] != VerbraucherAkku and SkriptWerte["WrNetzladen"] == False and SkriptWerte["Akkuschutz"] == False and SocMonitorWerte["Prozent"] < SkriptWerte["schaltschwelleNetzLadenaus"] and SocMonitorWerte["Prozent"] != InitAkkuProz:
#                SkriptWerte["Akkuschutz"] = True
#                myPrint("Info: %iP erreicht -> schalte Akkuschutz ein." %SkriptWerte["schaltschwelleNetzLadenaus"])
#            # Wenn Akkuschutz an ist und schaltschwelle NetzLadenEin erreicht ist dann laden wir vom Netz
#            elif SkriptWerte["WrNetzladen"] == False and SkriptWerte["Akkuschutz"] == True and SocMonitorWerte["Prozent"] <= SkriptWerte["schaltschwelleNetzLadenein"]:
#                schalteAlleWrNetzLadenEin()
#                myPrint("Info: Schalte auf Netz mit laden")
        EntladeFreigabeGesendet = False
    elif EntladeFreigabeGesendet == False:
        EntladeFreigabeGesendet = True
        schalteAlleWrAufNetzMitNetzladen()
        # Falls der Akkustand zu hoch ist würde nach einer Abschaltung das Netzladen gleich wieder abgeschaltet werden das wollen wir verhindern
        myPrint("Info: Schalte auf Netz mit laden")
        if SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
            # Wenn eine Unterspannnung SOC > schaltschwelleNetzLadenaus ausgelöst wurde dann stimmt mit dem SOC etwas nicht und wir wollen verhindern, dass die Ladung gleich wieder abgestellt wird
            NetzLadenAusGesperrt = True
            SkriptWerte["Akkuschutz"] = True
            myPrint("Error: Ladestand weicht ab")
        # wir setzen einen error weil das nicht plausibel ist und wir hin und her schalten sollte die freigabe wieder kommen
        # wir wollen den Akku erst bis 100 P aufladen 
        if SocMonitorWerte["Prozent"] >= SkriptWerte["schaltschwelleAkkuTollesWetter"]:
            SkriptWerte["Error"] = True
            myPrint("Error: Ladestand nicht plausibel")
        sendeMqtt = True

    passeSchaltschwellenAn()
    
    if sendeMqtt == True: 
        sendeMqtt = False
        sendeSkriptDaten()


def GetAndSendEffektaData(name, serial, beVerbose):

    global EffektaData
    sendeMqtt = False
    
    WR = EffektaConn(name, serial, beVerbose)
    EffektaData[WR.EffektaName()]["query"] = {"cmd":"", "response":"", "getValue": False}
    EffektaData[WR.EffektaName()]["EffektaWerte"] = {"timeStamp": 0, "Netzspannung": 0, "AcOutSpannung": 0, "AcOutPowerW": 0, "PvPower": 0, "BattChargCurr": 0, "BattDischargCurr": 0, "ActualMode": "", "DailyProduction": 0.0, "CompleteProduction": 0, "DailyCharge": 0.0, "DailyDischarge": 0.0, "BattCapacity": 0, "DeviceStatus2": "", "BattVoltage": 0.0}
    
    effekta_Query_Cycle = 20
    writeErrors = 0
    tempDailyProduction = 0.0
    battEnergyCycle = 8 
    timestampbattEnergyCycle = 0
    tempDailyDischarge = 0.0
    tempDailyCharge = 0.0
    #print(WR.getEffektaData("QPIRI"))
    
    while(1):
        time.sleep(0.5)
        if EffektaData[WR.EffektaName()]["EffektaWerte"]["timeStamp"] + effekta_Query_Cycle < time.time():
            EffektaData[WR.EffektaName()]["EffektaWerte"]["timeStamp"] = time.time()
            EffekaQPIGS = WR.getEffektaData("QPIGS") # Device general status parameters inquiry
            ActualMode = WR.getEffektaData("QMOD")

            if len(ActualMode) > 0:
                if EffektaData[WR.EffektaName()]["EffektaWerte"]["ActualMode"] != ActualMode:
                    sendeMqtt = True
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["ActualMode"] = ActualMode
            if len(EffekaQPIGS) > 0:
                (Netzspannung, Netzfrequenz, AcOutSpannung, AcOutFrequenz, AcOutPowerVA, AcOutPowerW, AcOutLoadProz, BusVoltage, BattVoltage, BattChargCurr, BattCapacity, InverterTemp, PvCurrent, PvVoltage, BattVoltageSCC, BattDischargCurr, DeviceStatus1, BattOffset, EeVersion, PvPower, DeviceStatus2) = EffekaQPIGS.split()

                EffektaData[WR.EffektaName()]["EffektaWerte"]["AcOutSpannung"] = float(AcOutSpannung)
                
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["Netzspannung"], int(float(Netzspannung)), 3, -1, 10000):
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["Netzspannung"] = int(float(Netzspannung))
                    sendeMqtt = True                
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["AcOutPowerW"], int(AcOutPowerW), 10, -1, 10000) or sendeMqtt:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["AcOutPowerW"] = int(AcOutPowerW)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["PvPower"], int(PvPower), 10, -1, 10000) or sendeMqtt:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["PvPower"] = int(PvPower)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["BattChargCurr"], int(BattChargCurr), 10, -1, 10000) or sendeMqtt:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["BattChargCurr"] = int(BattChargCurr)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["BattDischargCurr"], int(BattDischargCurr), 10, -1, 10000) or sendeMqtt:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["BattDischargCurr"] = int(BattDischargCurr)
                    sendeMqtt = True
                if EffektaData[WR.EffektaName()]["EffektaWerte"]["DeviceStatus2"] != DeviceStatus2:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["DeviceStatus2"] = DeviceStatus2
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["BattVoltage"], float(BattVoltage), 0.5, -1, 100) or sendeMqtt:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["BattVoltage"] = float(BattVoltage)
                    sendeMqtt = True
                if checkWerteSprung(EffektaData[WR.EffektaName()]["EffektaWerte"]["BattCapacity"], int(BattCapacity), 1, -1, 101) or sendeMqtt:
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["BattCapacity"] = int(BattCapacity)
                    sendeMqtt = True
                    
                    
            tempDailyProduction = tempDailyProduction + (int(PvPower) * effekta_Query_Cycle / 60 / 60 / 1000)
            EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyProduction"] = round(tempDailyProduction, 2)
            
        if len(EffekaQPIGS) > 0:
            if timestampbattEnergyCycle + battEnergyCycle < time.time():
                timestampbattEnergyCycle = time.time()
                if SocMonitorWerte["Currentaktuell"] > 0:
                    tempDailyCharge = tempDailyCharge  + ((float(BattVoltage) * SocMonitorWerte["Currentaktuell"]) * battEnergyCycle / 60 / 60 / 1000)
                    EffektaData[WR.EffektaName()]["EffektaWerte"]["DailyCharge"] = round(tempDailyCharge, 2)         
                elif SocMonitorWerte["Currentaktuell"] < 0:
                    tempDailyDischarge = tempDailyDischarge  + ((float(BattVoltage) * abs(SocMonitorWerte["Currentaktuell"])) * battEnergyCycle / 60 / 60 / 1000)
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
            sendeMqtt = True
            
        
        sendeQuery = False
        # prüfen ob ein wert abgefragt werden soll und ggf dies auch durchführen
        if EffektaData[WR.EffektaName()]["query"]["getValue"] == True:
            EffektaData[WR.EffektaName()]["query"]["response"] = ""
            EffektaData[WR.EffektaName()]["query"]["response"] = WR.getEffektaData(EffektaData[WR.EffektaName()]["query"]["cmd"])
            EffektaData[WR.EffektaName()]["query"]["getValue"] = False
            sendeQuery = True
            sendeMqtt = True            
        
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
                    myPrint("%s: mqtt konnte nicht gesendet werden"%WR.EffektaName())
                        

        if sendeMqtt == True: 
            sendeMqtt = False
            try: 
                topic = "PV/" + WR.EffektaName() + "/istwerte"
                client.publish(topic, json.dumps(EffektaData[WR.EffektaName()]["EffektaWerte"]))
                topic = "PV/" + WR.EffektaName() + "/CompleteProduction"
                client.publish(topic, str(EffektaData[WR.EffektaName()]["EffektaWerte"]["CompleteProduction"]), retain=True)
                if sendeQuery:
                    topic = "PV/" + WR.EffektaName() + "/query"
                    client.publish(topic, json.dumps(EffektaData[WR.EffektaName()]["query"]))
            except:
                myPrint("%s: mqtt konnte nicht gesendet werden"%WR.EffektaName())
    
    
def handleWeather(wetterdaten):
    publishWeather = False
    initWeather = False
    now = datetime.datetime.now()
    if "lastrequest" not in wetterdaten:
        wetterdaten["lastrequest"] = 0
        initWeather = True
        
    # Wir wollen das Wetter um 15 und um 6 Uhr holen
    if (now.hour == 14 and wetterdaten["lastrequest"] != 14) or (now.hour == 5 and wetterdaten["lastrequest"] != 5) or (now.hour == 19 and wetterdaten["lastrequest"] != 19) or initWeather:
        wetterdaten["lastrequest"] = now.hour
        publishWeather = True
        try:
            wetterdaten.update(getSonnenStunden())
            #tempWetter = getSonnenStunden()
            #wetterdaten.update( (k,v) for k,v in tempWetter.items() if v is not None)
        except:
            myPrint("Error: Wetter Daten konnten nicht geholt werden!")
            
    # Wenn der Tag_1 dem aktuellen Tag entspricht dann müssen wir die Tage um eins verrutschen
    # wir fragen zurest ab ob der key vorhanden ist denn es kann sein dass das Dict leer ist.
    if "Tag_1" in wetterdaten: 
        tempDate = wetterdaten["Tag_1"]["Datum"].split(".")
        if now.day == int(tempDate[0]):
            publishWeather = True
            if "Tag_1" in wetterdaten:
                wetterdaten["Tag_0"] = wetterdaten["Tag_1"]
            if "Tag_2" in wetterdaten:
                wetterdaten["Tag_1"] = wetterdaten["Tag_2"]
            if "Tag_3" in wetterdaten:
                wetterdaten["Tag_2"] = wetterdaten["Tag_3"]
            if "Tag_4" in wetterdaten:
                wetterdaten["Tag_3"] = wetterdaten["Tag_4"]
            # Wir füllen von hinten mit None auf
            wetterdaten["Tag_4"] = None
            
    if publishWeather:
        try: 
            topic = "PV/Wetter"
            client.publish(topic, json.dumps(wetterdaten), retain = True)           
        except:
            myPrint("Wetter Daten konnten nicht gesendet werden") 
            
    return wetterdaten


if len(MqttBrokerIp):
    try:
        mqttconnect()
    except:
        # MQtt Connect Funktion in einem Thread starten damit wir es zu einem späteren Zeitpunkt nocheinmal versuchen
        # Das Skript nach dem Netzwerk starten per sysctrl rule ist nicht sinnvoll da das Skript auch ohne Netzwerk funktionieren soll
        t = Thread(target=mqttconnectWaitAndRetry)
        t.start()

# Init Threads and globals for Effektas
for name in list(EffektaData.keys()):
    EffektaData[name]["EffektaCmd"] = []
    t = Thread(target=GetAndSendEffektaData, args=(name, EffektaData[name]["Serial"], beVerboseEffekta,))
    t.start()
    client.subscribe("PV/" + name + "/CompleteProduction")

# Warten bis CompleteProduction per MQTT kommt weil es kann mit schalteAlleWrAufAkku() oder schalteAlleWrAufNetzMitNetzladen() konflikte geben
time.sleep(1)

# Soc Monitor Funktion in einem Thread starten
if len(SocMonitorSerial):
    t = Thread(target=GetSocData)
    t.start()

# BMS Funktion in einem Thread starten
if len(BmsSerial):
    t = Thread(target=GetAndSendBmsData)
    t.start()
    
if len(UsbRelSerial):
    t = Thread(target=NetzUmschaltung)
    t.start()

#serBMS.write(b'vsoc 3300')
#serBMS.write(b'vsoc 3530')

#serBMS.write(b'vleer2750')
#serBMS.write(b'cap260') # 267 ware es auch schon

#serBMS.write(b'file')

#serBMS.write(b'file')
#serBMS.write(b'vsoc 3550')
#serBMS.write(b'vsoc 3550')
#serBMS.write(b'sensor 200')
#serBMS.write(getPassBMS())


#serBMS.write(b'vbal 3550')
#serBMS.write(b'vbal 3500')
#serBMS.write(b'vvoll 3900')
#serBMS.write(b'start')

sendDiscoveryHomeAssistant()

# Initial Zustand manuell herstellen damit das Umschalten bei leerem und voll werdenden Akku funktioniert
if not AutoInitWrMode:
    if StarteMitAkku:
        schalteAlleWrAufAkku()
        myPrint("ManualInit: schalte auf Akku")    
    else:
        schalteAlleWrAufNetzOhneNetzLaden()
        myPrint("ManualInit: schalte auf Netz ohne Laden")    
else:
    myPrint("subscribe to get skript data")
    client.subscribe("PV/Skript/istwerte")
    # Warten bis evtl eine Nachricht per MQTT kommt weil es kann mit schalteAlleWrAufAkku() oder schalteAlleWrAufNetzMitNetzladen() konflikte geben
    time.sleep(1)    
    client.unsubscribe("PV/Skript/istwerte")
    # Wenn daten angekommen sind dann wurde die Variable auf false gesetzt
    if not AutoInitWrMode:
        myPrint("Autoinit: Alte Daten wurden verwendet")
        
myPrint("starte main loop")

wetterdaten = {}

while 1:  
   
    time.sleep(1)
    setInverterMode(wetterdaten)
    wetterdaten = handleWeather(wetterdaten)
    

