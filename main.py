import asyncio
import sys

from viam.components.sensor.sensor import Sensor
from viam.components.motor.motor import Motor
from viam.module.module import Module
from load_cells import LoadCell
from STF06_IP import STF06IP

async def main(address: str):
    m = Module(address)
    m.add_model_from_registry(Sensor.SUBTYPE, LoadCell.MODEL)
    m.add_model_from_registry(Motor.SUBTYPE, STF06IP.MODEL)
    await m.start()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise Exception('need socket path as command line argument')
    asyncio.run(main(sys.argv[1]))