BmsWerte = {"AkkuStrom": 0.0, "Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "AkkuProz": 0, "Ladephase": "none", "BmsEntladeFreigabe":True, "WrEntladeFreigabe":True, "WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":""}


#  BmsWerte["BmsEntladeFreigabe"] = False
#  BmsWerte["BmsEntladeFreigabe"] = True
#  BmsWerte["AkkuProz"] = 5
#  BmsWerte["AkkuProz"] = 11
#  BmsWerte["AkkuProz"] = 26
#  BmsWerte["AkkuProz"] = 31
#  BmsWerte["AkkuProz"] = 41



beVerbose = True

VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
BattLeer = "PSDV43.0"
BattWiederEntladen = "PBDV48.0"
EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False

def schalteAlleWrAufAkku():
    BmsWerte["WrMode"] = VerbraucherAkku
    BmsWerte["WrEntladeFreigabe"] = True
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrNetzLadenAus():
    # Funktion ok, wr schaltet netzladen aus
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrNetzLadenEin():
    # Funktion ok, wr schaltet netzladen aus
    BmsWerte["WrNetzladen"] = True

def schalteAlleWrVerbraucherPVundNetz():
    BmsWerte["WrMode"] = VerbraucherPVundNetz
    BmsWerte["WrEntladeFreigabe"] = True

def schalteAlleWrAufNetzOhneNetzLaden():
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = False

def schalteAlleWrAufNetz():
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = True



def testfunk():
    global EntladeFreigabeGesendet
    global NetzLadenAusGesperrt
    
    SkriptWerte = {}
    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
    
    if BmsWerte["Akkuschutz"]:
        SkriptWerte["schaltschwelleAkku"] = 50.0
        SkriptWerte["schaltschwellePvNetz"] = 40.0
        SkriptWerte["schaltschwelleNetz"] = 25.0
    else:
        SkriptWerte["schaltschwelleAkku"] = 40.0
        SkriptWerte["schaltschwellePvNetz"] = 30.0
        SkriptWerte["schaltschwelleNetz"] = 15.0
        
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

            
            
            
            
def test():

# die folgenden Wertegrenzen wurden verwendet
#    if BmsWerte["Akkuschutz"]:
#        SkriptWerte["schaltschwelleAkku"] = 50.0
#        SkriptWerte["schaltschwellePvNetz"] = 40.0
#        SkriptWerte["schaltschwelleNetz"] = 25.0
#    else:
#        SkriptWerte["schaltschwelleAkku"] = 40.0
#        SkriptWerte["schaltschwellePvNetz"] = 30.0
#        SkriptWerte["schaltschwelleNetz"] = 15.0
#        
        
    global BmsWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-100-5 Zyklus xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk() 
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf Akku schalten")  
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()
    print("kein Print ist OK")
    
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()

    print("xxxxxxxxxxxxxxxxxxxxxxx 5-100-5 Zyklus nach unterspannung xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")    
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 5    
    testfunk()   
    testfunk()
    
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()    
    
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-31-5 Zyklus mit Entladung -> Akkuschutz ausloesen xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")    
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()
    
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-6-51-9 Zyklus. Test auf hoeheren Akkubereich Akkuschutz aktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    if BmsWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("Ok")
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("error")
    if BmsWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("error")
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("Ok")
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf PV und Netz schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es NetzLaden ein schalten")   
    BmsWerte["AkkuProz"] = 6
    testfunk()   
    testfunk()    
    print("vvvvv jetzt muss es NetzLaden aus schalten")   
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()    
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk()    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()   
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()    
    
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-5 Normaler Zyklus akkuschutz inaktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    if BmsWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("error")
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("Ok")

    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()   
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()    
    print("kein Print ist OK")    


    print("xxxxxxxxxxxxxxxxxxxxxxx 17-41-5 Zyklus unterspannung und falschen soc xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    

    BmsWerte["AkkuProz"] = 17
    testfunk()   
    testfunk() 

    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()

    global NetzLadenAusGesperrt
    
    if NetzLadenAusGesperrt:
        print("vvv NetzLadenAusGesperrt gesetzt")
        print("Ok")
    else:
        print("vvv NetzLadenAusGesperrt nicht gesetzt") 
        print("error")
        
    if BmsWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("Ok")
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("error")

    BmsWerte["AkkuProz"] = 27
    testfunk()    
    testfunk()
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    BmsWerte["AkkuProz"] = 5    
    testfunk()   
    testfunk()
    
test()


    