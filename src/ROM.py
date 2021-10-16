# from Classes import CROWD, CROWD_BD
from Classes import CROWD, TABLE, CROWDSHEET, CROWDFILES, TABLESHEET
import os
import shutil
import sys
# from Spreadsheets import XLSX
import pickle
import hashlib

class ROM:
    def __init__(self, settings):
        self.settings = settings
        self.game = settings['game']
        self.pathIn = self.settings['rom']
        if os.path.isdir(self.pathOut):
            return
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

    # Not sure why I did all these copies?
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

    # def dumpSpreadsheet(self, fileName):
    #     src = os.path.join(self.pathIn, fileName)
    #     dest = os.path.join(self.pathOut, fileName)
    #     base = os.path.dirname(dest)
    #     if not os.path.isdir(base):
    #         os.makedirs(base)
    #     sheet = XLSX(src)
    #     sheet.loadData()
    #     sheet.dumpSheet(dest)


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
            # NEVER CONSIDER THE PICKLE FILE!
            files = list(filter(lambda f: '.pickle' not in f, files))
            # # SKIP XLSX FOR NOW!
            # files = list(filter(lambda f: '.xlsx' not in f, files))
            # First load crowd using index
            root = root[2:]
            if root in crowdFiles:
                ## LOOP OVER FILES IN THE CROWD AND SEE IF ANY HAVE BEEN MODIFIED
                ## IF SO, BUILD AND DUMP CROWD AND INDEX FILES
                ## IF NOT, SKIP
                ## EITHER WAY, FILTER FILES LIST

                if root == 'Common_ko/Shop':
                    print('here')
                # IF SPREADHSEET EXISTS, CHECK SPREADSHEET FIRST
                # IF ANY SHEETS ARE MODIFIED, REBUILD AND DUMP INDEX AND CROWD FROM THE SHEETS
                if 'crowd.xlsx' in files:
                    fileName = os.path.join(root, 'crowd.xlsx')
                    print(fileName)
                    crowd = CROWDSHEET(root, crowdSpecs, sheetNames)
                else:
                    print(os.path.join(root, 'crowd.fs'))
                    crowd = CROWDFILES(root, crowdFiles[root], crowdSpecs)
                # if crowd.isModified():
                #     crowd.dumpCrowd(pathOut)
                crowd.dumpCrowd(self.pathOut)
                # Copy over remaining files
                files = list(filter(lambda x: x not in crowdFiles[root], files))
                if 'crowd.xlsx' in files:
                    files.remove('crowd.xlsx')
                if 'crowd.fs' in files:
                    files.remove('crowd.fs')
                if 'index.fs' in files:
                    files.remove('index.fs')

            # Check table spreadsheets
            sheets = list(filter(lambda x: '.xlsx' in x, files))
            for sheet in sheets:
                fileName = os.path.join(root, sheet)
                print(fileName)
                if fileName == 'Common_ko/Parameter/Item/ItemTable.xlsx':
                    print('here')
                if fileName == 'Common_ko/TutorialTable/TutorialJob_Data.xlsx':
                    print('here')
                table = TABLESHEET(root, sheet, crowdSpecs, sheetNames)
                if table.isModified():
                    table.dumpSheet(self.pathOut)
                    name = table.getFileName() # Gives modified spreadsheet priority over individual file.
                    files.remove(name)
                # table.dumpTable(self.pathOut)
                files.remove(sheet)
                ### CLEAN THIS UP WITH SHEEETNAMES?
                
            # Copy over the remaining files
            for file in files:
                fileName = os.path.join(root, file)
                print(fileName)
                with open(fileName, 'rb') as file:
                    data = file.read()
                sha = hashlib.sha1(data).hexdigest()
                # if sha != crowdSpecs[fileName]['sha']: # ONLY COPY IF MODIFIED
                #     self.copyFile(fileName)
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
            # if 'Graphics/' in root:
            #     continue
            # if 'Sound/' in root:
            #     continue
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
                        # os.remove(checkName)
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
