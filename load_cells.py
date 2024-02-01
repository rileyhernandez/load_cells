from typing import ClassVar
from typing import Any, ClassVar, Mapping, Optional
from typing_extensions import Self

from viam.components.sensor import Sensor
from viam.module.types import Reconfigurable
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.components.sensor import Sensor

from Phidget22.Phidget import *
from Phidget22.Devices.VoltageRatioInput import *
import time, asyncio
import numpy as np

class LoadCell(Sensor):
    MODEL: ClassVar[Model] = Model(ModelFamily('test-bench', 'sensor'), 'load-cell')
    id: int

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        sensor = cls(config.name)
        sensor.id = int(config.attributes.fields['id'].number_value)
        # Phidget set up
        sensor.cells = [VoltageRatioInput() for cell in range(4)]
        for cell in range(len(sensor.cells)):
            sensor.cells[cell].setChannel()
            sensor.cells[cell].openWaitForAttachment(1000)
            sensor.cells[cell].setDataInterval(sensor.cells[cell].getMinDataInterval())
        sensor.offset = 0
        sensor.coefficients = np.array([[ 1.05367982e+07],
        [ 5.58626571e+06],
        [ 1.22174287e+07],
        [ 1.08556060e+07],
        [-2.24938354e+03]])
        return sensor
    
    async def get_readings(self, *, extra: Optional[Mapping[str, Any]] = None, timeout: Optional[float] = None,
                            **kwargs) -> Mapping[str, Any]:
        weight = await self.weigh()
        return {'weight': weight}
    
    async def get_cell_readings(self) -> list:
        readings = [cell.getVoltageRatio() for cell in self.cells]
        return readings

    async def get_cell_averages(self, samples=64, sample_rate=125) -> list:
        averages = [0 for cell in self.cells]
        for sample in range(samples):
            readings = await self.get_cell_readings()
            averages = [averages[cell]+readings[cell] for cell in readings]
            asyncio.sleep(1/sample_rate)
        averages = [average/samples for average in averages]
        return averages
    
    async def tare(self):
        """Tares the system by recalibrating the offset value
        """
        try:
            input('Clear scale and press Enter')
        except(Exception, KeyboardInterrupt):
            pass
        self.offset = await self.weigh()

    async def calibrate(self, test_mass=393.8):
        """Calibrates the load cell system to determine what its coefficients are in order to account for 
        load cell variation and assembly tolerance.
        Then the system is tared.
        """
        A, b = [], []
        for trial in range(len(self.cells)):
            try:
                input('Place/move test mass and press Enter')
            except(Exception, KeyboardInterrupt):
                pass
            trial_readings = await self.get_cell_averages()
            trial_readings += [1]
            A += [trial_readings]
            b += [[test_mass]]
        
        try:
            input('Remove test mass and press Enter')
        except(Exception, KeyboardInterrupt):
            pass
        trial_readings = await self.get_cell_averages()
        trial_readings += [1]
        A += [trial_readings]
        b += [[0]]

        A, b = np.array(A), np.array(b)
        x = np.linalg.solve(A, b)
        self.coefficients = x
        await self.tare()
    
    async def live_weigh(self):
        readings = await self.get_cell_readings()
        weights = [readings[reading]*self.coefficients for reading in range(len(readings))]
        return float(sum(weights)-self.offset)
    
    async def weigh(self, samples=100, sample_rate=25, outliers_removed=30):
        weights = []
        for sample in range(samples):
            reading = await self.live_weigh()
            weights += [reading]
            asyncio.sleep(1/sample_rate)
        outliers = []
        for outlier in range(outliers_removed//2):
            outliers += [max(weights), min(weights)]
        weight = (sum(weights)-sum(outliers))/(len(weights)-len(outliers))
        return weight
    

Registry.register_resource_creator(
    Sensor.SUBTYPE,
    LoadCell.MODEL,
    ResourceCreatorRegistration(LoadCell.new)
)