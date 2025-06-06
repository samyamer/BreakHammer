#! /bin/bash

if [ ! -f "breakhammer_artifact.tar" ]; then
    echo "[INFO] Podman image unavailable. Saving breakhammer_artifact build for compute nodes to load"
    podman save -o breakhammer_artifact.tar breakhammer_artifact
fi

AE_SLURM_PART_NAME="cpu_part"

echo "[INFO] Generating Ramulator2 configurations and run scripts for attacker workloads"
podman run --rm -v $PWD:/app breakhammer_artifact "python3 setup_slurm_podman.py \
    --working_directory $PWD \
    --base_config /app/base_config.yaml \
    --trace_combination /app/mixes/microattack.mix \
    --trace_directory /app/cputraces \
    --result_directory /app/ae_results/microattack \
    --partition_name $AE_SLURM_PART_NAME"

echo "[INFO] Starting Ramulator2 attacker simulations"
python3 execute_run_script.py --slurm

echo "[INFO] Generating Ramulator2 configurations and run scripts for benign workloads"
podman run --rm -v $PWD:/app breakhammer_artifact "python3 setup_slurm_podman.py \
    --working_directory $PWD \
    --base_config /app/base_config.yaml \
    --trace_combination /app/mixes/microbenign.mix \
    --trace_directory /app/cputraces \
    --result_directory /app/ae_results/microbenign \
    --partition_name $AE_SLURM_PART_NAME"

echo "[INFO] Starting Ramulator2 benign simulations"
python3 execute_run_script.py --slurm

echo "[INFO] You can track run status with the <check_run_status.sh> script"
rm "$PWD/run.sh" 