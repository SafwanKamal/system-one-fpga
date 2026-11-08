"""Persistent local consolidated v9e service and CLI client. No automatic hardware recovery."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from sysone.v2.qwen_arm_service_candidate import hardware_session, validate_request

MAX_MESSAGE = 131072


def exchange(path, request, timeout=600):
    started = time.monotonic()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall(json.dumps(request).encode()+b'\n')
        with sock.makefile('rb') as stream:
            line = stream.readline(MAX_MESSAGE+1)
    if len(line) > MAX_MESSAGE or not line.endswith(b'\n'):
        raise RuntimeError('Invalid response framing')
    response = json.loads(line)
    response['client_seconds'] = time.monotonic()-started
    return response


def serve(package, path, ready, lock_path='/run/lock/sysone-inference.lock', factory=hardware_session, verification='startup', prefix_cache=True):
    import fcntl
    started = time.monotonic()
    # Refuse to unlink any pre-existing socket/file: it may belong to another owner.
    if path.exists():
        raise RuntimeError('Socket path already exists; reconcile its owner first')
    lock = Path(lock_path).open('a')
    session = None
    stopping = False
    server = None
    def stop(signum=None, frame=None):
        nonlocal stopping
        stopping = True
    old_handlers = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session = factory(package, verification=verification, prefix_cache=prefix_cache)
        startup = time.monotonic()-started
        class Handler(socketserver.StreamRequestHandler):
            timeout = 5
            def handle(self):
                nonlocal stopping
                try:
                    line = self.rfile.readline(MAX_MESSAGE+1)
                    if len(line) > MAX_MESSAGE or not line.endswith(b'\n'):
                        raise ValueError('Invalid request framing')
                    req = json.loads(line)
                    validate_request(req)
                    if stopping and req['op'] == 'generate':
                        raise RuntimeError('Service is draining')
                    if req['op'] == 'generate':
                        result = session.generate(req)
                        response = dict(ok=True, result=result)
                    elif req['op'] == 'reset-cache':
                        session.cache.reset()
                        response = dict(ok=True, state=session.state, prefix_tokens_reused=0)
                    elif req['op'] == 'health':
                        response = dict(ok=True, state=session.state, startup_seconds=startup,
                                        verification=session.verification, prefix_cache=session.prefix_cache,
                                        startup_proof=session.startup_proof)
                    else:
                        # Never voluntarily drop ownership of uncertain in-flight work.
                        if not session.engine._r(0) & 4:
                            raise RuntimeError('Hardware not idle; shutdown refused')
                        stopping = True
                        response = dict(ok=True, state='DRAINING')
                except Exception as exc:
                    response = dict(ok=False, state=session.state,
                                    error=type(exc).__name__+': '+str(exc))
                    if session.state == 'FAULTED':
                        response['result'] = getattr(session, 'last_result', {})
                try:
                    self.wfile.write(json.dumps(response).encode()+b'\n')
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Generation completed before attempting delivery.
        server = socketserver.UnixStreamServer(str(path), Handler)
        os.chmod(path, 0o600)
        server.timeout = .5
        info = dict(pid=os.getpid(), socket=str(path), package=str(package),
                    startup_seconds=startup, verification=session.verification, prefix_cache=session.prefix_cache,
                    startup_proof=session.startup_proof)
        ready.write_text(json.dumps(info, indent=2)+'\n')
        print(json.dumps(dict(event='ready', **info)), flush=True)
        while True:
            if stopping:
                if session.engine._r(0) & 4:
                    break
                session.state = 'FAULTED'  # Keep ownership until hardware is quiescent.
            server.handle_request()
    finally:
        if server is not None:
            server.server_close()
            path.unlink(missing_ok=True)
        if session is not None:
            session.close()
        lock.close()
        for s, handler in old_handlers.items():
            signal.signal(s, handler)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='mode', required=True)
    server = sub.add_parser('serve')
    server.add_argument('--package', type=Path, required=True)
    server.add_argument('--socket', type=Path, required=True)
    server.add_argument('--ready', type=Path, required=True)
    server.add_argument('--verification', choices=['startup', 'per-request'], default='startup')
    server.add_argument('--no-prefix-cache', action='store_true')
    client = sub.add_parser('request')
    client.add_argument('--socket', type=Path, required=True)
    client.add_argument('--op', choices=['generate', 'health', 'shutdown', 'reset-cache'], default='generate')
    client.add_argument('--query')
    client.add_argument('--conversation-id', default='default')
    client.add_argument('--reset-cache', action='store_true')
    client.add_argument('--max-tokens', type=int, default=64)
    client.add_argument('--out', type=Path)
    args = ap.parse_args()
    if args.mode == 'serve':
        serve(args.package, args.socket, args.ready, verification=args.verification,
              prefix_cache=not args.no_prefix_cache)
        return
    req = dict(op=args.op)
    if args.op == 'generate':
        req.update(query=args.query, max_tokens=args.max_tokens, conversation_id=args.conversation_id,
                   reset_cache=args.reset_cache)
    validate_request(req)
    response = exchange(args.socket, req)
    text = json.dumps(response, indent=2)+'\n'
    if args.out:
        args.out.write_text(text)
    print(text, end='')
    if not response['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
