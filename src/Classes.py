import os
import zlib
import xlrd
import xlwt
import math
# import pudb; pu.db

class FILE:
    def __init__(self, data):
        self.data = data
        self.address = 0
        self.encoding = {
            1: 'utf-8',
            2: 'utf-16',
        }

    def read(self, size=4):
        value = int.from_bytes(self.data[self.address:self.address+size], byteorder='little', signed=True)
        self.address += size
        return value

    def readValue(self, address, size=4):
        return int.from_bytes(self.data[address:address+size], byteorder='little', signed=True)

    def readString(self, size=1):
        # Find end of string
        addrStart = self.address
        while self.address < len(self.data) and self.data[self.address]:
            self.address += size
        # Decode string
        string = self.data[addrStart:self.address].decode(self.encoding[size])
        # Increment address up to the next string
        while self.address < len(self.data):
            if self.data[self.address] > 0:
                break
            self.address += 1
        return string


# FILE object + access to reading and patching as if a spreadsheet
class DATAFILE(FILE):
    def __init__(self, data):
        super().__init__(data)
        self.address = 8
        # Data
        self.base = self.read()
        self.size = self.read()
        # Command strings
        self.comBase = self.read()
        self.comSize = self.read()
        # Text
        self.textBase = self.read()
        self.textSize = self.read()
        # Entries
        self.stride = self.read() # bytes / entry
        self.count = self.read()  # number of entries

    def getTextData(self):
        data = self.data[self.textBase:self.textBase+self.textSize]
        data = bytes(data[::2]).split(b'\x00')
        y = len(data) // self.count
        x = [[str(d)[2:] for d in data[i::y]] for i in range(y)]
        return x

    def getComData(self):
        data = self.data[self.comBase:self.comBase+self.comSize]
        x = bytes(data).split(b'\x00')
        try:
            return [xi.decode() for xi in x]
        except:
            return []
        
    # Data tables can only be updated under certain circumstances.
    # Assumes all columns have the same byte size (currently 4)
    # Assumes no text.
    # Now, only use for Shops and Ability tables
    def updateData(self, *cols):
        # Ensure no text
        assert self.comSize == 0
        assert self.textSize == 0
        # Update data
        data = bytearray([])
        numEntries = 0
        for row in zip(*cols):
            for ri in row:
                data += ri.to_bytes(4, byteorder='little', signed=True)
            numEntries += 1
        lenData = len(data).to_bytes(4, byteorder='little', signed=True)
        fileSize = int(len(data)+0x30).to_bytes(4, byteorder='little', signed=True)
        header = bytearray(b'BTBF')
        header += fileSize
        header += int(0x30).to_bytes(4, byteorder='little', signed=True)
        header += lenData
        header += fileSize + bytearray([0]*4)
        header += fileSize + bytearray([0]*4)
        header += int(8).to_bytes(4, byteorder='little', signed=True)
        header += numEntries.to_bytes(4, byteorder='little', signed=True)
        header += bytearray([0]*8)
        self.data = header + data

    def readCol(self, col, row=0, numRows=None):
        if not numRows:
            numRows = self.count
        numRows = min(numRows, self.count - row)
        data = []
        for r in range(row, row+numRows):
            data.append( self.readValue(r, col) )
        return data

    def readRow(self, row, col=0, numCol=None):
        if not numCol:
            maxCol = int(self.stride / 4)
            numCol = maxCol - col
        data = []
        for c in range(col, col+numCol):
            data.append( self.readValue(row, c) )
        return data
    
    def readValue(self, row, col, size=4):
        address = self.base + row*self.stride + col*size
        return int.from_bytes(self.data[address:address+size], byteorder='little', signed=True)

    def patchCol(self, lst, col, row=0):
        for i, value in enumerate(lst):
            self.patchValue(value, row+i, col)

    def patchRow(self, lst, row, col=0):
        for i, value in enumerate(lst):
            self.patchValue(value, row, col+i)

    def patchValue(self, value, row, col, size=4):
        address = self.base + row*self.stride + col*size
        self.data[address:address+size] = value.to_bytes(size, byteorder='little', signed=True)
    
    def readComString(self, row, col):
        offset = self.readValue(row, col)
        self.address = self.comBase + offset
        return self.readString(size=1)

    def readTextString(self, row, col):
        offset = self.readValue(row, col)
        self.address = self.textBase + offset
        return self.readString(size=2)

    def readTextStringAll(self, col):
        strings = []
        for row in range(self.count):
            string = self.readTextString(row, col)
            strings.append(string)
        return strings
    
    # TODO
    def patchString(self):
        pass

    # TODO -- probably won't need to patch commands, only text
    def patchTextString(self, string, row, col):
        # Check string first to ensure it fits!
        check = self.readTextString(row, col)
        assert len(check) >= len(string), 'String is too long!'
        sizeDiff = 2 * (len(check) - len(string))
        # Encode string
        newString = string.encode('utf-16')[2:]
        newString += bytearray([0]*sizeDiff)
        # Patch
        offset = self.readValue(row, col)
        address = self.textBase + offset
        self.data[address:address+len(newString)] = newString
        


