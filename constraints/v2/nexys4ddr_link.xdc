## Nexys 4 DDR, v2 bring-up step 2 (nexys4ddr_link_top): DDR2 over raw Ethernet.
## Ethernet pins and timing are v1's (constraints/sysone_top.xdc), with the 50 MHz
## clock now on CLKOUT1. DDR2 pins and timing come from the MIG IP.

set_property -dict {PACKAGE_PIN E3 IOSTANDARD LVCMOS33} [get_ports clk_100MHz]
create_clock -name board_clk -period 10.000 [get_ports clk_100MHz]

set_property -dict {PACKAGE_PIN N17 IOSTANDARD LVCMOS33} [get_ports reset]

## LAN8720A RMII PHY
set_property -dict {PACKAGE_PIN D5  IOSTANDARD LVCMOS33} [get_ports PHY_ref_clk]
set_property -dict {PACKAGE_PIN B3  IOSTANDARD LVCMOS33} [get_ports PHY_reset_n]
set_property -dict {PACKAGE_PIN C9  IOSTANDARD LVCMOS33} [get_ports PHY_MDC]
set_property -dict {PACKAGE_PIN A9  IOSTANDARD LVCMOS33} [get_ports PHY_MDIO]
set_property -dict {PACKAGE_PIN A10 IOSTANDARD LVCMOS33} [get_ports {rmii_txd[0]}]
set_property -dict {PACKAGE_PIN A8  IOSTANDARD LVCMOS33} [get_ports {rmii_txd[1]}]
set_property -dict {PACKAGE_PIN B9  IOSTANDARD LVCMOS33} [get_ports rmii_tx_en]
set_property -dict {PACKAGE_PIN C11 IOSTANDARD LVCMOS33} [get_ports {rmii_rxd[0]}]
set_property -dict {PACKAGE_PIN D10 IOSTANDARD LVCMOS33} [get_ports {rmii_rxd[1]}]
set_property -dict {PACKAGE_PIN D9  IOSTANDARD LVCMOS33} [get_ports rmii_crs_dv]
set_property -dict {PACKAGE_PIN C10 IOSTANDARD LVCMOS33} [get_ports rmii_rx_er]

set_property -dict {PACKAGE_PIN H17 IOSTANDARD LVCMOS33} [get_ports {LED[0]}]
set_property -dict {PACKAGE_PIN K15 IOSTANDARD LVCMOS33} [get_ports {LED[1]}]
set_property -dict {PACKAGE_PIN J13 IOSTANDARD LVCMOS33} [get_ports {LED[2]}]
set_property -dict {PACKAGE_PIN N14 IOSTANDARD LVCMOS33} [get_ports {LED[3]}]
set_property -dict {PACKAGE_PIN R18 IOSTANDARD LVCMOS33} [get_ports {LED[4]}]
set_property -dict {PACKAGE_PIN V17 IOSTANDARD LVCMOS33} [get_ports {LED[5]}]
set_property -dict {PACKAGE_PIN U17 IOSTANDARD LVCMOS33} [get_ports {LED[6]}]
set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS33} [get_ports {LED[7]}]

## seven-segment: segments_n = {CG, CF, CE, CD, CC, CB, CA}
set_property -dict {PACKAGE_PIN T10 IOSTANDARD LVCMOS33} [get_ports {segments_n[0]}]
set_property -dict {PACKAGE_PIN R10 IOSTANDARD LVCMOS33} [get_ports {segments_n[1]}]
set_property -dict {PACKAGE_PIN K16 IOSTANDARD LVCMOS33} [get_ports {segments_n[2]}]
set_property -dict {PACKAGE_PIN K13 IOSTANDARD LVCMOS33} [get_ports {segments_n[3]}]
set_property -dict {PACKAGE_PIN P15 IOSTANDARD LVCMOS33} [get_ports {segments_n[4]}]
set_property -dict {PACKAGE_PIN T11 IOSTANDARD LVCMOS33} [get_ports {segments_n[5]}]
set_property -dict {PACKAGE_PIN L18 IOSTANDARD LVCMOS33} [get_ports {segments_n[6]}]
set_property -dict {PACKAGE_PIN H15 IOSTANDARD LVCMOS33} [get_ports decimal_point_n]
set_property -dict {PACKAGE_PIN J17 IOSTANDARD LVCMOS33} [get_ports {anodes_n[0]}]
set_property -dict {PACKAGE_PIN J18 IOSTANDARD LVCMOS33} [get_ports {anodes_n[1]}]
set_property -dict {PACKAGE_PIN T9  IOSTANDARD LVCMOS33} [get_ports {anodes_n[2]}]
set_property -dict {PACKAGE_PIN J14 IOSTANDARD LVCMOS33} [get_ports {anodes_n[3]}]
set_property -dict {PACKAGE_PIN P14 IOSTANDARD LVCMOS33} [get_ports {anodes_n[4]}]
set_property -dict {PACKAGE_PIN T14 IOSTANDARD LVCMOS33} [get_ports {anodes_n[5]}]
set_property -dict {PACKAGE_PIN K2  IOSTANDARD LVCMOS33} [get_ports {anodes_n[6]}]
set_property -dict {PACKAGE_PIN U13 IOSTANDARD LVCMOS33} [get_ports {anodes_n[7]}]

set_property BITSTREAM.CONFIG.UNUSEDPIN Pullnone [current_design]

## PHY reference clock: the 50 MHz clock forwarded through an ODDR, inverted
create_generated_clock -name PHY_clk -source [get_pins clock_manager/CLKOUT1] \
    -divide_by 1 -invert [get_ports PHY_ref_clk]

set_output_delay -clock PHY_clk -max 5.000 [get_ports {rmii_txd[*] rmii_tx_en}]
set_output_delay -clock PHY_clk -min -2.500 [get_ports {rmii_txd[*] rmii_tx_en}]
set_input_delay -clock PHY_clk -max 14.000 [get_ports {rmii_rxd[*] rmii_crs_dv rmii_rx_er}]
set_input_delay -clock PHY_clk -min 2.000 [get_ports {rmii_rxd[*] rmii_crs_dv rmii_rx_er}]

## The Ethernet side and the MIG ui_clk side only meet in async_fifo (Gray-coded
## pointers through two-flop synchronisers), so they are timed independently.
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks -of_objects [get_pins clock_manager/CLKOUT1]] \
    -group [get_clocks -of_objects [get_nets ui_clk]]

set_false_path -from [get_ports reset]
set_false_path -to [get_ports {LED[*] segments_n[*] decimal_point_n anodes_n[*] PHY_reset_n PHY_MDC PHY_MDIO}]

set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
