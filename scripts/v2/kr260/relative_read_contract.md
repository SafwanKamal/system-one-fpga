# Experimental high-DDR read descriptor contract

`relative_read_request.sv` is a standalone adapter, not part of the deployed
SYS2 executor or the frozen dot7 project. It composes the registered SYS3
address-window translator with an explicit finite-width beat-count check.

Input: aligned 40-bit physical model base, 1..4GiB window size, unsigned 32-bit
relative offset and positive aligned 33-bit byte length. The translated tuple
is captured on input valid/ready and stays stable through backpressure even if
model configuration changes. Range/alignment/40-bit overflow errors complete
on the separate error valid/ready channel (code 1). Transfers too long for the
memory-port descriptor complete with code 2. Neither error asserts memory valid.
Reset drops pending descriptors and suppresses input/memory/error handshakes.

With the current 16-bit beat-count memory port, one descriptor is at most
65535 beats = 1048560 bytes. A 1048576-byte request must not silently truncate
to zero beats. `MemoryWindow.request_descriptors` lazily chunks larger transfers
into relative offset/byte-length descriptors matching this limit. It can cover
a full 4GiB window in 4097 requests without allocating the model or all bursts.
The downstream AXI port still owns <=256-beat and physical 4KiB page splitting;
this adapter is not an AXI transaction generator or response/error aggregator.

Focused simulations cover high addresses, last-beat/end-of-window cases,
exact/excess beat capacity, misalignment, zero length, 40-bit overflow, changed
configuration under stalls, reset/restart and 256 back-to-back descriptors
alternating valid/range-error/capacity-error completions. Profiles use 16- and
8-bit beat counts. Python tests check lazy full-window coverage, chunk limits,
invalid descriptor fields and relative-image integer numerical compatibility.
Evidence lives in build/v2/relative-read-request; source hashes are recorded.

Remaining integration work: connect instruction/configuration registers and
capability negotiation, chunk generator and memory arbiter, retire errors to
the host, stop/recover faults, validate AXI responses and PS high-DDR mapping,
then exercise actual reserved memory on hardware. Do not feed SYS3 bundles to
the deployed SYS2 app, change boot memory, or claim high-DDR integration from
this standalone adapter. No qualified timing/resource result exists for it.

## Translator-to-AXI simulation, October 13

relative_read_axi_tb.sv connects the adapter to the frozen dot7 AXI memory port
and FIFO. Both direct and registered request profiles passed 12 scenarios each.
The scoreboard checks physical address bits and deterministic read data on every
accepted beat, exact <=256-beat/4KiB burst splitting including a 65535-beat
descriptor starting one beat before a page boundary, and read_last only at the
descriptor boundary. Invalid range/capacity requests do not enter AXI. Pending
work canceled before slave acceptance does not survive reset; an injected RRESP
fault sets the existing sticky response-error flag, which resets cleanly.

An overlap test confirms a later local validation error can complete while an
earlier valid read awaits memory data. Integration must either serialize request
retirement or attach request identities to distinguish those channels. The
adapter has no request-ID/reorder mechanism and does not turn the AXI-port sticky
RRESP status into a tagged completion. An integrating executor must define that
fault/retirement policy; do not infer ordered complete requests from these tests.

Evidence: build/v2/relative-read-axi/summary.json, result.log and frozen port/FIFO
source hashes. This is standalone RTL composition only, not executor, PS mapping,
reserved-memory or hardware validation. Production/frozen dot7 RTL is unchanged.

## Serialized retirement prototype, October 13

relative_read_retire.sv now wraps the raw adapter with one outstanding request
until its data and typed completion have retired. Local validation faults cannot
overtake an earlier DDR read. Codes0/1/2 mean success/window fault/descriptor
capacity fault. Completion remains stable under backpressure; only then can the
next request be accepted. A sticky memory response error is sampled one clock
after the last accepted data beat, drains that request and completes with code3.
The channel then refuses new requests until coordinated adapter/memory-port
reset. This extra sample avoids missing an RRESP status that latches on the last
read handshake. The memory port must provide its sticky status by that edge.

Focused simulation passed98requests:32 valid/stalled two-beat reads each followed
by window/capacity faults, a last-edge response error and reset recovery. It
checks offered later errors remain blocked, high physical descriptor addresses
stay stable, exactly33 memory descriptors and98completions, stalled data and
16-cycle completion stalls. Evidence build/v2/relative-read-retire. This uses a
controlled memory descriptor/data model; composition with the actual AXI port,
executor/configuration integration, PS high-DDR mapping and hardware remain
pending. The module has no watchdog and cannot bound an unresponsive slave.
Reset must coordinate the memory port; this test does not establish cancellation
of an already outstanding PS AXI transaction. No frozen/deployed RTL changed.

Strengthened retirement coverage:99requests /34memory descriptors now pass,
including an error on the first of three beats followed by stalls and full
three-beat drain before typed completion/poison. Last-beat error and reset
recovery remain covered. Initial98case log/source hashes retained separately.

