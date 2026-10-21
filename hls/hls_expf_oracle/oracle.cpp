// Bit-exact hls::expf oracle for host-side references (C simulation only).
#include <hls_math.h>
void hls_expf_top(const float *x,float *y,int n){for(int i=0;i<n;i++)y[i]=hls::expf(x[i]);}
