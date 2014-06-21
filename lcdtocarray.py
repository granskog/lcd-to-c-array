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

import sys
import os
import xml.etree.ElementTree as ET
from itertools import izip_longest

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return list(izip_longest(fillvalue=fillvalue, *args))

def getChar(ordVal):
    if ordVal == ord(' '):
        return '<space>'
    elif ordVal == ord('\\'):
        return '<backslash>'
    return chr(ordVal)

_CFONTSTART = """/*
 * Font name:                {name:s}
 * Font size (width:height): {width:d}:{height:d} pixels
 * Start char:               0x{fromChar:2x}
 * End char:                 0x{toChar:2x}
 * Generated with MikroElektronika GLCD Font Creator (http://www.mikroe.com/glcd-font-creator/) & lcdtocarray.py (www.granskog.com)
*/
static const uint8_t {name:s}_{width:d}x{height:d}[] PROGMEM =
{{
"""
_CFONTARRAYITEM = '     {:s},'
_CFONTARRAYITEMCOMMENT = ' // {:s}\n'
_CFONTEND = '};\n'
_CFILETYPE = '.c'

_ERR_INVALID_FILE_FORMAT = 'Invalid file format.'
_ERR_IO = 'Unable to open file.'
_lastErrStr = ''

def setError(errType = 'Error', errDescription = ''):
    global _lastErrStr
    _lastErrStr = 'Error: {:s} {:s}'.format(errType, errDescription)

def saveAsCHeader(fileName):
    try:
        tree = ET.parse(fileName)
        root = tree.getroot()

        fontSize = root.find('FONTSIZE')
        fontName = root.find('FONTNAME')
        fontRange = root.find('RANGE')

        if fontSize is None or fontName is None or fontRange is None:
            setError(_ERR_INVALID_FILE_FORMAT, 'Missing file parameters.')
            return 1

        font = {
            'height': int(fontSize.get('HEIGHT', '0')),
            'width': int(fontSize.get('WIDTH', '0')),
            'name': fontName.text,
            'fromChar': int(fontRange.get('FROM', '0')),
            'toChar': int(fontRange.get('TO', '0'))
        }

        if font['height'] % 8 != 0:
            setError(_ERR_INVALID_FILE_FORMAT, 'Font height not multiple of eight.')
            return 1

        if font['height'] <= 0 or font['width'] <= 0:
            setError(_ERR_INVALID_FILE_FORMAT, 'Font size parameter is invalid: {width:d}:{height:d} (width:height).'.format(**font))
            return 1

        outFile = open('{name:s}_{width:d}x{height:d}'.format(**font) + _CFILETYPE, 'w')
        outFile.write(_CFONTSTART.format(**font))

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
                setError(_ERR_INVALID_FILE_FORMAT, 'Missing character parameters.')
                outFile.close()
                os.remove(outFile.name)
                return 1

            charNo = int(charNo)
            pixels = pixels.split(',')

            # Validate pixel data for file.
            if len(pixels) != font['width']*(font['height']):
                setError(_ERR_INVALID_FILE_FORMAT, 'Error: Invalid file format. Missmatch in pixel length for char "{:s}"'.format(charStr))
                outFile.close()
                os.remove(outFile.name)
                return 1

            pixels = grouper(pixels, 8)
            for i in range(len(pixels)):
                byte = 0
                for bit in pixels[i]:
                    # Pixels are represented with a colour code, i.e.
                    # black (filled in non-inverted mode) is '0' and all other
                    # values are considered "background". The output is in LSB order.
                    byte >>= 1
                    byte |= 128 if bit == '0' else 0

                pixels[i] = '0x{:02x}'.format(byte)

            # Arrange pixels in vertical byte orientation.
            byteArray = grouper(pixels, font['height']/8)
            byteArray = zip(*byteArray)
            # Flatten the array of tuples.
            byteArray = [byte for vertBytes in byteArray for byte in vertBytes]

            outChars.append((charNo, byteArray))

        # Sort the chars so we aren't dependent on the order they appear in the XML file.
        outChars.sort()

        # Validate that the character array is correct. A misaligned array will be useless in the ouput
        if (font['fromChar'] != outChars[0][0] or
                font['toChar'] != outChars[len(outChars)-1][0] or
                len(outChars) != font['toChar'] - font['fromChar'] + 1):
            setError(_ERR_INVALID_FILE_FORMAT, 'Misaligned character array.')
            outFile.close()
            os.remove(outFile.name)
            return 1       

        # Print the character array to the output file formatted as a c-array.
        for char in outChars:
            charNo, bytes = char
            outFile.write(_CFONTARRAYITEM.format(','.join(bytes)))
            outFile.write(_CFONTARRAYITEMCOMMENT.format(getChar(charNo)))

        outFile.write(_CFONTEND)
        outFile.close()
        return 0

    except IOError:
        setError(_ERR_IO, 'File: "{:s}"'.format(fileName))
        return 1
    except ET.ParseError:
        setError(_ERR_INVALID_FILE_FORMAT, 'Unable to parse infile: {:s}.'.format(fileName))
        return 1

_USAGE = """Usage:
    lcdtocarray.py <filename.lcd>"""

if __name__ == '__main__':
    if len(sys.argv) == 2:
        if saveAsCHeader(sys.argv[1]) != 0:
            print _lastErrStr
            sys.exit(1);
    else:
        print _USAGE
        sys.exit(1)
