"""Memory subsystem."""

from .address_space import AddressSpace
from .segments import MemoryAccessError, MemorySegment, SegmentType

__all__ = ["AddressSpace", "MemoryAccessError", "MemorySegment", "SegmentType"]

