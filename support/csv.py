# coding: utf-8

from __future__ import absolute_import
import codecs
import csv

bomdict = {
    codecs.BOM_UTF8 : 'UTF8',
    codecs.BOM_UTF16_BE : 'UTF-16BE',
    codecs.BOM_UTF16_LE : 'UTF-16LE',
}

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')

def read_csv_file(filename):
    """Yields a dict per line (using the first line as the key names)"""

    if hasattr(filename, 'read') and hasattr(filename, 'seek'):
        start_bytes = filename.read(10)
        filename.seek(0)
        for bom, encoding in bomdict.items():
            if start_bytes.startswith(bom):
                filename.read(len(bom))  # Strip the BOM
                csvfile = codecs.EncodedFile(filename, 'UTF8', encoding)
                reader = csv.reader(csvfile)
                break
        else:
            bom = None
            encoding = None
            csvfile = filename
            reader = csv.reader(csvfile)
    else:
        start_bytes = open(filename, 'r').read(10)
        for bom, encoding in bomdict.items():
            if start_bytes.startswith(bom):
                csvfile = codecs.open(filename, 'r', encoding)
                csvfile.read(1)  # Strip the BOM
                reader = csv.reader(utf_8_encoder(csvfile))
                break
        else:
            bom = None
            encoding = None
            csvfile = open(filename, 'r')
            reader = csv.reader(csvfile)

    headers = reader.next()
    for row in reader:
        contact = dict(zip(headers, row))
        for k, v in contact.items():
            if not v:
                del contact[k]
            else:
                contact[k] = v.decode('utf8', 'ignore')
        yield contact
