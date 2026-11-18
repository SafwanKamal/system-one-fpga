// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vmac_pipeline_tb.h for the primary calling header

#ifndef VERILATED_VMAC_PIPELINE_TB___024ROOT_H_
#define VERILATED_VMAC_PIPELINE_TB___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vmac_pipeline_tb__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vmac_pipeline_tb___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ mac_pipeline_tb__DOT__clk;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__mac_pipeline_tb__DOT__clk__0;
    CData/*0:0*/ __VactContinue;
    IData/*31:0*/ mac_pipeline_tb__DOT__unnamedblk1__DOT__unnamedblk2__DOT__bv;
    IData/*31:0*/ __VactIterCount;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__a;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__b;
    VlUnpacked<VlUnpacked<IData/*16:0*/, 16>, 4> mac_pipeline_tb__DOT__plain;
    VlUnpacked<VlUnpacked<IData/*16:0*/, 16>, 4> mac_pipeline_tb__DOT__packed_direct;
    VlUnpacked<VlUnpacked<IData/*16:0*/, 16>, 4> mac_pipeline_tb__DOT__piped;
    VlUnpacked<VlUnpacked<IData/*16:0*/, 16>, 4> mac_pipeline_tb__DOT__packed_piped;
    VlUnpacked<VlUnpacked<IData/*31:0*/, 16>, 4> mac_pipeline_tb__DOT__previous;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__direct_dut__DOT__operand_a;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__direct_dut__DOT__operand_b;
    VlUnpacked<VlUnpacked<IData/*16:0*/, 16>, 4> mac_pipeline_tb__DOT__direct_dut__DOT__gen_plain__DOT__product_reg;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__packed_dut__DOT__operand_a;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__packed_dut__DOT__operand_b;
    VlUnpacked<VlUnpacked<QData/*42:0*/, 16>, 2> mac_pipeline_tb__DOT__packed_dut__DOT__gen_packed__DOT__packed_reg;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_a;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__pipeline_dut__DOT__operand_b;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__a_reg;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_inputs__DOT__b_reg;
    VlUnpacked<VlUnpacked<IData/*16:0*/, 16>, 4> mac_pipeline_tb__DOT__pipeline_dut__DOT__gen_plain__DOT__product_reg;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_a;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__operand_b;
    VlUnpacked<VlUnpacked<SData/*8:0*/, 16>, 4> mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__a_reg;
    VlUnpacked<CData/*7:0*/, 16> mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_inputs__DOT__b_reg;
    VlUnpacked<VlUnpacked<QData/*42:0*/, 16>, 2> mac_pipeline_tb__DOT__packed_pipeline_dut__DOT__gen_packed__DOT__packed_reg;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_haf4c1a17__0;
    VlTriggerScheduler __VtrigSched_haf4c204a__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<3> __VactTriggered;
    VlTriggerVec<3> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vmac_pipeline_tb__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vmac_pipeline_tb___024root(Vmac_pipeline_tb__Syms* symsp, const char* v__name);
    ~Vmac_pipeline_tb___024root();
    VL_UNCOPYABLE(Vmac_pipeline_tb___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
