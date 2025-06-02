#! /bin/bash

echo "[INFO] Generating Ramulator2 configurations and run scripts for alternating attacker workloads (This might take a while, e.g., >3 mins)"
python3 setup_personalcomputer.py \
    --working_directory "$PWD" \
    --base_config "$PWD/base_config.yaml" \
    --trace_combination "$PWD/mixes/alternating_attack.mix" \
    --trace_directory "$PWD/cputraces" \
    --result_directory "$PWD/alternating_attack" \
    --alternate 1 \
    --break_hammer 1

# echo "[INFO] Starting Ramulator2 alternating BH simulations"
# python3 execute_run_script.py

# echo "[INFO] Generating Ramulator2 configurations and run scripts for non alternating BH workloads (This might take a while, e.g., >3 mins)"
# python3 setup_personalcomputer.py \
#     --working_directory "$PWD" \
#     --base_config "$PWD/base_config.yaml" \
#     --trace_combination "$PWD/mixes/alternating_attack.mix" \
#     --trace_directory "$PWD/cputraces" \
#     --result_directory "$PWD/alternating_attack/no_alternate_BH" \
#     --alternate 0 \
#     --break_hammer 1

# echo "[INFO] Starting Ramulator2 non alternating no BH simulations"
# python3 execute_run_script.py

# echo "[INFO] Generating Ramulator2 configurations and run scripts for no alternate no BH workloads (This might take a while, e.g., >3 mins)"
# python3 setup_personalcomputer.py \
#     --working_directory "$PWD" \
#     --base_config "$PWD/base_config.yaml" \
#     --trace_combination "$PWD/mixes/alternating_attack.mix" \
#     --trace_directory "$PWD/cputraces" \
#     --result_directory "$PWD/alternating_attack/no_alternate_noBH" \
#     --alternate 0 \
#     --break_hammer 0

# echo "[INFO] Starting Ramulator2 benign simulations"
# python3 execute_run_script.py

# echo "[INFO] You can track run status with the <check_run_status.sh> script"