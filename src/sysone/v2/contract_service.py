"""Bounded-shape typed encoder results with fail-closed deadline publication.

This adapter enforces result types and refuses late successes. Python/Linux and
shared DDR still have no proven WCET: it does NOT guarantee host delivery time.
The isolated locality300 PL supervisor provides a distinct outcome-register
deadline, and is intentionally not admitted by the qualified SYS2 driver.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import hashlib
import math
import re
import threading
import time
from types import SimpleNamespace
from typing import Callable

from .timing_policy import TimingPolicy


class Outcome(str, Enum):
    ACCEPTED = 'accepted'
    CLARIFY = 'clarify'
    ABSTAIN = 'abstain'
    DEADLINE_EXCEEDED = 'deadline_exceeded'
    INVALID_INPUT = 'invalid_input'
    HARDWARE_FAULT = 'hardware_fault'


@dataclass(frozen=True)
class HeadType:
    name: str
    kind: str
    labels: tuple[str, ...]

    def __post_init__(self):
        if self.kind not in ('intent', 'slots', 'pair') or not _text(self.name, 128):
            raise ValueError('Unsupported head type/name')
        if (type(self.labels) is not tuple or not 1 <= len(self.labels) <= 4096
                or len(set(self.labels)) != len(self.labels)
                or any(not _text(v, 128) for v in self.labels)):
            raise ValueError('Expected bounded finite label enumeration')
        if not self.name.startswith(self.kind + '.'):
            raise ValueError('Head name does not match its output type')


def _text(value, limit):
    return type(value) is str and 0 < len(value.encode('utf-8')) <= limit


@dataclass(frozen=True)
class PredictionValue:
    head: str
    kind: str
    segment: int | None
    labels: tuple[str, ...]
    probabilities: tuple[float, ...]
    words: tuple[str, ...] | None


@dataclass(frozen=True)
class OutputSchema:
    heads: tuple[HeadType, ...]
    max_tokens: int = 128
    max_predictions: int = 32

    def __post_init__(self):
        if (type(self.heads) is not tuple or not 1 <= len(self.heads) <= 32
                or any(type(h) is not HeadType for h in self.heads)
                or len({h.name for h in self.heads}) != len(self.heads)
                or type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 128
                or type(self.max_predictions) is not int or not 1 <= self.max_predictions <= 128):
            raise ValueError('Invalid bounded output schema')

    @property
    def sha256(self):
        record = {'heads': [dict(name=h.name, kind=h.kind, labels=h.labels) for h in self.heads],
                  'max_tokens': self.max_tokens, 'max_predictions': self.max_predictions}
        return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
                                         ensure_ascii=True).encode('ascii')).hexdigest()

    @classmethod
    def from_manifest(cls, manifest, *, head_names):
        # Embeddings are continuous vectors, not finite intent/action labels.
        # Require an explicit head allowlist; never infer actuation authority.
        if type(head_names) is not tuple or not head_names or len(set(head_names)) != len(head_names):
            raise ValueError('Explicit unique head-name tuple required')
        available = {f"{h['kind']}.{h['name']}": h for h in manifest['heads'] if 'labels' in h}
        if any(name not in available for name in head_names):
            raise ValueError('Unknown or non-enumerated output head')
        if any(available[name]['classes'] != len(available[name]['labels']) for name in head_names):
            raise ValueError('Manifest label enumeration differs from class count')
        return cls(tuple(HeadType(name, available[name]['kind'], tuple(available[name]['labels']))
                         for name in head_names), max_tokens=manifest['dims']['max_tokens'])

    def validate(self, predictions) -> tuple[PredictionValue, ...]:
        if type(predictions) not in (list, tuple) or not 1 <= len(predictions) <= self.max_predictions:
            raise ValueError('Invalid output count')
        types = {h.name: h for h in self.heads}
        values = []
        seen = set()
        for p in predictions:
            h = types.get(p.head)
            if h is None:
                raise ValueError('Head not authorized by output schema')
            if h.kind == 'pair':
                if p.segment is not None:
                    raise ValueError('Pair result must not name a segment')
            elif type(p.segment) is not int or not 0 <= p.segment < self.max_tokens:
                raise ValueError('Invalid segment')
            key = (p.head, p.segment)
            if key in seen:
                raise ValueError('Duplicate result for head/segment')
            seen.add(key)
            if type(p.labels) not in (list, tuple) or type(p.probability) not in (list, tuple):
                raise ValueError('Expected bounded label and probability arrays')
            labels = tuple(p.labels)
            probabilities = tuple(p.probability)
            count = self.max_tokens if h.kind == 'slots' else 1
            if (not 1 <= len(labels) <= count or len(probabilities) != len(labels)
                    or any(type(v) is not str or v not in h.labels for v in labels)
                    or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                           for v in probabilities)):
                raise ValueError('Output is outside declared finite type')
            words = None
            if h.kind == 'slots':
                if (type(p.words) not in (list, tuple) or len(p.words) != len(labels)
                        or any(not _text(w, 128) for w in p.words)):
                    raise ValueError('Slot words/tags do not align')
                previous = None
                for label in labels:
                    if label == 'O':
                        previous = None
                    elif label.startswith('B-') and len(label) > 2:
                        previous = label[2:]
                    elif label.startswith('I-') and label[2:] == previous:
                        pass
                    else:
                        raise ValueError('Malformed BIO span; do not repair silently')
                words = tuple(p.words)
            elif p.words is not None:
                raise ValueError('Words belong only to slot outputs')
            values.append(PredictionValue(p.head, h.kind, p.segment, labels,
                                          tuple(float(v) for v in probabilities), words))
        return tuple(values)


@dataclass(frozen=True)
class TypedResult:
    outcome: Outcome
    model_sha256: str
    clock_hz: int
    request_cycles: int | None
    elapsed_ns: int
    payload: tuple[PredictionValue, ...] = ()
    reason: str = ''
    schema: OutputSchema | None = None
    contract_sha256: str | None = None

    def __post_init__(self):
        if type(self.outcome) is not Outcome or type(self.elapsed_ns) is not int or self.elapsed_ns < 0:
            raise ValueError('Invalid result outcome/time')
        if (type(self.model_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', self.model_sha256)
                or type(self.clock_hz) is not int or self.clock_hz <= 0
                or (self.request_cycles is not None and (type(self.request_cycles) is not int
                    or not 0 <= self.request_cycles < 1 << 32))
                or type(self.reason) is not str or len(self.reason.encode('utf-8')) > 128
                or type(self.payload) is not tuple):
            raise ValueError('Invalid identity, evidence or payload')
        if self.outcome is not Outcome.ACCEPTED and self.payload:
            raise ValueError('Failure/abstention cannot contain actionable payload')
        if self.outcome is Outcome.ACCEPTED:
            if type(self.schema) is not OutputSchema or not self.payload or self.request_cycles is None:
                raise ValueError('Accepted result requires a checked schema and timing evidence')
            if (type(self.contract_sha256) is not str
                    or not re.fullmatch('[0-9a-f]{64}', self.contract_sha256)):
                raise ValueError('Accepted result requires an identified admission contract')
            if any(type(p) is not PredictionValue for p in self.payload):
                raise ValueError('Invalid typed payload')
            if any(type(p.labels) is not tuple or type(p.probabilities) is not tuple
                   or (p.words is not None and type(p.words) is not tuple) for p in self.payload):
                raise ValueError('Accepted payload must be deeply immutable')
            self.schema.validate([SimpleNamespace(head=p.head, segment=p.segment, labels=p.labels,
                probability=p.probabilities, words=p.words) for p in self.payload])
            declared = {h.name: h.kind for h in self.schema.heads}
            if any(p.kind != declared[p.head] for p in self.payload):
                raise ValueError('Payload type differs from schema')

    def to_json(self):
        return json.dumps({
            'format': 'sysone.typed-encoder-result.v1', 'outcome': self.outcome.value,
            'model_sha256': self.model_sha256, 'clock_hz': self.clock_hz,
            'request_cycles': self.request_cycles, 'elapsed_ns': self.elapsed_ns,
            'payload': [dict(head=p.head, kind=p.kind, segment=p.segment, labels=p.labels,
                             probabilities=p.probabilities, words=p.words) for p in self.payload],
            'reason': self.reason, 'successful_completion_guaranteed': False,
            'host_delivery_guaranteed': False,
            'schema_sha256': self.schema.sha256 if self.schema is not None else None,
            'contract_sha256': self.contract_sha256,
            'timing_scope': 'encode_heads_validation_serialization',
            'semantic_correctness_guaranteed': False,
        }, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


class TypedEncoderService:
    """Admission → encode → trusted head callback → validate → deadline check.

    Bind this instance to the exact model hash of the encoder, never a caller's
    unverified filename. On timeout/fault it quarantines itself: no new request
    may reuse possibly outstanding hardware state. Recovery is external.
    """

    def __init__(self, encoder, schema: OutputSchema, policy: TimingPolicy, *, model_sha256,
                 clock_hz, monotonic_ns: Callable[[], int] = time.monotonic_ns):
        if type(clock_hz) is not int:
            raise ValueError('Integer fabric clock required')
        policy.admit(model_sha256, clock_hz, 1)
        if getattr(encoder, 'local', False):
            raise ValueError('CPU reference has no fabric cycle/clock evidence')
        link = getattr(encoder, 'link', None)
        if link is not None and getattr(link, 'clock_hz', None) != clock_hz:
            raise ValueError('Driver clock differs from admitted timing profile')
        if hashlib.sha256(encoder.machine.mem.buf).hexdigest() != model_sha256:
            raise ValueError('Encoder bytes differ from admitted model hash')
        self.vocab = encoder.machine.h['vocab']
        if (type(self.vocab) is not int or not 1 <= self.vocab <= 65536
                or policy.max_tokens > encoder.machine.h['max_tokens']):
            raise ValueError('Timing input profile exceeds model dimensions')
        if schema.max_tokens > policy.max_tokens:
            raise ValueError('Output schema exceeds timing input bound')
        self.encoder, self.schema, self.policy = encoder, schema, policy
        declaration = {**policy.metadata(), 'scope': 'encode_heads_validation_serialization',
                       'schema_sha256': schema.sha256}
        self.contract_sha256 = hashlib.sha256(json.dumps(declaration, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
        self.model_sha256, self.clock_hz = model_sha256, clock_hz
        self.now = monotonic_ns
        self.quarantined = False
        self.in_flight = False
        self._lock = threading.Lock()

    def run(self, ids, predict, *, decision: Outcome = Outcome.ACCEPTED, decide=None):
        start = self.now()
        cycles = None

        def result(outcome, reason='', payload=()):
            return TypedResult(outcome, self.model_sha256, self.clock_hz, cycles,
                               max(0, self.now()-start), payload, reason,
                               self.schema if outcome is Outcome.ACCEPTED else None,
                               self.contract_sha256)

        def expired():
            return self.now()-start > self.policy.host_request_budget_ms * 1_000_000

        if self.quarantined or self.in_flight:
            return result(Outcome.HARDWARE_FAULT, 'service_unavailable')
        if type(ids) not in (list, tuple) or any(type(v) is not int or not 0 <= v < self.vocab for v in ids):
            return result(Outcome.INVALID_INPUT, 'invalid_token_ids')
        try:
            self.policy.admit(self.model_sha256, self.clock_hz, len(ids))
        except ValueError:
            return result(Outcome.INVALID_INPUT, 'outside_admitted_profile')
        if type(decision) is not Outcome or decision not in (Outcome.ACCEPTED, Outcome.CLARIFY, Outcome.ABSTAIN):
            return result(Outcome.INVALID_INPUT, 'invalid_decision')
        if not self._lock.acquire(blocking=False):
            return result(Outcome.HARDWARE_FAULT, 'service_unavailable')
        if self.quarantined:
            self._lock.release()
            return result(Outcome.HARDWARE_FAULT, 'service_unavailable')
        self.in_flight = True
        try:
            encoded = self.encoder.encode(ids, timeout=self.policy.host_request_budget_ms / 1000)
            cycles = encoded.run.total_clocks
            if encoded.run.status:
                self.quarantined = True
                return result(Outcome.HARDWARE_FAULT, 'backend_status')
            if (type(cycles) is not int or not 0 <= cycles < 1 << 32
                    or cycles > self.policy.request_budget_cycles or expired()):
                self.quarantined = True
                return result(Outcome.DEADLINE_EXCEEDED, 'request_budget_exceeded')
            if decision is not Outcome.ACCEPTED:
                return result(decision, 'application_rejection')
            payload = self.schema.validate(predict(encoded.x))
            selected = Outcome.ACCEPTED if decide is None else decide(payload)
            if type(selected) is not Outcome or selected not in (Outcome.ACCEPTED, Outcome.CLARIFY, Outcome.ABSTAIN):
                raise ValueError('Invalid application decision')
            candidate = result(selected, '' if selected is Outcome.ACCEPTED else 'application_rejection',
                               payload if selected is Outcome.ACCEPTED else ())
            candidate.to_json()  # Bound shapes validated before serialization.
            finished = self.now()
            if finished-start > self.policy.host_request_budget_ms * 1_000_000:
                return result(Outcome.DEADLINE_EXCEEDED, 'head_validation_budget_exceeded')
            return replace(candidate, elapsed_ns=max(0, finished-start))
        except TimeoutError:
            self.quarantined = True
            return result(Outcome.DEADLINE_EXCEEDED, 'backend_timeout')
        except Exception:
            self.quarantined = True
            if type(cycles) is not int or not 0 <= cycles < 1 << 32:
                cycles = None
            return result(Outcome.HARDWARE_FAULT, 'backend_or_output_validation_failed')
        finally:
            self.in_flight = False
            self._lock.release()
