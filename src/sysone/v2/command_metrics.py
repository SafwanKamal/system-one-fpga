"""Host process memory observation, distinct from deployment requirements."""
import os


def process_memory():
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
            (n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize',
            'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    fn=kernel.K32GetProcessMemoryInfo
    fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    fn.restype=wintypes.BOOL
    c=Counters()
    c.cb=ctypes.sizeof(c)
    if not fn(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return dict(working_set_bytes=c.WorkingSetSize,peak_working_set_bytes=c.PeakWorkingSetSize,
                private_commit_bytes=c.PrivateUsage,peak_commit_bytes=c.PeakPagefileUsage,
                scope='whole host process; includes framework/training, not board allocation')
