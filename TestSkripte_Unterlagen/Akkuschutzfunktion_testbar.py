BmsWerte = {"AkkuStrom": 0.0, "Vmin": 0.0, "Vmax": 0.0, "AkkuAh": 0.0, "AkkuProz": 0, "Ladephase": "none", "BmsEntladeFreigabe":True, "WrEntladeFreigabe":True}
SocMonitorWerte = {"Prozent": 0}
SkriptWerte = {"WrNetzladen":False, "Akkuschutz":False, "RussiaMode": False, "Error":False, "WrMode":"", "SkriptMode":"Auto", "PowerSaveMode":False, "schaltschwelleAkku":100.0, "schaltschwelleNetz":20.0, "schaltschwelleAkkuTollesWetter":40.0, "schaltschwelleAkkuRussia":100.0, "schaltschwelleNetzRussia":80.0, "schaltschwelleAkkuSchlechtesWetter":50.0, "schaltschwelleNetzSchlechtesWetter":25.0}
InitAkkuProz = -1
EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False
wetterdaten = {}



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
    
    #now = datetime.datetime.now()
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
            #if now.hour >= 17 and now.hour < 23:
            if Zeit >= 17 and Zeit < 23:
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
            #if now.hour >= 12 and now.hour < 23:
            if Zeit >= 17 and Zeit < 23:
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

ErrorPresent = False

VerbraucherPVundNetz = "POP01"  # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherNetz = "POP00"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
VerbraucherAkku = "POP02"       # load prio 00=Netz, 02=Batt, 01=PV und Batt, wenn PV verfügbar ansonsten Netz
BattLeer = "PSDV43.0"
BattWiederEntladen = "PBDV48.0"
EntladeFreigabeGesendet = False
NetzLadenAusGesperrt = False
AutoInitWrMode = True

def sendeSkriptDaten():
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


def testfunk():
    global wetterDaten
    setInverterMode(wetterDaten)


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
    test_Auf_Akkusschutz_Wetter(50, int(SkriptWerte["verbrauchNachtAkku"] + SkriptWerte["MinSoc"] - 1.0))

    
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
            SocMonitorWerte["Prozent"] = i
            testfunk()
            testfunk() 
            istAufAkku(SkriptWerte)
    else:
        for i in reversed(range(wert2, wert1)):
            SocMonitorWerte["Prozent"] = i
            testfunk()
            testfunk() 
            istAufAkku(SkriptWerte)

def test_Auf_Akkusschutz_Wetter(start, umschaltpunkt):

    normaler_Zyklus_Test_auf_Akku(start, umschaltpunkt + 1)
    SocMonitorWerte["Prozent"] = umschaltpunkt
    testfunk()   
    testfunk()    
    istAufNetz(SkriptWerte)

def  Test_5_100_5_Zyklus():
    global SkriptWerte
    global BmsWerte
    # Wir starten im normalen Betrieb mit Akku
    SkriptWerte["WrMode"] = VerbraucherAkku
    SocMonitorWerte["Prozent"] = 27
    print("xxxxxxxxxxxxxxxxxxxxxxx 5-100-5 Zyklus xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 5
    testfunk()   
    testfunk()
    print("hier")
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 11
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 5
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    
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
    
    SocMonitorWerte["Prozent"] = 5
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
    

    SocMonitorWerte["Prozent"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")  
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 11
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 5    
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    
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

    SocMonitorWerte["Prozent"] = 5
    testfunk()   
    testfunk() 
    print("vvvvv jetzt muss es Laden ausschalten")    
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    if not SkriptWerte["MinSoc"]:
        print("vvvvv jetzt muss es auf PV und Netz schalten")
        SocMonitorWerte["Prozent"] = 31
        testfunk()   
        testfunk()
        istAufPvNetz(SkriptWerte)
        SocMonitorWerte["Prozent"] = 27
        testfunk()   
        testfunk() 
        istAufPvNetz(SkriptWerte)
        print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
        SocMonitorWerte["Prozent"] = 11
        testfunk()   
        testfunk()
        istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 9
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)

def Test_11_41_6_51_9_Zyklus_Test_auf_hoeheren_Akkubereich_Akkuschutz_aktiv():
    global BmsWerte
    global SkriptWerte
    
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-6-51-9 Zyklus. Test auf hoeheren Akkubereich Akkuschutz aktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    SkriptWerte["Akkuschutz"] = True
    
    if SkriptWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("error")
        ErrorPresent = True
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("Ok")
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk() 
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    SocMonitorWerte["Prozent"] = 51
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    print("vvvvv jetzt muss es auf Netz ohne Laden schalten")   
    SocMonitorWerte["Prozent"] = 11
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 9
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es NetzLaden ein schalten")   
    SocMonitorWerte["Prozent"] = 6
    testfunk()   
    testfunk()    
    istAufNetzMitLaden(SkriptWerte)
    print("vvvvv jetzt muss es NetzLaden aus schalten")   
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk()    
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()    
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk()    
    istAufNetz(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    SocMonitorWerte["Prozent"] = 51
    testfunk()   
    testfunk()    
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 66
    testfunk()   
    testfunk()   
    if SkriptWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("error")
        ErrorPresent = True
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("Ok")
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()   
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 9
    testfunk()   
    testfunk()  
    if SkriptWerte["MinSoc"]:
        istAufNetz(SkriptWerte)    
    else:
        istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 75
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)

def Test_11_41_5_Normaler_Zyklus_akkuschutz_inaktiv():
    global BmsWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 11-41-5 Normaler Zyklus akkuschutz inaktiv xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    SkriptWerte["Akkuschutz"] = False

    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 51
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)    
    SocMonitorWerte["Prozent"] = 11
    testfunk()
    testfunk() 
    istAufAkku(SkriptWerte)


def Test_17_41_5_Zyklus_unterspannung_und_falschen_soc():
    global BmsWerte
    global SkriptWerte
    print("xxxxxxxxxxxxxxxxxxxxxxx 17-41-5 Zyklus unterspannung und falschen soc xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    SkriptWerte["Akkuschutz"] = False
    SkriptWerte["WrMode"] = VerbraucherAkku
    SocMonitorWerte["Prozent"] = 17
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
    SocMonitorWerte["Prozent"] = 27
    testfunk()    
    testfunk()
    istAufNetzMitLaden(SkriptWerte)
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk() 
    istAufNetzMitLaden(SkriptWerte)
    SocMonitorWerte["Prozent"] = 41
    testfunk()   
    testfunk()
    istAufNetzMitLaden(SkriptWerte)
    print("vvvvv jetzt muss es auf Akku schalten")    
    SocMonitorWerte["Prozent"] = 51
    testfunk()   
    testfunk() 
    istAufAkku(SkriptWerte)
    if SkriptWerte["WrNetzladen"]:
        print("vvv WrNetzladen gesetzt") 
        print("error")
        ErrorPresent = True
    else:
        print("vvv WrNetzladen nicht gesetzt")
        print("Ok")
    SocMonitorWerte["Prozent"] = 31
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 27
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    if SkriptWerte["Akkuschutz"]:
        print("vvv Akkuschutz gesetzt")
        print("Ok")
    else:
        print("vvv Akkuschutz nicht gesetzt") 
        print("error")
        ErrorPresent = True
    SocMonitorWerte["Prozent"] = 66
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
    SocMonitorWerte["Prozent"] = 11
    testfunk()   
    testfunk()
    istAufAkku(SkriptWerte)
    SocMonitorWerte["Prozent"] = 5    
    testfunk()   
    testfunk()
    istAufNetz(SkriptWerte)
    SocMonitorWerte["Prozent"] = 66
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



    