import serial
from effekta_ax_class import EffektaConn
import _thread
from threading import Thread
import time
import datetime
from Secret import getPassBMS
 
 
# Globals
# Define a emty string if not used

# Serielle Schnittstellen der Wechselrichter Soc Monitore und BMS
EffektaData = {"WR1" : {"Serial" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0'}, "WR2" : {"Serial" : '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9HSILDS-if00-port0'}}
BmsSerial = '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'

WR = EffektaConn("WR1", '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9A5YBUE-if00-port0', False)

# Warten bis CompleteProduction per MQTT kommt weil es kann mit schalteAlleWrAufAkku() oder schalteAlleWrAufNetzMitNetzladen() konflikte geben
time.sleep(1)

# BMS Funktion in einem Thread starten
serBMS = serial.Serial(BmsSerial, 9600, timeout=4)

serBMS.write(getPassBMS())    
    
def parameterlesen():
    print(datetime.datetime.now())
    print(WR.getEffektaData("QPIRI"))

print("Starte Test skript, Moegliche Werte fur Utility Strom:")
moeglicheWerte = WR.getEffektaData("QMUCHGCR").split()
print(moeglicheWerte)
print("setze ersten parameter aus der Liste")
print(WR.setEffektaData("MUCHGC" + moeglicheWerte[0]))
print("Lese aktuelle Werte")
parameterlesen()

serBMS.write(getPassBMS())
serBMS.write(b'stop')    
input("Anlage bitte wieder starten! Weiter mit Taste.")
parameterlesen()

input("Weiter mit Taste!")

for i in moeglicheWerte:
    print(datetime.datetime.now())
    par = "MUCHGC" + i
    print("setze parameter: " + par)
    print(WR.setEffektaData(par))

serBMS.write(getPassBMS())
serBMS.write(b'stop')    

input("Anlage bitte wieder starten! Weiter mit Taste.")

parameterlesen()