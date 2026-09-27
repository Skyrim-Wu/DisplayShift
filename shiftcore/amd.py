"""AMD ADL2 DDC block transport for LG's nonstandard source address.

ABI reference: GPUOpen-LibrariesAndSDKs/display-library/include/adl_structures.h.
Only the installed system driver is loaded; no bundled driver or helper is needed.
"""
from __future__ import annotations

import ctypes as c
import time
from dataclasses import dataclass
from functools import reduce
from operator import xor


class AdapterInfo(c.Structure):
    _fields_ = [('size', c.c_int), ('index', c.c_int), ('udid', c.c_char * 256),
                ('bus', c.c_int), ('device', c.c_int), ('function', c.c_int),
                ('vendor', c.c_int), ('name', c.c_char * 256), ('gdi', c.c_char * 256),
                ('present', c.c_int), ('exist', c.c_int), ('driver', c.c_char * 256),
                ('driver_ext', c.c_char * 256), ('pnp', c.c_char * 256), ('os_index', c.c_int)]


class DisplayID(c.Structure):
    _fields_ = [('logical', c.c_int), ('physical', c.c_int),
                ('logical_adapter', c.c_int), ('physical_adapter', c.c_int)]


class DisplayInfo(c.Structure):
    _fields_ = [('id', DisplayID), ('controller', c.c_int), ('name', c.c_char * 256),
                ('manufacturer', c.c_char * 256), ('type', c.c_int),
                ('output', c.c_int), ('connector', c.c_int), ('mask', c.c_int),
                ('flags', c.c_int)]


@dataclass(frozen=True)
class Route:
    adapter: int
    display: int
    gdi: str
    name: str


def lg_packet(value: int) -> bytes:
    if not isinstance(value, int) or not 1 <= value <= 255:
        raise ValueError('LG 输入代码必须在 1–255 之间')
    # 0x50 is the DDC source byte, NOT the EDID I2C slave address.
    # DDCBlockAccess expects the destination byte (0x6e) in the full packet.
    data = bytes((0x6e, 0x50, 0x84, 0x03, 0xf4, 0, value))
    return data + bytes((reduce(xor, data),))


def match_route(routes, identifier, identifiers_for_gdi):
    matches = []
    for route in routes:
        # Clone/MST needs a finer identity mapping; never guess using list order/name.
        if sum(r.gdi.casefold() == route.gdi.casefold() for r in routes) != 1:
            continue
        ids = identifiers_for_gdi(route.gdi)
        if len(ids) == 1 and ids[0].casefold() == identifier.casefold():
            matches.append(route)
    if len(matches) != 1:
        raise RuntimeError('无法将 LG 唯一绑定到 AMD 输出；请重新检测并检查直连/MST/复制模式')
    return matches[0]


