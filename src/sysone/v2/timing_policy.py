"""Request admission and measured deadline checks; no hard bound on shared DDR."""
from dataclasses import dataclass, asdict
import re
import math

def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)

@dataclass(frozen=True)
class TimingPolicy:
    image_sha256: str
    clock_hz: int
    max_tokens: int
    request_budget_cycles: int
    host_request_budget_ms: float

    def __post_init__(self):
        if not isinstance(self.image_sha256,str) or not re.fullmatch('[0-9a-f]{64}',self.image_sha256):
            raise ValueError('Exact image SHA256 required')
        if type(self.clock_hz) is not int or self.clock_hz<=0 or type(self.max_tokens) is not int or not 1<=self.max_tokens<=128:
            raise ValueError('Positive integer clock and 1..128 token profile required')
        if type(self.request_budget_cycles) is not int or not 0<self.request_budget_cycles<1<<32:
            raise ValueError('Request budget must fit the hardware cycle counter')
        if not _finite_number(self.host_request_budget_ms) or not 0<self.host_request_budget_ms<self.counter_wrap_ms:
            raise ValueError('Host budget must be positive and shorter than counter wrap')

    @property
    def counter_wrap_ms(self):
        return (1<<32)*1000/self.clock_hz

    def admit(self, image_sha256, clock_hz, tokens):
        if image_sha256!=self.image_sha256 or not _finite_number(clock_hz) or clock_hz!=self.clock_hz:
            raise ValueError('Model/clock differs from timing profile')
        if type(tokens) is not int or not 1<=tokens<=self.max_tokens:
            raise ValueError('Request outside timing profile')

    def assess(self, request_cycles, host_request_ms):
        if type(request_cycles) is not int or not 0<=request_cycles<1<<32 or not _finite_number(host_request_ms) or host_request_ms<0:
            raise ValueError('Invalid timing measurement')
        unambiguous = host_request_ms < self.counter_wrap_ms
        return {'board_budget_met':unambiguous and request_cycles<=self.request_budget_cycles,
                'host_request_budget_met':host_request_ms<=self.host_request_budget_ms,
                'counter_unambiguous':unambiguous,'hard_timing_guarantee':False,
                'scope':'request only; excludes model startup, CPU heads and output rendering'}

    def metadata(self):
        return {**asdict(self),'hard_timing_guarantee':False,
                'unbounded_components':['shared DDR service','Linux scheduling','MMIO bus response']}
