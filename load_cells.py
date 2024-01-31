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
import time

class LoadCell(Sensor):
    MODEL: ClassVar[Model] = Model(ModelFamily('test-bench', 'sensor'), 'load-cell')
    id: int

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        sensor = cls(config.name)
        sensor.id = int(config.attributes.fields['id'].number_value)
        # Phidget set up
        sensor.channel = int(config.attributes.fields['channel'].number_value)
        sensor.input = VoltageRatioInput()
        sensor.input.setChannel(sensor.channel)
        sensor.input.openWaitForAttachment(1000)
        sensor.input.setDataInterval(sensor.input.getMinDataInterval())
        return sensor
    
    async def get_readings(self, *, extra: Optional[Mapping[str, Any]] = None, timeout: Optional[float] = None,
                            **kwargs) -> Mapping[str, Any]:
        reading = self.input.getVoltageRatio()
        return {'reading': reading}
    

Registry.register_resource_creator(
    Sensor.SUBTYPE,
    LoadCell.MODEL,
    ResourceCreatorRegistration(LoadCell.new)
)