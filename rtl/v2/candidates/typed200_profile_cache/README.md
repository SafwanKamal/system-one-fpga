# Separate typed200_profile_cache candidate

Only AXIL endpoint and guard change from frozen typed200_flush. Thirty-two
registered byte equalities replace the wide request-profile compare at admission.
Each flag is exactly equivalent to its stored byte, updated on the same write
edge/byte strobe; reset flags reflect equality to the zeroed bank. Commands do
not clear flags because they do not clear bank values. All256 digest bits remain
checked. No request/admission cycle, validation/deadline pause or numerical change.
Current quiet/error/epoch/shape/request and full fresh-frame checks remain intact.
Raw request banks may be pruned by synthesis if now unobservable; no ABI CSR reads
them. Only this endpoint may supply the new guard equality input; standalone guard
equivalence is insufficient. Full endpoint sequential equivalence is required.
Functional/physical benefit and hardware qualification are pending. Qualified
sources/package/recovery, numerical baselines and all prior candidates stay frozen.
