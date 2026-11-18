// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vmac_pipeline_tb__pch.h"

//============================================================
// Constructors

Vmac_pipeline_tb::Vmac_pipeline_tb(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vmac_pipeline_tb__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vmac_pipeline_tb::Vmac_pipeline_tb(const char* _vcname__)
    : Vmac_pipeline_tb(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vmac_pipeline_tb::~Vmac_pipeline_tb() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vmac_pipeline_tb___024root___eval_debug_assertions(Vmac_pipeline_tb___024root* vlSelf);
#endif  // VL_DEBUG
void Vmac_pipeline_tb___024root___eval_static(Vmac_pipeline_tb___024root* vlSelf);
void Vmac_pipeline_tb___024root___eval_initial(Vmac_pipeline_tb___024root* vlSelf);
void Vmac_pipeline_tb___024root___eval_settle(Vmac_pipeline_tb___024root* vlSelf);
void Vmac_pipeline_tb___024root___eval(Vmac_pipeline_tb___024root* vlSelf);

void Vmac_pipeline_tb::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vmac_pipeline_tb::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vmac_pipeline_tb___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vmac_pipeline_tb___024root___eval_static(&(vlSymsp->TOP));
        Vmac_pipeline_tb___024root___eval_initial(&(vlSymsp->TOP));
        Vmac_pipeline_tb___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vmac_pipeline_tb___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vmac_pipeline_tb::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vmac_pipeline_tb::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vmac_pipeline_tb::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vmac_pipeline_tb___024root___eval_final(Vmac_pipeline_tb___024root* vlSelf);

VL_ATTR_COLD void Vmac_pipeline_tb::final() {
    Vmac_pipeline_tb___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vmac_pipeline_tb::hierName() const { return vlSymsp->name(); }
const char* Vmac_pipeline_tb::modelName() const { return "Vmac_pipeline_tb"; }
unsigned Vmac_pipeline_tb::threads() const { return 1; }
void Vmac_pipeline_tb::prepareClone() const { contextp()->prepareClone(); }
void Vmac_pipeline_tb::atClone() const {
    contextp()->threadPoolpOnClone();
}

//============================================================
// Trace configuration

VL_ATTR_COLD void Vmac_pipeline_tb::trace(VerilatedVcdC* tfp, int levels, int options) {
    vl_fatal(__FILE__, __LINE__, __FILE__,"'Vmac_pipeline_tb::trace()' called on model that was Verilated without --trace option");
}
