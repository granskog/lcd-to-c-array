#!/usr/local/bin/python
# -*- coding: UTF-8 -*-

# Python script for reading a .lcd file from MikroElektronika GLCD Font Creator and
# export a c char array in horizontal byte order, LSB-first, for use with embedded LCDs
# (primarily old Nokia LCDs with the PDC8544 controller). GLCD Font Creator outputs
# c code with vertical byte order only, which is the reason for creating this script.

# The MIT License (MIT)

# Copyright (c) 2014 David Gran Skog, http://www.granskog.com, https://github.com/granskog/lcd-to-c-array

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys, getopt
import StringIO
import xml.etree.ElementTree as ET

# Since we validate the input file to have correct number of pixels represented
# and that they are in a multiple of eight, it's enough to use zip() function
# to group our lists together.
def _grouper(iterable, n):
    "Collect data into fixed-length chunks or blocks"
    # _grouper('ABCDEFG', 2) --> AB CD EF
    # (Note missing 'G'. But we don't care, since our input data should be in correct multiples.)
    args = [iter(iterable)] * n
    return zip(*args)

# Rearrange the pixels in horizontal byte order instead of the vertical byte order
# the GLCD Font Creator outputs. This is done by creating a matrix where each column is the vertical
# pixels, then transposing that matrix (using zip()) and flatten it to an array again.
def _reArrange(values, n):
    values = _grouper(values, n)
    values = zip(*values)
    # Flatten the array of tuples.
    values = [piece for pieces in values for piece in pieces]
    return values

def _getChar(ordVal):
    if ordVal == ord(' '):
        return '<space>'
    elif ordVal == ord('\\'):
        return '<backslash>'
    elif ordVal == 127:
        return '<delete>'
    return chr(ordVal)

_CFONTSTART = """#include <stdint.h>
#include <avr/pgmspace.h>
/*
 * Font name:                {name:s}
 * Font size (width:height): {width:d}:{height:d} pixels
 * Start char:               0x{fromChar:2x}
 * End char:                 0x{toChar:2x}
 * Font data generated with: MikroElektronika GLCD Font Creator (http://www.mikroe.com/glcd-font-creator/)
 * C formatting generated with: lcdtocarray.py (https://github.com/granskog/lcd-to-c-array)
*/
static const uint8_t {name:s}_{width:d}x{height:d}[] PROGMEM =
{{
"""
_CFONTARRAYITEM = '    {:s},'
_CFONTARRAYITEMCOMMENT = ' // {:s}\n'
_CFONTEND = '};\n'
_CFILETYPE = 'c'

