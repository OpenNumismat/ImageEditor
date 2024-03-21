class ImageProxy():

    def __init__(self):
        self._current = None
        self._images = []

    def images(self):
        return self._images

    def setImages(self, images):
        self._images = images

    def append(self, image):
        self._images.append(image)

    def currentImage(self):
        for image in self._images:
            if image.field == self._current:
                return image

    def setCurrent(self, field):
        self._current = field

    def imageSaved(self, image):
        self.currentImage().imageSaved(image)

    def prev(self):
        _prev = self._images[0]
        for image in self._images:
            if image.field == self._current:
                self.setCurrent(_prev.field)
                return _prev
            else:
                _prev = image

        return None

    def next(self):
        _next = self._images[-1]
        for image in reversed(self._images):
            if image.field == self._current:
                self.setCurrent(_next.field)
                return _next
            else:
                _next = image

        return None
