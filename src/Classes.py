import os
import sys
import zlib
import xlrd
import xlwt
import math
import struct
import hashlib
from io import BytesIO
import pudb; pu.db

class FILE:
    def __init__(self, data):
        self.fileSize = len(data)
        self.data = BytesIO(data)

    def getData(self):
        return self.data.getbuffer().tobytes()

    def readStringUTF8(self):
        string = bytearray()
        while True:
            string += self.data.read(1)
            if string[-1] == 0:
                break
        return string.decode('utf-8')[:-1]

    def readStringUTF16(self):
        string = bytearray()
        while True:
            string += self.data.read(2)
            if string[-2:] == b'\x00\x00':
                break
        return string.decode('utf-16')[:-1]

    def readString(self, size):
        string = self.data.read(size)
        return string.decode('utf-8')

    def readInt8(self):
        return struct.unpack("<b", self.data.read(1))[0]

    def readUInt8(self):
        return struct.unpack("<B", self.data.read(1))[0]

    def readInt16(self):
        return struct.unpack("<h", self.data.read(2))[0]

    def readInt32(self):
        return struct.unpack("<l", self.data.read(4))[0]

    def readUInt32(self):
        return struct.unpack("<L", self.data.read(4))[0]

    def readInt64(self):
        return struct.unpack("<q", self.data.read(8))[0]

    def readUInt64(self):
        return struct.unpack("<Q", self.data.read(8))[0]

    def readFloat(self):
        return struct.unpack("<f", self.data.read(4))[0]