## Serialized retirement composed with frozen AXI port

relative_retire_axi_tb.sv connects the retirement scheduler to the qualified
dot7 AXI-port/FIFO RTL. Both registered and direct request modes passed13
scenarios each. Every AR checks40-bit address, <=256beats and4KiB splitting;
every returned beat checks address-derived data and descriptor-level last. The
65535beat maximum and4GiB-window last beat pass; overflow/range/misalignment
faults never issue AXI. An offered later window error stays unaccepted while an
earlier read has outstanding responses, then retires after that read. Early
first-response and last-response RRESP faults drain all beats, return typed
error3 and poison; coordinated reset recovers, including cancellation before
any slave AR acceptance. Completion is checked stable during backpressure.

Evidence: build/v2/relative-retire-axi/summary.json/result.log/source-sha256.txt;
the port/FIFO hashes were rechecked against the frozen dot7 snapshot. These26
scenarios establish RTL composition with an AXI slave model, not SYS3 executor
or PS high-DDR mapping/hardware. No timeout/hard bound is implied. The initial
new runner had CRLF shell endings and failed before simulation; converted that
runner to LF, then both profiles passed. No production/frozen RTL edits.

## Whole-operation chunk planning (experimental)

`relative_read_chunker.sv` validates the entire aligned operation against its
model window before issuing any descriptor. It captures the physical base and
window size for the operation, uses 33-bit cursor/progress arithmetic, and waits
for each ordered typed completion before issuing the next chunk. Failed chunks
stop issuance; completed bytes count only successfully retired chunks. A caller
must discard any partial data from a failed chunk. Completion remains stable
under backpressure. Reset must coordinate downstream transactions.

Both descriptor-width profiles passed eight operations each. Width16 split a
full 4 GiB window into 4,097 descriptors, with a final 65,536-byte descriptor;
width8 split 65,536 bytes into 17 descriptors. Checks include descriptor stalls,
changed external configuration, delayed retirement, stalled completion,
whole-operation range/alignment/zero-length rejection, the last window word,
the 40-bit physical endpoint, mid-operation fault and following-operation
recovery. Evidence: `build/v2/relative-read-chunker/summary.json`, result log and
source hashes. This proof uses a controlled completion model: retirement/AXI
composition, executor integration, PS high-DDR mapping and hardware remain
pending. No 4 GiB physical allocation, timing bound or deployed change is implied.

## Chunk planning composed with typed retirement

A separate simulation now connects the chunker to `relative_read_retire.sv`
and its address/descriptor adapter. Four whole operations pass: a 65,536-byte
transfer through 17 descriptors and 4,096 data beats, whole-range rejection
before any memory request, a last-edge sticky response fault on the third
chunk followed by full drain and retirement poison, and coordinated reset
recovery at the window's final word. The failed chunk is excluded from the
8,160 successful-byte count. Descriptor/data/completion backpressure is covered.
`read_last` remains chunk-local; `done_valid` marks whole-operation completion.
Evidence: `build/v2/relative-chunk-retire/summary.json` and logs/source hashes.
This composition uses a controlled memory descriptor/data model, not an AXI
slave or SYS3 executor; PS mapping and hardware validation remain pending.

## Whole-operation chunking through the frozen AXI port

The chunker, typed retirement, address adapter and frozen dot7 AXI port now
compose in simulation. Both direct and registered request profiles passed six
operations each. A 1 MiB read splits into 65,535-beat and one-beat descriptors;
all AXI requests obey 256-beat and 4 KiB limits. Every returned data beat and
chunk-local last is checked. Coverage includes changed external configuration,
pre-issue whole-range rejection, exact 4 GiB window and 40-bit physical endpoints,
and last-response failure in chunk2 with full drain, 1,048,560 successful bytes,
poison and coordinated reset recovery. Frozen port/FIFO hashes rechecked.
Evidence: `build/v2/relative-chunk-axi/summary.json`, logs and source inventory.
These 12 cases use an AXI slave model; SYS3 executor integration, PS mapping,
hardware allocation and timing guarantees remain unproved.

The same whole-operation composition also passed both request modes with the
frozen capture-flags AXI port and registered length-FIFO flags enabled: 12 cases.
Separate test/runner/evidence retain the original dot7 proof unchanged. Evidence:
`build/v2/relative-chunk-axi-flags-final/summary.json`. This does not expand the
integration/hardware/timing claims above.

## Experimental executor ABI separation

The old proposed SYS3 feature bit6 overlapped SYS2 local capture, so its check
could admit an incompatible deployed capture app. Relative bundles now require
ABI `0x53590300` under mask `0xffffff00` plus relative-address bit0. No deployed
app advertises this experimental ABI. Manifests explicitly record ABI/mask/bit.
Thirty relative-model/window tests pass, including rejecting all256 SYS2 feature
combinations and malformed capability types/ranges. Existing tiny-image integer
reference checks remain exact. Evidence: `build/v2/relative-abi-validation.json`.
This changes experimental negotiation only; it does not implement a SYS3 executor.

