### ABOUT

This is a little editor for data tables in Bravely Default and Bravely
Second. It unpacks the crowd files, organizes data into speadsheets
whenever possible, and packs edited files and spreadsheets into a mod.

### USAGE

This tool is only compatible with an extracted RomFS. You'll need to do
this first with other tools such as GodMode9 or
[DotNet3DS](https://github.com/evandixon/DotNet3dsToolkit/releases). Follow
[this
link](https://gist.github.com/PixelSergey/73d0a4bc1437dbaa53a1d1ce849fdda1)
for help with GodMode9.

When that is done, you can run executable from the Releases page. To
unpack the files and make spreadsheets, just browse for the RomFS
folder, select which game is being used, and select Unpack.

Unpacked files will be dumped in the folder `romfs_unpacked`. There
you can edit spreadsheets or any of the other file with a hex
editor. When done, run the executable, browse for `romfs_unpacked`,
and click Pack to pack the files and build a mod. The mod will be
output in the folder `romfs_packed`, along with a log file listing
each file modified. You can run your mod on your console, for example,
with [Luma
LayeredFS](https://gist.github.com/PixelSergey/5dbb4a9b90d290736353fa58e4fcbb42).

### IMPORTANT NOTES

Editing files, even in a spreadsheet, will be a bit complicated. Please read this carefully:

- The executable is only compatible with spreadsheets of the `.xls`
  format. Do not reformat these files into `.xlsx` or anything else.

- Unpacking and packing files can be a bit slow. You can speed this up
  by removing large folders you won't be modding, such as `Graphics`
  or `Sound`. Never remove files individually, as this can lead to
  issues when packing crowds.

- Some spreadsheets have text in them. These columns are labeled
  `Text` and `Labels`. When these are present you'll also see some
  columns labeled `Text Pntr` and `Label Pntr`. These columns need to
  be updated if you change any text, but don't worry! The tool will
  automatically update them for you!

- You can label column headers in any spreadsheet you're reading or
  editing. These headers will be saved in the
  `romfs_packed/headers_XX` folder and will be used when unpacked in
  the future. Don't move or delete this folder.