import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from release import RELEASE
import hjson
import os
import shutil
import hashlib
import sys
sys.path.append('src')
from Utilities import get_filename
from ROM import UNPACK, PACK

MAIN_TITLE = f"Bravely Crowd v{RELEASE}"


class GuiApplication:
    def __init__(self, settings=None):
        self.master = tk.Tk()
        self.master.geometry('625x175')
        self.master.title(MAIN_TITLE)
        self.initialize_gui()
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

        pathToPak = tk.Entry(lf, textvariable=self.settings['rom'], width=65, state='readonly')
        pathToPak.grid(row=0, column=0, columnspan=2, padx=(10,0), pady=3)

        pathLabel = tk.Label(lf, text='Path to "romfs" folder')
        pathLabel.grid(row=1, column=0, sticky='w', padx=5, pady=2)

        pathButton = tk.Button(lf, text='Browse ...', command=self.getRomPath, width=20) # needs command..
        pathButton.grid(row=1, column=1, sticky='e', padx=5, pady=2)

        lf = tk.LabelFrame(self.master, text="Packer", font=labelfonts)
        lf.grid(row=0, column=2, columnspan=2, sticky='nsew', padx=5, pady=5, ipadx=5, ipady=5)
        
        self.unpackBtn = tk.Button(lf, text='Unpack', command=self.unpack, height=1)
        self.unpackBtn.grid(row=0, column=0, columnspan=1, sticky='we', padx=30, ipadx=30)

        self.packBtn = tk.Button(lf, text='Pack', command=self.pack, height=1)
        self.packBtn.grid(row=1, column=0, columnspan=1, sticky='we', padx=30, ipadx=30)

        # For warnings/text at the bottom
        self.canvas = tk.Canvas()
        self.canvas.grid(row=6, column=0, columnspan=20, pady=10)

    def getRomPath(self, path=None):
        self.clearBottomLabels()
        if not path:
            path = filedialog.askdirectory()
        # Exited askdirectory
        if path == ():
            return
        # Set path to valid rom
        self.settings['rom'].set(path)

    def initialize_settings(self, settings):
        self.settings['release'].set(RELEASE)
        if settings is None:
            return
        for key, value in settings.items():
            if key == 'release': continue
            if key not in self.settings: continue
            self.settings[key].set(value)
        self.getRomPath(path=self.settings['rom'].get())

    def bottomLabel(self, text, fg, row):
        L = tk.Label(self.canvas, text=text, fg=fg)
        L.grid(row=row, columnspan=20)
        self.warnings.append(L)
        self.master.update()

    def clearBottomLabels(self):
        while self.warnings != []:
            warning = self.warnings.pop()
            warning.destroy()
        self.master.update()
        
    def unpack(self, settings=None):
        if settings is None:
            settings = { key: value.get() for key, value in self.settings.items() }
        self.clearBottomLabels()
        self.bottomLabel('Unpacking....', 'blue', 0)
        if unpack(settings):
            self.clearBottomLabels()
            self.bottomLabel('Unpacking...done!', 'blue', 0)
        else:
            self.clearBottomLabels()
            self.bottomLabel('Mrgrgrgrgr!', 'red', 0)
            self.bottomLabel('Unpacking failed.', 'red', 1)

    def pack(self, settings=None):
        if settings is None:
            settings = { key: value.get() for key, value in self.settings.items() }
        self.clearBottomLabels()
        self.bottomLabel('Packing....', 'blue', 0)
        if pack(settings):
            self.clearBottomLabels()
            self.bottomLabel('Packing...done!', 'blue', 0)
        else:
            self.clearBottomLabels()
            self.bottomLabel('Mrgrgrgrgr!', 'red', 0)
            self.bottomLabel('Packing failed.', 'red', 1)


def unpack(settings):
    UNPACK(settings)
    # try:
    #     UNPACK(settings)
    # except:
    #     return False
    return True


def pack(settings):
    PACK(settings)
    # try:
    #     PACK(settings)
    # except:
    #     return False
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
