"""pymodbus 3.7 TCP server with 4 holding registers (unit 1), used as a target by plc_refusal_probe.py.

  python scripts/v2/gate/pymodbus_server.py [port]
"""
import sys

import pymodbus
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.server import StartTcpServer


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5022
    try:                                       # pymodbus 3.7
        from pymodbus.datastore import ModbusSlaveContext
        store = ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0] * 4), zero_mode=True)
        ctx = ModbusServerContext(slaves={1: store}, single=False)
    except ImportError:                        # pymodbus >= 3.10 renamed slave -> device; addresses are 0-based
        from pymodbus.datastore import ModbusDeviceContext
        store = ModbusDeviceContext(hr=ModbusSequentialDataBlock(1, [0] * 4))
        ctx = ModbusServerContext(devices={1: store}, single=False)
    print(f"pymodbus {pymodbus.__version__} server on {port}", flush=True)
    StartTcpServer(context=ctx, address=("127.0.0.1", port))


if __name__ == "__main__":
    main()
