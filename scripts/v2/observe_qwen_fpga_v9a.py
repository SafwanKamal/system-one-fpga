"""Build a BOARD_STATUS observation from a live inventory job's stdout.

Every identity field comes from the board's own inventory output; nothing is
copied from an earlier observation. --state unknown records a failure without
claiming a configuration. Writes only --out (candidate evidence directory).
"""
import argparse,datetime,json
from pathlib import Path

PACKAGES={'sysone-qwen-decoder-wide-int8.bit.bin':'/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2',
          'sysone-qwen-decoder-v9a.bit.bin':'/var/lib/sysone/qwen-fpga-decoder-v9a-candidate1',
          'sysone-qwen-decoder-v9a-b3.bit.bin':'/var/lib/sysone/qwen-fpga-decoder-v9a-candidate3',
          'sysone-qwen-decoder-v9c.bit.bin':'/var/lib/sysone/qwen-fpga-decoder-v9c-candidate1',
          'sysone-qwen-decoder-v9d.bit.bin':'/var/lib/sysone/qwen-fpga-decoder-v9d-candidate1'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inventory',type=Path,required=True,help='stdout of an inventory job')
    ap.add_argument('--state',choices=['ready','stopped','unknown'],required=True)
    ap.add_argument('--evidence',type=Path,action='append',required=True)
    ap.add_argument('--note',default='')
    ap.add_argument('--validation',type=Path,help='optional JSON with validation results')
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    live=json.loads(args.inventory.read_text())
    clocks=live['clocks']
    observation=dict(state=args.state,verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        verification_scope='Live inventory by Claude hardware session: '+str(args.inventory),
        evidence=[str(p.resolve()) for p in args.evidence],
        active_package=PACKAGES.get(live['firmware'],'unrecognised: '+str(live['firmware'])),
        active_fpga_app=live['firmware'].removesuffix('.bit.bin'),boot_id=live['boot_id'],
        fpga_manager_state=live['fpga_state'],launcher_sha256=live['launcher_sha256'],
        dma_header=live['dma_header'],dma_table_sha256=live['dma_table_sha256'],
        decoder_clock_hz=clocks.get('pl0_ref',{}).get('rate_hz'),memory_clock_hz=clocks.get('pl1_ref',{}).get('rate_hz'),
        installed_apps=live['installed_apps'],mvp_service=live['mvp_service'],r5_loaded=live['r5_loaded'],
        benchmark_processes=[p for p in live['python_processes'] if 'benchmark' in p or 'sweep' in p],
        preflight_required_before_use=True,note=args.note)
    if args.validation:observation['last_validation']=json.loads(args.validation.read_text())
    args.out.write_text(json.dumps(observation,indent=2)+'\n')
    print(json.dumps(observation,indent=2))

if __name__=='__main__':main()
