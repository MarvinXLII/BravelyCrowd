### ABOUT

This is a little tool for unpacking and packing the crowd files in Bravely Second.

### USAGE

To run the executable from the Releases page, it is assumed that you
have [extracted RomFS from your
cartridge](https://gist.github.com/PixelSergey/73d0a4bc1437dbaa53a1d1ce849fdda1).
It will not work with `*.3ds`, `*.cia`, etc. files. The executable
requires that you input the path to (and including) the folder
`romfs`.

Selecting `Unpack` in the executable will unpack and decompress all
crowd files in the selected `romfs` folder. This will take some time
if all the files are there. The unpacked files will be put in the
folder `romfs_unpacked`.

Selecting `Pack` in the executable will pack and compress all crowd
files in the selected folder. It is strongly recommended that you
remove any unmodified folders (NEVER delete a single file) to speed
this up. The packed files will be put in the folder `romfs_packed`.

You can run your packed files on your console with [Luma
LayeredFS](https://gist.github.com/PixelSergey/5dbb4a9b90d290736353fa58e4fcbb42).
NOTE that you will have to copy and rename the `romfs_packed` folder
to `romfs` for it to work.
