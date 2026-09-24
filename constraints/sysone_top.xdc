## Nexys 4 DDR constraints for sysone_top.
## Clock, reset, PHY reference clock, reset, MDIO and transmit pins are the ones
## Genome-Classifier's ethernet test top uses on this board. The receive pins are
## from the Digilent Nexys 4 DDR master XDC (ETH_RXD, ETH_CRSDV, ETH_RXERR).

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

## LEDs: locked, PHY out of reset, result toggle, drop/transmit error, receive error, busy
set_property -dict {PACKAGE_PIN H17 IOSTANDARD LVCMOS33} [get_ports {LED[0]}]
set_property -dict {PACKAGE_PIN K15 IOSTANDARD LVCMOS33} [get_ports {LED[1]}]
set_property -dict {PACKAGE_PIN J13 IOSTANDARD LVCMOS33} [get_ports {LED[2]}]
set_property -dict {PACKAGE_PIN N14 IOSTANDARD LVCMOS33} [get_ports {LED[3]}]
set_property -dict {PACKAGE_PIN R18 IOSTANDARD LVCMOS33} [get_ports {LED[4]}]
set_property -dict {PACKAGE_PIN V17 IOSTANDARD LVCMOS33} [get_ports {LED[5]}]

set_property BITSTREAM.CONFIG.UNUSEDPIN Pullnone [current_design]

## The PHY reference clock is the 50 MHz logic clock forwarded through an ODDR
## with D1 = 0 and D2 = 1, so it is the logic clock inverted.
create_generated_clock -name PHY_clk -source [get_pins clock_manager/CLKOUT0] \
    -divide_by 1 -invert [get_ports PHY_ref_clk]

## Transmit: the PHY samples on its rising edge, half a period after our update
set_output_delay -clock PHY_clk -max 5.000 [get_ports {rmii_txd[*] rmii_tx_en}]
set_output_delay -clock PHY_clk -min -2.500 [get_ports {rmii_txd[*] rmii_tx_en}]

## Receive: RMII allows the PHY 2 to 14 ns from its rising edge to valid output.
## rmii_RX captures on our falling edge, which is the PHY's next rising edge.
set_input_delay -clock PHY_clk -max 14.000 [get_ports {rmii_rxd[*] rmii_crs_dv rmii_rx_er}]
set_input_delay -clock PHY_clk -min 2.000 [get_ports {rmii_rxd[*] rmii_crs_dv rmii_rx_er}]

set_false_path -from [get_ports reset]
set_false_path -to [get_ports {LED[*] PHY_reset_n PHY_MDC PHY_MDIO}]

set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