def saveAsCHeader(fileName, outFileName = '', LSB = True, horizByteOrder = True, horizontalBits = False):
    try:
        tree = ET.parse(fileName)
    except IOError:
        return (1, 'Unable to open file: "{:s}"."'.format(fileName))
    except ET.ParseError:
        return (1, 'Invalid file format. Unable to parse infile: {:s}.'.format(fileName))

    root = tree.getroot()

    fontSize = root.find('FONTSIZE')
    fontName = root.find('FONTNAME')
    fontRange = root.find('RANGE')

    if fontSize is None or fontName is None or fontRange is None:
        return (1, 'Invalid file format. Missing file parameters.')

    font = {
        'height': int(fontSize.get('HEIGHT', '0')),
        'width': int(fontSize.get('WIDTH', '0')),
        'name': fontName.text,
        'fromChar': int(fontRange.get('FROM', '0')),
        'toChar': int(fontRange.get('TO', '0'))
    }

    font['name'] = font['name'].replace(' ', '_')

    if font['height'] <= 0 or font['width'] <= 0:
        return (1, 'Invalid file format. Font size parameter is invalid: {width:d}:{height:d} (width:height).'.format(**font))

    if horizontalBits and font['width']  % 8 != 0:
        return (1, 'Invalid file format. Font width not multiple of eight.')

    if not horizontalBits and font['height'] % 8 != 0:
        return (1, 'Invalid file format. Font height not multiple of eight.')

    # Create a string buffer to write to. Doing it this way we don't overwrite
    # any previously created files if we find the input file being invalid
    # later on.
    out = StringIO.StringIO()
    out.write(_CFONTSTART.format(**font))

    chars = root.find('CHARS')
    if chars is None:
        chars = []

    outChars = []
    for char in chars:
        # Validate data in file. If no pixels are present in the XML file or no information of which character it is
        # abort the whole operation, because a missing ASCII character or uncertain char order will make a char array
        # have undefined offsets. Rendering the output useless.
        pixels = char.get('PIXELS')
        charNo = char.get('CODE')
        if pixels is None or charNo is None:
            out.close()
            return (1, _ERR_INVALID_FILE_FORMAT, 'Missing character parameters.')

        charNo = int(charNo)
        pixels = pixels.split(',')

        # Validate pixel data for file.
        if len(pixels) != font['width']*(font['height']):
            out.close()
            return (1, 'Invalid file format. Missmatch in pixel length for char "{:d}" ({:s}).'.format(charNo, _getChar(charNo)))

        byteArray = []

        if horizontalBits:
            pixels = _reArrange(pixels, font['height'])

        for byteOfPixels in _grouper(pixels, 8):
            byte = 0
            # Pixels are represented with a colour code, i.e.
            # black (filled in non-inverted mode) is '0' and all other
            # values are considered "background" (e.g. white is represented by'16777215').
            for bit in byteOfPixels:
                byte = byte>>1 if LSB else byte<<1
                byte |= (128 if LSB else 1) if bit == '0' else 0

            byteArray.append('0x' + '{:02x}'.format(byte).upper())

        if horizByteOrder and not horizontalBits:
            byteArray = _reArrange(byteArray, font['height']/8)

        outChars.append((charNo, byteArray))

    # Sort the chars so we aren't dependent on the order they appear in the XML file.
    outChars.sort()

    # Validate that the character array is correct. A misaligned array will be useless in the ouput
    if (font['fromChar'] != outChars[0][0] or
            font['toChar'] != outChars[len(outChars)-1][0] or
            len(outChars) != font['toChar'] - font['fromChar'] + 1):
        out.close()
        return (1, 'Invalid file format. Misaligned character array.')

    # Print the character array to the output file formatted as a c-array.
    for charNo, bytes in outChars:
        out.write(_CFONTARRAYITEM.format(','.join(bytes)))
        out.write(_CFONTARRAYITEMCOMMENT.format(_getChar(charNo)))

    out.write(_CFONTEND)

    # Flush content of memorybuffer to file.
    if outFileName == '':
        outFileName = '{name:s}_{width:d}x{height:d}.{filetype:s}'.format(filetype = _CFILETYPE, **font).replace(' ', '_')
    try:
        outFile = open(outFileName, 'w')
    except IOError:
        out.close()
        return (1, 'Unable to create file: "{:s}"."'.format(outFileName))

    outFile.write(out.getvalue())
    outFile.close()
    out.close()
    return (0, '')

_USAGE = """Usage:
    lcdtocarray.py [options] input_file
Options:
    -i input_file   Specifies the input file and ignores input_file argument. Typically *.lcd.
    -o output_file  Specifies the output filename. If omitted, defaults to "fontname_size.c".
    -h, --help      Shows this message.
    -l, --LSB       Least significant bit first in bitmap. This is the default.
    -m, --MSB       Most significant bit first in bitmap. Default is LSB.
    -z              Horizontal byte order of array in output file. This is the default.
    -v              Vertical byte order of array in output file. Default is horizontal byte order.
    -H              Create bytes from horizontally aligned bits in the bitmap. Overrides -z & -v options."""
    
def main(argv):
    inputfile = ''
    outputfile = ''
    hbyteorder = True
    lsb = True
    hrzBits = False
    try:
        opts, args = getopt.getopt(argv, "hi:o:lmzvH",["help, LSB, MSB"])
    except getopt.GetoptError:
        print _USAGE
        sys.exit(2)
    for opt, arg in opts:
        if opt == ('-h', '--help'):
            print _USAGE
            sys.exit()
        elif opt in ("-i"):
            inputfile = arg
        elif opt in ("-o"):
            outputfile = arg
        elif opt in ("-l", "--LSB"):
            lsb = True
        elif opt in ("-m", "--MSB"):
            lsb = False
        elif opt in ("-z"):
            hbyteorder = True
        elif opt in ("-v"):
            hbyteorder = False
        elif opt in ("-H"):
            hrzBits = True
    
    if inputfile == '':
        if len(args) == 1:
            inputfile = args[0]
        else:
            print _USAGE
            sys.exit(2)

    errCode, errMsg = saveAsCHeader(inputfile, outputfile, lsb, hbyteorder, hrzBits)
    if errCode != 0:
        print errMsg
        sys.exit(2);

if __name__ == '__main__':
    main(sys.argv[1:])
