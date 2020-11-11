import serial
import time


# avrdude -v -p atmega328p -c arduino -P /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 -b 57600 -D -U flash:w:SOCMeter.ino.with_bootloader.eightanaloginputs.hex:i
# avrdude -C /usr/local/etc/avrdude.conf -v -p atmega328p -c arduino -P /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 -b 57600 -D -U flash:w:SOCMeter.ino.with_bootloader.eightanaloginputs.hex:i

SocMonitorSerial = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"

beVerbose = True

def myPrint(msg):
    if beVerbose:
        print(msg)
    temp = msg.split()
    if "Info:" in temp or "Error:" in temp or "Autoinit:" in temp:
        try:
            client.publish("PV/Skript/Info", msg)
        except:
            if beVerbose:
                print("myPrint: mqtt konnte nicht gesendet werden")

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
        
        
        
        
        
        
        


SocMonitorWerte = {"Commands":[], "Ah":-1, "Current":0, "Prozent":-1}

#SocMonitorWerte["Commands"] = ["socResetMaxAndHold"]

def GetSocData():
    global SocMonitorWerte
    # b'Current A -1.92\r\n'
    # b'SOC Ah 258\r\n'
    # b'SOC <upper Bytes!!!> mAsec 931208825\r\n'
    # b'SOC Prozent 99\r\n'
    
    # supported commands: "config, socResetMax, socResetMin, socResetMaxAndHold, releaseMaxSocHold"
    
    serialSocMonitor = serial.Serial(SocMonitorSerial, 115200, timeout=2)

    
    sendeMqtt = False
    while 1:    
        try:
            x = serialSocMonitor.readline()
        except:
            myPrint("Error: SocMonitor Serial error. Init Serial again!")
            try:
                myPrint("Info: SocMonitor Serial reInit!")
                serBMS.close()  
                serBMS.open()  
            except:
                myPrint("Error: SocMonitor reInit Serial failed!")        
        try:
            y = x.split()
            for i in y:
                if i == b'Current' and y[1] == b'A':
                    if checkWerteSprung(float(y[2]), SocMonitorWerte["Current"], 5, -200, 200):
                        sendeMqtt = True  
                    SocMonitorWerte["Current"] = float(y[2])
                elif i == b'Prozent':
                    if checkWerteSprung(float(y[2]), SocMonitorWerte["Prozent"], 1, -1, 101):
                        sendeMqtt = True                  
                    SocMonitorWerte["Prozent"] = float(y[2])       
                elif i == b'Ah':
                    if checkWerteSprung(float(y[2]), SocMonitorWerte["Ah"], 1, -1, 500):
                        sendeMqtt = True                        
                    SocMonitorWerte["Ah"] = float(y[2])       
        except:
            myPrint("Info: SocMonitor Convert Data failed!")

        if sendeMqtt == True: 
            sendeMqtt = False
            #try: 
            #myPrint(SocMonitorWerte)
            # Workaround damit der Strom auf der PV Anzeige richtig angezeigt wird
            temp = {}
            temp["AkkuStrom"] = SocMonitorWerte["Current"]
            client.publish("PV/SocMonitor/istwerte", json.dumps(SocMonitorWerte))
            client.publish("PV/SocMonitor/istwerte", json.dumps(temp))
            #except:
            myPrint("Error: SocMonitor mqtt konnte nicht gesendet werden")
        
        if len(SocMonitorWerte["Commands"]):
            tempcmd = SocMonitorWerte["Commands"][0]
            cmd = tempcmd.encode('utf-8')
            cmd = cmd + b'\n'
            print("send command")
            print(cmd)
            print(SocMonitorWerte["Commands"])
            if serialSocMonitor.write(cmd):
                del SocMonitorWerte["Commands"][0]
                
        myPrint(x)
        


# Arduino gets a reset if you start the skript, wait until config is done
time.sleep(3)
GetSocData()
    