class TABLE:
    def __init__(self, fileName):
        self.fileName = fileName
        with open(self.fileName, 'rb') as file:
            self.tableData = bytearray(file.read())
        baseName = os.path.basename(self.fileName)
        self.crowdFiles = {baseName: DATAFILE(self.tableData)}

    def dumpSheet(self):
        sheetName = self.fileName.split('.')[0] + '.xlsx'
        wb = xlwt.Workbook()
        for file in self.crowdFiles:
            if file == '.fscache':
                continue

            x = file.replace('_', ' ')
            if len(x) > 31:
                x = x[:31]
            wb.add_sheet(x)
            sheet = wb.get_sheet(x)

            data = self.crowdFiles[file]
            com = data.getComData()
            textData = data.getTextData()
            numCol = int(data.stride / 4)
            numRows = data.count

            # TEXT STUFF
            comCols = int(round(len(com) / numRows))
            if comCols == 0 and com:
                for c in com:
                    assert c == ''
                comCols = len(com)

            col = 0
            row = 1
            counter = 0
            while com:
                for i in range(comCols):
                    if com:
                        value = com.pop(0)
                        sheet.write(row, col+i, value)
                row += 1
                counter += 1
                if counter == 10000:
                    print('STUCK IN LOOP IN ', file, sheetName)
            col += max(1, comCols)

            for text in textData:
                for row, value in enumerate(text):
                    sheet.write(row+1, col, value)
                col += 1

            for i in range(numCol):
                colData = data.readCol(i)
                for row, value in enumerate(colData):
                    sheet.write(row+1, col, value)
                col += 1

            pre, ext = os.path.splitext(self.fileName)
            output = pre + '.xlsx'
            wb.save(output)
            

    def dump(self):
        with open(self.fileName, 'wb') as file:
            file.write(self.tableData)



