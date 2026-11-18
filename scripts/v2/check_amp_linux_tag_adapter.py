"""Reuse the sealed actual-function harness on the separate clock-holding adapter."""
from pathlib import Path
import check_amp_linux_r5_adapter as harness

harness.BASE=Path(__file__).resolve().parents[2]/'build/v2/typed200-amp-linux-tag-probe-v1'
harness.SOURCE=Path(__file__).resolve().parents[2]/'firmware/typed200_amp_linux_tag_probe'
if __name__=='__main__':harness.main()
