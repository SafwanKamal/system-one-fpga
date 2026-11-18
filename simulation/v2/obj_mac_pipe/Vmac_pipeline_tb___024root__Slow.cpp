// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vmac_pipeline_tb.h for the primary calling header

#include "Vmac_pipeline_tb__pch.h"
#include "Vmac_pipeline_tb__Syms.h"
#include "Vmac_pipeline_tb___024root.h"

void Vmac_pipeline_tb___024root___ctor_var_reset(Vmac_pipeline_tb___024root* vlSelf);

Vmac_pipeline_tb___024root::Vmac_pipeline_tb___024root(Vmac_pipeline_tb__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vmac_pipeline_tb___024root___ctor_var_reset(this);
}

void Vmac_pipeline_tb___024root::__Vconfigure(bool first) {
    if (false && first) {}  // Prevent unused
}

Vmac_pipeline_tb___024root::~Vmac_pipeline_tb___024root() {
}
