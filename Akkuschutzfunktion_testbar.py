BmsWerte = {"AkkuStrom": 0.0, "Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "AkkuProz": 0, "Ladephase": "none", "BmsEntladeFreigabe":True, "WrEntladeFreigabe":True, "WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":""}


#  BmsWerte["BmsEntladeFreigabe"] = False
#  BmsWerte["BmsEntladeFreigabe"] = True
#  BmsWerte["AkkuProz"] = 5
#  BmsWerte["AkkuProz"] = 11
#  BmsWerte["AkkuProz"] = 26
#  BmsWerte["AkkuProz"] = 31
#  BmsWerte["AkkuProz"] = 41



ErrorPresent = False

VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
BattLeer = "PSDV43.0"
BattWiederEntladen = "PBDV48.0"
EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False

sehrSchlecht = 1
schlecht = 2
gut = 3
sehrGut = 4

def myPrint(msg):

    print(msg)

def schalteAlleWrAufAkku():
    SkriptWerte["WrMode"] = VerbraucherAkku
    SkriptWerte["WrEntladeFreigabe"] = True
    SkriptWerte["WrNetzladen"] = False

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

def schalteAlleWrAufNetzMitNetzladen():
    BmsWerte["WrMode"] = VerbraucherNetz
    BmsWerte["WrEntladeFreigabe"] = False
    BmsWerte["WrNetzladen"] = True

def autoInitInverter():
    pass

SkriptWerte = {}
InitAkkuProz = -1

def testfunk():

    global SkriptWerte
    global BmsWerte
    global EntladeFreigabeGesendet
    global NetzLadenAusGesperrt
    global wetterDaten

    AutoInitWrMode = False
    
    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
    SkriptWerte["schaltschwelleNetzLadenein"] = 7.0

    SkriptWerte["verbrauchNachtAkku"] = 25.0
    SkriptWerte["verbrauchNachtNetz"] = 3.0
    
    if BmsWerte["Akkuschutz"]:
        SkriptWerte["schaltschwelleAkku"] = 50.0
        SkriptWerte["schaltschwellePvNetz"] = 40.0
        SkriptWerte["schaltschwelleNetz"] = 25.0
    else:
        SkriptWerte["schaltschwelleAkku"] = 40.0
        SkriptWerte["schaltschwellePvNetz"] = 30.0
        SkriptWerte["schaltschwelleNetz"] = 15.0
                 
    # Wetter Sonnenstunden Schaltschwellen
    SkriptWerte["wetterSchaltschwelleNetz"] = 6
    
        
    # Wenn init gesetzt ist und das BMS einen Akkuwert gesendet hat dann stellen wir einen Initial Zustand der Wr her
    if AutoInitWrMode == True and BmsWerte["AkkuProz"] != InitAkkuProz:
        AutoInitWrMode = False
        autoInitInverter()
        
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
        #if now.hour >= 17 and now.hour < 23:
        if Zeit >= 17 and Zeit < 23:
            if "Tag_1" in wetterDaten:
                if wetterDaten["Tag_1"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"]:
                # Wir wollen den Akku schonen weil es nichts bringt wenn wir ihn leer machen
                    if BmsWerte["AkkuProz"] < (SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"]):
                        if BmsWerte["WrMode"] == VerbraucherAkku:
                            BmsWerte["Akkuschutz"] = True
                            schalteAlleWrAufNetzOhneNetzLaden()
                            myPrint("Info: Sonne morgen < %ih -> schalte auf Netz." %SkriptWerte["wetterSchaltschwelleNetz"])
        #elif now.hour >= 8:
        elif Zeit >= 8:
            # Ab hier beginnnt der Teil der die Anlage stufenweise wieder auf Akkubetrieb schaltet 
            # dieser Teil soll Tagsüber aktiv sein das macht Nachts keinen Sinn weil der Akkustand nicht steigt
            EntladeFreigabeGesendet = False
            # Wenn der Akku wieder über die schaltschwelleAkku ist dann wird er wieder Tag und Nacht genutzt
            if not BmsWerte["WrMode"] == VerbraucherAkku and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleAkku"]:
                schalteAlleWrAufAkku()
                BmsWerte["Akkuschutz"] = False
                sendeMqtt = True
                myPrint("Schalte alle WR auf Akku")
            # Wenn der Akku über die schaltschwellePvNetz ist dann geben wir den Akku wieder frei wenn PV verfügbar ist. PV (Tag), Netz (Nacht)
            elif BmsWerte["WrMode"] == VerbraucherNetz and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
                # Hier wird explizit nur geschalten wenn der WR auf VerbraucherNetz steht damit der Zweig nur reagiert wenn der Akku leer war und voll wird 
                schalteAlleWrNetzLadenAus()
                schalteAlleWrVerbraucherPVundNetz()
                NetzLadenAusGesperrt = False
                sendeMqtt = True
                myPrint("Schalte alle WR Verbraucher PV und Netz")
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
            myPrint("Schalte alle WR Netz ohne laden")
        elif BmsWerte["WrMode"] != VerbraucherAkku and BmsWerte["WrNetzladen"] == False and BmsWerte["Akkuschutz"] == False and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetzLadenaus"] and BmsWerte["AkkuProz"] > 0.0:
            BmsWerte["Akkuschutz"] = True
            sendeMqtt = True
            myPrint("Schalte Akkuschutz ein")
            myPrint("Info: %iP erreicht -> schalte Akkuschutz ein." %SkriptWerte["schaltschwelleNetzLadenaus"])
        elif BmsWerte["WrNetzladen"] == False and BmsWerte["Akkuschutz"] == True and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetzLadenein"]:
            schalteAlleWrNetzLadenEin()
            sendeMqtt = True
            myPrint("Schalte alle WR Netz laden ein")
    elif EntladeFreigabeGesendet == False:
        EntladeFreigabeGesendet = True
        schalteAlleWrAufNetzMitNetzladen()
        # Falls der Akkustand zu hoch ist würde nach einer Abschaltung das Netzladen gleich wieder abgeschaltet werden das wollen wir verhindern
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
            # Wenn eine Unterspannnung SOC > schaltschwelleNetzLadenaus ausgelöst wurde dann stimmt mit dem SOC etwas nicht der Wird bei vollem akku wieder zurück gesetzt
            NetzLadenAusGesperrt = True
            BmsWerte["Akkuschutz"] = True
        # wir setzen einen error weil das nicht plausibel ist und wir hin und her schalten sollte die freigabe wieder kommen
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
            BmsWerte["Error"] = True
        sendeMqtt = True
        myPrint("Schalte alle WR auf Netz mit laden")



def istAufAkku(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherAkku and BmsWerte["WrNetzladen"] == False:
        print("OK")
    else: 
        print("Error")
        ErrorPresent = True

def istAufPvNetz(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherPVundNetz and BmsWerte["WrNetzladen"] == False:
        print("OK")
    else: 
        print("Error")
        ErrorPresent = True

def istAufNetz(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherNetz and BmsWerte["WrNetzladen"] == False:
        print("OK")
    else: 
        print("Error")     
        ErrorPresent = True        

def istAufNetzMitLaden(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherNetz and BmsWerte["WrNetzladen"] == True:
        print("OK")
    else: 
        print("Error")    
        ErrorPresent = True


# neuen Test überlegen: Akku bei 4%, manuelles umschalten auf Netz -> was soll passieren... Momentan Netzladen + Akkuschutz evtl sogar sinnvoll!
# Automatisch auf Netz Umschalten wenn der errechnete Stromverbrauch in der Nacht höher ist als die verfügbare Energie..



def testA():

#    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
#    SkriptWerte["schaltschwelleNetzLadenein"] = 7.0
#
#    SkriptWerte["verbrauchNachtAkku"] = 25.0
#    SkriptWerte["verbrauchNachtNetz"] = 3.0
#    
#    if BmsWerte["Akkuschutz"]:
#        SkriptWerte["schaltschwelleAkku"] = 50.0
#        SkriptWerte["schaltschwellePvNetz"] = 40.0
#        SkriptWerte["schaltschwelleNetz"] = 25.0
#    else:
#        SkriptWerte["schaltschwelleAkku"] = 40.0
#        SkriptWerte["schaltschwellePvNetz"] = 30.0
#        SkriptWerte["schaltschwelleNetz"] = 15.0

    global ErrorPresent
    global BmsWerte
    global SkriptWerte
    global wetterDaten
    global Zeit
    
    SkriptWerte["MinSoc"] = 0.0

    wetterDaten = {'Tag_0': {'Sonnenstunden': 12, 'Datum': '13.09.'}, 'Tag_1': {'Sonnenstunden': 12, 'Datum': '14.09.'}, 'Tag_2': {'Sonnenstunden': 12, 'Datum': '15.09.'}, 'Tag_3': {'Sonnenstunden': 11, 'Datum': '16.09.'}}
    Zeit = 12    
    
    
    Test_5_100_5_Zyklus()
    Test_5_100_5_Zyklus_nach_unterspannung()    
    Test_5_31_5_Zyklus_mit_Entladung_Akkuschutz_ausloesen()
    Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv()
    Test_11_41_5_Normaler_Zyklus_akkuschutz_inaktiv()
    Test_17_41_5_Zyklus_unterspannung_und_falschen_soc()
    
    if ErrorPresent == True:
        print("Ergebnis min Soc deaktiviert: ERROR")
    else:
        print("Ergebnis min Soc deaktiviert: OK")


def testB():

#    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
#    SkriptWerte["schaltschwelleNetzLadenein"] = 7.0
#
#    SkriptWerte["verbrauchNachtAkku"] = 25.0
#    SkriptWerte["verbrauchNachtNetz"] = 3.0
#    
#    if BmsWerte["Akkuschutz"]:
#        SkriptWerte["schaltschwelleAkku"] = 50.0
#        SkriptWerte["schaltschwellePvNetz"] = 40.0
#        SkriptWerte["schaltschwelleNetz"] = 25.0
#    else:
#        SkriptWerte["schaltschwelleAkku"] = 40.0
#        SkriptWerte["schaltschwellePvNetz"] = 30.0
#        SkriptWerte["schaltschwelleNetz"] = 15.0
  
    global ErrorPresent
    global BmsWerte
    global SkriptWerte
    global wetterDaten
    global Zeit
    
    SkriptWerte["MinSoc"] = 10.0
    wetterDaten = {'Tag_0': {'Sonnenstunden': 12, 'Datum': '13.09.'}, 'Tag_1': {'Sonnenstunden': 12, 'Datum': '14.09.'}, 'Tag_2': {'Sonnenstunden': 12, 'Datum': '15.09.'}, 'Tag_3': {'Sonnenstunden': 11, 'Datum': '16.09.'}}
    Zeit = 12    
    
    normaler_Zyklus_Test_auf_Akku(11, 100)
    normaler_Zyklus_Test_auf_Akku(100, 11)

    Test_5_31_5_Zyklus_mit_Entladung_Akkuschutz_ausloesen()
    Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv()
    
    #Test_5_31_5_Zyklus_mit_Entladung_Akkuschutz_ausloesen()
    #Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv()
    #Test_11_41_5_Normaler_Zyklus_akkuschutz_inaktiv()
    #Test_17_41_5_Zyklus_unterspannung_und_falschen_soc()
    
    if ErrorPresent == True:
        print("Ergebnis min Soc aktiviert: ERROR")
    else:
        print("Ergebnis min Soc aktiviert: OK")


def testC():

#    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
#    SkriptWerte["schaltschwelleNetzLadenein"] = 7.0
#
#    SkriptWerte["verbrauchNachtAkku"] = 25.0
#    SkriptWerte["verbrauchNachtNetz"] = 3.0
#    
#    if BmsWerte["Akkuschutz"]:
#        SkriptWerte["schaltschwelleAkku"] = 50.0
#        SkriptWerte["schaltschwellePvNetz"] = 40.0
#        SkriptWerte["schaltschwelleNetz"] = 25.0
#    else:
#        SkriptWerte["schaltschwelleAkku"] = 40.0
#        SkriptWerte["schaltschwellePvNetz"] = 30.0
#        SkriptWerte["schaltschwelleNetz"] = 15.0
  
    global ErrorPresent
    global BmsWerte
    global SkriptWerte
    global wetterDaten
    global Zeit
    
    SkriptWerte["MinSoc"] = 10.0
    wetterDaten = {'Tag_0': {'Sonnenstunden': 12, 'Datum': '13.09.'}, 'Tag_1': {'Sonnenstunden': 4, 'Datum': '14.09.'}, 'Tag_2': {'Sonnenstunden': 12, 'Datum': '15.09.'}, 'Tag_3': {'Sonnenstunden': 11, 'Datum': '16.09.'}}
    Zeit = 18  
    
    normaler_Zyklus_Test_auf_Akku(50, 100)
    normaler_Zyklus_Test_auf_Akku(100, 50)
    test_Auf_Akkusschutz(50, int(SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"] - 1.0))

    
    #Test_5_31_5_Zyklus_mit_Entladung_Akkuschutz_ausloesen()
    #Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv()
    #Test_11_41_5_Normaler_Zyklus_akkuschutz_inaktiv()
    #Test_17_41_5_Zyklus_unterspannung_und_falschen_soc()
    
    if ErrorPresent == True:
        print("Ergebnis Wetter: ERROR")
    else:
        print("Ergebnis Wetter: OK")

def normaler_Zyklus_Test_auf_Akku(wert1,wert2):

    print("xxxxxxxxxxxxxxxxxxxxxxx %i-%i Zyklus xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"%(wert1,wert2))
    global BmsWerte
    if wert1 < wert2:
        for i in range(wert1, wert2):
            BmsWerte["AkkuProz"] = i
            testfunk()
            testfunk() 
            istAufAkku(BmsWerte)
    else:
        for i in reversed(range(wert2, wert1)):
            BmsWerte["AkkuProz"] = i
            testfunk()
            testfunk() 
            istAufAkku(BmsWerte)

def test_Auf_Akkusschutz(start, umschaltpunkt):

    normaler_Zyklus_Test_auf_Akku(start, umschaltpunkt + 1)
    BmsWerte["AkkuProz"] = umschaltpunkt
    testfunk()   
    testfunk()    
    istAufNetz(BmsWerte)

def  Test_5_100_5_Zyklus():
    global BmsWerte
    # Wir starten im normalen Betrieb mit Akku
    BmsWerte["WrMode"] = VerbraucherAkku
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-100-5 Zyklus xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    istAufNetzMitLaden(BmsWerte)
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()
    istAufNetzMitLaden(BmsWerte)

def Test_5_100_5_Zyklus_nach_unterspannung():
    global BmsWerte
    
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()

    print("xxxxxxxxxxxxxxxxxxxxxxx 5-100-5 Zyklus nach unterspannung xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    istAufNetzMitLaden(BmsWerte)
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()
    istAufNetzMitLaden(BmsWerte)
    

    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")  
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufPvNetz(BmsWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 5    
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    istAufNetzMitLaden(BmsWerte)
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()   
    istAufNetzMitLaden(BmsWerte)    

def Test_5_31_5_Zyklus_mit_Entladung_Akkuschutz_ausloesen():
    global BmsWerte
    global SkriptWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-31-5 Zyklus mit Entladung -> Akkuschutz ausloesen xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    if BmsWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("Error")
        ErrorPresent = True
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("OK")

    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")    
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    if not SkriptWerte["MinSoc"]:
        print("vvvvv jetzt muss es auf PV und Netz schalten")
        BmsWerte["AkkuProz"] = 31
        testfunk()   
        testfunk()
        istAufPvNetz(BmsWerte)
        BmsWerte["AkkuProz"] = 27
        testfunk()   
        testfunk() 
        istAufPvNetz(BmsWerte)
        print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
        BmsWerte["AkkuProz"] = 11
        testfunk()   
        testfunk()
        istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)

def Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv():
    global BmsWerte
    global SkriptWerte
    
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-6-51-9 Zyklus. Test auf hoeheren Akkubereich Akkuschutz aktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    if BmsWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("Ok")
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("error")
        ErrorPresent = True
    if BmsWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("error")
        ErrorPresent = True
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("Ok")
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    print("vvvvv jetzt muss es auf PV und Netz schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    istAufPvNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    print("vvvvv jetzt muss es NetzLaden ein schalten")   
    BmsWerte["AkkuProz"] = 6
    testfunk()   
    testfunk()    
    istAufNetzMitLaden(BmsWerte)
    print("vvvvv jetzt muss es NetzLaden aus schalten")   
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk()    
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()    
    istAufNetz(BmsWerte)
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()    
    istAufPvNetz(BmsWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk()    
    istAufAkku(BmsWerte)
    if BmsWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("error")
        ErrorPresent = True
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("Ok")
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()   
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()  
    if SkriptWerte["MinSoc"]:
        istAufNetz(BmsWerte)    
    else:
        istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 75
    testfunk()
    testfunk() 
    istAufAkku(BmsWerte)

def Test_11_41_5_Normaler_Zyklus_akkuschutz_inaktiv():
    global BmsWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-5 Normaler Zyklus akkuschutz inaktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    if BmsWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("error")
        ErrorPresent = True
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("Ok")

    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk() 
    istAufAkku(BmsWerte)    
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()    
    istAufAkku(BmsWerte)

def Test_17_41_5_Zyklus_unterspannung_und_falschen_soc():
    global BmsWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 17-41-5 Zyklus unterspannung und falschen soc xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    

    BmsWerte["AkkuProz"] = 17
    testfunk()   
    testfunk() 
    istAufAkku(BmsWerte)

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
        ErrorPresent = True
        
    if BmsWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("Ok")
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("error")
        ErrorPresent = True
        
    istAufNetzMitLaden(BmsWerte)

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
    istAufPvNetz(BmsWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk() 
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    BmsWerte["AkkuProz"] = 5    
    testfunk()   
    testfunk()
    istAufAkku(BmsWerte)
    
    
testA()
testB()
testC()



    