class CROWD:
    def __init__(self, path):
        self.path = path
        
        fileName = os.path.join(path, 'index.fs')
        with open(fileName, 'rb') as file:
            self.indexData = bytearray(file.read())
            self.indexFile = FILE(self.indexData)

        fileName = os.path.join(path, 'crowd.fs')
        with open(fileName, 'rb') as file:
            self.crowdData = bytearray(file.read())

        # Split crowd files
        self.isCompressed = {}
        self.crowdFiles = {}
        self.separateCrowd()

    def dump(self):
        # Rebuild index and crowd data
        self.joinCrowd()
        # Dump index
        fileOut = os.path.join(self.path, 'index.fs')
        with open(fileOut, 'wb') as file:
            file.write(self.indexData)
        # Dump crowd
        fileOut = os.path.join(self.path, 'crowd.fs')
        with open(fileOut, 'wb') as file:
            file.write(self.crowdData)

    def dumpFiles(self, outpath):
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        for fileName, data in self.crowdFiles.items():
            fileOut = os.path.join(self.path, fileName)
            with open(fileOut, 'wb') as file:
                file.write(data.data)

    def separateCrowd(self):
        nextAddr = self.indexFile.read()
        while True:
            # Extract file from crowd.fs
            base = self.indexFile.read()
            size = self.indexFile.read()
            self.indexFile.address += 4
            fileName = self.indexFile.readString()
            self.crowdFiles[fileName] = self.extractFile(fileName, base, size)
            # Last entry?
            if nextAddr == 0:
                break
            # Setup for next file
            self.indexFile.address = nextAddr
            nextAddr = self.indexFile.read()

    def adjustSize(self, data):
        if len(data) % 4:
            x = 4 - (len(data) % 4)
            data += bytearray([0]*x)
        return data

    def joinCrowd(self):
        self.indexData = bytearray([])
        self.crowdData = bytearray([])
        for i, fileName in enumerate(self.crowdFiles):
            # File for the crowd (compressed if necessary)
            data = self.getData(fileName)
            # Entry in the index file
            crowdStart = len(self.crowdData).to_bytes(4, byteorder='little')
            crowdSize = len(data).to_bytes(4, byteorder='little')
            byteFileName = bytearray(map(ord, fileName))
            crc32 = zlib.crc32(byteFileName).to_bytes(4, byteorder='little')
            entry = crowdStart + crowdSize + crc32 + byteFileName + bytearray([0])
            entry = self.adjustSize(entry)
            if i < len(self.crowdFiles)-1:
                size = len(self.indexData) + 4 + len(entry)
                pointer = size.to_bytes(4, byteorder='little')
            else:
                pointer = bytearray([0]*4)
            self.indexData +=  pointer + entry
            # Append crowd file
            self.crowdData += data
            self.crowdData = self.adjustSize(self.crowdData)
        # Finalize crowdData (actually necessary sometimes!)
        self.crowdData = self.adjustSize(self.crowdData)

    def extractFile(self, fileName, base, size):
        self.isCompressed[fileName] = self.crowdData[base] == 0x60
        if self.isCompressed[fileName]:
            decompSize = int.from_bytes(self.crowdData[base+1:base+4], byteorder='little', signed=True)
            try: # On the off chance the file starts with 0x60 but is not compressed!
                data = zlib.decompress(self.crowdData[base+4:base+size], -15)
                data = bytearray(data)
                assert len(data) == decompSize
            except:
                self.isCompressed[fileName] = False
        if not self.isCompressed[fileName]:
            data = self.crowdData[base:base+size]
        return DATAFILE(data)
        # self.isCompressed[fileName] = self.crowdData[base] & 0xFF  == 0x60
        # if self.isCompressed[fileName]:
        #     data = zlib.decompress(self.crowdData[base+4:base+size], -15)
        #     data = bytearray(data)
        # else:
        #     data = self.crowdData[base:base+size]
        # return DATAFILE(data)

    def getData(self, fileName):
        data = self.crowdFiles[fileName].data
        if self.isCompressed[fileName]:
            size = len(data)
            data = zlib.compress(data)[2:-4]
            header = int((size << 8) + 0x60).to_bytes(4, byteorder='little')
            data = header + data
        return data

    def dumpSheet(self):
        wb = xlwt.Workbook()
        for file in self.crowdFiles:
            if file == '.fscache':
                continue
            # x = os.path.basename(self.fileName).replace('_', ' ')
            x = file.replace('_', ' ')
            if len(x) > 31:
                x = x[:31]
            wb.add_sheet(x)
            sheet = wb.get_sheet(x)

            data = self.crowdFiles[file]
            com = data.getComData()
            textData = data.getTextData()
            numCol = int(data.stride / 4)
            numRows = data.count

            # TEXT STUFF
            comCols = int(round(len(com) / numRows))
            if comCols == 0 and com:
                for c in com:
                    assert c == ''
                comCols = len(com)

            col = 0
            row = 1
            while com:
                for i in range(comCols):
                    if com:
                        value = com.pop(0)
                        sheet.write(row, col+i, value)
                row += 1
            col += max(1, comCols)

            for text in textData:
                for row, value in enumerate(text):
                    sheet.write(row+1, col, value)
                col += 1

            for i in range(numCol):
                colData = data.readCol(i)
                for row, value in enumerate(colData):
                    sheet.write(row+1, col, value)
                col += 1

        sheetName = os.path.join(self.path, 'crowd.xlsx')
        wb.save(sheetName)
            
