import os
import zlib
import sys
# import pudb; pu.db
import struct

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


class CROWD:
    def __init__(self, path):
        if path is None:
            return

        self.path = path
        
        fileName = os.path.join(path, 'index.fs')
        with open(fileName, 'rb') as file:
            self.indexData = bytearray(file.read())
            self.indexFile = FILE(self.indexData)

        fileName = os.path.join(path, 'crowd.fs')
        if os.path.exists(fileName):
            with open(fileName, 'rb') as file:
                self.crowdData = bytearray(file.read())
            # Split crowd files
            self.crowdFiles = {}
            self.separateCrowd()
        else:
            # Load files
            self.crowdFiles = {}
            self.loadFiles()

    def dumpCrowd(self, outpath):
        # Rebuild index and crowd data
        self.joinCrowd()
        # Make directory
        if not os.path.isdir(outpath):
            os.makedirs(outpath)
        # Dump index
        fileOut = os.path.join(outpath, 'index.fs')
        with open(fileOut, 'wb') as file:
            file.write(self.indexData)
        # Dump crowd
        fileOut = os.path.join(outpath, 'crowd.fs')
        with open(fileOut, 'wb') as file:
            file.write(self.crowdData)

    def dumpFiles(self, outpath):
        if 'romfs' in self.path:
            base = self.path.split('romfs')[-1]
        elif 'RomFS' in self.path:
            base = self.path.split('RomFS')[-1]
        else:
            sys.exit("Folder must be romfs or RomFS")

        # remove "." and "/"
        while base and not (base[0].isdigit() or base[0].isalpha()):
            base = base[1:]
            
        path = os.path.join(outpath, base)
        if not os.path.isdir(path):
            os.makedirs(path)
        for fileName, data in self.crowdFiles.items():
            fileOut = os.path.join(path, fileName)
            with open(fileOut, 'wb') as file:
                file.write(data.data)

    def loadFiles(self):
        self.indexFile.address = 0
        nextAddr = self.indexFile.read()
        while True:
            self.indexFile.address += 0xc
            fileName = self.indexFile.readString()
            fullName = os.path.join(self.path, fileName)
            if os.path.exists(fullName):
                with open(fullName, 'rb') as file:
                    self.crowdFiles[fileName] = FILE(bytearray(file.read()))
            else:
                sys.exit(f"{fileName} does not exist in {self.path}")
            if nextAddr == 0:
                break
            self.indexFile.address = nextAddr
            nextAddr = self.indexFile.read()

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
        data = zlib.decompress(self.crowdData[base+4:base+size], -15)
        data = bytearray(data)
        return FILE(data)

    def getData(self, fileName):
        size = len(data)
        data = zlib.compress(data)[2:-4]
        header = int((size << 8) + 0x60).to_bytes(4, byteorder='little')
        return header + data

class CROWD_BD(CROWD):
    def __init__(self, path):
        super().__init__(path)

    def extractFile(self, fileName, base, size):
        data = self.crowdData[base:base+size]
        return FILE(data)

    def getData(self, fileName):
        return self.crowdFiles[fileName].data
