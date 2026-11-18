// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VMAC_PIPELINE_TB__SYMS_H_
#define VERILATED_VMAC_PIPELINE_TB__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vmac_pipeline_tb.h"

// INCLUDE MODULE CLASSES
#include "Vmac_pipeline_tb___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vmac_pipeline_tb__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vmac_pipeline_tb* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vmac_pipeline_tb___024root     TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_mac_pipeline_tb;
    VerilatedScope __Vscope_mac_pipeline_tb__unnamedblk1__unnamedblk2__unnamedblk5__unnamedblk6;

    // CONSTRUCTORS
    Vmac_pipeline_tb__Syms(VerilatedContext* contextp, const char* namep, Vmac_pipeline_tb* modelp);
    ~Vmac_pipeline_tb__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
