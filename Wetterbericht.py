import requests
import re
import datetime



beVerbose = False

def myPrint(data):
    if beVerbose:
        print(data)

def getSonnenStunden():

    now = datetime.datetime.now()

    tabellenName = "table id=\"sun"
    sucheBeenden = "<\/tr>"
    tabellenTeil = "tr id=\"asd24"
    # <td data-tt-args="[&quot;Donnerstag, 16.07.&quot;,0]"
    tabellenDatum = r"""td data-tt-args=\"\[&quot;(.+)&quot;"""
    # <div>\n  0 h\n </div>\n
    #tabelleSonnenStunden = r"""<div>\n(.+)\n\s+</div>"""
    tabelleSonnenStunden = r"""<div>"""
    #tabelleSonnenStunden = r"""\S\s\S"""
    
    
    """
    
  </tbody>
 </table>

 <!-- Sonnenscheindauer, Aufgang und Untergang, UV -->
 <table id="sun">
    <tbody>    
    
    ...
    
        </tr>
    <tr id="asd24">
        <td data-tt-args="[&quot;Freitag, 17.07.&quot;,0]" data-tt-function="TTasdwrapper">
 <div>
  5 h
 </div>
 <span class="label">Sonnenstunden</span>
</td>
<td data-tt-args="[&quot;Samstag, 18.07.&quot;,1]" data-tt-function="TTasdwrapper">
 <div>
  7 h
 </div>
 <span class="label">Sonnenstunden</span>
</td>
<td data-tt-args="[&quot;Sonntag, 19.07.&quot;,2]" data-tt-function="TTasdwrapper">
 <div>
  6 h
 </div>
 <span class="label">Sonnenstunden</span>
</td>
<td data-tt-args="[&quot;Montag, 20.07.&quot;,3]" data-tt-function="TTasdwrapper">
 <div>
  13 h
 </div>
 <span class="label">Sonnenstunden</span>
</td>
"""

    url = r"https://www.wetteronline.de/wetter/geratskirchen?prefpar=sun"

    # hole website
    v = requests.get(url)
    
    # konvertiere von bytes zu string
    webstring = v.content.decode('utf-8')
    
    # mache eine Liste mit den einzelnen Zeilen
    li = webstring.splitlines()
    
    
    richtigeTabelleGefunden = False
    richtigeTabellenTeilGefunden = False
    tabelleDatumGefunden = False
    tabelleSonnenStundenGefunden = False
    wetterDaten = {}
    datum = ""
    sonnenStunden = ""
    
    for line in li:
    
        if re.findall(tabellenName, line):
            myPrint("Tabelle gefunden")
            #myPrint(line)
            richtigeTabelleGefunden = True
        
        if richtigeTabelleGefunden:
            
            if re.findall(tabellenTeil, line):
                richtigeTabellenTeilGefunden = True
                myPrint("TabellenTeil gefunden")
                
            if richtigeTabellenTeilGefunden:
                #myPrint(line)
                match = re.findall(tabellenDatum, line)
                if match:
                    myPrint("Datum gefunden")
                    datum = match[0]
                    tabelleDatumGefunden = True
  
            if tabelleSonnenStundenGefunden:
                sonnenStunden = line
                tabelleSonnenStundenGefunden = False
                tabelleDatumGefunden = False
                tempDate = datum.split()
                temp = tempDate[1].split(".")
                extDay = int(temp[0])
                extMonth = int(temp[1])
                tempSun = sonnenStunden.split()
                if extMonth == now.month:
                    if (extDay == now.day):
                        wetterDaten["Tag_0"] = {}
                        wetterDaten["Tag_0"]["Sonnenstunden"] = int(tempSun[0])
                        wetterDaten["Tag_0"]["Datum"] = tempDate[1]
                    elif (extDay == now.day + 1):
                        wetterDaten["Tag_1"] = {}
                        wetterDaten["Tag_1"]["Sonnenstunden"] = int(tempSun[0])
                        wetterDaten["Tag_1"]["Datum"] = tempDate[1]                  
                    elif (extDay == now.day + 2):
                        wetterDaten["Tag_2"] = {}
                        wetterDaten["Tag_2"]["Sonnenstunden"] = int(tempSun[0])
                        wetterDaten["Tag_2"]["Datum"] = tempDate[1]     
                    elif (extDay == now.day + 3):
                        wetterDaten["Tag_3"] = {}
                        wetterDaten["Tag_3"]["Sonnenstunden"] = int(tempSun[0])
                        wetterDaten["Tag_3"]["Datum"] = tempDate[1]      
                    elif (extDay == now.day + 4):
                        wetterDaten["Tag_4"] = {}
                        wetterDaten["Tag_4"]["Sonnenstunden"] = int(tempSun[0])
                        wetterDaten["Tag_4"]["Datum"] = tempDate[1]      
                myPrint("Datum: %s" %datum)
                myPrint("Sonne: %s" %sonnenStunden)
                myPrint("******")
                
            if tabelleDatumGefunden:
                match = re.findall(tabelleSonnenStunden, line)
                if match:
                    match = re.findall(tabelleSonnenStunden, line)
                    if match:
                        myPrint("Sonnenstunden gefunden")
                        tabelleSonnenStundenGefunden = True
                    
        if re.findall(sucheBeenden, line) and richtigeTabellenTeilGefunden:
            richtigeTabelleGefunden = False
            richtigeTabellenTeilGefunden = False
            tabelleDatumGefunden = False

    return wetterDaten
    
#print(getSonnenStunden())