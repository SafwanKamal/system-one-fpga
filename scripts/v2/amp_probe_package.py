"""Package diagnostic probe after exact physical review; never deploy here."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'
APP='sysone-amp-origin-probe'

def main():
 physical=BASE/'probe-physical-v2';review=json.loads((physical/'physical-review.json').read_text())
 assert review['bitstream_admitted'] and json.loads((physical/'bitstream-completion.json').read_text())['exit_code']==0
 for n,h in review['sha256'].items():assert hashlib.sha256((physical/n).read_bytes()).hexdigest()==h,n
 out=BASE/'probe-package-v1';out.mkdir(exist_ok=False);staging=out/'conversion';staging.mkdir()
 app=out/APP;app.mkdir()
 shutil.copyfile(physical/'probe.bit',staging/(APP+'.bit'))
 (staging/'bitstream.bif').write_text('all: { '+APP+'.bit }\n')
 cmd=['C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat','-arch','zynqmp','-image','bitstream.bif','-process_bitstream','bin']
 r=subprocess.run(cmd,cwd=staging,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
 (out/'bootgen.log').write_bytes(r.stdout);assert not r.returncode
 bins=list(staging.glob('*.bin'));assert len(bins)==1
 shutil.copyfile(bins[0],app/(APP+'.bit.bin'))
 # No assigned-clock-rates: retain the reviewed live PL0 rate, verified before
 # and after loading. AFI FS selects 128-bit HPM0/1; no HP DDR master exists.
 dts='''/dts-v1/;
/plugin/;
/ {
 fragment@0 {
  target = <&fpga_full>;
  __overlay__ {
   firmware-name = "sysone-amp-origin-probe.bit.bin";
   resets = <&zynqmp_reset 116>, <&zynqmp_reset 117>, <&zynqmp_reset 118>, <&zynqmp_reset 119>;
  };
 };
 fragment@1 {
  target = <&amba>;
  __overlay__ {
   #address-cells = <2>;
   #size-cells = <2>;
   amp_probe_clock: amp-probe-clock {
    compatible = "xlnx,fclk";
    status = "okay";
    clocks = <&zynqmp_clk 71>;
    #clock-cells = <0>;
   };
   amp-probe-afi {
    compatible = "xlnx,afi-fpga";
    status = "okay";
    resets = <&zynqmp_reset 116>, <&zynqmp_reset 117>, <&zynqmp_reset 118>, <&zynqmp_reset 119>;
    config-afi = <14 0xa00>;
   };
   origin-probe@a0000000 {
    compatible = "sysone,axi-origin-probe-v1";
    reg = <0 0xa0000000 0 0x1000>;
    clocks = <&zynqmp_clk 71>;
    status = "okay";
   };
  };
 };
};
'''
 (app/(APP+'.dts')).write_text(dts)
 wsl='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:];rel=app.relative_to(ROOT).as_posix()
 cmd=['wsl','-d','Ubuntu-24.04','--','/mnt/c/AMDDesignTools/2025.2/Vivado/bin/dtc','-@','-I','dts','-O','dtb',
      '-o',wsl+'/'+rel+'/'+APP+'.dtbo',wsl+'/'+rel+'/'+APP+'.dts']
 r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
 (out/'dtc.log').write_bytes(r.stdout);assert not r.returncode
 (app/'shell.json').write_text(json.dumps(dict(shell_type='XRT_FLAT',num_slots='1'),indent=2)+'\n')
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in app.iterdir() if p.suffix!='.dts'}
 manifest=dict(app_name=APP,diagnostic_only=True,no_encoder=True,no_pl_ddr_master=True,
  inference_deployment_ready=False,files_sha256=files,control_base=0xa0000000,control_size=4096,
  timing_period_ns=10.0,clock_must_be_preserved=True,clock_upper_hz=100000000,
  physical_review_sha256=hashlib.sha256((physical/'physical-review.json').read_bytes()).hexdigest(),
  bitstream_sha256=hashlib.sha256((physical/'probe.bit').read_bytes()).hexdigest(),
  stock_backup_and_recovery_required=True,source_tags_target_qualified=False)
 (app/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,target_modified=False,diagnostic_only=True,
  manifest_sha256=hashlib.sha256((app/'build.json').read_bytes()).hexdigest()),indent=2)+'\n')
 print('PASS diagnostic probe package; target-access/backup gate must pass before load',flush=True)
if __name__=='__main__':main()
