BmsWerte = {"AkkuStrom": 0.0, "Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "AkkuProz": 0, "Ladephase": "none", "BmsEntladeFreigabe":True, "WrEntladeFreigabe":True}


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


def sendeSkripDaten():
    pass

def myPrint(msg):

    print(msg)

def schalteAlleWrAufAkku():
    SkriptWerte["WrMode"] = VerbraucherAkku
    SkriptWerte["WrEntladeFreigabe"] = True
    SkriptWerte["WrNetzladen"] = False

def schalteAlleWrNetzLadenAus():
    # Funktion ok, wr schaltet netzladen aus
    SkriptWerte["WrNetzladen"] = False

def schalteAlleWrNetzLadenEin():
    # Funktion ok, wr schaltet netzladen aus
    SkriptWerte["WrNetzladen"] = True

def schalteAlleWrVerbraucherPVundNetz():
    SkriptWerte["WrMode"] = VerbraucherPVundNetz
    SkriptWerte["WrEntladeFreigabe"] = True

def schalteAlleWrAufNetzOhneNetzLaden():
    SkriptWerte["WrMode"] = VerbraucherNetz
    SkriptWerte["WrEntladeFreigabe"] = False
    SkriptWerte["WrNetzladen"] = False

def schalteAlleWrAufNetzMitNetzladen():
    SkriptWerte["WrMode"] = VerbraucherNetz
    SkriptWerte["WrEntladeFreigabe"] = False
    SkriptWerte["WrNetzladen"] = True

def autoInitInverter():
    pass

SkriptWerte = {"WrNetzladen":False, "Akkuschutz":False, "Error":False, "WrMode":"", "SkriptMode":"Auto"}
InitAkkuProz = -1

def testfunk():

    global SkriptWerte
    global BmsWerte
    global EntladeFreigabeGesendet
    global NetzLadenAusGesperrt
    global wetterDaten

    AutoInitWrMode = False
    sendeMqtt = False
    
    SkriptWerte["schaltschwelleNetzLadenaus"] = 10.0
    SkriptWerte["schaltschwelleNetzLadenein"] = 7.0

    SkriptWerte["verbrauchNachtAkku"] = 25.0
    SkriptWerte["verbrauchNachtNetz"] = 3.0
    
    if SkriptWerte["Akkuschutz"]:
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
        sendeMqtt = True
        
    # Wir setzen den Error bei 100 prozent zurück. In der Hoffunng dass nicht immer 100 prozent vom BMS kommen dieses fängt aber bei einem Neustart bei 0 proz an.
    if BmsWerte["AkkuProz"] >= 100.0:
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
            #if now.hour >= 17 and now.hour < 23:
            if Zeit >= 17 and Zeit < 23:
                if "Tag_1" in wetterDaten:
                    if wetterDaten["Tag_1"] != None:
                        if wetterDaten["Tag_1"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"]:
                        # Wir wollen den Akku schonen weil es nichts bringt wenn wir ihn leer machen
                            if BmsWerte["AkkuProz"] < (SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"]):
                                if SkriptWerte["WrMode"] == VerbraucherAkku:
                                    SkriptWerte["Akkuschutz"] = True
                                    schalteAlleWrAufNetzOhneNetzLaden()
                                    myPrint("Info: Sonne morgen < %ih -> schalte auf Netz." %SkriptWerte["wetterSchaltschwelleNetz"])
                    else:
                        myPrint("Info: Keine Wetterdaten!")
            # In der Sommerzeit löst now.hour = 17 um 18 Uhr aus, In der Winterzeit dann um 17 Uhr
            #elif now.hour >= 12 and now.hour < 23:
            elif Zeit >= 12 and Zeit < 23:
                if "Tag_0" in wetterDaten:
                    if wetterDaten["Tag_0"] != None and wetterDaten["Tag_1"] != None:
                        if wetterDaten["Tag_0"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"] and wetterDaten["Tag_1"]["Sonnenstunden"] <= SkriptWerte["wetterSchaltschwelleNetz"]:
                        # Wir wollen den Akku schonen weil es nichts bringt wenn wir ihn leer machen
                            if BmsWerte["AkkuProz"] < (SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"]):
                                if SkriptWerte["WrMode"] == VerbraucherAkku or SkriptWerte["WrMode"] == VerbraucherPVundNetz:
                                    SkriptWerte["Akkuschutz"] = True
                                    schalteAlleWrAufNetzOhneNetzLaden()
                                    myPrint("Info: Sonne heute und morgen < %ih -> schalte auf Netz." %SkriptWerte["wetterSchaltschwelleNetz"])
                    else:
                        myPrint("Info: Keine Wetterdaten!")

            #if now.hour >= 8 and now.hour < 17:
            if Zeit >= 8 and Zeit < 17:
                # Ab hier beginnnt der Teil der die Anlage stufenweise wieder auf Akkubetrieb schaltet 
                # dieser Teil soll Tagsüber aktiv sein das macht Nachts keinen Sinn weil der Akkustand nicht steigt
                EntladeFreigabeGesendet = False
                # Wenn der Akku wieder über die schaltschwelleAkku ist dann wird er wieder Tag und Nacht genutzt
                if not SkriptWerte["WrMode"] == VerbraucherAkku and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleAkku"]:
                    SkriptWerte["Akkuschutz"] = False
                    schalteAlleWrAufAkku()
                    myPrint("Info: Schalte alle WR auf Akku")
                # Wenn der Akku über die schaltschwellePvNetz ist dann geben wir den Akku wieder frei wenn PV verfügbar ist. PV (Tag), Netz (Nacht)
                elif SkriptWerte["WrMode"] == VerbraucherNetz and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
                    # Hier wird explizit nur geschalten wenn der WR auf VerbraucherNetz steht damit der Zweig nur reagiert wenn der Akku leer war und voll wird 
                    schalteAlleWrNetzLadenAus()
                    NetzLadenAusGesperrt = False
                    schalteAlleWrVerbraucherPVundNetz()
                    myPrint("Info: Schalte alle WR Verbraucher PV und Netz")
            # Ab hier beginnt der Teil der die Anlage auf  Netz schaltet sowie das Netzladen ein und aus schaltet
            # Wir schalten auf Netz wenn der min Soc unterschritten wird
            if SkriptWerte["WrMode"] == VerbraucherAkku and BmsWerte["AkkuProz"] <= SkriptWerte["MinSoc"]:
                schalteAlleWrAufNetzOhneNetzLaden()
                myPrint("Schalte alle WR Netz ohne laden. MinSOC.")
                myPrint("Info: MinSoc %iP erreicht -> schalte auf Netz." %SkriptWerte["MinSoc"])
            # Wenn das Netz Laden durch eine Unterspannungserkennung eingeschaltet wurde schalten wir es aus wenn der Akku wieder 10% hat
            elif SkriptWerte["WrNetzladen"] == True and NetzLadenAusGesperrt == False and BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
                schalteAlleWrNetzLadenAus()
                myPrint("Schalte alle WR Netz laden aus")
                myPrint("Info: NetzLadenaus %iP erreicht -> schalte Laden aus." %SkriptWerte["schaltschwelleNetzLadenaus"])
            # Wenn die Verbraucher auf PV (Tag) und Netz (Nacht) geschaltet wurden und der Akku wieder unter die schaltschwelleNetz fällt dann wird auf Netz geschaltet
            elif SkriptWerte["WrMode"] == VerbraucherPVundNetz and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetz"]:
                schalteAlleWrAufNetzOhneNetzLaden()
                myPrint("Info: Schalte auf Netz")
            elif SkriptWerte["WrMode"] != VerbraucherAkku and SkriptWerte["WrNetzladen"] == False and SkriptWerte["Akkuschutz"] == False and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetzLadenaus"] and BmsWerte["AkkuProz"] > 0.0:
                SkriptWerte["Akkuschutz"] = True
                myPrint("Schalte Akkuschutz ein")
                myPrint("Info: %iP erreicht -> schalte Akkuschutz ein." %SkriptWerte["schaltschwelleNetzLadenaus"])
            elif SkriptWerte["WrNetzladen"] == False and SkriptWerte["Akkuschutz"] == True and BmsWerte["AkkuProz"] <= SkriptWerte["schaltschwelleNetzLadenein"]:
                schalteAlleWrNetzLadenEin()
                myPrint("Info: Schalte Netz mit laden")
    elif EntladeFreigabeGesendet == False:
        EntladeFreigabeGesendet = True
        schalteAlleWrAufNetzMitNetzladen()
        # Falls der Akkustand zu hoch ist würde nach einer Abschaltung das Netzladen gleich wieder abgeschaltet werden das wollen wir verhindern
        myPrint("Info: Schalte auf Netz mit laden")
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwelleNetzLadenaus"]:
            # Wenn eine Unterspannnung SOC > schaltschwelleNetzLadenaus ausgelöst wurde dann stimmt mit dem SOC etwas nicht der wird bei schaltschwelle PVNEtz wieder zurück gesetzt
            NetzLadenAusGesperrt = True
            SkriptWerte["Akkuschutz"] = True
            myPrint("Error: Ladestand weicht ab")
        # wir setzen einen error weil das nicht plausibel ist und wir hin und her schalten sollte die freigabe wieder kommen
        if BmsWerte["AkkuProz"] >= SkriptWerte["schaltschwellePvNetz"]:
            SkriptWerte["Error"] = True
            myPrint("Error: Ladestand nicht plausibel")
        sendeMqtt = True

    if sendeMqtt == True: 
        sendeMqtt = False
        sendeSkripDaten()


def istAufAkku(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherAkku and SkriptWerte["WrNetzladen"] == False:
        print("OK")
    else: 
        print("Error")
        ErrorPresent = True

def istAufPvNetz(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherPVundNetz and SkriptWerte["WrNetzladen"] == False:
        print("OK")
    else: 
        print("Error")
        ErrorPresent = True

def istAufNetz(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherNetz and SkriptWerte["WrNetzladen"] == False:
        print("OK")
    else: 
        print("Error")     
        ErrorPresent = True        

def istAufNetzMitLaden(dict):
    global ErrorPresent
    if dict["WrMode"] == VerbraucherNetz and SkriptWerte["WrNetzladen"] == True:
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
    
    schalteAlleWrAufAkku()
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
            istAufAkku(SkriptWerte)
    else:
        for i in reversed(range(wert2, wert1)):
            BmsWerte["AkkuProz"] = i
            testfunk()
            testfunk() 
            istAufAkku(SkriptWerte)

def test_Auf_Akkusschutz(start, umschaltpunkt):

    normaler_Zyklus_Test_auf_Akku(start, umschaltpunkt + 1)
    BmsWerte["AkkuProz"] = umschaltpunkt
    testfunk()   
    testfunk()    
    istAufNetz(SkriptWerte)

def  Test_5_100_5_Zyklus():
    global BmsWerte
    # Wir starten im normalen Betrieb mit Akku
    BmsWerte["WrMode"] = VerbraucherAkku
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-100-5 Zyklus xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    istAufNetzMitLaden(SkriptWerte)
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()
    istAufNetzMitLaden(SkriptWerte)

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
    istAufNetzMitLaden(SkriptWerte)
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()
    istAufNetzMitLaden(SkriptWerte)
    

    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")  
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufPvNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 5    
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    
    print("vvvvv jetzt muss es auf Netz mit Laden schalten") 
    BmsWerte["BmsEntladeFreigabe"] = False
    testfunk()   
    testfunk()
    istAufNetzMitLaden(SkriptWerte)
    BmsWerte["BmsEntladeFreigabe"] = True
    testfunk()   
    testfunk()   
    istAufNetzMitLaden(SkriptWerte)    

def Test_5_31_5_Zyklus_mit_Entladung_Akkuschutz_ausloesen():
    global BmsWerte
    global SkriptWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-31-5 Zyklus mit Entladung -> Akkuschutz ausloesen xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    if SkriptWerte["Akkuschutz"]:
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
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    if not SkriptWerte["MinSoc"]:
        print("vvvvv jetzt muss es auf PV und Netz schalten")
        BmsWerte["AkkuProz"] = 31
        testfunk()   
        testfunk()
        istAufPvNetz(SkriptWerte)
        BmsWerte["AkkuProz"] = 27
        testfunk()   
        testfunk() 
        istAufPvNetz(SkriptWerte)
        print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
        BmsWerte["AkkuProz"] = 11
        testfunk()   
        testfunk()
        istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)

def Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv():
    global BmsWerte
    global SkriptWerte
    
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-6-51-9 Zyklus. Test auf hoeheren Akkubereich Akkuschutz aktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    if SkriptWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("Ok")
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("error")
        ErrorPresent = True
    if SkriptWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("error")
        ErrorPresent = True
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("Ok")
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf PV und Netz schalten")    
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk() 
    istAufPvNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es NetzLaden ein schalten")   
    BmsWerte["AkkuProz"] = 6
    testfunk()   
    testfunk()    
    istAufNetzMitLaden(SkriptWerte)
    print("vvvvv jetzt muss es NetzLaden aus schalten")   
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk()    
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()    
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf PV und Netz schalten")
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()    
    istAufPvNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk()    
    istAufAkku(SkriptWerte)
    if SkriptWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("error")
        ErrorPresent = True
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("Ok")
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()   
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 9
    testfunk()   
    testfunk()  
    if SkriptWerte["MinSoc"]:
        istAufNetz(SkriptWerte)    
    else:
        istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 75
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)

def Test_11_41_5_Normaler_Zyklus_akkuschutz_inaktiv():
    global BmsWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-5 Normaler Zyklus akkuschutz inaktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    if SkriptWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("error")
        ErrorPresent = True
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("Ok")

    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)    
    BmsWerte["AkkuProz"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 5
    testfunk()   
    testfunk()    
    istAufAkku(SkriptWerte)

def Test_17_41_5_Zyklus_unterspannung_und_falschen_soc():
    global BmsWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 17-41-5 Zyklus unterspannung und falschen soc xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    

    BmsWerte["AkkuProz"] = 17
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)

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
        
    if SkriptWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("Ok")
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("error")
        ErrorPresent = True
        
    istAufNetzMitLaden(SkriptWerte)

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
    istAufPvNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    BmsWerte["AkkuProz"] = 51
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 11
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    BmsWerte["AkkuProz"] = 5    
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    
    
testA()
testB()
testC()

if ErrorPresent == True:
    print("Ergebnis Gesamt: ERROR")
else:
    print("Ergebnis Gesamt: OK")



    