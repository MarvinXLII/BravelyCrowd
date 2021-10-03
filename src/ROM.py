from Classes import CROWD, CROWD_BD
import os
import shutil
import sys

class ROM:
    def __init__(self, settings):
        self.settings = settings
        self.game = settings['game']
        self.pathIn = self.settings['rom']
        if os.path.isdir(self.pathOut):
            shutil.rmtree(self.pathOut)
        os.mkdir(self.pathOut)

    def fail(self):
        shutil.rmtree(self.pathOut)

    def loadCrowd(self, path):
        src = os.path.join(self.pathIn, path)
        if self.game == 'BD':
            obj = CROWD_BD(src) # No decompression/compression
        elif self.game == 'BS':
            obj = CROWD(src) # Decompress/compresses all crowds
        else:
            sys.exit(f"Game setting must be BD or BS, not {self.game}")
        return obj

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

        obj = CROWD(None)

        dir = os.getcwd()
        os.chdir(self.pathIn)
        for root, dirs, files in os.walk('.'):
            root = root[2:]
            for file in files:
                if file == 'crowd.fs':
                    crowd = self.loadCrowd(root)
                    crowd.dumpFiles(self.pathOut)
                else: # Copies index.fs and any other files
                    fileName = os.path.join(root, file)
                    self.copyFile(fileName)
        os.chdir(dir)