# FILE object + access to reading and patching as if a spreadsheet
class DATAFILE(FILE):
    def __init__(self, fileName, data):
        inflated = self.decompress(data)
        self.sha = hashlib.sha1(inflated).hexdigest()
        super().__init__(inflated)

        # File
        self.fileName = fileName
        self.fileFormat = self.readFileFormat()
        self.dumpSpreadsheet = self.fileFormat == b'BTBF' or '.fscache' in self.fileName
        if not self.dumpSpreadsheet: return
        if '.fscache' in self.fileName: return
        assert self.fileSize == self.readInt32(), f'FILE SIZE DOES NOT MATCH THE DATA!\n{self.fileName}\n{self.fileFormat}'
        # Data
        self.base = self.readInt32()
        self.size = self.readInt32()
        # Command strings
        self.comBase = self.readInt32()
        self.comSize = self.readInt32()
        # Text
        self.textBase = self.readInt32()
        self.textSize = self.readInt32()
        # Entries
        self.stride = self.readInt32() # bytes / entry
        self.count = self.readInt32()  # number of entries

    def readFileFormat(self):
        string = self.data.read(4)
        if string.isalpha():
            return string
        return None

    def decompress(self, data):
        self.isComp = data[0] == 0x60
        if self.isComp:
            decompSize = int.from_bytes(data[1:4], byteorder='little', signed=True)
            try: # On the off chance a non-compressed file starts with 0x60!
                decompData = zlib.decompress(data[4:], -15)
                decompData = bytearray(decompData)
                assert len(decompData) == decompSize
            except:
                self.isComp = False
        if self.isComp:
            return decompData
        return data

    # Data to dump for packing
    def fileContents(self):
        return {
            self.fileName: {
                'format': self.fileFormat if '.fscache' not in self.fileName else None,
                'compressed': self.isComp, # Used to determine whether or not to compress data
                'sha': self.sha,           # Needed to check if file has been modified (NB: sha of inflated data)
                'spreadsheet': self.dumpSpreadsheet,
            }
        }

    # def getComData(self, offsets):
    #     if self.comSize == 0:
    #         return []
    #     strings = []
    #     for start, end in zip(offsets[:-1], offsets[1:]):
    #         self.data.seek(self.comBase + start)
    #         s = self.data.read(end - start)
    #         try:
    #             strings.append(s.decode('utf-8')[:-1])
    #         except:
    #             strings.append(list(map(chr, s)))
    #     return strings
        
    # def getTextData(self, offsets):
    #     if self.textSize == 0:
    #         return []
    #     strings = []
    #     for start, end in zip(offsets[:-1], offsets[1:]):
    #         self.data.seek(self.textBase + start)
    #         s = self.data.read(end - start)
    #         strings.append(s.decode('utf-16')[:-1])
    #     return strings

    def readAllComData(self):
        self.data.seek(self.comBase)
        strings = []; sizes = [0]
        while self.data.tell() < self.comBase + self.comSize:
            s = self.data.read(1)
            while s[-1] > 0:
                s += self.data.read(1)
            try:
                strings.append(s.decode('utf-8')[:-1])
            except:
                print('exception for ', s)
                strings.append('0x' + s.hex())
                # strings.append(s[:-1].decode('utf-16'))
            sizes.append(self.data.tell() - self.comBase)
        assert sizes.pop() == self.comSize
        return strings, sizes

    def readAllTextData(self):
        self.data.seek(self.textBase)
        strings = []; sizes = [0]
        while self.data.tell() < self.textBase + self.textSize:
            s = self.data.read(2)
            while s[-2:] != b'\x00\x00':
                s += self.data.read(2)
                assert self.data.tell() <= self.textBase + self.textSize
            strings.append(s.decode('utf-16')[:-1])
            sizes.append(self.data.tell() - self.textBase)
        assert sizes.pop() == self.textSize
        return strings, sizes
        
    # # Data tables can only be updated under certain circumstances.
    # # Assumes all columns have the same byte size (currently 4)
    # # Assumes no text.
    # # Now, only use for Shops and Ability tables
    # def updateData(self, *cols):
    #     # Ensure no text
    #     assert self.comSize == 0
    #     assert self.textSize == 0
    #     # Update data
    #     data = bytearray([])
    #     numEntries = 0
    #     for row in zip(*cols):
    #         for ri in row:
    #             data += ri.to_bytes(4, byteorder='little', signed=True)
    #         numEntries += 1
    #     lenData = len(data).to_bytes(4, byteorder='little', signed=True)
    #     fileSize = int(len(data)+0x30).to_bytes(4, byteorder='little', signed=True)
    #     header = bytearray(b'BTBF')
    #     header += fileSize
    #     header += int(0x30).to_bytes(4, byteorder='little', signed=True)
    #     header += lenData
    #     header += fileSize + bytearray([0]*4)
    #     header += fileSize + bytearray([0]*4)
    #     header += int(8).to_bytes(4, byteorder='little', signed=True)
    #     header += numEntries.to_bytes(4, byteorder='little', signed=True)
    #     header += bytearray([0]*8)
    #     self.data = header + data

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
        assert size == 4, "SIZES AREN'T ALWAYS 4!"
        address = self.base + row*self.stride + col*size
        self.data.seek(address)
        return self.readInt32()

    def readComString(self, row, col):
        offset = self.readValue(row, col)
        self.data.seek(self.comBase + offset)
        return self.readStringUTF8()

    def readTextString(self, row, col):
        offset = self.readValue(row, col)
        self.data.seek(self.textBase + offset)
        return self.readStringUTF16()

    def readTextStringAll(self, col):
        strings = []
        for row in range(self.count):
            string = self.readTextString(row, col)
            strings.append(string)
        return strings

