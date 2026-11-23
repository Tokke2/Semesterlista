"""Pure display preferences and WCAG relative-luminance contrast calculation."""
import re


def contrast_ratio(first, second='#FFFFFF'):
    def luminance(value):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Expected #RRGGBB')
        channels = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def text_scale(value):
    try:
        return max(100, min(200, int(value))) / 100
    except (ValueError, TypeError):
        return 1.0
