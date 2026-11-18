// Experimental logical KV slice -> relative byte span. Not in the encoder,
// SYS3 executor or deployed app. An errored output MUST be rejected before DDR.
// The host supplies the padded INT8 row stride from KvCacheLayout. The complete
// cache must fit the window, even when this particular slice would fit alone.
// Two elastic stages; metadata is captured on acceptance and stable under stall.
module kv_cache_span (
    input logic clk, reset,
    input logic in_valid,
    output logic in_ready,
    input logic [32:0] window_bytes,
    input logic [31:0] cache_offset, row_stride, capacity,
    input logic [15:0] layers, layer,
    input logic value_matrix,
    input logic [31:0] first_token, token_count,
    output logic out_valid,
    input logic out_ready,
    output logic [31:0] offset,
    output logic [32:0] bytes,
    output logic [1:0] error_code
);
    logic stage_valid, stage_ready;
    logic [63:0] matrix_bytes, first_bytes, slice_bytes;
    logic [32:0] window_reg;
    logic [31:0] cache_reg;
    logic [15:0] layers_reg, layer_reg;
    logic value_reg, invalid_config, invalid_slice;
    assign stage_ready = !out_valid || out_ready;
    assign in_ready = !reset && (!stage_valid || stage_ready);

    always_ff @(posedge clk) begin
        if (reset) begin
            stage_valid <= 0;
            out_valid <= 0;
            offset <= 0;
            bytes <= 0;
            error_code <= 0;
        end else begin
            if (in_ready) begin
                stage_valid <= in_valid;
                if (in_valid) begin
                    matrix_bytes <= 64'(capacity) * 64'(row_stride);
                    first_bytes <= 64'(first_token) * 64'(row_stride);
                    slice_bytes <= 64'(token_count) * 64'(row_stride);
                    window_reg <= window_bytes;
                    cache_reg <= cache_offset;
                    layers_reg <= layers;
                    layer_reg <= layer;
                    value_reg <= value_matrix;
                    invalid_config <= window_bytes==0 || window_bytes>33'h100000000
                        || capacity==0 || layers==0 || row_stride==0
                        || row_stride[3:0]!=0 || cache_offset[3:0]!=0;
                    invalid_slice <= layer>=layers || token_count==0
                        || {1'b0,first_token}+{1'b0,token_count}>{1'b0,capacity};
                end
            end
            if (stage_ready) begin
                out_valid <= stage_valid;
                if (stage_valid) begin
                    logic [81:0] total_end, slice_start, slice_end;
                    logic bad_config, bad_slice;
                    // 82 bits preserve the full product of UINT16 layer count
                    // and two UINT32 factors; never validate a truncated sum.
                    total_end = 82'(cache_reg) + 82'(layers_reg)*82'd2*82'(matrix_bytes);
                    slice_start = 82'(cache_reg) + 82'({layer_reg,value_reg})*82'(matrix_bytes) + 82'(first_bytes);
                    slice_end = slice_start + 82'(slice_bytes);
                    bad_config = invalid_config || total_end>82'(window_reg);
                    bad_slice = invalid_slice || slice_start>=82'h100000000 || slice_end>82'(window_reg);
                    error_code <= bad_config ? 2'd1 : bad_slice ? 2'd2 : 2'd0;
                    offset <= bad_config || bad_slice ? 0 : 32'(slice_start);
                    bytes <= bad_config || bad_slice ? 0 : 33'(slice_bytes);
                end
            end
        end
    end
endmodule
