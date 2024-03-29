import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from release import RELEASE
import hjson
import os
import shutil
import hashlib
import lzma
import pickle
import sys
sys.path.append('src')
from Utilities import get_filename
from ROM import UNPACK, PACK

MAIN_TITLE = f"Bravely Crowd v{RELEASE}"

class GuiApplication:
    def __init__(self, settings=None):
        self.homeDir = os.getcwd()
        self.master = tk.Tk()
        self.master.geometry('625x275')
        self.master.title(MAIN_TITLE)
        self.initialize_gui()

        if not settings:
            if os.path.isfile('settings.json'):
                with open('settings.json', 'r') as file:
                    settings = hjson.load(file)
            
        self.initialize_settings(settings)
        self.master.mainloop()


    def initialize_gui(self):

        self.warnings = []
        self.togglers = []
        self.gameTogglers = []
        self.settings = {}
        self.settings['release'] = tk.StringVar()

        labelfonts = ('Helvetica', 14, 'bold')
        lf = tk.LabelFrame(self.master, text='ROM Folder', font=labelfonts)
        lf.grid(row=0, columnspan=2, sticky='nsew', padx=5, pady=5, ipadx=5, ipady=5)

        self.settings['rom'] = tk.StringVar()
        self.settings['rom'].set('')
        self.settings['game'] = tk.StringVar()
        self.settings['game'].set('')
        

        pathToPak = tk.Entry(lf, textvariable=self.settings['rom'], width=65, state='readonly')
        pathToPak.grid(row=0, column=0, columnspan=2, padx=(10,0), pady=3)

        pathLabel = tk.Label(lf, text='Path to "romfs" folder')
        pathLabel.grid(row=1, column=0, sticky='w', padx=5, pady=2)

        pathButton = tk.Button(lf, text='Browse ...', command=self.getRomPath, width=20) # needs command..
        pathButton.grid(row=1, column=1, sticky='e', padx=5, pady=2)

        lf = tk.LabelFrame(self.master, text="Packer", font=labelfonts)
        lf.grid(row=0, column=2, columnspan=2, sticky='nsew', padx=5, pady=5, ipadx=5, ipady=5)
        
        self.unpackBtn = tk.Button(lf, text='Unpack', command=self._unpack, height=1)
        self.unpackBtn.grid(row=0, column=0, columnspan=1, sticky='we', padx=30, ipadx=30)

        self.packBtn = tk.Button(lf, text='Pack', command=self._pack, height=1)
        self.packBtn.grid(row=1, column=0, columnspan=1, sticky='we', padx=30, ipadx=30)

        # Tabs setup
        tabControl = ttk.Notebook(self.master)
        tab = ttk.Frame(tabControl)
        tabControl.add(tab, text="Settings")
        tabControl.grid(row=2, column=0, columnspan=20, sticky='news')
        
        lf = tk.LabelFrame(tab, text="Game", font=labelfonts)
        lf.grid(row=0, column=0, padx=10, pady=5, ipadx=30, ipady=5, sticky='news')

        button1 = ttk.Radiobutton(lf, text='Bravely Default', variable=self.settings['game'], value='BD', state=tk.NORMAL)
        button1.grid(row=1, padx=10, sticky='we')
        button2 = ttk.Radiobutton(lf, text='Bravely Second', variable=self.settings['game'], value='BS', state=tk.NORMAL)
        button2.grid(row=2, padx=10, sticky='we')

        # For warnings/text at the bottom
        self.canvas = tk.Canvas()
        self.canvas.grid(row=6, column=0, columnspan=20, pady=10)

    def toggler(self, lst, key):
        def f():
            if self.settings[key].get():
                for vi, bi in lst:
                    if self.settings['game'].get() in vi['game']:
                        bi.config(state=tk.NORMAL)
                    else:
                        bi.config(state=tk.DISABLED)
        return f

    def buildToolTip(self, button, field):
        if 'help' in field:
            CreateToolTip(button, field['help'])

    def turnBoolsOff(self):
        for si in self.settings.values():
            if type(si.get()) == bool:
                si.set(False)
            
    def getRomPath(self, path=None):
        self.clearBottomLabels()
        if not path:
            path = filedialog.askdirectory()
            if path == ():
                return
        else:
            if not os.path.isdir(path):
                self.settings['rom'].set('')
                return

        # Set path
        path, dir = os.path.split(path)
        while dir:
            # Allow for romfs/<titleID> to be selected
            is_romfs = 'romfs' in dir.lower()
            is_titleid = '00040000' in dir
            if is_romfs:
                _, directories, _ = next(os.walk(os.path.join(path, dir)))
                if any(['0004000' in d for d in directories]):
                    if len(directories) == 1 and '00040000' in directories[0]:
                        dir = '/'.join([dir, directories[0]])
                    if '00040000000FC500' in directories:
                        dir = '/'.join([dir, '00040000000FC500'])
                    elif '000400000017BA00' in directories:
                        dir = '/'.join([dir, '000400000017BA00'])
                    else:
                        self.clearBottomLabels()
                        self.bottomLabel("Pick the titleID", 'red')
                        self.settings['rom'].set('')
                        return
                        
            if is_romfs or is_titleid:
            # if 'romfs' in dir or 'RomFS' in dir or '0004000000' in dir:
                # path = os.path.join(path, dir)
                path = '/'.join([path, dir])
                self.settings['rom'].set(path)
                self.checkForGame()
                return
            path, dir = os.path.split(path)
        self.clearBottomLabels()
        self.bottomLabel("Folder name must start with 'romfs'", 'red')
        self.settings['rom'].set('')

    def checkForGame(self):
        self.settings['game'].set('')

        # Specified path exists
        path = self.settings['rom'].get()
        if not os.path.isdir(path):
            return

        os.chdir(self.homeDir)

    def initialize_settings(self, settings):
        self.settings['release'].set(RELEASE)
        if settings is None:
            return
        for key, value in settings.items():
            if key == 'release': continue
            if key not in self.settings: continue
            self.settings[key].set(value)
        self.getRomPath(path=self.settings['rom'].get())
        if self.settings['rom'].get() == '':
            self.settings['game'].set('')

    def bottomLabel(self, text, fg):
        L = tk.Label(self.canvas, text=text, fg=fg)
        L.grid(row=len(self.warnings), columnspan=20)
        self.warnings.append(L)
        self.master.update()

    def clearBottomLabels(self):
        while self.warnings != []:
            warning = self.warnings.pop()
            warning.destroy()
        self.master.update()

    def _checkSettings(self):
        self.clearBottomLabels()
        if self.settings['rom'].get() == '':
            self.bottomLabel('Must select a folder!', 'red')
            return False
        elif self.settings['game'].get() == '':
            self.bottomLabel('Must identify the game!', 'red')
            return False
        return True

    def _unpackPopup(self):
        window = tk.Toplevel(self.master)

        def continueUnpack():
            window.destroy()
            self.unpack()

        def abortUnpack():
            window.destroy()
            self.clearBottomLabels()
            self.bottomLabel('Aborting unpacking.', 'red')
            self.bottomLabel('Backup or remove the folder romfs_unpacked yourself, then continue.', 'red')

        label = tk.Label(window, text="The folder romfs_unpacked will be removed.\nMake sure to back up any modded files before continuing.")
        label.grid(row=0, column=0, columnspan=2)
        b1 = ttk.Button(window, text="Continue", command=continueUnpack)
        b1.grid(row=1, column=0, sticky='we')
        b2 = ttk.Button(window, text="Abort", command=abortUnpack)
        b2.grid(row=1, column=1, sticky='we')
        
    def _packPopup(self):
        window = tk.Toplevel(self.master)

        def continuePack():
            window.destroy()
            self.pack()

        def abortPack():
            window.destroy()
            self.clearBottomLabels()
            self.bottomLabel('Aborting packing.', 'red')
            self.bottomLabel('Backup or remove the folder romfs_packed yourself, then continue.', 'red')

        label = tk.Label(window, text="The folder romfs_packed will be removed.\nMake sure to back up any modded files before continuing.")
        label.grid(row=0, column=0, columnspan=2)
        b1 = ttk.Button(window, text="Continue", command=continuePack)
        b1.grid(row=1, column=0, sticky='we')
        b2 = ttk.Button(window, text="Abort", command=abortPack)
        b2.grid(row=1, column=1, sticky='we')
        
    def _unpack(self):
        if not self._checkSettings():
            return
        if os.path.isdir('romfs_unpacked'):
            self._unpackPopup()
        else:
            self.unpack()

    def _pack(self):
        if not self._checkSettings():
            return
        if os.path.isdir('romfs_packed'):
            self._packPopup()
        else:
            self.pack()

    def unpack(self, settings=None):
        
        if settings is None:
            settings = { key: value.get() for key, value in self.settings.items() }
            with open('settings.json', 'w') as file:
                hjson.dump(settings, file)

        dir = os.getcwd()
        self.clearBottomLabels()
        self.bottomLabel('Unpacking....', 'blue')
        if unpack(settings):
            self.clearBottomLabels()
            self.bottomLabel('Unpacking...done!', 'blue')
        else:
            self.clearBottomLabels()
            self.bottomLabel('Mrgrgrgrgr!', 'red')
            self.bottomLabel('Unpacking failed.', 'red')
        os.chdir(dir)

    def pack(self, settings=None):

        if settings is None:
            settings = { key: value.get() for key, value in self.settings.items() }
            with open('settings.json', 'w') as file:
                hjson.dump(settings, file)

        dir = os.getcwd()
        self.clearBottomLabels()
        self.bottomLabel('Packing....', 'blue')
        if pack(settings):
            self.clearBottomLabels()
            self.bottomLabel('Packing...done!', 'blue')
        else:
            self.clearBottomLabels()
            self.bottomLabel('Mrgrgrgrgr!', 'red')
            self.bottomLabel('Packing failed.', 'red')
        os.chdir(dir)


def unpack(settings):
    try:
        UNPACK(settings)
    except:
        return False
    return True

def pack(settings):
    try:
        PACK(settings)
    except:
        return False
    return True


if __name__ == '__main__':
    if len(sys.argv) > 2:
        print('Usage: python gui.py <settings.json>')
    elif len(sys.argv) == 2:
        with open(sys.argv[1], 'r') as file:
            settings = hjson.load(file)
        GuiApplication(settings)
    else:
        GuiApplication()
