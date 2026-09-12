"""Windows: `iphlpapi.dll` (`IcmpSendEcho`) を用いた ICMP echo 実装.

このモジュールは Windows 上でのみ import 可能(`ctypes.WinDLL` が他OSでは
存在しないため)。ディスパッチ側 (`common.ping.ping_async`) は Windows判定後に
のみこのモジュールを import するため、Linux上でこのモジュールが誤って
importされることはない。

`argtypes`/`restype` は全関数で明示的に宣言する。ctypesはこれを省略すると
戻り値を32bit `c_int` として扱うため、`IcmpCreateFile` が返す64bit `HANDLE`
(x64環境でのポインタサイズ値)を暗黙に切り詰めてしまう、意図しない型変換が
発生しうる。これを避けるため全て明示する。

`tools/mping` で実装し、ユーザー環境(Windows 11, nitro5-skull)での実機実行
(`mping 8.8.8.8`等)により正常動作(RTT表示・CSVログ出力とも正常)を確認済みの
実装を、`common.ping.base`への参照に切り替えた上でそのまま移植したもの
(移植元: `mping/ping/windows.py`)。**import先の変更以外はロジック無変更だが、
移植後の`common.ping`経由での実機再確認はまだ行っていない点に注意。**
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import socket
import struct
import time
from dataclasses import dataclass

from common.ping.base import (
    CODE_NONE,
    ICMP_TYPE_ECHO_REPLY,
    TYPE_NO_REPLY,
    TYPE_UNKNOWN_ERROR,
    PingResult,
    ip_status_to_icmp,
)

IP_STATUS_SUCCESS = 0
IP_STATUS_REQ_TIMED_OUT = 11010
IP_FLAG_DF = 0x02

_iphlpapi = ctypes.WinDLL("iphlpapi.dll")
_ws2_32 = ctypes.WinDLL("ws2_32.dll")
_kernel32 = ctypes.WinDLL("kernel32.dll")


class IPOptionInformation(ctypes.Structure):
    _fields_ = [
        ("Ttl", ctypes.c_ubyte),
        ("Tos", ctypes.c_ubyte),
        ("Flags", ctypes.c_ubyte),
        ("OptionsSize", ctypes.c_ubyte),
        ("OptionsData", ctypes.c_char_p),
    ]


class IcmpEchoReply(ctypes.Structure):
    _fields_ = [
        ("Address", wintypes.ULONG),
        ("Status", wintypes.ULONG),
        ("RoundTripTime", wintypes.ULONG),
        ("DataSize", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("Data", ctypes.c_void_p),
        ("Options", IPOptionInformation),
    ]


# --- 呼び出す各Win32 APIの argtypes/restype を明示的に宣言 ---

_iphlpapi.IcmpCreateFile.argtypes = []
_iphlpapi.IcmpCreateFile.restype = ctypes.c_void_p

_iphlpapi.IcmpCloseHandle.argtypes = [ctypes.c_void_p]
_iphlpapi.IcmpCloseHandle.restype = ctypes.c_int

_iphlpapi.IcmpSendEcho.argtypes = [
    ctypes.c_void_p,  # IcmpHandle
    ctypes.c_uint32,  # DestinationAddress (IPAddr = ULONG)
    ctypes.c_void_p,  # RequestData
    ctypes.c_uint16,  # RequestSize (WORD)
    ctypes.POINTER(IPOptionInformation),  # RequestOptions (NULL可)
    ctypes.c_void_p,  # ReplyBuffer
    ctypes.c_uint32,  # ReplySize (DWORD)
    ctypes.c_uint32,  # Timeout (DWORD, ミリ秒)
]
_iphlpapi.IcmpSendEcho.restype = ctypes.c_uint32

_ws2_32.inet_addr.argtypes = [ctypes.c_char_p]
_ws2_32.inet_addr.restype = ctypes.c_uint32

_kernel32.GetLastError.argtypes = []
_kernel32.GetLastError.restype = ctypes.c_uint32

# HANDLE(c_void_p)は失敗時 INVALID_HANDLE_VALUE ((HANDLE)-1) を返す。
# ctypesのrestype=c_void_pはNULL(0)をNoneとして返すため、INVALID_HANDLE_VALUEは
# 「ポインタサイズいっぱいのビットパターン」の整数として比較する必要がある。
_INVALID_HANDLE_VALUE = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1

INADDR_NONE = 0xFFFFFFFF


@dataclass
class WindowsPingConfig:
    ttl: int
    timeout_ms: int
    data_size: int
    df: bool


def _open_handle() -> int:
    handle = _iphlpapi.IcmpCreateFile()
    if handle is None or handle == 0 or handle == _INVALID_HANDLE_VALUE:
        last_error = _kernel32.GetLastError()
        raise OSError(f"IcmpCreateFile に失敗しました (GetLastError={last_error})")
    return handle


def _addr_to_str(addr: int) -> str:
    """`inet_addr`と同じ生の32bit値表現を、逆変換でドット付き十進表記に戻す."""
    return socket.inet_ntoa(struct.pack("<L", addr))


def ping_once(dst_ip: str, config: WindowsPingConfig) -> PingResult:
    """指定した宛先IPに対して1回 ICMP echo を送信する(同期・ブロッキング).

    非同期実行は呼び出し側 (`common.ping.ping_async`) が `asyncio.to_thread` で
    スレッドオフロードする前提で、ここでは同期APIとして実装する。
    """
    handle = _open_handle()
    try:
        dest_addr = _ws2_32.inet_addr(dst_ip.encode("ascii"))
        if dest_addr == INADDR_NONE:
            return PingResult(
                ok=False,
                rtt=None,
                icmp_type=TYPE_UNKNOWN_ERROR,
                icmp_code=CODE_NONE,
                reply_from=None,
                message=f"inet_addr failed for {dst_ip!r} (不正なIPv4アドレス文字列)",
            )

        request_data = b"\x61" * max(config.data_size, 0)  # 'a' 埋め (オリジナル踏襲)

        options = IPOptionInformation(
            Ttl=config.ttl,
            Tos=0,
            Flags=IP_FLAG_DF if config.df else 0,
            OptionsSize=0,
            OptionsData=None,
        )

        reply_size = ctypes.sizeof(IcmpEchoReply) + len(request_data) + 8
        reply_buffer = ctypes.create_string_buffer(reply_size)

        start = time.monotonic()
        ret = _iphlpapi.IcmpSendEcho(
            handle,
            dest_addr,
            request_data,
            len(request_data),
            ctypes.byref(options),
            reply_buffer,
            reply_size,
            config.timeout_ms,
        )
        elapsed_fallback = time.monotonic() - start

        if ret == 0:
            # 送信自体が失敗 (ルートなし等)。実ICMP応答は無いため疑似type/codeを使う。
            last_error = _kernel32.GetLastError()
            return PingResult(
                ok=False,
                rtt=None,
                icmp_type=TYPE_UNKNOWN_ERROR,
                icmp_code=CODE_NONE,
                reply_from=None,
                message=f"IcmpSendEcho failed (GetLastError={last_error})",
            )

        reply = ctypes.cast(reply_buffer, ctypes.POINTER(IcmpEchoReply)).contents
        status = reply.Status
        reply_from = _addr_to_str(reply.Address) if reply.Address else None

        if status == IP_STATUS_SUCCESS:
            rtt = reply.RoundTripTime / 1000.0
            return PingResult(
                ok=True, rtt=rtt, icmp_type=ICMP_TYPE_ECHO_REPLY, icmp_code=0, reply_from=reply_from
            )

        if status == IP_STATUS_REQ_TIMED_OUT:
            # 純粋なタイムアウト(応答を一切受信できなかった)。実ICMP応答は無いため
            # 疑似type/code(TYPE_NO_REPLY)で埋める。応答者も存在しないためreply_from=None。
            return PingResult(
                ok=False, rtt=None, icmp_type=TYPE_NO_REPLY, icmp_code=CODE_NONE, reply_from=None, message="timeout"
            )

        # タイムアウト以外の応答(到達不能・TTL超過等)は、オリジナル実装同様
        # 実応答があった場合のRTTとして扱う。reply_fromは中継ルータ等、実際に
        # 応答したホストのアドレス(宛先そのものとは限らない)。
        icmp_type, icmp_code = ip_status_to_icmp(status)
        if icmp_type is None:
            # 変換表に無い IP_STATUS (未知のエラー種別)。
            icmp_type, icmp_code = TYPE_UNKNOWN_ERROR, CODE_NONE
        rtt = reply.RoundTripTime / 1000.0 if reply.RoundTripTime else elapsed_fallback
        return PingResult(
            ok=False,
            rtt=rtt,
            icmp_type=icmp_type,
            icmp_code=icmp_code,
            reply_from=reply_from,
            message=f"IP_STATUS={status}",
        )
    finally:
        _iphlpapi.IcmpCloseHandle(handle)
