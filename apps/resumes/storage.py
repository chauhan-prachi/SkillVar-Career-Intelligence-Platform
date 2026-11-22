from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """Files live outside static/ and have no URL: they can only be read through an ownership-checked view."""

    def __init__(self, *args, **kwargs):
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)

    def url(self, name):
        raise ValueError("Private files have no public URL; serve them through an ownership-checked view.")

    def deconstruct(self):  # keeps migrations independent of the machine-specific path
        return ("apps.resumes.storage.PrivateStorage", [], {})


def private_storage():
    return PrivateStorage()
