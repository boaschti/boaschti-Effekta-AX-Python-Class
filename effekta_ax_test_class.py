import serial
import crc16
 
# For Debuging:
#serWR1 = serial.Serial('/dev/ttyUSB0', 2400, timeout=2)  # open serial port effekta 1
#serextra = serial.Serial('/dev/ttyUSB2', 2400, timeout=2)  # open serial port

#stty -F /dev/ttyUSB2 2400 cs8 -cstopb -parenb
#tail -f /dev/ttyUSB2
#tail -f /dev/ttyUSB2 | hexdump -v -e '/1 "%02X\n"'

#echo -ne "\x51\x50\x49\xBE\xAC\x0D" > /dev/ttyUSB0

#http://allican.be/blog/2017/01/28/reverse-engineering-cypress-serial-usb.html


#beVerbose = True



class EffektaConn:

    def __init__(self, name, serialName, beVerbose = False):
        self.name = name
        self.beVerbose = beVerbose
        self.serialName = serialName
        self.serialConn = serial.Serial(serialName, 2400, timeout=2)
        
    def __delete__(self):
        self.serialConn.close()
        
    def EffektaName(self):
        return self.name

    def getEffektaCRC(self, cmd):
        crc = crc16.crc16xmodem(cmd).to_bytes(2,'big')
        crcbytes = bytearray(crc)
        for i in range(len(crcbytes)):
            if crcbytes[i] == 0x0a or crcbytes[i] == 0x0d or crcbytes[i] == 0x28:
                crcbytes[i] = crcbytes[i] + 1
                if self.beVerbose:
                    print("CRCBytes escaped")
                
        return bytes(crcbytes)

    def getCommand(self, cmd):
        cmd = cmd.encode('utf-8')
        crc = self.getEffektaCRC(cmd)
        cmd = cmd + crc
        cmd = cmd + b'\r'
        return cmd
    

    def getEffektaData(self, cmd):
        cmd = self.getCommand(cmd)
        if self.beVerbose:
            print(cmd)
        try:
            self.serialConn.write(cmd)

            x = self.serialConn.readline()
        except:
            self.serialConn.close()
            self.serialConn = serial.Serial(self.serialName, 2400, timeout=2)
            return None
        
        y = bytearray(x)
        lenght = len(y)
        receivedCrc = bytearray(b'')
        receivedCrc = y[lenght - 3 : lenght - 1]
        del y[lenght - 3 : lenght - 0]
        

        if bytes(receivedCrc) == self.getEffektaCRC(bytes(y)):
            del y[0]
            data = y.decode()
            if self.beVerbose:
                print("crc ok")
                print(data)
            if data == "NAK":
                return ""
            else:
                return data
        else:
            if self.beVerbose:
                print("crc error")
                print("incoming data:")
                print(x)
            return ""

    def setEffektaData(self, cmd, value = ""):
        
        retVal = self.getEffektaData(cmd + value)
        
        if "ACK" == retVal:
            if self.beVerbose:
                print("set cmd OK")
            return True
        else:
            if self.beVerbose:
                print("set cmd: %s error" % cmd + value)
                print(retVal)
            return False
