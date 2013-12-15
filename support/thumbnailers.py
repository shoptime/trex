# coding=utf-8

from __future__ import absolute_import

from PIL import Image
from cStringIO import StringIO

class ImageThumbnailer(object):
    @classmethod
    def can_thumbnail(cls, trex_upload):
        return trex_upload.file.content_type in ['image/png', 'image/gif', 'image/jpeg']

    @classmethod
    def generate_thumbnail(cls, trex_upload, width, height, fit):
        from .model import TrexUploadThumbnail
        thumbnail = TrexUploadThumbnail(upload=trex_upload, width=width, height=height, fit=fit)

        image = Image.open(trex_upload.file.get())
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
