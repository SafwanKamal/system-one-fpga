"""Linux-only integration checks, runnable with stdlib unittest (no FPGA)."""
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/v2')]


def fake_session(package):
    from sysone.v2.qwen_arm_service_v15 import Session, COUNTERS
    from types import SimpleNamespace
    e = SimpleNamespace(context=1024, prefill_batch_size=8, manifest={'eos_ids':[99]},
                        clock_hz=125000000, memory_clock_hz=250000000,
                        command_timing={}, **dict.fromkeys(COUNTERS,0))
    e._r=lambda offset:4
    e.begin_prefix=lambda ids,enabled:None
    def prefill(ids,pos,logits):
        e.tokens+=len(ids)
        time.sleep(.03)
        return 1
    e.prefill_batch=prefill
    e.close=lambda:None
    v=SimpleNamespace(encode_text=lambda s:[7]*9,
                      piece=lambda t:b'["read_linux_file","/proc/uptime"]',close=lambda:None)
    return Session(e,v,lambda:dict(resident_weights_verified=True,verified_bytes=16),
                   lambda:None,lambda s:(json.loads(s),{'executed':True}))


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux mappings and Unix socket lifecycle')
class Integration(unittest.TestCase):
    def test_all_resident_bytes_and_tail_are_verified_and_corruption_rejected(self):
        from sysone.v2.qwen_weight_verification_v15 import verify_weights
        payload=os.urandom((20<<20)+37)
        model=dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
        header=dict(model_bytes=len(payload),chunk_bytes=1<<24,segments=2)
        tail=(len(payload)-(1<<24)+4095)//4096*4096
        regions=[dict(index=0,bytes=1<<24),dict(index=1,bytes=tail)]
        with tempfile.TemporaryFile() as f:
            f.write(payload);f.truncate((1<<24)+tail);f.flush()
            result=verify_weights(f.fileno(),model,header,regions)
            self.assertEqual(result['verified_bytes'],len(payload))
            f.seek(len(payload)-1);f.write(bytes([payload[-1]^1]));f.flush()
            with self.assertRaisesRegex(RuntimeError,'weights differ'):
                verify_weights(f.fileno(),model,header,regions)

    def test_socket_rejection_disconnect_serialization_shutdown_and_lock(self):
        from qwen_arm_service_v15 import serve,exchange
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);sock=root/'api.sock';ready=root/'ready.json';lock=root/'lock'
            p=multiprocessing.Process(target=serve,args=(root,sock,ready,str(lock),fake_session))
            p.start()
            try:
                deadline=time.monotonic()+5
                while not ready.exists():
                    self.assertTrue(p.is_alive())
                    if time.monotonic()>deadline:self.fail('Service startup timeout')
                    time.sleep(.01)
                self.assertEqual(sock.stat().st_mode & 0o777,0o600)
                self.assertEqual(exchange(sock,dict(op='health'))['state'],'READY')
                self.assertFalse(exchange(sock,dict(op='generate',query='x',max_tokens=0))['ok'])
                import fcntl
                with lock.open('a') as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
                request=dict(op='generate',query='Read /proc/uptime')
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                    client.connect(str(sock));client.sendall(json.dumps(request).encode()+b'\n')
                for _ in range(2):
                    result=exchange(sock,request)
                    self.assertTrue(result['ok'])
                    self.assertEqual(result['result']['work']['tokens'],9)
                self.assertTrue(exchange(sock,dict(op='shutdown'))['ok'])
                p.join(5)
                self.assertEqual(p.exitcode,0)
                self.assertFalse(sock.exists())
                with lock.open('a') as other:
                    fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:
                if p.is_alive():
                    p.terminate();p.join(5)  # Fake engine has no real in-flight hardware.


if __name__=='__main__':
    unittest.main()