class AmdAdl:
    def __init__(self):
        try:
            # LOAD_LIBRARY_SEARCH_SYSTEM32 prevents loading a DLL from the working directory.
            self.dll = c.CDLL('atiadlxx.dll' if c.sizeof(c.c_void_p) == 8 else 'atiadlxy.dll',
                             winmode=0x800)
        except OSError as exc:
            raise RuntimeError('LG 专用协议需要 AMD 显卡及其 ADL 驱动；当前无法加载系统驱动') from exc
        self.crt = c.CDLL('msvcrt.dll', winmode=0x800)
        self.crt.malloc.argtypes = [c.c_size_t]
        self.crt.malloc.restype = c.c_void_p
        self.crt.free.argtypes = [c.c_void_p]
        self.crt.free.restype = None
        # ADL entry points are cdecl; the allocation callback is __stdcall.
        self.allocator = c.WINFUNCTYPE(c.c_void_p, c.c_int)(self.crt.malloc)
        self.context = c.c_void_p()
        definitions = [
            ('ADL2_Main_Control_Create', [type(self.allocator), c.c_int, c.POINTER(c.c_void_p)]),
            ('ADL2_Main_Control_Destroy', [c.c_void_p]),
            ('ADL2_Adapter_NumberOfAdapters_Get', [c.c_void_p, c.POINTER(c.c_int)]),
            ('ADL2_Adapter_AdapterInfo_Get', [c.c_void_p, c.POINTER(AdapterInfo), c.c_int]),
            ('ADL2_Display_DisplayInfo_Get', [c.c_void_p, c.c_int, c.POINTER(c.c_int),
                                            c.POINTER(c.POINTER(DisplayInfo)), c.c_int]),
            ('ADL2_Display_DDCBlockAccess_Get', [c.c_void_p, c.c_int, c.c_int, c.c_int,
                                               c.c_int, c.c_int, c.c_void_p,
                                               c.POINTER(c.c_int), c.c_void_p]),
        ]
        try:
            for name, args in definitions:
                function = getattr(self.dll, name)
                function.argtypes, function.restype = args, c.c_int
        except AttributeError as exc:
            raise RuntimeError('AMD 驱动缺少 ADL2 DDC 接口；请更新 AMD 驱动') from exc
        try:
            self.check(self.dll.ADL2_Main_Control_Create(self.allocator, 1, c.byref(self.context)), '初始化')
        except Exception:
            self.close()
            raise

    @staticmethod
    def check(code, action):
        if code != 0:
            raise RuntimeError(f'AMD ADL {action}失败（错误码 {code}）')

    def close(self):
        if self.context.value:
            self.dll.ADL2_Main_Control_Destroy(self.context)
            self.context = c.c_void_p()

    def routes(self):
        count = c.c_int()
        self.check(self.dll.ADL2_Adapter_NumberOfAdapters_Get(self.context, c.byref(count)), '枚举显卡')
        if not 0 < count.value <= 128:
            raise RuntimeError('AMD ADL 未返回有效显卡')
        adapters = (AdapterInfo * count.value)()
        for adapter in adapters:
            adapter.size = c.sizeof(AdapterInfo)
        self.check(self.dll.ADL2_Adapter_AdapterInfo_Get(self.context, adapters, c.sizeof(adapters)), '读取显卡')
        routes = []
        for adapter in adapters:
            if not adapter.present or not adapter.gdi:
                continue
            number, displays = c.c_int(), c.POINTER(DisplayInfo)()
            try:
                self.check(self.dll.ADL2_Display_DisplayInfo_Get(
                    self.context, adapter.index, c.byref(number), c.byref(displays), 0), '枚举输出')
                if not 0 <= number.value <= 128 or (number.value and not displays):
                    raise RuntimeError('AMD ADL 返回无效输出列表')
                for i in range(number.value):
                    display = displays[i]
                    if (display.mask & display.flags & 3) != 3:
                        continue
                    if display.id.logical_adapter != adapter.index:
                        continue
                    routes.append(Route(adapter.index, display.id.logical,
                                        adapter.gdi.decode('ascii'),
                                        display.name.decode('utf-8', errors='replace')))
            finally:
                if displays:
                    self.crt.free(c.cast(displays, c.c_void_p))
        return routes

    def write(self, route, value):
        packet = lg_packet(value)
        buffer = c.create_string_buffer(packet, len(packet))
        # Match m1ddc's two writes and the locally verified Windows sequence.
        # Use 50 ms spacing (m1ddc documents up to 50 ms for slower displays).
        for attempt in range(2):
            time.sleep(0.05)
            received = c.c_int(0)
            code = self.dll.ADL2_Display_DDCBlockAccess_Get(
                self.context, route.adapter, route.display, 0, 0, len(packet), buffer,
                c.byref(received), None)
            if code != 0:
                if attempt == 0:
                    self.check(code, '发送 LG 输入切换')
                # The first accepted write may disconnect this host. A failed
                # duplicate must not undo its "sent" status (still not verified).
                break
