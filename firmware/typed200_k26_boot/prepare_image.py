"""Prepare local-only cold-boot image for layout audit; no media/target access.

This is NOT a runnable KR260 launch path: cold-POR/debug interception is an open
physical/procedure gate. Never use volatile system-reset override with frozen v5.
"""
from pathlib import Path
import argparse,hashlib,json,re,secrets,struct,uuid
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-k26-boot-chain-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='image-layout-v1')
    name=ap.parse_args().name;assert re.fullmatch(r'image-layout-v[0-9]+',name)
    dst=OUT/name;dst.mkdir(exist_ok=False)
    session=secrets.randbits(64) or 1
    boot=struct.pack('<IIQ12I',0x4d565031,1,session,533328000,*([0]*11))
    request=bytearray(384)
    struct.pack_into('<IIQIIIIHHHHI',request,0,0x54594331,1,session,0,0,1,1,2,0,1,0,1)
    struct.pack_into('<2H',request,44,101,102)
    (dst/'input.bin').write_bytes(boot+request)
    files={
      'fsbl':OUT/'app-fsbl-v1/build/typed200_fsbl.elf',
      'pmu':OUT/'app-pmu-v1/build/typed200_pmufw.elf',
      'bit':OUT/'typed200.bit',
      'model':ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img',
      'input':dst/'input.bin',
      'relay':ROOT/'build/v2/typed200-boot-relay-v1/relay.elf'}
    def s(p):return 'S:/'+p.relative_to(ROOT).as_posix()
    bif='typed200_lab:\n{\n'+''.join([
      f' [bootloader, destination_cpu=a53-0] {s(files["fsbl"])}\n',
      f' [pmufw_image] {s(files["pmu"])}\n',
      f' [destination_device=pl] {s(files["bit"])}\n',
      f' [destination_cpu=a53-0, load=0x60000000] {s(files["model"])}\n',
      f' [destination_cpu=a53-0, load=0x100f0000] {s(files["input"])}\n',
      f' [destination_cpu=a53-0, exception_level=el-3, trustzone] {s(files["relay"])}\n'])+'}\n'
    (dst/'boot.bif').write_text(bif)
    recipe=dict(schema='sysone.typed200.local-boot-recipe.v1',purpose='Local image layout audit only',
      ready_for_target=False,executed=False,persistent_write_authorized=False,
      run_id=str(uuid.uuid4()),session=session,
      input=dict(bytes=448,address=0x100f0000,tokens=[101,102],first=0,count=1,budget=1,
         expected='Deadline if admitted with stable clocks; diagnostic first case, not accepted inference'),
      artifacts={role:dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for role,p in files.items()},
      bif=dict(path=(dst/'boot.bif').relative_to(ROOT).as_posix(),sha256=sha(dst/'boot.bif')),
      image_path=(dst/'BOOT.bin').relative_to(ROOT).as_posix(),
      ordered_steps=[
       'Verify all hashes, target identity, independent recovery and reviewed cold-POR launch route',
       'Do not use this image through ordinary stock U-Boot or volatile system-reset override',
       'BootROM loads dedicated PMU/FSBL; FSBL initializes matching PS, PL, model, input, DDR relay',
       'Final A53_0 EL3 hook checks cold-POR, powers RPU, holds peer/R5 reset, waits common completion',
       'Verify CSU drained; seal PMU via fresh-session IPI, after callbacks return',
       'Final FSBL exit to DDR relay only; replace frozen A53 OCM and transfer',
       'A53 installs frozen R5 and resets all A53 cores; R5 independently validates ownership before permit',
       'Wait for terminal/park via separately reviewed observer; debug snapshots are diagnostic only',
       'Capture immutable raw evidence; cold-power-cycle to unchanged stock QSPI recovery'],
      blockers=['Independent recovery not currently connected (user has SSH only)',
       'Exact cold-POR launch interception/procedure for fixed QSPI boot not established',
       'Current board permissions/power/debug physical checks unmeasured',
       'Passive completion observer not implemented/reviewed; no clean end-to-end timing claim'],
      prohibited=['QSPI/eMMC/eFuse/security-lock programming','reboot/deploy before readiness',
       'Clearing reset history or relaxing cold-POR prerequisite to make warm launch pass'])
    (OUT/'boot-recipe.json').write_text(json.dumps(recipe,indent=2))
    print('Prepared fresh-session local layout recipe:',hex(session),'NOT target-ready')
if __name__=='__main__':main()
