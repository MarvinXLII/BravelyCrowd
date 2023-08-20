import os
import sys
import zlib
import xlrd
import xlwt
import math
import struct
import hashlib
import logging
import hjson
from io import BytesIO
# import pudb; pu.db

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


class CROWDFILES:
    def __init__(self, root, crowds, specs, sheetToFile):
        self.root = root
        self.specs = specs
        self.fileList = crowds[root]
        self.sheetToFile = sheetToFile
        self.data = {}
        self._isModified = False
        self._moddedFiles = []
        self.allHeaders = {}

    # Checks if any file in the crowd is modified
    @property
    def isModified(self):
        if self._isModified:
            return True
        self._moddedFiles = []
        for name, data in self.data.items():
            sha = hashlib.sha1(data).hexdigest()
            # if name in self.specs and sha != self.specs[name]['sha']:
            if sha != self.specs[name]['sha']:
                self._isModified = True
                self._moddedFiles.append(os.path.basename(name))
        return self._isModified

    @property
    def moddedFiles(self):
        if not self.isModified:
            self._moddedFiles = []
        return self._moddedFiles

    def loadData(self):
        # Try spreadsheet first
        sheetName = os.path.join(self.root, 'crowd.xls')
        self._loadSheet('crowd.xls')
        if self.isModified:
            self._moddedFiles.insert(0, sheetName)
            return

        # Try tables if sheets are unedited/don't exist
        self._loadTables(self.fileList)
        if self.isModified:
            fileName = os.path.join(self.root, 'crowd.fs')
            self._moddedFiles.insert(0, fileName)
            return

    def allFilesExist(self, fileList=None):
        if fileList is None:
            fileList = self.fileList
        logger = logging.getLogger()
        for fileName in fileList:
            fileName = os.path.join(self.root, fileName)
            if not os.path.isfile(fileName):
                logger.info(f'Missing {fileName}!')
                return False
        return True

    def _loadSheet(self, fileName):
        self.data = {}
        fileName = os.path.join(self.root, fileName)
        if os.path.isfile(fileName):
            self.spreadsheet = xlrd.open_workbook(fileName)
            for sheet in self.spreadsheet.sheets():
                sheetName = os.path.join(self.root, self.sheetToFile[sheet.name])
                if '.fscache' in sheetName:
                    self.data[sheetName] = b''
                else:
                    self.data[sheetName] = self.getDataFromSheet(sheet, sheetName)
                    self.getHeadersFromSheet(sheet, sheetName)
                # sha = hashlib.sha1(self.data[sheetName]).hexdigest()
                # assert sha == self.specs[sheetName]['sha'], f"{self.root}/{sheet.name}"

    def _loadTables(self, fileList):
        self.data = {}
        if self.allFilesExist(fileList):
            for fileName in fileList:
                fileName = os.path.join(self.root, fileName)
                with open(fileName, 'rb') as file:
                    self.data[fileName] = file.read()

    def dump(self, pathOut):
        if not self.isModified:
            print(f'{self.root}: No modified crowd data to dump!')
            return

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

    def dumpHeaders(self, pathOut):
        for f, h in self.allHeaders.items():
            filename = os.path.join(pathOut, f)
            dirname = os.path.dirname(filename)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            with open(filename, 'w') as file:
                hjson.dump(h, file)

    def _getData(self, fileName):
        assert self.isModified
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
        # Finalize crowdData (actually necessary sometimes!)
        crowd = self._adjustSize(crowd)
        return index, crowd

    def toBytes(self, i):
        return i.to_bytes(4, byteorder='little', signed=True)

    def getHeadersFromSheet(self, sheet, name):
        headers = sheet.row_values(0)
        headersData = {}
        v = [ord('A')-1] * 3
        for h in headers:
            v[-1] += 1
            i = len(v) - 1
            while i:
                if v[i] == ord('Z') + 1:
                    v[i-1] += 1
                    v[i] = ord('A')
                i -= 1
            vh = ''.join(map(chr, v)).replace(chr(ord('A')-1), '')
            headersData[vh] = h
        name_json = os.path.splitext(name)[0] + '.hjson'
        self.allHeaders[name_json] = headersData
        
    def getDataFromSheet(self, sheet, name):
        if '.fscache' in name:
            return b''
        # assert self.specs[name]['nrows'] == sheet.nrows, "Missing or added row(s)!"
        assert self.specs[name]['ncols'] >= sheet.ncols, "Missing column(s)!"
        nrows = sheet.nrows - 1
        ncols = self.specs[name]['ncols']
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
            data[colIndex] = sizes
        for sizes, colIndex in zip(commandSizes, comCols):
            data[colIndex] = sizes
        # Join commands, text, and data into bytearrays
        def getByteArray(lst):
            x = bytearray()
            for i in range(nrows):
                for lj in lst:
                    x += lj[i]
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
        fileData += dataBytes
        fileData += commandBytes
        fileData += textBytes
        return fileData


