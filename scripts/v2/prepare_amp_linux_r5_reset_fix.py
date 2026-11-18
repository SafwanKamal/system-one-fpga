"""Derive a separate R5 reset fix while retaining every original sealed file."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'


def main():
    out=BASE/'reset-fix-v1';out.mkdir(exist_ok=False)
    seal=json.loads((ROOT/'docs/research/2026-10-17-typed200-amp-linux-r5-validation.json').read_text())
    records={**seal['preserved_sha256'],**seal['candidate_sha256']}
    def original(name):
        data=(ROOT/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==records[name],name
        return data.decode()
    source=original('firmware/typed200_amp_linux_r5/smoke.S')
    bad=' mov r0,#0\n mcr p15,0,r0,c12,c0,0\n'
    assert source.count(bad)==1
    fixed=source.replace(bad,' /* Cortex-R5 has no VBAR. Low vectors are selected by SCTLR.V below. */\n')
    target=ROOT/'firmware/typed200_amp_linux_r5_controller/smoke-v2.S'
    assert not target.exists();target.write_bytes(fixed.encode())
    linker=ROOT/'firmware/typed200_amp_linux_r5_controller/smoke-padded.ld'
    assert not linker.exists()
    linker.write_bytes(original('firmware/typed200_amp_linux_r5/smoke-padded.ld').encode())
    builder=original('scripts/v2/build_amp_linux_r5_smoke.py')
    builder=builder.replace("BASE = ROOT/'build/v2/typed200-amp-linux-r5-v1'", "BASE = ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'")
    builder=builder.replace("source = ROOT/'firmware/typed200_amp_linux_r5'", "source = ROOT/'firmware/typed200_amp_linux_r5_controller'")
    builder=builder.replace("source/'smoke.S'", "source/'smoke-v2.S'")
    checker=original('scripts/v2/check_amp_linux_r5_smoke.py')
    checker=checker.replace("BASE = ROOT/'build/v2/typed200-amp-linux-r5-v1'", "BASE = ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'")
    checker=checker.replace("str(BASE/'emulator-deps')", "str(ROOT/'build/v2/typed200-amp-linux-r5-v1/emulator-deps')")
    marker="    build = json.loads((BASE/args.build/'receipt.json').read_text())"
    guard="""    unsupported_vbar = struct.pack('<I',0xee0c0f10)
    old_elf = (ROOT/'build/v2/typed200-amp-linux-r5-v1/smoke-build-v2/sysone-r5-smoke.elf').read_bytes()
    assert unsupported_vbar in old_elf, 'Prior-image negative regression must detect VBAR'
    assert unsupported_vbar not in elf, 'Cortex-R5 does not implement VBAR'
"""
    assert checker.count(marker)==1;checker=checker.replace(marker,guard+marker)
    marker="            # Reset-state fault injection overrides only the diagnostic read;"
    guard="""            if instruction & 0x0f000f10 == 0x0e000f10:
                assert instruction in [0xee118f10,0xee10af10,0xee010f10], hex(instruction)
"""
    assert checker.count(marker)==1;checker=checker.replace(marker,guard+marker)
    checker=checker.replace("software_only=True,power_reset_clock_qualified=False,target_executed=False,",
                            "software_only=True,power_reset_clock_qualified=False,target_executed=False,\n        prior_vbar_image_rejected=True,cp15_instruction_allowlist_checked=True,")
    for name,text in [('build_amp_linux_r5_reset_smoke.py',builder),('check_amp_linux_r5_reset_smoke.py',checker)]:
        compile(text,name,'exec');path=ROOT/'scripts/v2'/name
        assert not path.exists();path.write_bytes(text.encode())
    receipt=dict(passed=True,change='Remove unsupported VBAR write; retain low SCTLR.V selection',
        original_image_and_sources_preserved=True,prior_emulator_compatibility_blind_spot=True,
        changed_source_sha256=hashlib.sha256(fixed.encode()).hexdigest(),
        primary_reference='https://lore.pengutronix.de/barebox/20250113-k3-r5-v3-5-065fcdcc28d3@pengutronix.de/',
        amd_local_reference='build/v2/typed200-k26-boot-chain-v1/bsp-pmu-v1/libsrc/standalone/src/arm/cortexr5/gcc/boot.S',
        amd_reference_vbar_is_conditional_on_ARMR52=True,target_executed=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS separate no-VBAR candidate and explicit prior-image negative regression generated')


if __name__=='__main__':main()
