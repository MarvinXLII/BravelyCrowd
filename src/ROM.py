# from Classes import CROWD, CROWD_BD
from Classes import CROWD, TABLE
import os
import shutil
import sys
# from Spreadsheets import XLSX

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
        return CROWD(dest)

    # Not sure why I did all these copies?
    def loadTable(self, fileName):
        src = os.path.join(self.pathIn, fileName)
        dest = os.path.join(self.pathOut, fileName)
        base = os.path.dirname(dest)
        if not os.path.isdir(base):
            os.makedirs(base)
        shutil.copy(src, dest)
        return TABLE(dest)

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
        for root, dirs, files in os.walk('.'):
            # First load crowd using index
            root = root[2:]
            if 'index.fs' in files:
                crowd = self.loadCrowd(root)
                pathOut = os.path.join(self.pathOut, root)
                crowd.dumpCrowd(pathOut)
                # Copy over remaining files
                files = list(filter(lambda x: x not in crowd.crowdFiles.keys(), files))
            # Copy over the remaining files
            for file in files:
                if file == 'index.fs':
                    continue
                fileName = os.path.join(root, file)
                self.copyFile(fileName)

        os.chdir(dir)


class UNPACK(ROM):
    def __init__(self, settings):
        self.pathOut = os.path.join(os.getcwd(), f"romfs_unpacked")
        super().__init__(settings)
        dir = os.getcwd()
        os.chdir(self.pathIn)
        for root, dirs, files in os.walk('.'):
            root = root[2:]
            for file in files:
                if file == 'index.fs':
                    continue
                fileName = os.path.join(root, file)
                checkName = os.path.join(self.pathOut, fileName)
                if os.path.isfile(checkName):
                    continue
                if 'Script/Scene/TW_13_FlowerCountry/Scene/crowd.fs' == fileName:
                    print('DECOMPRESS ERROR UP NEXT!')
                if file == 'crowd.fs':
                    table = self.loadCrowd(root)
                    table.dumpFiles(self.pathOut)
                    self.copyFile(fileName)
                else:
                    table = self.loadTable(fileName)
                    self.copyFile(fileName)
                # if 'Graphics' in fileName:
                #     continue

                ### OKAY FILES:
                # btb
                # tbl
                if file == 'crowd.fs' or fileName.split('.')[-1] in ['btb', 'tbl']:
                    try:
                        print(fileName)
                        table.dumpSheet()
                    except:
                        print(fileName, 'failed!')
                        # sys.exit()
                
        os.chdir(dir)
