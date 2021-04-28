import serial
import time

Stromausfall = False
UsbRelSerial = "/dev/serial/by-path/platform-20980000.usb-usb-0:1.2:1.0-port0"

VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz

SkriptWerte = {"WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":VerbraucherPVundNetz, "SkriptMode":"Auto", "PowerSaveMode":True}

def myPrint(text):
    print(text)


def NetzUmschaltung():

    global SkriptWerte
    global Stromausfall
    
    netzMode = "Netz"
    pvMode = "Pv"
    unknownMode = "unknownMode"
    modeError = "error"
    relWr1 = b"Relay4 "
    relWr2 = b"Relay3 "
    relPvAus = b"Relay2 "
    relNetzAus = b"Relay1 "
    ein = b"1"
    aus = b"0"
    comandEnd = b"\n"
    
    aktualMode = None
    
    myPrint("Init Serial")
    
    serUsbRel = serial.Serial(UsbRelSerial, 115200, timeout=4)  # open serial port
    # kurz warten damit das zurücklesen nicht zu schnell geht
    time.sleep(2)
    
    def schalteRelaisAufNetz():
        myPrint("Info: Schalte Netzumschaltung auf Netz.")
        try:
            #serUsbRel.write(relNetzAus + aus + comandEnd)
            #serUsbRel.write(relPvAus + ein + comandEnd)
            time.sleep(2)
            serUsbRel.write(relWr1 + aus + comandEnd)
            serUsbRel.write(relWr2 + aus + comandEnd)
            # warten bis keine Spannung mehr am ausgang anliegt damit der Schütz nicht wieder kurz anzieht
            #time.sleep(80)
            #serUsbRel.write(relPvAus + aus + comandEnd)
            # kurz warten damit das zurücklesen nicht zu schnell geht
            time.sleep(0.5)
        except:
            myPrint("Error: UsbRel send Serial failed!")           

    def schalteRelaisAufPv():
        myPrint("Info: Schalte Netzumschaltung auf PV.")
        try:
            #serUsbRel.write(relPvAus + aus + comandEnd)
            #serUsbRel.write(relNetzAus + aus + comandEnd)
            serUsbRel.write(relWr1 + ein + comandEnd)
            serUsbRel.write(relWr2 + ein + comandEnd) 
            # kurz warten damit das zurücklesen nicht zu schnell geht
            time.sleep(0.5)
        except:
            myPrint("Error: UsbRel send Serial failed!")             
    
    myPrint("start main")
    while 1:
        if SkriptWerte["PowerSaveMode"] == True:
            if SkriptWerte["WrMode"] == VerbraucherAkku and aktualMode == netzMode:
                aktualMode = unknownMode
                schalteRelaisAufPv()
            elif SkriptWerte["WrMode"] == VerbraucherNetz and aktualMode == pvMode and Stromausfall == False:
                aktualMode = unknownMode
                schalteRelaisAufNetz()
        elif aktualMode == netzMode:
            aktualMode = unknownMode
            schalteRelaisAufPv()    
                    
        if aktualMode == unknownMode or aktualMode == None:
            relays = {"Relay1": "unknown", "Relay2": "unknown", "Relay3": "unknown", "Relay4": "unknown"}
            try:
                serUsbRel.reset_input_buffer()
                serUsbRel.write(b"getIO\n")
                # Die nächsten 6 Zeilen lesen
                zeilen = []
                for i in range(8):
                    zeilen.append("")
                    zeilen[i] = serUsbRel.readline()
            except:
                myPrint("Error: UsbRel Serial error. Init Serial again!")
                try:
                    myPrint("Error: UsbRel Serial reInit!")
                    serUsbRel.close()  
                    serUsbRel.open()  
                except:
                    myPrint("Error: UsbRel reInit Serial failed!")        
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
                #SkriptWerte["WrMode"] = VerbraucherAkku
            elif relays == {"Relay1": "0", "Relay2": "0", "Relay3": "1", "Relay4": "1"}:
                aktualMode = pvMode
                #SkriptWerte["WrMode"] = VerbraucherNetz
            else:
                aktualMode = modeError
            myPrint("Info: Die Netz Umschaltung steht jetzt auf %s"%aktualMode)
            
            if aktualMode == modeError:
                time.sleep(20)
                aktualMode = unknownMode
                myPrint("Error: UsbRel try again reading state!")
                
                
NetzUmschaltung()