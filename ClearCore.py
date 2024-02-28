from typing import Any, ClassVar, Dict, Mapping, Optional, Tuple, Sequence
from typing_extensions import Self
from viam.components.motor.motor import Motor
from viam.module.types import Reconfigurable
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from tcp_client import tcp_write
from viam.utils import ValueTypes
from viam.logging import getLogger

LOGGER = getLogger(__name__)

# header, cr updated
HEADER = '\x02M0'
CR = '\x13'
DRIVE_TCP_PORT = 7776


class ClearCore(Motor, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily('test-bench', 'motor'), 'clear-core')
    id: int
    steps: int
    max_current: int
    last_pos: float
    ip_address: str

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        motor = cls(config.name)
        motor.id = config.attributes.fields['id'].number_value
        motor.ip_address = config.attributes.fields['ip_address'].string_value
        motor.steps = int(config.attributes.fields['steps'].number_value)
        motor.max_current = int(config.attributes.fields["max_current"].number_value)
        motor.last_pos = 0.0
        if dependencies:
            print(f"{dependencies}")
        return motor

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        self.ip_address = config.attributes.fields['ip_address'].string_value
        self.steps = int(config.attributes.fields['steps'].number_value)
        self.max_current = int(config.attributes.fields["max_current"].number_value)

    async def drive_write(self, cmd, amt:str='') -> str:
        """ ??? Reply format '\x00\x05XX=986\r
        """
        message = HEADER + cmd + str(amt) + CR
        resp = await tcp_write(self.ip_address, DRIVE_TCP_PORT, message)
        print(resp)
        if resp is None or resp[2] == '?':
            raise Exception('Invalid message sent to drive: ' + message + 'Resp: ' + resp)
        return resp[5:-1]

    async def set_power(self, power: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None,
                        **kwargs):
        # updated
        await self.drive_write('EN', power)

    async def go_for(self, rpm: float, revolutions: float, *, extra: Optional[Dict[str, Any]] = None,
                     timeout: Optional[float] = None, **kwargs):
        # updated
        await self.change_speed(rpm)
        await self.drive_write('RM', revolutions)
    
    async def go_to(self, rpm: float, position_revolutions: float, *, extra: Optional[Dict[str, Any]] = None,
                    timeout: Optional[float] = None, **kwargs):
        # updated
        await self.change_speed(rpm)
        await self.drive_write('AM', self.steps*position_revolutions)
    
    async def stop(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        await self.drive_write('ST')

    # async def do_command(self, command: Mapping[str, ValueTypes], *, timeout: float | None = None, **kwargs) -> Mapping[str, ValueTypes]:
    #     msg = {'msg': 'filler'}
    #     match command['command']:
    #         case 'test':
    #             await self.stop()
    #             await self.go_for(200, 20)
    #         case "change-speed":
    #             await self.change_speed(command["rpm"])
    #             msg = {"rpm.": command["rpm"]}
    #     return msg

    async def get_properties(self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None,
                             **kwargs) -> Motor.Properties:
        return Motor.Properties(True)

    async def is_powered(self,
                         *,
                         extra: Optional[Dict[str, Any]] = None,
                         timeout: Optional[float] = None,
                         **kwargs) -> Tuple[bool, float]:
        resp = await self.drive_write(f'SC')
        state = int(resp, 16) & 0x01
        resp = await self.drive_write(f'CC')
        power = self.max_current
        return bool(state), power

    async def is_moving(self) -> bool:
        resp = await self.drive_write(f'SC')
        return bool(int(resp, 16) & 0x10)
    
    '''Helpers
    '''
    async def change_speed(self, rpm: float, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs):
        await self.drive_write(f'RV{round(rpm/60, 2)}')
        return rpm


Registry.register_resource_creator(
    Motor.SUBTYPE,
    ClearCore.MODEL,
    ResourceCreatorRegistration(ClearCore.new)
)