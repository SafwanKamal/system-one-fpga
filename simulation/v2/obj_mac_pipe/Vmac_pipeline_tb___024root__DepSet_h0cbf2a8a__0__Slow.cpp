// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vmac_pipeline_tb.h for the primary calling header

#include "Vmac_pipeline_tb__pch.h"
#include "Vmac_pipeline_tb___024root.h"

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_static__TOP(Vmac_pipeline_tb___024root* vlSelf);

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_static(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_static\n"); );
    // Body
    Vmac_pipeline_tb___024root___eval_static__TOP(vlSelf);
}

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_static__TOP(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_static__TOP\n"); );
    // Body
    vlSelf->mac_pipeline_tb__DOT__clk = 0U;
}

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_final(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_final\n"); );
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vmac_pipeline_tb___024root___dump_triggers__stl(Vmac_pipeline_tb___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vmac_pipeline_tb___024root___eval_phase__stl(Vmac_pipeline_tb___024root* vlSelf);

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_settle(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_settle\n"); );
    // Init
    IData/*31:0*/ __VstlIterCount;
    CData/*0:0*/ __VstlContinue;
    // Body
    __VstlIterCount = 0U;
    vlSelf->__VstlFirstIteration = 1U;
    __VstlContinue = 1U;
    while (__VstlContinue) {
        if (VL_UNLIKELY((0x64U < __VstlIterCount))) {
#ifdef VL_DEBUG
            Vmac_pipeline_tb___024root___dump_triggers__stl(vlSelf);
#endif
            VL_FATAL_MT("mac_pipeline_tb.sv", 3, "", "Settle region did not converge.");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        __VstlContinue = 0U;
        if (Vmac_pipeline_tb___024root___eval_phase__stl(vlSelf)) {
            __VstlContinue = 1U;
        }
        vlSelf->__VstlFirstIteration = 0U;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vmac_pipeline_tb___024root___dump_triggers__stl(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___dump_triggers__stl\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VstlTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VstlTriggered.word(0U))) {
        VL_DBG_MSGF("         'stl' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vmac_pipeline_tb___024root___stl_sequent__TOP__0(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___stl_sequent__TOP__0\n"); );
    // Body
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][1U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [1U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][1U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][1U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][1U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][2U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [2U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][2U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][2U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][2U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][3U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [3U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][3U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][3U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][3U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][4U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [4U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][4U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][4U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][4U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][5U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [5U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][5U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][5U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][5U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][6U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [6U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][6U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][6U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][6U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][7U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [7U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][7U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][7U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][7U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][8U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [8U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][8U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][8U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][8U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][9U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [9U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][9U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][9U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][9U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0xaU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xaU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0xaU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xaU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xaU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0xbU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xbU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0xbU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xbU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xbU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0xcU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xcU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0xcU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xcU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xcU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0xdU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xdU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0xdU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xdU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xdU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0xeU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xeU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0xeU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xeU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xeU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[1U][0xfU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xfU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[0U][0xfU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xfU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xfU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][1U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [1U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][1U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][1U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][1U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][2U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [2U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][2U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][2U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][2U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][3U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [3U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][3U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][3U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][3U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][4U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [4U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][4U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][4U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][4U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][5U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [5U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][5U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][5U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][5U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][6U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [6U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][6U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][6U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][6U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][7U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [7U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][7U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][7U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][7U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][8U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [8U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][8U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][8U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][8U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][9U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [9U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][9U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][9U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][9U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0xaU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xaU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0xaU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xaU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xaU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0xbU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xbU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0xbU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xbU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xbU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0xcU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xcU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0xcU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xcU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xcU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0xdU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xdU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0xdU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xdU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xdU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0xeU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xeU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0xeU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xeU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xeU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[3U][0xfU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xfU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_direct[2U][0xfU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xfU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xfU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][1U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [1U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][1U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][1U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][1U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][2U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [2U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][2U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][2U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][2U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][3U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [3U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][3U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][3U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][3U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][4U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [4U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][4U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][4U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][4U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][5U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [5U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][5U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][5U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][5U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][6U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [6U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][6U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][6U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][6U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][7U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [7U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][7U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][7U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][7U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][8U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [8U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][8U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][8U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][8U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][9U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [9U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][9U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][9U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][9U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0xaU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xaU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0xaU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xaU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xaU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0xbU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xbU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0xbU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xbU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xbU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0xcU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xcU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0xcU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xcU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xcU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0xdU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xdU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0xdU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xdU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xdU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0xeU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xeU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0xeU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xeU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xeU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[1U][0xfU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [0U]
                                                      [0xfU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[0U][0xfU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [0U][0xfU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [0U][0xfU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][1U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [1U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][1U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][1U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][1U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][2U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [2U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][2U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][2U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][2U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][3U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [3U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][3U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][3U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][3U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][4U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [4U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][4U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][4U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][4U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][5U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [5U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][5U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][5U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][5U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][6U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [6U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][6U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][6U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][6U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][7U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [7U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][7U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][7U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][7U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][8U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [8U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][8U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][8U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][8U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][9U] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [9U]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][9U] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][9U] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][9U] >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0xaU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xaU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0xaU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xaU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xaU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0xbU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xbU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0xbU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xbU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xbU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0xcU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xcU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0xcU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xcU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xcU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0xdU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xdU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0xdU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xdU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xdU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0xeU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xeU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0xeU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xeU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xeU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[3U][0xfU] 
        = (0x1ffffU & VL_EXTENDS_II(17,16, (0xffffU 
                                            & (IData)(
                                                      vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                                      [1U]
                                                      [0xfU]))));
    vlSelf->mac_pipeline_tb__DOT__packed_piped[2U][0xfU] 
        = (0x1ffffU & ((IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                [1U][0xfU] >> 0x10U)) 
                       + (1U & (IData)((vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg
                                        [1U][0xfU] 
                                        >> 0xfU)))));
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0U] 
        = vlSelf->mac_pipeline_tb__DOT__b[0U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[1U] 
        = vlSelf->mac_pipeline_tb__DOT__b[1U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[2U] 
        = vlSelf->mac_pipeline_tb__DOT__b[2U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[3U] 
        = vlSelf->mac_pipeline_tb__DOT__b[3U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[4U] 
        = vlSelf->mac_pipeline_tb__DOT__b[4U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[5U] 
        = vlSelf->mac_pipeline_tb__DOT__b[5U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[6U] 
        = vlSelf->mac_pipeline_tb__DOT__b[6U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[7U] 
        = vlSelf->mac_pipeline_tb__DOT__b[7U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[8U] 
        = vlSelf->mac_pipeline_tb__DOT__b[8U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[9U] 
        = vlSelf->mac_pipeline_tb__DOT__b[9U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xaU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xbU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xcU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xdU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xeU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0U] 
        = vlSelf->mac_pipeline_tb__DOT__b[0U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[1U] 
        = vlSelf->mac_pipeline_tb__DOT__b[1U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[2U] 
        = vlSelf->mac_pipeline_tb__DOT__b[2U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[3U] 
        = vlSelf->mac_pipeline_tb__DOT__b[3U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[4U] 
        = vlSelf->mac_pipeline_tb__DOT__b[4U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[5U] 
        = vlSelf->mac_pipeline_tb__DOT__b[5U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[6U] 
        = vlSelf->mac_pipeline_tb__DOT__b[6U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[7U] 
        = vlSelf->mac_pipeline_tb__DOT__b[7U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[8U] 
        = vlSelf->mac_pipeline_tb__DOT__b[8U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[9U] 
        = vlSelf->mac_pipeline_tb__DOT__b[9U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__b[0xfU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[1U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [1U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[2U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [2U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[3U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [3U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[4U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [4U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[5U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [5U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[6U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [6U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[7U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [7U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[8U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [8U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[9U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [9U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xaU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xbU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xcU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xdU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xeU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[1U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [1U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[2U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [2U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[3U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [3U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[4U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [4U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[5U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [5U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[6U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [6U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[7U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [7U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[8U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [8U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[9U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [9U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg
        [0xfU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][1U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][2U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][3U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][4U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][5U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][6U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][7U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][8U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][9U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[0U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][1U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][2U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][3U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][4U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][5U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][6U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][7U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][8U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][9U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[1U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][1U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][2U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][3U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][4U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][5U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][6U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][7U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][8U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][9U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[2U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][1U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][2U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][3U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][4U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][5U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][6U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][7U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][8U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][9U];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[3U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][1U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][1U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][2U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][2U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][3U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][3U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][4U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][4U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][5U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][5U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][6U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][6U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][7U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][7U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][8U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][8U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][9U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][9U];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__plain[0U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][1U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][1U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][2U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][2U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][3U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][3U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][4U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][4U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][5U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][5U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][6U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][6U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][7U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][7U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][8U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][8U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][9U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][9U];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__plain[1U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][1U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][1U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][2U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][2U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][3U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][3U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][4U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][4U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][5U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][5U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][6U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][6U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][7U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][7U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][8U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][8U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][9U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][9U];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__plain[2U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][1U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][1U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][2U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][2U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][3U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][3U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][4U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][4U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][5U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][5U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][6U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][6U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][7U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][7U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][8U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][8U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][9U] = vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][9U];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__plain[3U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[0U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[0U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[1U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[1U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[2U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[2U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[3U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__a[3U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][1U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][2U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][3U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][4U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][5U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][6U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][7U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][8U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][9U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[0U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][1U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][2U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][3U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][4U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][5U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][6U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][7U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][8U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][9U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[1U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][1U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][2U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][3U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][4U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][5U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][6U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][7U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][8U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][9U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[2U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][1U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][2U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][3U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][4U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][5U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][6U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][7U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][8U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][9U];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[3U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][1U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][1U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][2U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][2U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][3U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][3U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][4U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][4U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][5U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][5U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][6U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][6U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][7U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][7U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][8U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][8U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][9U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][9U];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__piped[0U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [0U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][1U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][1U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][2U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][2U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][3U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][3U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][4U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][4U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][5U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][5U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][6U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][6U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][7U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][7U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][8U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][8U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][9U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][9U];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__piped[1U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [1U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][1U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][1U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][2U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][2U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][3U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][3U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][4U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][4U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][5U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][5U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][6U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][6U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][7U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][7U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][8U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][8U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][9U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][9U];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__piped[2U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [2U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][1U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][1U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][2U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][2U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][3U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][3U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][4U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][4U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][5U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][5U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][6U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][6U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][7U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][7U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][8U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][8U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][9U] = vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][9U];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0xaU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0xbU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0xcU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0xdU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0xeU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__piped[3U][0xfU] = 
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg
        [3U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[0U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [0U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[1U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [1U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[2U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [2U][0xfU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][1U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][1U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][2U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][2U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][3U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][3U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][4U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][4U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][5U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][5U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][6U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][6U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][7U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][7U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][8U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][8U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][9U] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][9U];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0xaU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xaU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0xbU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xbU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0xcU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xcU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0xdU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xdU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0xeU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xeU];
    vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[3U][0xfU] 
        = vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg
        [3U][0xfU];
}

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_stl(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_stl\n"); );
    // Body
    if ((1ULL & vlSelf->__VstlTriggered.word(0U))) {
        Vmac_pipeline_tb___024root___stl_sequent__TOP__0(vlSelf);
    }
}

VL_ATTR_COLD void Vmac_pipeline_tb___024root___eval_triggers__stl(Vmac_pipeline_tb___024root* vlSelf);

VL_ATTR_COLD bool Vmac_pipeline_tb___024root___eval_phase__stl(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_phase__stl\n"); );
    // Init
    CData/*0:0*/ __VstlExecute;
    // Body
    Vmac_pipeline_tb___024root___eval_triggers__stl(vlSelf);
    __VstlExecute = vlSelf->__VstlTriggered.any();
    if (__VstlExecute) {
        Vmac_pipeline_tb___024root___eval_stl(vlSelf);
    }
    return (__VstlExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vmac_pipeline_tb___024root___dump_triggers__act(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___dump_triggers__act\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VactTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(posedge mac_pipeline_tb.clk)\n");
    }
    if ((2ULL & vlSelf->__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 1 is active: @(negedge mac_pipeline_tb.clk)\n");
    }
    if ((4ULL & vlSelf->__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 2 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vmac_pipeline_tb___024root___dump_triggers__nba(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___dump_triggers__nba\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VnbaTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(posedge mac_pipeline_tb.clk)\n");
    }
    if ((2ULL & vlSelf->__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 1 is active: @(negedge mac_pipeline_tb.clk)\n");
    }
    if ((4ULL & vlSelf->__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 2 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vmac_pipeline_tb___024root___ctor_var_reset(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___ctor_var_reset\n"); );
    // Body
    vlSelf->mac_pipeline_tb__DOT__clk = VL_RAND_RESET_I(1);
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__a[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__b[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__plain[__Vi0][__Vi1] = VL_RAND_RESET_I(17);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_direct[__Vi0][__Vi1] = VL_RAND_RESET_I(17);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__piped[__Vi0][__Vi1] = VL_RAND_RESET_I(17);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_piped[__Vi0][__Vi1] = VL_RAND_RESET_I(17);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__previous[__Vi0][__Vi1] = VL_RAND_RESET_I(32);
        }
    }
    vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv = 0;
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_a[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__operand_b[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg[__Vi0][__Vi1] = VL_RAND_RESET_I(17);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_a[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__operand_b[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 2; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg[__Vi0][__Vi1] = VL_RAND_RESET_Q(43);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg[__Vi0][__Vi1] = VL_RAND_RESET_I(17);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg[__Vi0][__Vi1] = VL_RAND_RESET_I(9);
        }
    }
    for (int __Vi0 = 0; __Vi0 < 16; ++__Vi0) {
        vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg[__Vi0] = VL_RAND_RESET_I(8);
    }
    for (int __Vi0 = 0; __Vi0 < 2; ++__Vi0) {
        for (int __Vi1 = 0; __Vi1 < 16; ++__Vi1) {
            vlSelf->mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg[__Vi0][__Vi1] = VL_RAND_RESET_Q(43);
        }
    }
    vlSelf->__Vtrigprevexpr___TOP__mac_pipeline_tb__DOT__clk__0 = VL_RAND_RESET_I(1);
}
