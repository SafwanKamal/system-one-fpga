// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vmac_pipeline_tb__pch.h"
#include "Vmac_pipeline_tb.h"
#include "Vmac_pipeline_tb___024root.h"

// FUNCTIONS
Vmac_pipeline_tb__Syms::~Vmac_pipeline_tb__Syms()
{
}

Vmac_pipeline_tb__Syms::Vmac_pipeline_tb__Syms(VerilatedContext* contextp, const char* namep, Vmac_pipeline_tb* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_mac_pipeline_tb.configure(this, name(), "mac_pipeline_tb", "mac_pipeline_tb", -9, VerilatedScope::SCOPE_OTHER);
    __Vscope_mac_pipeline_tb__unnamedblk1__unnamedblk2__unnamedblk5__unnamedblk6.configure(this, name(), "mac_pipeline_tb.unnamedblk1.unnamedblk2.unnamedblk5.unnamedblk6", "unnamedblk6", -9, VerilatedScope::SCOPE_OTHER);
}
