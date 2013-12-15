# coding=utf-8

from __future__ import absolute_import

from PIL import Image
from cStringIO import StringIO
import subprocess

class ImageThumbnailer(object):
    @classmethod
    def can_thumbnail(cls, trex_upload):
        return trex_upload.file.content_type in ['image/png', 'image/gif', 'image/jpeg']

    @classmethod
    def generate_thumbnail(cls, trex_upload, width, height, fit, source_fp=None):
        from .model import TrexUploadThumbnail
        thumbnail = TrexUploadThumbnail(upload=trex_upload, width=width, height=height, fit=fit)

        if source_fp is None:
            source_fp = trex_upload.file.get()

        image = Image.open(source_fp)
        orig_width, orig_height = image.size

        if fit == 'stretch':
            image = image.resize((width, height), Image.ANTIALIAS)
        elif fit == 'contain':
            if not width:
                width = float(height) * float(orig_width) / float(orig_height)
            if not height:
                height = float(width) * float(orig_height) / float(orig_width)
            image.thumbnail((width, height), Image.ANTIALIAS)
        elif fit == 'cover':
            target_aspect = float(width) / float(height)
            source_aspect = float(orig_width) / float(orig_height)
            if source_aspect > target_aspect:
                target_width = target_aspect * orig_height
                image = image.crop((int(float(orig_width / 2) - target_width / 2), 0, int(float(orig_width / 2) + target_width / 2), orig_height))
            else:
                target_height = orig_width / target_aspect
                image = image.crop((0, int(float(orig_height / 2) - target_height / 2), orig_width, int(float(orig_height / 2) + target_height / 2)))

            image.thumbnail((width, height), Image.ANTIALIAS)
        else:
            raise NotImplementedError("No fit method %s" % fit)

        if image.mode == 'P':
            fp = StringIO()
            image.save(fp, 'png')
            fp.seek(0)
            thumbnail.file.put(fp, content_type='image/png')
            thumbnail.save()
            return thumbnail
        else:
            fp = StringIO()
            image.save(fp, 'jpeg')
            fp.seek(0)
            thumbnail.file.put(fp, content_type='image/jpeg')
            thumbnail.save()
            return thumbnail

class PDFThumbnailer(object):
    @classmethod
    def can_thumbnail(cls, trex_upload):
        return trex_upload.file.content_type == 'application/pdf'

    @classmethod
    def generate_thumbnail(cls, trex_upload, width, height, fit):
        gs_command = [
            'gs',
            '-q',                       # Quiet
            '-sDEVICE=jpeg',            # Output as JPEG
            '-r60',                     # DPI to render at
            '-dJPEGQ=95',               # Output JPEGs with 95% quality
            '-o-',                      # Write to STDOUT
            '-dSAFER',                  # For safety
            '-dTextAlphaBits=4',        # High quality antialiasing of text
            '-dGraphicsAlphaBits=4',    # High quality antialiasing of graphics
            '-dNumRenderingThreads=4',  # Only used in some cases we'll probably never encounter (gs mostly single threaded)
            '-dMaxBitmap=500000000',    # Allow images of this size to be in RAM
            '-dAlignToPixels=0',        # Improves rendering of poorly hinted fonts at possible expense of well hinted ones (we can play with this over time)
            '-dGridFitTT=2',            # Default value, helps with font hinting
            '-c', '30000000', 'setvmthreshold',  # Helps speed in PDFs with fonts with large character sets (reserves 30MB ram for characters)
            '-dFirstPage=1', '-dLastPage=1',  # Only the first page
            '-'                         # Read from STDIN
        ]
        gs_proc = subprocess.Popen(gs_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = gs_proc.communicate(input=trex_upload.file.get().read())
        if gs_proc.returncode:
            raise Exception("ghost script command returned non-zero exit code: %d" % gs_proc.returncode)

        return ImageThumbnailer.generate_thumbnail(trex_upload, width, height, fit, source_fp=StringIO(stdout))
