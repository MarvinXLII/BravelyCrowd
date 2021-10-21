# from Classes import CROWD, CROWD_BD
from Classes import CROWD, TABLE, CROWDFILES, TABLEFILE
import os
import shutil
import sys
import pickle
import hashlib

class ROM:
    def __init__(self, settings):
        self.settings = settings
        self.game = settings['game']
        self.pathIn = self.settings['rom']
        if os.path.isdir(self.pathOut):
            shutil.rmtree(self.pathOut)
        os.makedirs(self.pathOut)

    def fail(self):
        shutil.rmtree(self.pathOut)

    # Not sure why I did all these copies?
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

    def copyFile(self, fileName):
        src = os.path.join(self.pathIn, fileName)
        dest = os.path.join(self.pathOut, fileName)
        base = os.path.dirname(dest)
        if not os.path.isdir(base):
            os.makedirs(base)
        shutil.copy(src, dest)


class PACK(ROM):
    def __init__(self, settings):
        dir = os.getcwd()

        # Setup output paths and files
        dirOut = os.path.join(dir, 'romfs_packed')
        if os.path.isdir(dirOut):
            shutil.rmtree(dirOut)
        if settings['game'] == 'BD':
            self.pathOut = os.path.join(dirOut, '00040000000FC500', 'romfs')
            logFileName = os.path.join(dirOut, 'BD_mod.log')
        elif settings['game'] == 'BS':
            self.pathOut = os.path.join(dirOut, '000400000017BA00', 'romfs')
            logFileName = os.path.join(dirOut, 'BS_mod.log')
        else:
            sys.exit(f"{settings['game']} is not allowed as the game setting!")

        super().__init__(settings)

        os.chdir(self.pathIn)
        with open('data.pickle','rb') as file:
            crowdSpecs = pickle.load(file)
            crowdFiles = pickle.load(file)
            sheetNames = pickle.load(file)

        moddedFiles = []
        for root, dirs, files in os.walk('.'):
            root = root[2:]
            spreadsheets = list(filter(lambda f: '.xls' in f, files))
            bytefiles = list(filter(lambda f: '.xls' not in f, files))
            if 'data.pickle' in bytefiles:
                bytefiles.remove('data.pickle')

            if root in crowdFiles:
                crowd = CROWDFILES(root, crowdFiles, crowdSpecs, sheetNames)
                crowd.loadData()
                crowd.dump(self.pathOut)
                moddedFiles += crowd.moddedFiles
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
                    moddedFiles += table.moddedFiles
                    name = table.getFileName()
                    if name in bytefiles:
                        bytefiles.remove(name)

            for fileName in bytefiles:
                table = TABLEFILE(root, fileName, crowdSpecs, sheetNames)
                table.loadData()
                table.dump(self.pathOut)

        os.chdir(dir)

        moddedFiles.sort()
        with open(logFileName, 'w') as file:
            if moddedFiles:
                for m in moddedFiles:
                    file.write(m)
            else:
                file.write('No modified files!')
                shutil.rmtree(self.pathOut)
                shutil.rmtree(self.pathOut[:-6])


class UNPACK(ROM):
    def __init__(self, settings):
        dir = os.getcwd()
        self.pathOut = os.path.join(dir, f"romfs_unpacked")
        super().__init__(settings)
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
                checkName = os.path.join(self.pathOut, fileName)
                if os.path.isfile(checkName):
                    continue
                if file == 'crowd.fs':
                    table = self.loadCrowd(root)
                    table.dumpFiles(self.pathOut)
                else:
                    table = self.loadTable(fileName)

                print(fileName)
                if table.dumpSpreadsheet:
                    print(f'Dumping spreadsheet {fileName}')
                    try:
                        sheetNames.update(table.dumpSheet())
                    except:
                        print(f'removing {checkName}')
                        os.remove(checkName)
                        sys.exit(f"Error dumping spreadsheet {fileName}")

                crowdSpecs.update(table.crowdSpecs)
                if file == 'crowd.fs':
                    baseNames = []
                    for key in table.crowdSpecs:
                        name = os.path.basename(key)
                        baseNames.append(name)
                    crowdFiles.update({root: baseNames})

        # Dump data needed for packing
        os.chdir(self.pathOut)
        with open('data.pickle','wb') as file:
            pickle.dump(crowdSpecs, file)
            pickle.dump(crowdFiles, file)
            pickle.dump(sheetNames, file)
            
        os.chdir(dir)
