import serial
import time
import datetime

Stromausfall = False
#UsbRelSerial = "/dev/serial/by-path/platform-20980000.usb-usb-0:1.2:1.0-port0"
UsbRelSerial = "COM11"

VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz

SkriptWerte = {"WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":VerbraucherAkku, "SkriptMode":"Auto", "PowerSaveMode":True}


#datetime = datetime.replace(minute=59, hour=23, second=59, year=2018, month=6, day=1)

def myPrint(text):
    print(text)

def getGlobalEffektaData():
    
    return {"FloatingModeOr" : False, "OutputVoltageHighOr" : True, "InputVoltageAnd" : True, "OutputVoltageHighAnd" : True, "OutputVoltageLowAnd" : True, "ErrorPresentOr" : False}
    #return {"FloatingModeOr" : False, "OutputVoltageHighOr" : True, "InputVoltageAnd" : True, "OutputVoltageHighAnd" : True, "OutputVoltageLowAnd" : False}
    
def sendeSkriptDaten():
    pass

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
        #while i < 100:
        while i < 2:
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
            time.sleep(3)
            #time.sleep(30)
            serUsbRel.write(relWr1 + aus + comandEnd)
            serUsbRel.write(relWr2 + aus + comandEnd)
            # warten bis keine Spannung mehr am ausgang anliegt damit der Schütz nicht wieder kurz anzieht
            time.sleep(5)
            #time.sleep(500)
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
        #time.sleep(30)
        time.sleep(3)
        try:
            serUsbRel.write(relPvAus + ein + comandEnd)
            serUsbRel.write(relNetzAus + aus + comandEnd)
            serUsbRel.write(relWr1 + ein + comandEnd)
            serUsbRel.write(relWr2 + ein + comandEnd)
            if warteAufAcOutHigh():
                #time.sleep(20)
                time.sleep(2)
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
                time.sleep(5)
                #time.sleep(500)
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
                # Nach der Winterzeit von 7 - 22 Uhr
                if now.hour >= 6 and now.hour < 21:
                    dayTime = True
                else:
                    dayTime = False
                    aufNetzSchaltenErlaubt = True
                    aufPvSchaltenErlaubt = True
                # VerbraucherAkku -> schalten auf PV, VerbraucherNetz -> schalten auf Netz, VerbraucherPVundNetz -> zwischen 6-22 Uhr auf PV sonst Netz 
                if (SkriptWerte["WrMode"] == VerbraucherAkku or (dayTime and SkriptWerte["WrMode"] == VerbraucherPVundNetz)) and aktualMode == netzMode:
                    aktualMode = schalteRelaisAufPv()
                    # Wir wollen nur einmal am Tag umschalten damit nicht zu oft geschaltet wird.
                    aufNetzSchaltenErlaubt = False
                elif ((SkriptWerte["WrMode"] == VerbraucherNetz and aufNetzSchaltenErlaubt == True) or (not dayTime and SkriptWerte["WrMode"] == VerbraucherPVundNetz)) and aktualMode == pvMode:
                    # prüfen ob alle WR vom Netz versorgt werden
                    if tmpglobalEffektaData["InputVoltageAnd"] == True:
                        aktualMode = schalteRelaisAufNetz()
                        time.sleep(2)
            elif aktualMode == netzMode and aufPvSchaltenErlaubt == True:
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
                    #time.sleep(10)
                    time.sleep(1)
                except:
                    myPrint("Error: UsbRel reInit Serial failed!") 
                    #time.sleep(200)
                    time.sleep(2)
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
                #time.sleep(20)
                time.sleep(2)
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

                                
NetzUmschaltung()

