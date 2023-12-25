from PySide6.QtCore import Qt, QPointF, QPoint, QRectF
from PySide6.QtGui import QTransform, QPolygonF, QImage, QPainter, QBrush, QColor
import math
try:
    import numpy as np
    # import scipy.spatial.distance
    NUMPY_SCIPY_AVAILABLE = True
except ModuleNotFoundError:
    NUMPY_SCIPY_AVAILABLE = False
try:
    from PIL import Image, ImageChops, ImageQt
    PIL_AVAILABLE = True
except ModuleNotFoundError:
    PIL_AVAILABLE = False

COLOR_THRESHOLD = 20


def findBorders(image):
    if PIL_AVAILABLE:
        return _findBorders1(image)
    else:
        return _findBorders2(image)


def _findBorders1(image):
    im = ImageQt.fromqimage(image)

    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])

    return (0, 0, image.width(), image.height())


def _findBorders2(image):
    w = image.width()
    h = image.height()

    x1 = _findBorderV(image, range(w // 2), range(h))
    x2 = _findBorderV(image, range(w - 1, w // 2, -1), range(h)) + 1
    y1 = _findBorderH(image, range(h // 2), range(w))
    y2 = _findBorderH(image, range(h - 1, h // 2, -1), range(w)) + 1

    return (x1, y1, x2 - x1, y2 - y1)


def _findBorderH(image, range_v, range_h):
    c = image.pixel(range_h[0], range_v[0])
    start_r, start_g, start_b, _ = QColor(c).getRgb()
    for i in range_v:
        for j in range_h:
            c = image.pixel(j, i)
            r, g, b, _ = QColor(c).getRgb()
            if abs(r - start_r) > COLOR_THRESHOLD or \
                    abs(g - start_g) > COLOR_THRESHOLD or \
                    abs(b - start_b) > COLOR_THRESHOLD:
                return i


def _findBorderV(image, range_h, range_v):
    c = image.pixel(range_h[0], range_v[0])
    start_r, start_g, start_b, _ = QColor(c).getRgb()
    for i in range_h:
        for j in range_v:
            c = image.pixel(i, j)
            r, g, b, _ = QColor(c).getRgb()
            if abs(r - start_r) > COLOR_THRESHOLD or \
                    abs(g - start_g) > COLOR_THRESHOLD or \
                    abs(b - start_b) > COLOR_THRESHOLD:
                return i


def cropCircle(pixmap, points):
    rect = QRectF(points[3].x(), points[0].y(),
                  points[1].x() - points[3].x(),
                  points[2].y() - points[0].y()).toRect()

    pixmap = pixmap.copy(rect)
    # Create the output image with the same dimensions and an alpha channel
    # and make it completely transparent:
    image = QImage(pixmap.width(), pixmap.height(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    # Create a texture brush and paint a circle with the original image onto
    # the output image:
    brush = QBrush(pixmap)  # Create texture brush
    painter = QPainter(image)  # Paint the output image
    painter.setBrush(brush)  # Use the image texture brush
    painter.setPen(Qt.PenStyle.NoPen)  # Don't draw an outline
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)  # Use AA
    painter.drawEllipse(pixmap.rect())  # Actually draw the circle
    painter.end()  # We are done

    return image


def perspectiveTransformation(pixmap, points):
    orig_rect = pixmap.rect()

    if NUMPY_SCIPY_AVAILABLE:
        width, height = _perspectiveTransformation2(points, orig_rect)
    else:
        width, height = _perspectiveTransformation1(points, orig_rect)

    poly1 = QPolygonF(points)

    poly2 = QPolygonF()
    poly2.append(QPointF(0, 0))
    poly2.append(QPointF(width, 0))
    poly2.append(QPointF(width, height))
    poly2.append(QPointF(0, height))

    transform = QTransform()
    res = QTransform.quadToQuad(poly1, poly2, transform)
    if res:
        tl = transform.map(QPoint(0, 0))
        bl = transform.map(QPoint(0, orig_rect.height()))
        tr = transform.map(QPoint(orig_rect.width(), 0))

        x = max(-tl.x(), -bl.x())
        y = max(-tr.y(), -tl.y())

        pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        pixmap = pixmap.copy(x, y, width, height)

        return pixmap

    return None


def _perspectiveTransformation1(points, rect):
# Based on https://stackoverflow.com/questions/38285229/calculating-aspect-ratio-of-perspective-transform-destination-image
    u0 = rect.width() / 2
    v0 = rect.height() / 2
    m1x = points[0].x() - u0
    m1y = points[0].y() - v0
    m2x = points[1].x() - u0
    m2y = points[1].y() - v0
    m3x = points[3].x() - u0
    m3y = points[3].y() - v0
    m4x = points[2].x() - u0
    m4y = points[2].y() - v0

    k2 = ((m1y - m4y) * m3x - (m1x - m4x) * m3y + m1x * m4y - m1y * m4x) / ((m2y - m4y) * m3x - (m2x - m4x) * m3y + m2x * m4y - m2y * m4x)

    k3 = ((m1y - m4y) * m2x - (m1x - m4x) * m2y + m1x * m4y - m1y * m4x) / ((m3y - m4y) * m2x - (m3x - m4x) * m2y + m3x * m4y - m3y * m4x)

    if k2 == 1 or k3 == 1:
        whRatio = math.sqrt((pow((m2y - m1y), 2) + pow((m2x - m1x), 2)) / (pow((m3y - m1y), 2) + pow((m3x - m1x), 2)))
    else:
        f_squared = -((k3 * m3y - m1y) * (k2 * m2y - m1y) + (k3 * m3x - m1x) * (k2 * m2x - m1x)) / ((k3 - 1) * (k2 - 1))
        whRatio = math.sqrt((pow((k2 - 1), 2) + pow((k2 * m2y - m1y), 2) / f_squared + pow((k2 * m2x - m1x), 2) / f_squared) / (pow((k3 - 1), 2) + pow((k3 * m3y - m1y), 2) / f_squared + pow((k3 * m3x - m1x), 2) / f_squared))

    h1 = math.sqrt(pow((points[2].x() - points[1].x()), 2) + pow((points[2].y() - points[1].y()), 2))
    h2 = math.sqrt(pow((points[3].x() - points[0].x()), 2) + pow((points[3].y() - points[0].y()), 2))
    h = max(h1, h2)

    height = int(h)
    width = int(whRatio * height)

    return (width, height)


def _perspectiveTransformation2(points, rect):
# Based on https://stackoverflow.com/questions/38285229/calculating-aspect-ratio-of-perspective-transform-destination-image
    rows = rect.height()
    cols = rect.width()

    # image center
    u0 = (cols) / 2.0
    v0 = (rows) / 2.0

    # detected corners on the original image
    p = []
    p.append((points[0].x(), points[0].y()))
    p.append((points[1].x(), points[1].y()))
    p.append((points[3].x(), points[3].y()))
    p.append((points[2].x(), points[2].y()))

    # widths and heights of the projected image
    # w1 = scipy.spatial.distance.euclidean(p[0], p[1])
    w1 = math.sqrt(pow((points[0].x() - points[1].x()), 2) + pow((points[0].y() - points[1].y()), 2))
    # w2 = scipy.spatial.distance.euclidean(p[2], p[3])
    w2 = math.sqrt(pow((points[2].x() - points[3].x()), 2) + pow((points[2].y() - points[3].y()), 2))

    # h1 = scipy.spatial.distance.euclidean(p[0], p[2])
    h1 = math.sqrt(pow((points[0].x() - points[2].x()), 2) + pow((points[0].y() - points[2].y()), 2))
    # h2 = scipy.spatial.distance.euclidean(p[1], p[3])
    h2 = math.sqrt(pow((points[1].x() - points[3].x()), 2) + pow((points[1].y() - points[3].y()), 2))

    w = max(w1, w2)
    h = max(h1, h2)

    # visible aspect ratio
    ar_vis = float(w) / float(h)

    # make numpy arrays and append 1 for linear algebra
    m1 = np.array((p[0][0], p[0][1], 1)).astype('float32')
    m2 = np.array((p[1][0], p[1][1], 1)).astype('float32')
    m3 = np.array((p[2][0], p[2][1], 1)).astype('float32')
    m4 = np.array((p[3][0], p[3][1], 1)).astype('float32')

    # calculate the focal distance
    k2 = np.dot(np.cross(m1, m4), m3) / np.dot(np.cross(m2, m4), m3)
    k3 = np.dot(np.cross(m1, m4), m2) / np.dot(np.cross(m3, m4), m2)

    n2 = k2 * m2 - m1
    n3 = k3 * m3 - m1

    n21 = n2[0]
    n22 = n2[1]
    n23 = n2[2]

    n31 = n3[0]
    n32 = n3[1]
    n33 = n3[2]

    f = math.sqrt(np.abs((1.0 / (n23 * n33)) * ((n21 * n31 - (n21 * n33 + n23 * n31) * u0 + n23 * n33 * u0 * u0) + (n22 * n32 - (n22 * n33 + n23 * n32) * v0 + n23 * n33 * v0 * v0))))

    A = np.array([[f, 0, u0], [0, f, v0], [0, 0, 1]]).astype('float32')

    At = np.transpose(A)
    Ati = np.linalg.inv(At)
    Ai = np.linalg.inv(A)

    # calculate the real aspect ratio
    ar_real = math.sqrt(np.dot(np.dot(np.dot(n2, Ati), Ai), n2) / np.dot(np.dot(np.dot(n3, Ati), Ai), n3))

    if ar_real < ar_vis:
        W = int(w)
        H = int(W / ar_real)
    else:
        H = int(h)
        W = int(ar_real * H)

    return (W, H)
