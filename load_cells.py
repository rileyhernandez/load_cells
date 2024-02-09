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
from viam.logging import getLogger
from viam.utils import ValueTypes

from Phidget22.Phidget import *
from Phidget22.Devices.VoltageRatioInput import *
import asyncio
import numpy as np

LOGGER = getLogger(__name__)

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
            sensor.cells[cell].setChannel(cell)
            sensor.cells[cell].openWaitForAttachment(1000)
            sensor.cells[cell].setDataInterval(sensor.cells[cell].getMinDataInterval())
        sensor.offset = 0
        sensor.coefficients = [1.05367982e+07, 5.58626571e+06, 1.22174287e+07, 1.08556060e+07, -2.24938354e+03]
        sensor.data = []
        return sensor
  
    async def do_command(self, command: Mapping[str, ValueTypes], *, timeout: float | None = None, **kwargs) -> Mapping[str, ValueTypes]:
        match command['command']:
            case 'tare':
                method = await self.tare()
            case 'calibrate':
                method = await self.calibrate()
            case 'live-weigh':
                method = await self.live_weigh()
            case 'weigh-until':
                method = await self.weigh_until(command['serving'])
        return method
        

    
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
        self.offset = await self.weigh()

    async def calibrate(self, test_mass=393.8):
        """Calibrates the load cell system to determine what its coefficients are in order to account for 
        load cell variation and assembly tolerance.
        Then the system is tared.
        """
        # Conducts weight trials and collects data
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
        # Conducts final trial (no weight)
        trial_readings = await self.get_cell_averages()
        trial_readings += [1]
        A += [trial_readings]
        b += [[0]]

        # Inputs trial data into matrices and solves 'Ax = b'
        A, b = np.array(A), np.array(b)
        x = np.linalg.solve(A, b)
        # Converts x into a list and saves it as an attribute
        x.reshape(1, -1).tolist()[0]
        self.coefficients = x

        # Tares scale and ends method
        await self.tare()
        return {'msg': 'successful'}
    
    async def live_weigh(self):
        """Measures instantaneous weight
        """
        # Collects instantaneous cell readings
        readings = await self.get_cell_readings()
        # Takes dot product of readings and coefficients to calculate 
        weight = sum([readings[reading]*self.coefficients[reading] for reading in range(len(readings))])
        # Returns weight minus offset (from tare)
        return weight-self.offset
    
    async def weigh(self, samples=100, sample_rate=25, outliers_removed=30):
        """Takes the average weight over a given time period, at a given sample rate, while removing outliers
        """
        # Collects weight measurement data over given sample period
        weights = []
        for sample in range(samples):
            reading = await self.live_weigh()
            weights += [reading]
            await asyncio.sleep(1/sample_rate)
        # Finds outliers in the data set
        outliers = []
        for outlier in range(outliers_removed//2):
            outliers += [max(weights), min(weights)]
        # Takes the average of the data set, removing outliers
        weight = (sum(weights)-sum(outliers))/(len(weights)-len(outliers))
        return weight
    
    async def weigh_until(self, serving, samples=100, sample_rate=25, outliers_removed=30):
        """Takes the pruned average weight over at given settings until the target is reached
        """
        def prune(lst, n):
            """Function that takes in a data set and a removes a given number of outliers.
            The average of the remaining data set is returned.
            """
            outliers = []
            for i in range(n):
                outliers += [max(lst), min(lst)]
            return (sum(lst)-sum(outliers))/(len(lst)-len(outliers))

        last_n = []
        curr_weight = await self.weigh()
        target = curr_weight-serving
        for sample in range(samples):
            reading = await self.live_weigh()
            last_n += [reading]
            await asyncio.sleep(1/sample_rate)
        while curr_weight > target:
            curr_weight = await self.live_weigh()
            last_n = last_n[1:] + [curr_weight]
            avg = prune(last_n, outliers_removed)
            asyncio.sleep(1/sample_rate)
        return 'Dispensed ' + str(serving) + ' g'

        
    

Registry.register_resource_creator(
    Sensor.SUBTYPE,
    LoadCell.MODEL,
    ResourceCreatorRegistration(LoadCell.new)
)