class TABLEFILE(CROWDFILES):
    def __init__(self, root, fileName, specs, sheetToFile):
        self.root = root
        self.fileName = fileName
        self.specs = specs
        self.sheetToFile = sheetToFile
        self.data = {}
        self._isModified = False
        self._moddedFiles = []
        self.allHeaders = {}
 
    def loadData(self):
        assert not self.data, "DATA ALREADY LOADED!"
        _, ext = os.path.splitext(self.fileName)
        if ext == '.xls':
            self._loadSheet(self.fileName)
        else:
            self._loadTables([self.fileName])
        assert len(self.data) <= 1, "ONLY ONE ENTRY OF DATA ALLOWED!"

    def dump(self, pathOut):
        if not self.isModified:
            print(f"{self.root}/{self.fileName}: No modified table data to dump!")
            return

        directory = os.path.join(pathOut, self.root)
        if not os.path.isdir(directory):
            os.makedirs(directory)

        assert len(self.data) == 1, "ONLY ONE TABLE ENTRY IS ALLOWED!"
        for fileName, data in self.data.items(): # fileName = root + file
            assert not self.specs[fileName]['compressed'], "NEED TO CALL _getData WHEN DUMPING INDIVIDUAL TABLES"
            fileName = os.path.join(pathOut, fileName)
            with open(fileName, 'wb') as file:
                file.write(data)

    def getFileName(self):
        sheetName = list(self.data.keys())[0]
        fileName = os.path.relpath(sheetName, self.root)
        return fileName


class CROWD:
    def __init__(self, path, pathOut, headersPath):
        self.path = path
        self.pathOut = pathOut
        self.headersPath = headersPath
        
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
            sheetNames[x] = os.path.basename(file)
            
            wb.add_sheet(x, cell_overwrite_ok=True)
            sheet = wb.get_sheet(x)
            if x == '.fscache': # EMPTY FILES
                assert self.crowdFiles[file].data.getbuffer().tobytes() == b''
                continue

            data = self.crowdFiles[file]
            numCols = int(data.stride / 4)
            numRows = data.count

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
                sheet.write(0, col, "Label")
                for row, value in enumerate(column):
                    sheet.write(row+1, col, value)
                col += 1

            for column in textData:
                sheet.write(0, col, "Text")
                for row, value in enumerate(column):
                    sheet.write(row+1, col, value)
                col += 1

            for column in columns:
                for row, value in enumerate(column):
                    sheet.write(row+1, col, value)
                col += 1

            # Store number of rows and columns
            self.crowdSpecs[file]['nrows'] = numRows + 1
            self.crowdSpecs[file]['ncols'] = col

            # Store text and command column numbers
            self.crowdSpecs[file]['commandColumns'] = []
            self.crowdSpecs[file]['textColumns'] = []
            colOffset = len(commandData) + len(textData)
            while commandSizes:
                lst = commandSizes.pop(0)
                index = columns.index(lst)
                sheet.write(0, colOffset + index, "Label Pntr")
                assert index >= 0
                self.crowdSpecs[file]['commandColumns'].append(index)
            while textSizes:
                lst = textSizes.pop(0)
                index = columns.index(lst)
                sheet.write(0, colOffset + index, "Text Pntr")
                assert index >= 0
                self.crowdSpecs[file]['textColumns'].append(index)
            assert set(self.crowdSpecs[file]['textColumns']).isdisjoint(self.crowdSpecs[file]['commandColumns'])

            # Load default column headers
            # TODO

            # Load user column headers
            headerName = os.path.splitext(os.path.join(self.headersPath, file))[0] + '.hjson'
            if os.path.isfile(headerName):
                with open(headerName, 'r') as file:
                    headers = hjson.load(file)
                for col, v in enumerate(headers.values()):
                    sheet.write(0, col, v)

        wb.save(self.sheetName)
        print('   Done!')
        return sheetNames


class TABLE(CROWD):
    def __init__(self, fileName, pathOut, headersPath):
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
        self.headersPath = headersPath

    def dump(self):
        with open(self.fileName, 'wb') as file:
            file.write(self.tableData)
