// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vmac_pipeline_tb.h for the primary calling header

#include "Vmac_pipeline_tb__pch.h"
#include "Vmac_pipeline_tb__Syms.h"
#include "Vmac_pipeline_tb___024root.h"

VL_INLINE_OPT VlCoroutine Vmac_pipeline_tb___024root___eval_initial__TOP__Vtiming__0(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_initial__TOP__Vtiming__0\n"); );
    // Init
    IData/*31:0*/ mac_pipeline_tb__DOT__unnamedblk1__DOT__av;
    mac_pipeline_tb__DOT__unnamedblk1__DOT__av = 0;
    // Body
    mac_pipeline_tb__DOT__unnamedblk1__DOT__av = 0xffffff80U;
    while (VL_GTES_III(32, 0xffU, mac_pipeline_tb__DOT__unnamedblk1__DOT__av)) {
        vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv = 0xffffff80U;
        while (VL_GTES_III(32, 0x7fU, vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) {
            co_await vlSelf->__VtrigSched_haf4c1a17__0.trigger(0U, 
                                                               nullptr, 
                                                               "@(negedge mac_pipeline_tb.clk)", 
                                                               "mac_pipeline_tb.sv", 
                                                               19);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][1U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[1U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][2U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[2U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][3U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[3U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][4U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[4U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][5U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[5U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][6U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[6U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][7U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[7U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][8U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[8U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][9U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[9U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0xaU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xaU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0xbU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xbU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0xcU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xcU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0xdU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xdU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0xeU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xeU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[0U][0xfU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xfU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][1U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[1U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][2U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[2U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][3U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[3U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][4U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[4U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][5U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[5U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][6U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[6U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][7U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[7U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][8U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[8U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][9U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[9U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0xaU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xaU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0xbU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xbU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0xcU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xcU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0xdU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xdU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0xeU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xeU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[1U][0xfU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xfU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][1U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[1U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][2U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[2U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][3U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[3U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][4U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[4U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][5U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[5U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][6U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[6U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][7U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[7U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][8U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[8U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][9U] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[9U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0xaU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xaU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0xbU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xbU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0xcU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xcU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0xdU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xdU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0xeU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xeU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[2U][0xfU] 
                = (0x1ffU & mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
            vlSelf->mac_pipeline_tb__DOT__b[0xfU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][1U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[1U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][2U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[2U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][3U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[3U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][4U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[4U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][5U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[5U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][6U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[6U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][7U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[7U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][8U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[8U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][9U] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[9U] = (0xffU 
                                                   & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0xaU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xaU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0xbU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xbU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0xcU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xcU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0xdU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xdU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0xeU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xeU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            vlSelf->mac_pipeline_tb__DOT__a[3U][0xfU] 
                = (0x1ffU & ((IData)(0x7fU) - mac_pipeline_tb__DOT__unnamedblk1__DOT__av));
            vlSelf->mac_pipeline_tb__DOT__b[0xfU] = 
                (0xffU & vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
            co_await vlSelf->__VtrigSched_haf4c204a__0.trigger(0U, 
                                                               nullptr, 
                                                               "@(posedge mac_pipeline_tb.clk)", 
                                                               "mac_pipeline_tb.sv", 
                                                               27);
            co_await vlSelf->__VdlySched.delay(0x3e8ULL, 
                                               nullptr, 
                                               "mac_pipeline_tb.sv", 
                                               27);
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [0U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [0U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][0U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][0U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][1U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [1U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [1U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][1U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][1U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [1U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][1U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][1U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][1U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][1U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [1U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [1U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][2U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [2U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [2U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][2U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][2U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [2U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][2U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][2U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][2U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][2U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [2U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [2U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][3U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [3U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [3U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][3U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][3U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [3U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][3U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][3U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][3U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][3U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [3U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [3U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][4U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [4U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [4U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][4U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][4U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [4U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][4U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][4U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][4U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][4U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [4U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [4U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][5U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [5U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [5U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][5U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][5U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [5U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][5U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][5U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][5U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][5U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [5U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [5U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][6U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [6U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [6U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][6U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][6U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [6U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][6U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][6U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][6U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][6U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [6U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [6U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][7U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [7U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [7U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][7U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][7U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [7U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][7U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][7U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][7U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][7U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [7U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [7U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][8U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [8U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [8U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][8U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][8U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [8U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][8U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][8U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][8U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][8U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [8U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [8U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][9U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [0U]
                                                                          [9U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [9U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][9U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][9U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [9U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][9U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [0U][9U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [0U][9U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][9U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [9U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [9U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0xaU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [0U]
                                                                            [0xaU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xaU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0xaU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0xaU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0xaU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0xaU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [0U]
                                                [0xaU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [0U]
                                                [0xaU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0xaU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0xaU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xaU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0xbU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [0U]
                                                                            [0xbU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xbU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0xbU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0xbU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0xbU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0xbU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [0U]
                                                [0xbU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [0U]
                                                [0xbU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0xbU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0xbU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xbU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0xcU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [0U]
                                                                            [0xcU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xcU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0xcU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0xcU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0xcU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0xcU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [0U]
                                                [0xcU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [0U]
                                                [0xcU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0xcU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0xcU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xcU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0xdU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [0U]
                                                                            [0xdU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xdU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0xdU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0xdU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0xdU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0xdU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [0U]
                                                [0xdU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [0U]
                                                [0xdU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0xdU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0xdU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xdU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0xeU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [0U]
                                                                            [0xeU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xeU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0xeU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0xeU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0xeU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0xeU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [0U]
                                                [0xeU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [0U]
                                                [0xeU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0xeU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0xeU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xeU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [0U][0xfU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [0U]
                                                                            [0xfU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xfU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [0U][0xfU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [0U][0xfU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [0U]
                                               [0xfU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [0U][0xfU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [0U]
                                                [0xfU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [0U]
                                                [0xfU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=0\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[0U][0xfU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [0U]
                                                [0xfU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xfU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [0U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [0U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][0U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][0U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][1U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [1U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [1U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][1U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][1U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [1U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][1U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][1U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][1U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][1U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [1U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [1U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][2U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [2U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [2U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][2U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][2U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [2U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][2U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][2U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][2U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][2U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [2U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [2U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][3U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [3U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [3U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][3U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][3U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [3U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][3U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][3U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][3U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][3U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [3U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [3U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][4U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [4U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [4U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][4U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][4U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [4U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][4U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][4U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][4U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][4U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [4U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [4U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][5U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [5U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [5U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][5U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][5U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [5U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][5U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][5U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][5U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][5U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [5U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [5U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][6U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [6U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [6U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][6U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][6U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [6U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][6U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][6U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][6U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][6U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [6U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [6U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][7U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [7U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [7U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][7U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][7U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [7U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][7U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][7U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][7U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][7U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [7U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [7U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][8U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [8U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [8U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][8U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][8U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [8U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][8U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][8U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][8U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][8U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [8U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [8U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][9U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [1U]
                                                                          [9U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [9U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][9U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][9U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [9U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][9U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [1U][9U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [1U][9U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][9U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [9U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [9U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0xaU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [1U]
                                                                            [0xaU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xaU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0xaU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0xaU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0xaU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0xaU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [1U]
                                                [0xaU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [1U]
                                                [0xaU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0xaU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0xaU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xaU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0xbU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [1U]
                                                                            [0xbU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xbU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0xbU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0xbU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0xbU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0xbU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [1U]
                                                [0xbU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [1U]
                                                [0xbU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0xbU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0xbU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xbU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0xcU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [1U]
                                                                            [0xcU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xcU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0xcU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0xcU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0xcU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0xcU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [1U]
                                                [0xcU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [1U]
                                                [0xcU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0xcU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0xcU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xcU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0xdU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [1U]
                                                                            [0xdU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xdU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0xdU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0xdU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0xdU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0xdU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [1U]
                                                [0xdU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [1U]
                                                [0xdU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0xdU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0xdU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xdU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0xeU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [1U]
                                                                            [0xeU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xeU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0xeU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0xeU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0xeU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0xeU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [1U]
                                                [0xeU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [1U]
                                                [0xeU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0xeU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0xeU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xeU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [1U][0xfU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [1U]
                                                                            [0xfU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xfU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [1U][0xfU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [1U][0xfU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [1U]
                                               [0xfU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [1U][0xfU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [1U]
                                                [0xfU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [1U]
                                                [0xfU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=1\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[1U][0xfU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [1U]
                                                [0xfU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xfU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [0U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [0U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][0U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][0U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][1U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [1U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [1U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][1U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][1U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [1U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][1U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][1U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][1U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][1U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [1U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [1U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][2U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [2U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [2U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][2U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][2U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [2U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][2U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][2U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][2U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][2U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [2U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [2U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][3U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [3U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [3U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][3U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][3U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [3U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][3U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][3U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][3U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][3U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [3U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [3U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][4U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [4U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [4U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][4U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][4U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [4U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][4U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][4U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][4U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][4U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [4U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [4U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][5U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [5U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [5U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][5U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][5U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [5U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][5U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][5U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][5U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][5U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [5U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [5U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][6U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [6U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [6U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][6U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][6U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [6U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][6U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][6U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][6U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][6U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [6U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [6U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][7U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [7U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [7U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][7U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][7U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [7U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][7U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][7U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][7U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][7U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [7U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [7U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][8U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [8U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [8U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][8U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][8U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [8U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][8U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][8U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][8U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][8U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [8U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [8U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][9U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [2U]
                                                                          [9U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [9U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][9U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][9U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [9U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][9U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [2U][9U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [2U][9U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][9U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [9U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [9U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0xaU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [2U]
                                                                            [0xaU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xaU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0xaU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0xaU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0xaU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0xaU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [2U]
                                                [0xaU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [2U]
                                                [0xaU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0xaU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0xaU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xaU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0xbU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [2U]
                                                                            [0xbU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xbU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0xbU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0xbU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0xbU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0xbU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [2U]
                                                [0xbU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [2U]
                                                [0xbU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0xbU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0xbU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xbU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0xcU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [2U]
                                                                            [0xcU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xcU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0xcU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0xcU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0xcU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0xcU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [2U]
                                                [0xcU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [2U]
                                                [0xcU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0xcU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0xcU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xcU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0xdU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [2U]
                                                                            [0xdU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xdU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0xdU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0xdU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0xdU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0xdU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [2U]
                                                [0xdU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [2U]
                                                [0xdU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0xdU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0xdU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xdU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0xeU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [2U]
                                                                            [0xeU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xeU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0xeU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0xeU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0xeU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0xeU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [2U]
                                                [0xeU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [2U]
                                                [0xeU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0xeU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0xeU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xeU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [2U][0xfU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [2U]
                                                                            [0xfU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xfU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [2U][0xfU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [2U][0xfU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [2U]
                                               [0xfU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [2U][0xfU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [2U]
                                                [0xfU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [2U]
                                                [0xfU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=2\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[2U][0xfU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [2U]
                                                [0xfU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xfU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [0U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [0U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][0U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][0U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][1U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [1U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [1U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][1U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][1U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [1U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][1U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][1U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][1U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][1U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [1U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [1U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][2U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [2U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [2U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][2U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][2U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [2U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][2U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][2U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][2U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][2U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [2U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [2U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][3U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [3U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [3U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][3U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][3U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [3U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][3U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][3U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][3U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][3U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [3U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [3U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][4U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [4U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [4U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][4U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][4U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [4U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][4U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][4U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][4U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][4U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [4U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [4U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][5U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [5U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [5U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][5U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][5U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [5U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][5U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][5U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][5U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][5U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [5U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [5U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][6U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [6U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [6U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][6U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][6U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [6U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][6U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][6U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][6U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][6U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [6U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [6U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][7U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [7U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [7U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][7U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][7U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [7U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][7U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][7U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][7U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][7U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [7U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [7U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][8U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [8U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [8U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][8U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][8U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [8U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][8U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][8U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][8U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][8U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [8U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [8U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][9U] != (0x1ffffU 
                                           & VL_MULS_III(17, 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,9, 
                                                                          vlSelf->mac_pipeline_tb__DOT__a
                                                                          [3U]
                                                                          [9U])), 
                                                         (0x1ffffU 
                                                          & VL_EXTENDS_II(17,8, 
                                                                          vlSelf->mac_pipeline_tb__DOT__b
                                                                          [9U]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][9U] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][9U])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [9U]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][9U]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                              [3U][9U] 
                                              != vlSelf->mac_pipeline_tb__DOT__piped
                                              [3U][9U]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][9U] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [9U]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [9U]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0xaU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [3U]
                                                                            [0xaU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xaU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0xaU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0xaU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0xaU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0xaU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [3U]
                                                [0xaU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [3U]
                                                [0xaU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0xaU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0xaU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xaU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0xbU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [3U]
                                                                            [0xbU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xbU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0xbU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0xbU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0xbU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0xbU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [3U]
                                                [0xbU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [3U]
                                                [0xbU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0xbU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0xbU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xbU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0xcU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [3U]
                                                                            [0xcU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xcU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0xcU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0xcU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0xcU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0xcU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [3U]
                                                [0xcU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [3U]
                                                [0xcU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0xcU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0xcU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xcU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0xdU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [3U]
                                                                            [0xdU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xdU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0xdU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0xdU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0xdU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0xdU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [3U]
                                                [0xdU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [3U]
                                                [0xdU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0xdU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0xdU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xdU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0xeU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [3U]
                                                                            [0xeU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xeU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0xeU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0xeU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0xeU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0xeU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [3U]
                                                [0xeU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [3U]
                                                [0xeU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0xeU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0xeU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xeU]));
            if (VL_UNLIKELY(((vlSelf->mac_pipeline_tb__DOT__plain
                              [3U][0xfU] != (0x1ffffU 
                                             & VL_MULS_III(17, 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,9, 
                                                                            vlSelf->mac_pipeline_tb__DOT__a
                                                                            [3U]
                                                                            [0xfU])), 
                                                           (0x1ffffU 
                                                            & VL_EXTENDS_II(17,8, 
                                                                            vlSelf->mac_pipeline_tb__DOT__b
                                                                            [0xfU]))))) 
                             | (vlSelf->mac_pipeline_tb__DOT__packed_direct
                                [3U][0xfU] != vlSelf->mac_pipeline_tb__DOT__plain
                                [3U][0xfU])))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:32: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: direct product mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 32, "");
            }
            if (VL_UNLIKELY((((0xffffff80U != mac_pipeline_tb__DOT__unnamedblk1__DOT__av) 
                              | (0xffffff80U != vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv)) 
                             & ((VL_EXTENDS_II(32,17, 
                                               vlSelf->mac_pipeline_tb__DOT__piped
                                               [3U]
                                               [0xfU]) 
                                 != vlSelf->mac_pipeline_tb__DOT__previous
                                 [3U][0xfU]) | (vlSelf->mac_pipeline_tb__DOT__packed_piped
                                                [3U]
                                                [0xfU] 
                                                != 
                                                vlSelf->mac_pipeline_tb__DOT__piped
                                                [3U]
                                                [0xfU]))))) {
                VL_WRITEF("[%0t] %%Fatal: mac_pipeline_tb.sv:35: Assertion failed in %Nmac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6: pipeline product/latency mismatch a=%0d b=%0d lane=3\n",
                          64,VL_TIME_UNITED_Q(1000),
                          -9,vlSymsp->name(),32,mac_pipeline_tb__DOT__unnamedblk1__DOT__av,
                          32,vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
                VL_STOP_MT("mac_pipeline_tb.sv", 35, "");
            }
            vlSelf->mac_pipeline_tb__DOT__previous[3U][0xfU] 
                = VL_MULS_III(32, VL_EXTENDS_II(32,9, 
                                                vlSelf->mac_pipeline_tb__DOT__a
                                                [3U]
                                                [0xfU]), 
                              VL_EXTENDS_II(32,8, vlSelf->mac_pipeline_tb__DOT__b
                                            [0xfU]));
            vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv 
                = ((IData)(1U) + vlSelf->mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv);
        }
        mac_pipeline_tb__DOT__unnamedblk1__DOT__av 
            = ((IData)(1U) + mac_pipeline_tb__DOT__unnamedblk1__DOT__av);
    }
    VL_WRITEF("PASS: 98,304 operand pairs, mixed adjacent lanes, packed/plain, latencies 1/2\n");
    VL_FINISH_MT("mac_pipeline_tb.sv", 42, "");
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vmac_pipeline_tb___024root___dump_triggers__act(Vmac_pipeline_tb___024root* vlSelf);
#endif  // VL_DEBUG

void Vmac_pipeline_tb___024root___eval_triggers__act(Vmac_pipeline_tb___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vmac_pipeline_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vmac_pipeline_tb___024root___eval_triggers__act\n"); );
    // Body
    vlSelf->__VactTriggered.set(0U, ((IData)(vlSelf->mac_pipeline_tb__DOT__clk) 
                                     & (~ (IData)(vlSelf->__Vtrigprevexpr___TOP__mac_pipeline_tb__DOT__clk__0))));
    vlSelf->__VactTriggered.set(1U, ((~ (IData)(vlSelf->mac_pipeline_tb__DOT__clk)) 
                                     & (IData)(vlSelf->__Vtrigprevexpr___TOP__mac_pipeline_tb__DOT__clk__0)));
    vlSelf->__VactTriggered.set(2U, vlSelf->__VdlySched.awaitingCurrentTime());
    vlSelf->__Vtrigprevexpr___TOP__mac_pipeline_tb__DOT__clk__0 
        = vlSelf->mac_pipeline_tb__DOT__clk;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vmac_pipeline_tb___024root___dump_triggers__act(vlSelf);
    }
#endif
}
