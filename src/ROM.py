from Classes import CROWD, TABLE, CROWDFILES, TABLEFILE
import os
import shutil
import sys
import lzma
import pickle
import hashlib
sys.path.append('src')
from Utilities import get_filename

class PACK:
    def __init__(self, settings):
        dir = os.getcwd()

        # Setup output paths and files
        dirOut = os.path.join(dir, 'romfs_packed')
        if settings['game'] == 'BD':
            self.pathOut = os.path.join(dirOut, '00040000000FC500', 'romfs')
            logFileName = os.path.join(dirOut, 'BD_mod.log')
            dataFile = get_filename(os.path.join(dir, 'data/bd.xz'))
        elif settings['game'] == 'BS':
            self.pathOut = os.path.join(dirOut, '000400000017BA00', 'romfs')
            logFileName = os.path.join(dirOut, 'BS_mod.log')
            dataFile = get_filename(os.path.join(dir, 'data/bs.xz'))
        else:
            sys.exit(f"{settings['game']} is not allowed as the game setting!")

        if os.path.isdir(dirOut):
            shutil.rmtree(dirOut)
        os.makedirs(self.pathOut)

        self.pathIn = settings['rom']

        with lzma.open(dataFile,'rb') as file:
            crowdSpecs = pickle.load(file)
            crowdFiles = pickle.load(file)
            sheetNames = pickle.load(file)

        os.chdir(self.pathIn)
        moddedFiles = []
        for root, dirs, files in os.walk('.'):
            root = root[2:]
            spreadsheets = list(filter(lambda f: '.xls' in f, files))
            bytefiles = list(filter(lambda f: '.xls' not in f, files))
            bytefiles = list(filter(lambda f: '.xz' not in f, bytefiles))

            if root in crowdFiles:
                crowd = CROWDFILES(root, crowdFiles, crowdSpecs, sheetNames)
                crowd.loadData()
                if crowd.isModified:
                    crowd.dump(self.pathOut)
                    moddedFiles.append(crowd.moddedFiles)
                if 'crowd.xls' in spreadsheets:
                    spreadsheets.remove('crowd.xls')
                if 'crowd.fs' in bytefiles:
                    bytefiles.remove('crowd.fs')
                if 'index.fs' in bytefiles:
                    bytefiles.remove('index.fs')
                bytefiles = list(filter(lambda x: x not in crowdFiles[root], bytefiles))

            for sheet in spreadsheets:
                table = TABLEFILE(root, sheet, crowdSpecs, sheetNames)
                table.loadData()
                if table.isModified:
                    table.dump(self.pathOut)
                    moddedFiles.append([os.path.join(root, sheet)])
                    name = table.getFileName()
                    if name in bytefiles:
                        bytefiles.remove(name)

            for fileName in bytefiles:
                table = TABLEFILE(root, fileName, crowdSpecs, sheetNames)
                table.loadData()
                if table.isModified:
                    table.dump(self.pathOut)
                    moddedFiles.append([os.path.join(root, fileName)])

        moddedFiles.sort(key=lambda x: x[0])
        with open(logFileName, 'w') as file:
            if moddedFiles:
                for m in moddedFiles:
                    file.write(m.pop(0) + '\n')
                    for mi in m:
                        file.write('    - ' + mi + '\n')
            else:
                file.write('No modified files!')
                shutil.rmtree(self.pathOut[:-6]) # titleID directory

        os.chdir(dir)


class UNPACK:
    def __init__(self, settings):
        dir = os.getcwd()

        self.pathIn = settings['rom']
        self.pathOut = os.path.join(dir, f"romfs_unpacked")
        if os.path.isdir(self.pathOut):
            shutil.rmtree(self.pathOut)
        os.makedirs(self.pathOut)

        os.chdir(self.pathIn)
        crowdSpecs = {}
        crowdFiles = {}
        sheetNames = {}
        for root, dirs, files in os.walk('.'):
            root = root[2:]
            for file in files:
                if file == 'index.fs':
                    continue
                fileName = os.path.join(root, file)
                if file == 'crowd.fs':
                    table = self.loadCrowd(root)
                    table.dumpFiles(self.pathOut)
                else:
                    table = self.loadTable(fileName)
                print(f'Loaded {fileName}')

                if table.dumpSpreadsheet:
                    print(f'Dumping spreadsheet {fileName}')
                    try:
                        sheetNames.update(table.dumpSheet())
                    except:
                        sys.exit(f"Error dumping spreadsheet {fileName}")

                crowdSpecs.update(table.crowdSpecs)
                if file == 'crowd.fs':
                    baseNames = []
                    for key in table.crowdSpecs:
                        name = os.path.basename(key)
                        baseNames.append(name)
                    crowdFiles.update({root: baseNames})

        # Dump data needed for packing
        if 'dumpData' in settings:
            if settings['dumpData']:
                os.chdir(self.pathOut)
                with lzma.open('data.xz', 'wb') as file:
                    pickle.dump(crowdSpecs, file)
                    pickle.dump(crowdFiles, file)
                    pickle.dump(sheetNames, file)
            
        os.chdir(dir)

    def loadCrowd(self, path):
        dest = os.path.join(self.pathOut, path)
        if not os.path.isdir(dest):
            os.makedirs(dest)
        src = os.path.join(self.pathIn, path, 'crowd.fs')
        shutil.copy(src, dest)
        src = os.path.join(self.pathIn, path, 'index.fs')
        shutil.copy(src, dest)
        return CROWD(dest, self.pathOut)

    def loadTable(self, fileName):
        src = os.path.join(self.pathIn, fileName)
        dest = os.path.join(self.pathOut, fileName)
        base = os.path.dirname(dest)
        if not os.path.isdir(base):
            os.makedirs(base)
        shutil.copy(src, dest)
        return TABLE(dest, self.pathOut)
