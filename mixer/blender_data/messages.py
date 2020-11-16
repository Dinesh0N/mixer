# GPLv3 License
#
# Copyright (C) 2020 Ubisoft
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Definition of messages used by the full Blender protocol

Currently used only in tests. Could be used also in all send_xxx() and build_xxx() functions
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import traceback
from typing import List, Optional, TYPE_CHECKING, Union

from mixer.codec import Message
from mixer.blender_data.types import Soa

from mixer.broadcaster.common import (
    decode_int,
    decode_py_array,
    decode_string,
    encode_int,
    encode_py_array,
    encode_string,
)

if TYPE_CHECKING:
    from mixer.blender_data.datablock_proxy import DatablockProxy

logger = logging.getLogger(__name__)


def soa_buffers(datablock_proxy: Optional[DatablockProxy]) -> List[bytes]:
    if datablock_proxy is None:
        # empty update, should not happen
        return [encode_int(0)]

    # Layout is
    #   number of AosProxy: 2
    #       soa path in datablock : ("vertices")
    #       number of SoaElement : 2
    #           element name: "co"
    #           array
    #           element name: "normals"
    #           array
    #       soa path in datablock : ("edges")
    #       number of SoaElement : 1
    #           element name: "vertices"
    #           array

    items: List[bytes] = []
    items.append(encode_int(len(datablock_proxy._soas)))
    for path, soa_proxies in datablock_proxy._soas.items():
        path_string = json.dumps(path)
        items.append(encode_string(path_string))
        items.append(encode_int(len(soa_proxies)))
        for element_name, soa_element in soa_proxies:
            if soa_element._array is not None:
                items.append(encode_string(element_name))
                items.append(encode_py_array(soa_element._array))
    return items


def _decode_soas(buffer: bytes) -> List[Soa]:
    path: List[Union[int, str]] = ["unknown"]
    name = "unknown"
    soas: List[Soa] = []
    try:
        # see soa_buffers()
        aos_count, index = decode_int(buffer, 0)
        for _ in range(aos_count):
            path_string, index = decode_string(buffer, index)
            path = json.loads(path_string)

            logger.info("%s: %s ", "build_soa", path)

            element_count, index = decode_int(buffer, index)
            members = []
            for _ in range(element_count):
                name, index = decode_string(buffer, index)
                array_, index = decode_py_array(buffer, index)
                members.append(
                    (name, array_),
                )
            soas.append(
                Soa(path, members),
            )
    except Exception:
        logger.error(f"Exception while decoding for {path} {name}")
        for line in traceback.format_exc().splitlines():
            logger.error(line)
        logger.error("ignored")
        return []

    return soas


class BlenderCreateMessage:
    def __init__(self):
        self.proxy_string: str = ""
        self.soas: List[Soa] = []

    def __lt__(self, other):
        if self.proxy_string < other.proxy_string:
            # guaranteed to contain a uuid and be unique
            return True

    def decode(self, buffer: bytes):
        self.proxy_string, index = decode_string(buffer, 0)
        self.soas = _decode_soas(buffer[index:])

    @staticmethod
    def encode(datablock_proxy: DatablockProxy, encoded_proxy: str) -> bytes:
        items = []
        items.append(encode_string(encoded_proxy))
        items.extend(soa_buffers(datablock_proxy))
        return b"".join(items)


@dataclass(order=True)
class BlenderUpdateMessage(Message):
    proxy_string: str


@dataclass(order=True)
class BlenderRemoveMessage(Message):
    uuid: str
    debug_info: str


@dataclass(order=True)
class BlenderRenameMessage(Message):
    uuid: str
    new_name: str
    debug_info: str
