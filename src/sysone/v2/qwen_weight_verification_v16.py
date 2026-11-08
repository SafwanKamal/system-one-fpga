"""Full ordered SHA verification of sealed, read-only DMA mappings."""
import ctypes
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, wait
import hashlib
import mmap
import time


class PyBuffer(ctypes.Structure):
    _fields_ = [('buf', ctypes.c_void_p), ('obj', ctypes.c_void_p),
                ('len', ctypes.c_ssize_t), ('itemsize', ctypes.c_ssize_t),
                ('readonly', ctypes.c_int), ('ndim', ctypes.c_int),
                ('format', ctypes.c_char_p), ('shape', ctypes.POINTER(ctypes.c_ssize_t)),
                ('strides', ctypes.POINTER(ctypes.c_ssize_t)),
                ('suboffsets', ctypes.POINTER(ctypes.c_ssize_t)), ('internal', ctypes.c_void_p)]


def readonly_address(mapping, stack):
    # CPython's buffer API obtains a readable address without a writable export.
    get = ctypes.pythonapi.PyObject_GetBuffer
    get.argtypes = [ctypes.py_object, ctypes.POINTER(PyBuffer), ctypes.c_int]
    get.restype = ctypes.c_int
    release = ctypes.pythonapi.PyBuffer_Release
    release.argtypes = [ctypes.POINTER(PyBuffer)]
    release.restype = None
    buf = PyBuffer()
    get(mapping, ctypes.byref(buf), 0)
    stack.callback(release, ctypes.byref(buf))
    return buf.buf


def verify_weights(dmafd, manifest, header, regions):
    if header['model_bytes'] != manifest['bytes'] or header['chunk_bytes'] != 1 << 24 or header['segments'] != len(regions):
        raise RuntimeError('DMA model extent/layout mismatch')
    if len(regions) != (manifest['bytes'] + (1 << 24) - 1) // (1 << 24):
        raise RuntimeError('DMA segment count mismatch')
    started = time.monotonic()
    digest=hashlib.sha256();copied_bytes=0;chunk=4<<20
    # Four bounded buffers form a ring. Refill each consumed buffer
    # immediately, overlapping the next DMA read with ordered SHA.
    # All mappings outlive every native reader, including on failure.
    staging=[ctypes.create_string_buffer(chunk) for _ in range(4)]
    with ExitStack() as mappings, ThreadPoolExecutor(max_workers=4) as copies:
        plans=[]
        for index,region in enumerate(regions):
            payload=min(1<<24,manifest['bytes']-index*(1<<24))
            if region['index']!=index or not 0<payload<=region['bytes']:
                raise RuntimeError('Resident DMA segment coverage differs')
            view=mappings.enter_context(mmap.mmap(dmafd,region['bytes'],mmap.MAP_SHARED,mmap.PROT_READ,offset=index*(1<<24)))
            address=readonly_address(view, mappings)
            plans.extend((address+offset,min(chunk,payload-offset)) for offset in range(0,payload,chunk))
        def stage(index,slot):
            address,size=plans[index]
            return copies.submit(ctypes.memmove,ctypes.addressof(staging[slot]),address,size)
        pending=[stage(i,i) for i in range(min(4,len(plans)))]
        try:
            for index,(_,size) in enumerate(plans):
                slot=index%4;pending[slot].result()
                digest.update(memoryview(staging[slot]).cast('B')[:size]);copied_bytes+=size
                if index+4<len(plans):pending[slot]=stage(index+4,slot)
        finally:wait(pending)
    if copied_bytes!=manifest['bytes'] or digest.hexdigest()!=manifest['sha256']:
        raise RuntimeError('Resident DMA weights differ from pinned Q8 model')
    return dict(model_verify_ms=(time.monotonic()-started)*1000, verified_bytes=copied_bytes, resident_weights_verified=True, model_verify_method="resident_pipelined_native_copy_ordered_sha256")
