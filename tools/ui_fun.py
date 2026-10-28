"""Native walkie-talkie artwork. All decorative movement stays within its frame."""
import math

import AppKit
import Quartz


def emotion_for(mode, text):
    if text.startswith('Cancelled'):
        return 'calm'
    return {'listening': 'curious', 'editing': 'focused', 'processing': 'thinking',
            'success': 'happy', 'notice': 'concerned', 'meeting': 'attentive'}[mode]


def screen_hint(mode, text, badge):
    if mode == 'notice':
        if 'Copy Last' in text or text.startswith('Selection changed'):
            return 'COPY LAST RESULT'
        if text.startswith('Cancelled'):
            return 'ALL GOOD. CANCELLED.'
        if 'permission' in text.lower() or 'set up' in text.lower():
            return 'CHECK TALKY MENU'
        return 'DETAILS IN TALKY MENU'
    if mode in ('listening', 'editing', 'processing'):
        return badge.upper() or 'ESC TO CANCEL'
    return 'ALL ON YOUR MAC' if mode == 'success' else 'RECORDING MEETING'


def color(hex_value):
    rgb = tuple(int(hex_value[i:i+2], 16) / 255 for i in (0, 2, 4))
    return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgb, 1).CGColor()


class FunCharacter:
    WIDTH, HEIGHT = 260, 200
    INK = '273334'
    SCREEN = '132D24'
    PIXEL = 'B7ED8B'

    def __init__(self, parent):
        self.view = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, self.WIDTH, self.HEIGHT))
        self.view.setWantsLayer_(True)
        parent.addSubview_(self.view)
        root = self.view.layer()
        self._emotion = 'curious'
        # Feet and mittens are behind the body; the silhouette reads as a tiny friend.
        self._rect(root, (65, 6, 35, 19), self.INK, 9)
        self._rect(root, (161, 6, 35, 19), self.INK, 9)
        self._rect(root, (69, 15, 16, 16), 'C8923F', 5)
        self._rect(root, (176, 15, 16, 16), 'C8923F', 5)
        self._rect(root, (18, 64, 27, 15), 'D9A74C', 7)
        self._rect(root, (216, 64, 27, 15), 'D9A74C', 7)
        self._rect(root, (9, 57, 21, 28), 'F8D982', 10, self.INK, 2)
        self._rect(root, (232, 57, 19, 28), 'F8D982', 9, self.INK, 2)
        # The antenna has its own pivot. Its tip stays inside the reserved top margin.
        self.antenna = Quartz.CALayer.layer()
        self.antenna.setFrame_(AppKit.NSMakeRect(52, 151, 22, 43))
        self.antenna.setAnchorPoint_(AppKit.NSMakePoint(.5, 0))
        self.antenna.setPosition_(AppKit.NSMakePoint(63, 151))
        root.addSublayer_(self.antenna)
        self._rect(self.antenna, (6, 0, 10, 40), self.INK, 5)
        self._rect(self.antenna, (9, 8, 3, 27), '65706B', 1)
        self._rect(self.antenna, (3, 32, 16, 11), 'E7AF51', 5, self.INK, 2)
        self._rect(root, (181, 155, 19, 15), self.INK, 5)
        self._rect(root, (185, 161, 11, 7), '718078', 2)
        body = self._rect(root, (32, 19, 196, 146), 'E2AE52', 28, self.INK, 2.5)
        body.setShadowColor_(color('000000'))
        body.setShadowOpacity_(.18)
        body.setShadowRadius_(5)
        body.setShadowOffset_(AppKit.NSMakeSize(0, -2))
        self._rect(root, (38, 25, 184, 134), 'F5CA70', 23)
        self._rect(root, (45, 148, 161, 5), 'FFE5A4', 2)
        self._rect(root, (28, 106, 7, 24), self.INK, 3)  # Push-to-talk button.
        self._rect(root, (28, 111, 4, 14), 'E68163', 2)
        self._rect(root, (47, 59, 166, 88), self.INK, 12)
        self._rect(root, (52, 64, 156, 78), self.SCREEN, 8)
        self._rect(root, (55, 138, 148, 2), '456B43', 1)
        # Quiet two-pixel grid hints at an LCD without flickering scanlines.
        for x in range(58, 204, 6):
            for y in range(69, 136, 6):
                dot = self._rect(root, (x, y, 1, 1), '274532', 0)
                dot.setOpacity_(.35)
        self.title = self._label('LISTENING', (58, 125, 144, 15), 10, True)
        self.hint = self._label('', (57, 67, 146, 14), 8, False)
        self._label('T A L K Y', (52, 34, 70, 15), 8, True, self.INK)
        for y in (32, 38, 44):
            self._rect(root, (126, y, 47, 2), 'AE803D', 1)
        self.led = self._rect(root, (188, 34, 10, 10), 'E67E62', 5, self.INK, 1)
        self.face = Quartz.CALayer.layer()
        self.face.setFrame_(AppKit.NSMakeRect(86, 101, 88, 23))
        root.addSublayer_(self.face)
        self._eyes = []
        for origin in (14, 58):
            pixels = []
            for row in range(5):
                for column in range(5):
                    pixels.append(self._rect(self.face, (origin + column * 2, 9 + (4-row) * 2, 2, 2), self.PIXEL))
            self._eyes.append(pixels)
        self._mouth = []
        for row in range(4):
            for column in range(9):
                self._mouth.append(self._rect(self.face, (35 + column * 2, 1 + (3-row) * 2, 2, 2), self.PIXEL))
        self._cheeks = [self._rect(self.face, (x, 7, 6, 2), '6D9A58') for x in (4, 78)]
        self.bars = [self._rect(root, (91 + i * 7, 91, 4, 2), self.PIXEL) for i in range(11)]
        self._last_face = None

    @staticmethod
    def _rect(parent, rect, fill, radius=0, border=None, border_width=0):
        layer = Quartz.CALayer.layer()
        layer.setFrame_(AppKit.NSMakeRect(*rect))
        layer.setBackgroundColor_(color(fill))
        layer.setCornerRadius_(radius)
        if border:
            layer.setBorderColor_(color(border))
            layer.setBorderWidth_(border_width)
        parent.addSublayer_(layer)
        return layer

    def _label(self, text, rect, size, bold, ink=None):
        label = AppKit.NSTextField.labelWithString_(text)
        label.setFrame_(AppKit.NSMakeRect(*rect))
        label.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(
            size, AppKit.NSFontWeightBold if bold else AppKit.NSFontWeightMedium))
        label.setTextColor_(AppKit.NSColor.colorWithCGColor_(color(ink or self.PIXEL)))
        label.setAlignment_(AppKit.NSTextAlignmentCenter)
        label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
        self.view.addSubview_(label)
        return label

    def update(self, title, mode, text, badge):
        self._emotion = emotion_for(mode, text)
        short_title = {'Editing selection': 'VOICE EDIT', 'Checking destination': 'APPLYING',
                       'Getting ready': 'WAKING UP', 'Dictation complete': 'ALL DONE!',
                       'Edit complete': 'NICE EDIT!', 'Text inserted': 'ALL DONE!',
                       'Text ready': 'SAVED FOR YOU', 'Notice': 'NEED A HAND?'}.get(title, title)
        self.title.setStringValue_(short_title.upper())
        self.hint.setStringValue_(screen_hint(mode, text, badge))
        self.view.setAccessibilityLabel_(f'Talky, {self._emotion}. {text}')
        self.view.setToolTip_(text)

    def tick(self, mode, heights, now, reduced, age):
        active = mode in ('listening', 'editing', 'processing', 'meeting')
        blink = active and not reduced and now % 5.2 < .13
        glance = int(math.sin(now * 1.4) * 1.5) if mode == 'processing' and not reduced else 0
        faces = {
            'curious': ('01110/11011/11011/11111/01110', '100000001/010000010/001111100/000000000'),
            'focused': ('00000/11110/01110/01110/00100', '000000000/001111100/000000000/000000000'),
            'thinking': ('01110/11110/11110/11110/01110', '000000000/000111000/000000000/000000000'),
            'happy': ('00100/01010/10001/00000/00000', '100000001/110000011/011111110/001111100'),
            'concerned': ('00011/00110/01110/01110/00100', '000111000/001000100/000111000/000000000'),
            'attentive': ('01110/11011/11011/11111/01110', '000000000/001111100/000000000/000000000'),
            'calm': ('00000/00000/11111/00000/00000', '000000000/001111100/000000000/000000000'),
        }
        eyes, mouth = faces[self._emotion]
        if blink:
            eyes = '00000/00000/11111/00000/00000'
        signature = (eyes, mouth)
        if signature != self._last_face:
            for pixels in self._eyes:
                for pixel, bit in zip(pixels, eyes.replace('/', '')):
                    pixel.setHidden_(bit == '0')
            for pixel, bit in zip(self._mouth, mouth.replace('/', '')):
                pixel.setHidden_(bit == '0')
            self._last_face = signature
        self.face.setTransform_(Quartz.CATransform3DMakeTranslation(glance, 0, 0))
        wiggle = .035 * math.sin(now * 3) if active and not reduced else 0
        if mode == 'success' and not reduced and age < .75:
            wiggle = .08 * math.sin(age * 16) * (1 - age / .75)
        self.antenna.setTransform_(Quartz.CATransform3DMakeRotation(wiggle, 0, 0, 1))
        self.led.setBackgroundColor_(color('A2CF6E' if mode == 'success' else 'E67E62'))
        for bar, height in zip(self.bars, heights):
            h = max(2, round((height - 3) * .45 / 2) * 2 + 2)
            frame = bar.frame()
            bar.setFrame_(AppKit.NSMakeRect(frame.origin.x, 92 - h / 2, 4, h))
            bar.setHidden_(mode in ('success', 'notice'))