## Lazy physical burst planning

`MemoryWindow.iter_bursts` streams physical-address/beat-count tuples for large
windows; `bursts` retains the existing list API. A 4 GiB window beginning at
physical-page offset1024 passes1,048,577 bursts, contiguous coverage,256-beat
limits and physical4 KiB page boundaries. Tests also cover the40-bit endpoint,
zero-length compatibility and pre-issuance invalid transfer rejection.
SYS3 negotiation now rejects all1,280 feature combinations across legacy SYS2
and new pipeline ABI families.36 memory/relative-model tests pass. Evidence:
`build/v2/high-ddr-stream-planning.json`; its tracemalloc sample covers planner
allocations only, not system RSS or DDR payload allocation. No DMA/executor,
reserved-memory or high-DDR hardware integration is established by this change.

## Independent KV-cache storage layout

`KvCacheLayout` plans packed INT8 K/V matrices per layer, with 16-byte padded
rows and immutable excluded spans for model/scratch separation. It validates
every relative offset against a `MemoryWindow`; prefix descriptors reuse the
finite-width beat-count contract. The full-window case plans a 4 GiB cache
without allocating it, including the final 32-bit offset and 40-bit physical
endpoint. The second 2 GiB matrix takes 2,049 16-bit descriptors. A 32-layer,
4-KV-head, 64-dimensional, 4,096-token example occupies 64 MiB; this is a storage
formula, not a deployed model configuration.

Twenty-five layout tests cover layer/matrix disjointness, model exclusion, row
padding, endpoints, descriptor limits, invalid accesses and exclusion mutability.
Together with window/bundle tests, 61 tests passed. ABI checks now reject 5,376
legacy/new SYS2 capability combinations, including every operand-capture
feature combination. Evidence: `build/v2/kv-cache-layout-proof.json`.
No decoder, cache writeback, DMA, PS high-DDR mapping, physical allocation or
service-time guarantee is established by this independent planning proof.

## Independent RTL logical KV slice planning

`kv_cache_span.sv` converts layer/key-or-value/first-token/token-count into a
relative byte span using the host's padded row stride. Two elastic stages capture
configuration, calculate full-width products, validate the complete cache against
the window, then reject invalid slices. 82-bit intermediate sums prevent invalid
UINT16-layer/UINT32-capacity/stride products from becoming valid after truncation.
Error code1 denotes invalid layout, code2 invalid slice; errored outputs are zero
and MUST be rejected before DDR. Model/scratch exclusion remains the compiler's
`KvCacheLayout` responsibility.

The independent Python layout oracle generated10,013 packets:10,011 compared and
two deliberately reset-cancelled. Cases cover valid GQA/matrix/token boundaries,
the final32-bit offset, full-window layout, overflow, zero/alignment/range faults,
input bubbles, changed configuration and output backpressure/stability. Native
Verilator build4.926s and simulation0.039s. Evidence:`build/v2/kv-cache-span`.
This new primitive is outside the frozen22encoder sources. It has no Vivado
inference/timing, SYS3 executor, AXI/cache-writeback, decoder or hardware proof.

## Logical KV spans composed with whole-operation chunk planning

A separate testbench connects the logical KV planner to the existing chunker,
using captured window context and a controlled completion model. Seven
operations passed with2,057 descriptors: a final40-bit physical word,1MiB and
2MiB prefixes, invalid layer/overflow layouts gated before issue, a fault on
chunk2 excluding its bytes from successful progress, and a2GiB value prefix
through2,049 finite-width descriptors. Descriptor and completion backpressure,
changed caller configuration and stalled final completion are covered. Native
Verilator build8.573s/simulation0.007s; evidence:`build/v2/kv-chunk-plan`.
This is descriptor composition only. The bench holds the accepted model-window
context; no production executor/window capture, AXI data/retirement, decoder,
cache-writeback or hardware allocation is proved by these cases.


## Experimental KV command context controller

kv_read_command captures the model base and window size when accepting a logical
KV slice. It permits one command outstanding and holds that context through all
chunk retirement and the final completion handshake. Caller configuration changes
cannot alter the accepted operation. Span errors retire locally with done_local_error
and zero completed bytes; they never enter the chunker. A valid span passes the
chunker's whole-operation address checks before descriptors issue. Consumers must
retire each accepted descriptor exactly once and in order. Error-code interpretation
must distinguish local layout/slice failure from downstream completion failure.

Reset cancels the command, planner and chunker, suppresses ready/valid handshakes
while asserted and rejects late completion packets while idle. It does not cancel
an external AXI transaction: an eventual real executor still needs its own drain/
reset fence before admitting new transactions. Controlled tests include sequential
commands without reset, changed host configuration, 2 GiB ranges, the final 40-bit
word, descriptor/done backpressure, second-chunk failure, local faults and resets
before descriptor issuance and after acceptance. This module is absent from the
frozen encoder and deployed app; no AXI data/retirement/decoder integration claim.