class CROWDFILES:
    def __init__(self, root, crowds, specs):
        self.root = root
        self.specs = specs
        self.fileList = crowds[root]
        self.data = {}

    # Checks if any file in the crowd is modified
    def isModified(self):
        for name, data in self.data.items():
            sha = hashlib.sha1(data).hexdigest()
            if sha != self.specs[name]['sha']:
                return True
        return False

    def allFilesExist(self):
        for fileName in self.fileList:
            fileName = os.path.join(self.root, fileName)
            if not os.path.isfile(fileName):
                print(f'Missing {fileName}')
                return False
        return True

    def loadData(self):
        for fileName in self.fileList:
            fileName = os.path.join(self.root, fileName)
            with open(fileName, 'rb') as file:
                self.data[fileName] = file.read()

    def dumpCrowd(self, pathOut):
        index, crowd = self._joinCrowd()
        path = os.path.join(pathOut, self.root)
        if not os.path.isdir(path):
            os.makedirs(path)
        fileIndex = os.path.join(path, 'index.fs')
        with open(fileIndex, 'wb') as file:
            file.write(index)
        fileCrowd = os.path.join(path, 'crowd.fs')
        with open(fileCrowd, 'wb') as file:
            file.write(crowd)

    def _getData(self, fileName):
        data = self.data[fileName]
        if self.specs[fileName]['compressed']:
            size = len(data)
            data = zlib.compress(data)[2:-4]
            header = int((size << 8) + 0x60).to_bytes(4, byteorder='little')
            data = header + data
        return data

    def _adjustSize(self, data):
        if len(data) % 4:
            x = 4 - (len(data) % 4)
            data += bytearray([0]*x)
        return data

    def _joinCrowd(self):
        # indexFile = os.path.join(self.root, 'index.fs')
        # crowdFile = os.path.join(self.root, 'crowd.fs')
        # with open(os.path.join(self.root, 'index.fs'), 'rb') as file:
        #     indexOrig = file.read()
        #     indexOrigSHA = hashlib.sha1(indexOrig).hexdigest()
        # with open(os.path.join(self.root, 'crowd.fs'), 'rb') as file:
        #     crowdOrig = file.read()
        #     crowdOrigSHA = hashlib.sha1(crowdOrig).hexdigest()

        index = bytearray([])
        crowd = bytearray([])
        for i, fileName in enumerate(self.data):
            # File for the crowd (compressed if necessary)
            data = self._getData(fileName)
            # Entry in the index file
            crowdStart = len(crowd).to_bytes(4, byteorder='little')
            crowdSize = len(data).to_bytes(4, byteorder='little')
            byteFileName = bytearray(map(ord, os.path.basename(fileName)))
            crc32 = zlib.crc32(byteFileName).to_bytes(4, byteorder='little')
            entry = crowdStart + crowdSize + crc32 + byteFileName + bytearray([0])
            entry = self._adjustSize(entry)
            if i < len(self.data)-1:
                size = len(index) + 4 + len(entry)
                pointer = size.to_bytes(4, byteorder='little')
            else:
                pointer = bytearray([0]*4)
            index +=  pointer + entry
            # Append crowd file
            crowd += data
            crowd = self._adjustSize(crowd)

            # assert index == indexOrig[:len(index)]
            # assert crowd == crowdOrig[:len(crowd)]
        # Finalize crowdData (actually necessary sometimes!)
        crowd = self._adjustSize(crowd)

        # indexSHA = hashlib.sha1(index).hexdigest()
        # crowdSHA = hashlib.sha1(crowd).hexdigest()
        
        # assert indexSHA == indexOrigSHA
        # assert crowdSHA == crowdOrigSHA
        return index, crowd


