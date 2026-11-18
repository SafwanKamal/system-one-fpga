/* Fixed existing validation-tuned CLINC decision rule; no host head math. */
#ifndef R5_CLINC_POLICY_H
#define R5_CLINC_POLICY_H
#include <stdint.h>
#define CLINC_TAU 0.36
#define CLINC_OOS_LABEL 150
/* exp(x), x<=0: range reduction and Taylor polynomial, without libc/libm.
 * The reduced argument is in [-ln(2),0]; degree18 truncation is <2e-20.
 * IEEE754 scaling handles very small probabilities; doubles use R5 VFP.
 */
static double policy_exp_negative(double x) {
 if(x < -745.0)return 0.0;
 uint32_t n=(uint32_t)(-x*1.4426950408889634074);
 double r=x+(double)n*0.69314718055994530942;
 double term=1.0,sum=1.0;
 for(uint32_t k=1;k<=18;k++){term*=r/(double)k;sum+=term;}
 union {uint64_t bits;double value;} scale;
 if(n<=1022)scale.bits=(uint64_t)(1023-n)<<52;
 else if(n<=1074)scale.bits=(uint64_t)1<<(1074-n);
 else return 0.0;
 return sum*scale.value;
}
static uint32_t calibrated_clinc_label(const double *scores,uint32_t count,uint32_t winner) {
 double maximum=scores[winner],denominator=0.0;
 for(uint32_t c=0;c<count;c++)denominator+=policy_exp_negative(scores[c]-maximum);
 return 1.0/denominator < CLINC_TAU ? CLINC_OOS_LABEL : winner;
}
#endif
