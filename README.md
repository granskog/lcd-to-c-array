Info
==============

Python script for reading a .lcd file from MikroElektronika GLCD Font Creator and export a c char array in horizontal byte order, LSB-first, for use with embedded LCDs (primarily old Nokia LCDs with the PDC8544 controller). GLCD Font Creator outputs c code with vertical byte order only, which is the reason for creating this script.

Syntax
--------------

The script was created for use together with AVR microcontroller and a Nokia LCD using the PCD8544 controller. Therefore there is compilator specific syntax in the output file, e.g. PROGMEM. However it's easy enough to just copy the parts needed from the c array.

Usage
==============

Run the python script with the .lcd input file as the argument:
```
$ lcdtocarray.py [options] input_file

Options:
    -i input_file   Specifies the input file and ignores input_file argument. Typically *.lcd.
    -o output_file  Specifies the output filename. If omitted, defaults to "fontname_size.c".
    -h, --help      Shows this message.
    -l              Least significant bit first in bitmap. This is the default.
    -m              Most significant bit first in bitmap. Default is LSB.
    -z              Horizontal byte order of array in output file. This is the default.
    -v              Vertical byte order of array in output file. Default is horizontal byte order.
```
The output file will be saved in the active directory with the name "{font-name}_{font-width}x{font-height}.c".