class CROWDSHEET(CROWDFILES):
    def __init__(self, root, specs, sheetToFile):
        self.root = root
        self.specs = specs
        self.sheetToFile = sheetToFile
        fileName = os.path.join(root, 'crowd.xls')
        # assert self.specs[fileName]['spreadsheet']
        self.spreadsheet = xlrd.open_workbook(fileName)
        self.data = {}
        for sheet in self.spreadsheet.sheets():
            with open(os.path.join(root, self.sheetToFile[sheet.name]), 'rb') as file:
                origData = file.read()
            sheetName = os.path.join(root, self.sheetToFile[sheet.name])
            self.data[sheetName] = self.getDataFromSheet(sheet, origData, sheetName)
            # sha = hashlib.sha1(self.data[sheetName]).hexdigest()
            # assert sha == self.specs[sheetName]['sha'], f"{root}/{sheet.name}"

    def toBytes(self, i):
        return i.to_bytes(4, byteorder='little', signed=True)
        
    def getDataFromSheet(self, sheet, origData, name):
        if '.fscache' in name:
            return b''
        nrows = sheet.nrows - 1
        ncols = sheet.ncols
        # name = os.path.join(self.root, sheet.name)
        assert self.specs[name]['spreadsheet']
        textCols = self.specs[name]['textColumns']
        nTextCols = len(textCols)
        comCols = self.specs[name]['commandColumns']
        nComCols = len(comCols)
        # Sort columns by commands, text, and data
        columns = []
        for i in range(ncols):
            columns.append(sheet.col_values(i)[1:])
        commands = []
        for i in range(nComCols):
            commands.append(columns.pop(0))
        text = []
        for i in range(nTextCols):
            text.append(columns.pop(0))
        data = []
        while columns:
            data.append(list(map(int, columns.pop(0))))
        # Encode commands and text accordingly
        for i in range(nTextCols):
            for j in range(nrows):
                text[i][j] = text[i][j].encode('utf-16')[2:] + b'\x00\x00'
        for i in range(nComCols):
            for j in range(nrows):
                if commands[i][j][:2] == '0x':
                    commands[i][j] = bytes.fromhex(commands[i][j][2:])
                else:
                    s = commands[i][j].encode('utf-8')
                    assert not any([si & 0x80 for si in s])
                    commands[i][j] = s + b'\x00'

        # Get size lists
        def getSizeList(lst):
            a = [] # a11 a12 ... a1n a21 a22 ...
            for j in range(nrows):
                for li in lst:
                    a.append(li[j])
            sizes = []; j = 0
            for ai in a:
                sizes.append(j)
                j += len(ai)
            n = len(lst)
            return [sizes[i::n] for i in range(n)]
        textSizes = getSizeList(text)
        commandSizes = getSizeList(commands)
        # Update appropriate data columns for any modifications to text and commands
        for sizes, colIndex in zip(textSizes, textCols):
            assert sizes == data[colIndex] # TEMPORARY
            # data[colIndex] = sizes # KEEP
        for sizes, colIndex in zip(commandSizes, comCols):
            assert sizes == data[colIndex] # TEMPORARY
            # data[colIndex] = sizes # KEEP
        # Join commands, text, and data into bytearrays
        def getByteArray(lst):
            x = bytearray()
            for i in range(nrows):
                for lj in lst:
                    x += lj[i]
            # for li in lst:
            #     for lj in li:
            #         x += lj
            return x
        def getByteArrayInt(lst):
            x = bytearray()
            for i in range(nrows):
                for lj in lst:
                    x += self.toBytes(lj[i])
            return x
        commandBytes = getByteArray(commands)
        textBytes = getByteArray(text)
        dataBytes = getByteArrayInt(data)
        # Merge into byte array
        fileFormat = b'BTBF'
        stride = len(data) * 4
        count = nrows
        base = 0x30
        size = len(dataBytes)
        comBase = base + size
        if comBase % 4 > 0:
            x = 4 - comBase % 4
            comBase += x
            dataBytes += b'\x00'*x
        comSize = len(commandBytes)
        textBase = comBase + comSize
        if textBase % 2 > 0:
            textBase += 1
            commandBytes += b'\x00'
        textSize = len(textBytes)
        fileSize = textBase + textSize

        fileData = bytearray()
        fileData += fileFormat
        fileData += self.toBytes(fileSize)
        fileData += self.toBytes(base)
        fileData += self.toBytes(size)
        fileData += self.toBytes(comBase)
        fileData += self.toBytes(comSize)
        fileData += self.toBytes(textBase)
        fileData += self.toBytes(textSize)
        fileData += self.toBytes(stride)
        fileData += self.toBytes(count)
        fileData += bytearray([0]*8)
        assert len(fileData) == base
        # for i, d in enumerate(dataBytes):
        #     fileData.append(d)
        #     assert fileData == origData[:len(fileData)], i
        fileData += dataBytes
        assert len(fileData) == comBase
        fileData += commandBytes
        assert len(fileData) == textBase
        fileData += textBytes
        assert len(fileData) == fileSize
        return fileData

