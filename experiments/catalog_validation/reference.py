"""Run unmodified upstream examples, with Windows resource monitoring adapter."""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
from importlib.metadata import distributions
import io
from pathlib import Path
import runpy
import subprocess
import sys
import types

import study as s


def windows_resource():
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ['PeakWorkingSetSize', 'WorkingSetSize',
            'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage']]
    def usage(_):
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32; kernel.GetCurrentProcess.restype = ctypes.c_void_p
        function = ctypes.windll.psapi.GetProcessMemoryInfo
        function.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), wintypes.DWORD]
        assert function(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return types.SimpleNamespace(ru_maxrss=counters.PeakWorkingSetSize/1024)
    module = types.ModuleType('resource'); module.RUSAGE_SELF = 0; module.getrusage = usage
    return module


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--example', default='multistep_refined_demo.py')
    args = parser.parse_args()
    reference = s.WORK/'reference'; library = s.WORK/'immrax'
    # The Windows shim affects only upstream memory reporting, never arithmetic.
    if sys.platform == 'win32': sys.modules['resource'] = windows_resource()
    path = reference/'unicycle'/args.example
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream): runpy.run_path(str(path), run_name='__main__')
    output = stream.getvalue(); print(output)
    target = s.OUT/'reference'; target.mkdir(parents=True, exist_ok=True)
    (target/(path.stem+'.txt')).write_text(output)
    s.dump(target/(path.stem+'.json'), dict(completed_utc=s.utc(), example=args.example,
        reference_commit=subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip(),
        immrax_commit=subprocess.check_output(['git','-C',str(library),'rev-parse','HEAD'],text=True).strip(),
        upstream_source_sha256=s.sha(path), arithmetic_source_sha256=s.sha(reference/'unicycle/car_separating_input.py'),
        source_unmodified=not bool(subprocess.check_output(['git','-C',str(reference),'status','--porcelain'],text=True).strip()),
        windows_resource_monitor_adapter=sys.platform == 'win32',
        packages=sorted(f'{d.metadata["Name"]}=={d.version}' for d in distributions())))
