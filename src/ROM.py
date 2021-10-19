# from Classes import CROWD, CROWD_BD
from Classes import CROWD, TABLE, CROWDSHEET, CROWDFILES, TABLESHEET
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
            return #### MUST REMOVE TO ENSURE PICKLE GETS UPDATED WITH ALL THE FILES!
            shutil.rmtree(self.pathOut)
        os.mkdir(self.pathOut)

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
        self.pathOut = os.path.join(os.getcwd(), f"romfs_packed")
        super().__init__(settings)

        dir = os.getcwd()
        os.chdir(self.pathIn)
        with open('data.pickle','rb') as file:
            crowdSpecs = pickle.load(file)
            crowdFiles = pickle.load(file)
            sheetNames = pickle.load(file)

        for root, dirs, files in os.walk('.'):
            root = root[2:]
            spreadsheets = list(filter(lambda f: '.xlsx' in f, files))
            bytefiles = list(filter(lambda f: '.xlsx' not in f, files))
            if 'data.pickle' in bytefiles:
                bytefiles.remove('data.pickle')
            if root in crowdFiles:
                # Give priority to spreadsheets
                if 'crowd.xlsx' in spreadsheets:
                    print(os.path.join(root, 'crowd.xlsx'))
                    crowd = CROWDSHEET(root, crowdSpecs, sheetNames)
                    spreadsheets.remove('crowd.xlsx')
                    if crowd.isModified():
                        crowd.dumpCrowd(pathOut)
                        if 'crowd.fs' in bytefiles:
                            bytefiles.remove('crowd.fs')
                        if 'index.fs' in bytefiles:
                            bytefiles.remove('index.fs')

                # Consider crowd tables if spreadsheets are unmodified
                if 'crowd.fs' in bytefiles:
                    print(os.path.join(root, 'crowd.fs'))
                    crowd = CROWDFILES(root, crowdFiles, crowdSpecs)
                    if crowd.allFilesExist():
                        crowd.loadData()
                        if crowd.isModified():
                            crowd.dumpCrowd(pathOut)
                    bytefiles.remove('crowd.fs')
                    if 'index.fs' in bytefiles:
                        bytefiles.remove('index.fs')
                    bytefiles = list(filter(lambda x: x not in crowdFiles[root], bytefiles))

            # Check table spreadsheets
            for sheet in spreadsheets:
                fileName = os.path.join(root, sheet)
                print(fileName)
                table = TABLESHEET(root, sheet, crowdSpecs, sheetNames)
                if table.isModified():
                    table.dumpSheet(self.pathOut)
                    name = table.getFileName()
                    bytefiles.remove(name)

            # Copy over any remaining modified files
            for fileName in bytefiles:
                fileName = os.path.join(root, fileName)
                print(fileName)
                with open(fileName, 'rb') as file:
                    data = file.read()
                sha = hashlib.sha1(data).hexdigest()
                if sha != crowdSpecs[fileName]['sha']:
                    self.copyFile(fileName)

        os.chdir(dir)


class UNPACK(ROM):
    def __init__(self, settings):
        self.pathOut = os.path.join(os.getcwd(), f"romfs_unpacked")
        super().__init__(settings)
        dir = os.getcwd()
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
                self.copyFile(fileName) # COPY AFTER JUST IN CASE THERE IS AN ERROR!

                print(fileName)
                if table.dumpSpreadsheet:
                    print(f'Dumping spreadsheet {fileName}')
                    try:
                        sheetNames.update(table.dumpSheet())
                    except:
                        print(f'removing {checkName}')
                        os.remove(checkName)
                        table.dumpSheet()
                        sys.exit()

                crowdSpecs.update(table.crowdSpecs)
                if file == 'crowd.fs':
                    baseNames = []
                    for key in table.crowdSpecs:
                        name = os.path.basename(key)
                        baseNames.append(name)
                    crowdFiles.update({root: baseNames})

        os.chdir(self.pathOut)
        with open('data.pickle','wb') as file:
            pickle.dump(crowdSpecs, file)
            pickle.dump(crowdFiles, file)
            pickle.dump(sheetNames, file)
            
        os.chdir(dir)