class TABLESHEET(CROWDSHEET):
    def __init__(self, root, fileName, specs, sheetToFile):
        self.root = root
        self.fileName = os.path.join(root, fileName)
        self.specs = specs
        self.sheetToFile = sheetToFile
        self.spreadsheet = xlrd.open_workbook(self.fileName)
        self.data = {}
        for sheet in self.spreadsheet.sheets():
            with open(os.path.join(root, self.sheetToFile[sheet.name]), 'rb') as file:
                origData = file.read()
            sheetName = os.path.join(root, self.sheetToFile[sheet.name])
            self.data[sheetName] = self.getDataFromSheet(sheet, origData, sheetName)
            sha = hashlib.sha1(self.data[sheetName]).hexdigest()
            assert sha == self.specs[sheetName]['sha'], f"{root}/{sheet.name}"

    def dumpTable(self, path):
        directory = os.path.join(path, self.root)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        for name, data in self.data.items(): # name = root + file
            fileName = os.path.join(path, name)
            with open(fileName, 'wb') as file:
                file.write(data)

    def getFileName(self):
        sheetName = list(self.data.keys())[0]
        fileName = os.path.relpath(sheetName, self.root)
        return fileName


class CROWD:
    def __init__(self, path, pathOut):
        self.path = path
        self.pathOut = pathOut
        
        fileName = os.path.join(path, 'index.fs')
        with open(fileName, 'rb') as file:
            self.indexData = bytearray(file.read())
            self.indexFile = FILE(self.indexData)

        fileNameCrowd = os.path.join(path, 'crowd.fs')
        with open(fileNameCrowd, 'rb') as file:
            self.crowdData = bytearray(file.read())

        # Split crowd files
        self.crowdFiles = {}
        self.separateCrowd()
        self.dumpSpreadsheet = all([f.dumpSpreadsheet for f in self.crowdFiles.values()])
        self.crowdSpecs = {}
        for key, value in self.crowdFiles.items():
            self.crowdSpecs.update(value.fileContents())
        self.sheetName = os.path.join(path, 'crowd.xls')

    def dumpCrowd(self):
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
            fileOut = os.path.join(self.pathOut, fileName)
            with open(fileOut, 'wb') as file:
                file.write(data.getData())

    def separateCrowd(self):
        nextAddr = self.indexFile.readInt32()
        while True:
            # Extract file from crowd.fs
            base = self.indexFile.readInt32()
            size = self.indexFile.readInt32()
            self.indexFile.data.seek(4, 1)
            fileName = os.path.join(self.path, self.indexFile.readStringUTF8())
            fileName = os.path.relpath(fileName, self.pathOut)
            data = self.crowdData[base:base+size]
            self.crowdFiles[fileName] = DATAFILE(fileName, data)
            # Done with file?
            if nextAddr == 0:
                break
            # Setup for next file
            self.indexFile.data.seek(nextAddr)
            nextAddr = self.indexFile.readInt32()

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

    # def getData(self, fileName):
    #     data = self.crowdFiles[fileName].data
    #     if self.isCompressed[fileName]:
    #         size = len(data)
    #         data = zlib.compress(data)[2:-4]
    #         header = int((size << 8) + 0x60).to_bytes(4, byteorder='little')
    #         data = header + data
    #     return data

    def dumpSheet(self):
        for filename, data in self.crowdFiles.items():
            if '.fscache' in filename:
                continue
            assert data.dumpSpreadsheet, f'DUMPSPREADSHEET IS FALSE! {filename}'

        # Do this here to include 'fscache'
        columnIDs = {file:{'commands':[], 'text':[]} for file in self.crowdFiles}
        wb = xlwt.Workbook()
        sheetNames = {}
        for file in self.crowdFiles:
            basename = os.path.basename(file)
            print(f'   building {file}')

            x = basename.replace('_', ' ')
            if len(x) > 31:
                x = x[:31]
            # self.crowdSpecs[file]['sheetname'] = x
            sheetNames[x] = os.path.basename(file)
            
            wb.add_sheet(x)
            sheet = wb.get_sheet(x)
            if x == '.fscache': # EMPTY FILES
                assert self.crowdFiles[file].data.getbuffer().tobytes() == b''
                continue

            data = self.crowdFiles[file]
            numCols = int(data.stride / 4)
            numRows = data.count

            def mono_increase(col):
                return all(map(lambda x, y: x < y, col[:-1], col[1:]))

            # READ ALL COLUMNS
            columns = []
            for i in range(numCols):
                column = data.readCol(i)
                columns.append(data.readCol(i))

            # Read all commands
            allCommandData, allCommandSizes = data.readAllComData()
            assert len(allCommandData) % numRows == 0
            comCols = len(allCommandData) // numRows
            commandData = []; commandSizes = []
            for i in range(comCols):
                commandData.append(allCommandData[i::comCols])
                commandSizes.append(allCommandSizes[i::comCols])

            # Read all text
            allTextData, allTextSizes = data.readAllTextData()
            assert len(allTextData) % numRows == 0
            textCols = len(allTextData) // numRows
            textData = []; textSizes = []
            for i in range(textCols):
                textData.append(allTextData[i::textCols])
                textSizes.append(allTextSizes[i::textCols])

            # Dump data to spreadsheets
            col = 0
            for column in commandData:
                for row, value in enumerate(column):
                    sheet.write(row+1, col, value)
                col += 1

            for column in textData:
                for row, value in enumerate(column):
                    sheet.write(row+1, col, value)
                col += 1

            for column in columns:
                for row, value in enumerate(column):
                    sheet.write(row+1, col, value)
                col += 1

            # Store text and command column numbers
            self.crowdSpecs[file]['commandColumns'] = []
            self.crowdSpecs[file]['textColumns'] = []
            while commandSizes:
                lst = commandSizes.pop(0)
                index = columns.index(lst)
                assert index >= 0
                self.crowdSpecs[file]['commandColumns'].append(index)
            while textSizes:
                lst = textSizes.pop(0)
                index = columns.index(lst)
                assert index >= 0
                self.crowdSpecs[file]['textColumns'].append(index)
            assert set(self.crowdSpecs[file]['textColumns']).isdisjoint(self.crowdSpecs[file]['commandColumns'])

        wb.save(self.sheetName)
        print('   Done!')
        return sheetNames


class TABLE(CROWD):
    def __init__(self, fileName, pathOut):
        self.path = os.path.dirname(fileName)
        self.fileName = fileName
        self.baseName = os.path.basename(fileName)
        with open(self.fileName, 'rb') as file:
            self.tableData = bytearray(file.read())
        fileName = os.path.relpath(self.fileName, pathOut)
        self.crowdFiles = {fileName: DATAFILE(fileName, self.tableData)}
        self.dumpSpreadsheet = all([f.dumpSpreadsheet for f in self.crowdFiles.values()])
        self.crowdSpecs = {}
        for key, value in self.crowdFiles.items():
            self.crowdSpecs.update(value.fileContents())
        pre, _ = os.path.splitext(self.fileName)
        self.sheetName = f"{pre}.xls"

    def dump(self):
        with open(self.fileName, 'wb') as file:
            file.write(self.tableData)
