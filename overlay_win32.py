"""Click-through, per-pixel transparent Windows crosshair overlay."""

import ctypes
from ctypes import wintypes as w
from PIL import Image, ImageDraw


class POINT(ctypes.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", w.LONG), ("cy", w.LONG)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
        ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD), ("biXPelsPerMeter", w.LONG),
        ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD), ("biClrImportant", w.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 1)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   w.HWND, w.HANDLE, w.HANDLE, ctypes.c_void_p]
user32.CreateWindowExW.restype = w.HWND
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, w.UINT]
user32.SetWindowPos.restype = w.BOOL
user32.UpdateLayeredWindow.argtypes = [w.HWND, w.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
                                       w.HDC, ctypes.POINTER(POINT), w.DWORD,
                                       ctypes.POINTER(BLENDFUNCTION), w.DWORD]
user32.UpdateLayeredWindow.restype = w.BOOL
user32.GetDC.argtypes = [w.HWND]
user32.GetDC.restype = w.HDC
user32.ReleaseDC.argtypes = [w.HWND, w.HDC]
user32.DestroyWindow.argtypes = [w.HWND]
gdi32.CreateCompatibleDC.argtypes = [w.HDC]
gdi32.CreateCompatibleDC.restype = w.HDC
gdi32.CreateDIBSection.argtypes = [w.HDC, ctypes.POINTER(BITMAPINFO), w.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD]
gdi32.CreateDIBSection.restype = w.HANDLE
gdi32.SelectObject.argtypes = [w.HDC, w.HANDLE]
gdi32.SelectObject.restype = w.HANDLE
gdi32.DeleteObject.argtypes = [w.HANDLE]
gdi32.DeleteDC.argtypes = [w.HDC]


class CrosshairOverlay:
    SIZE = 300

    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.hwnd = user32.CreateWindowExW(
            0x00080000 | 0x00000020 | 0x00000008 | 0x00000080 | 0x08000000,
            "Static", "Chibi Crosshair", 0x80000000,
            0, 0, self.SIZE, self.SIZE, None, None, None, None,
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

    def update(self, color, length, gap, thickness, opacity, dot, offset_x, offset_y):
        width = self.SIZE
        center = width // 2
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        alpha = max(0, min(255, round(int(opacity) * 255 / 100)))
        image = Image.new("RGBA", (width, width), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        gap, length, thickness = int(gap), int(length), int(thickness)
        segments = [
            (center - gap - length, center, center - gap, center),
            (center + gap, center, center + gap + length, center),
            (center, center - gap - length, center, center - gap),
            (center, center + gap, center, center + gap + length),
        ]
        for segment in segments:
            draw.line(segment, fill=(red, green, blue, alpha), width=thickness)
        if dot:
            radius = max(1, thickness // 2)
            draw.ellipse((center - radius, center - radius, center + radius, center + radius),
                         fill=(red, green, blue, alpha))

        # UpdateLayeredWindow expects premultiplied BGRA pixels.
        rgba = image.tobytes()
        bgra = bytearray(len(rgba))
        for pos in range(0, len(rgba), 4):
            r, g, b, a = rgba[pos:pos + 4]
            bgra[pos] = b * a // 255
            bgra[pos + 1] = g * a // 255
            bgra[pos + 2] = r * a // 255
            bgra[pos + 3] = a

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -width  # Top-down DIB.
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        bits = ctypes.c_void_p()
        screen_dc = user32.GetDC(None)
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bitmap = gdi32.CreateDIBSection(screen_dc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(None, screen_dc)
            raise ctypes.WinError(ctypes.get_last_error())
        previous = gdi32.SelectObject(memory_dc, bitmap)
        try:
            ctypes.memmove(bits, bytes(bgra), len(bgra))
            x = self.screen_width // 2 - center + int(offset_x)
            y = self.screen_height // 2 - center + int(offset_y)
            destination = POINT(x, y)
            source = POINT(0, 0)
            size = SIZE(width, width)
            blend = BLENDFUNCTION(0, 0, 255, 1)
            if not user32.UpdateLayeredWindow(self.hwnd, screen_dc, ctypes.byref(destination),
                                               ctypes.byref(size), memory_dc, ctypes.byref(source),
                                               0, ctypes.byref(blend), 2):
                raise ctypes.WinError(ctypes.get_last_error())
            if not user32.SetWindowPos(self.hwnd, w.HWND(-1), x, y, width, width,
                                       0x0010 | 0x0040):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            gdi32.SelectObject(memory_dc, previous)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(None, screen_dc)

    def close(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
