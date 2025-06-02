import os
import yaml
import copy
import argparse
import pandas as pd

from scripts.run_config import *

argparser = argparse.ArgumentParser(
    prog="RunPersonal",
    description="Run ramulator2 simulations on a personal computer"
)

argparser.add_argument("-wd", "--working_directory")
argparser.add_argument("-bc", "--base_config")
argparser.add_argument("-tc", "--trace_combination")
argparser.add_argument("-td", "--trace_directory")
argparser.add_argument("-rd", "--result_directory")
argparser.add_argument("-a", "--alternate")
argparser.add_argument("-bh", "--break_hammer")

args = argparser.parse_args()

WORK_DIR = args.working_directory
BASE_CONFIG_FILE = args.base_config
TRACE_COMBINATION_FILE = args.trace_combination
TRACE_DIR = args.trace_directory
BASE_DIR = args.result_directory

CMD_HEADER = "#! /bin/bash"
BASE_CMD = f"{WORK_DIR}/ramulator2"

BASE_CONFIG = None

ALTERNATE = True if args.alternate == '1' else False
BH = True if args.break_hammer == '1' else False


with open(BASE_CONFIG_FILE, "r") as f:
    try:
        BASE_CONFIG = yaml.safe_load(f)
    except Exception as e:
        print(e)

if BASE_CONFIG == None:
    print("[ERR] Could not read base config.")
    exit(0)

BASE_CONFIG["Frontend"]["num_expected_insts"] = NUM_EXPECTED_INSTS


if NUM_MAX_CYCLES > 0:
    BASE_CONFIG["Frontend"]["num_max_cycles"] = NUM_MAX_CYCLES 


TRACE_COMBS = {}
TRACE_TYPES = {}
with open(TRACE_COMBINATION_FILE, "r") as f:
    for line in f:
        line = line.strip()
        tokens = line.split(',')
        trace_name = tokens[0]
        trace_type = tokens[1]
        traces = tokens[2:]
        TRACE_COMBS[trace_name] = traces
        TRACE_TYPES[trace_name] = trace_type

def create_dirs(dir):
    for mitigation in mitigation_list:
        for path in [
                f"{dir}/{mitigation}/stats",
                f"{dir}/{mitigation}/configs",
                f"{dir}/{mitigation}/cmd_count",
                f"{dir}/{mitigation}/mem_latency"

            ]:
            if not os.path.exists(path):
                os.makedirs(path)

def get_singlecore_run_commands():
    run_commands = []
    singlecore_params = get_singlecore_params_list()
    singlecore_traces, _ = get_trace_lists(TRACE_COMBINATION_FILE)
    for config in singlecore_params:
        mitigation, throttle_type, _, tRH, flat_thresh, dynamic_thresh = config
        stat_str = make_stat_str(config[1:])
        for trace in singlecore_traces:
            result_filename = f"{RESULT_DIR}/{mitigation}/stats/{stat_str}_{trace}.txt"
            config_filename = f"{RESULT_DIR}/{mitigation}/configs/{stat_str}_{trace}.yaml"
            cmd_count_filename = f"{RESULT_DIR}/{mitigation}/cmd_count/{stat_str}_{trace}.cmd.count"
            latency_dump_filename = f"{RESULT_DIR}/{mitigation}/mem_latency/{stat_str}_{trace}.memlat.dump"
            config = copy.deepcopy(BASE_CONFIG)

            config["Frontend"]["lat_dump_path"] = latency_dump_filename 
            config["MemorySystem"][CONTROLLER]["plugins"][0]["ControllerPlugin"]["path"] = cmd_count_filename
            config["MemorySystem"][CONTROLLER]["RowPolicy"]["cap"] = COLUMN_CAP 
            config["MemorySystem"][CONTROLLER]["plugins"].append({
                "ControllerPlugin": {
                    "impl": "Throttler",
                    "throttle_type": throttle_type,
                    "throttle_flat_thresh": flat_thresh,
                    "throttle_dynamic_thresh": dynamic_thresh,
                    "window_period_ns": 64000000,
                    "blacklist_mshr_decrement": 1,
                    "breakhammer_plus": True
                }
            })
                
            config["Frontend"]["traces"] = [f"{TRACE_DIR}/{trace}"]

            add_mitigation(config, mitigation, tRH)

            config_file = open(config_filename, "w")
            yaml.dump(config, config_file, default_flow_style=False)
            config_file.close()

            cmd = f"{BASE_CMD} -f {config_filename} > {result_filename} 2>&1"           
            run_commands.append(cmd)

    return run_commands

def get_multicore_run_commands():
    run_commands = []
    multicore_params = get_multicore_params_list(params_list)
    _, multicore_traces = get_trace_lists(TRACE_COMBINATION_FILE)
    for config in multicore_params:
        mitigation, throttle_type, _, tRH, flat_thresh, dynamic_thresh = config
        stat_str = make_stat_str(config[1:])
        for trace in multicore_traces:
            trace_comb = TRACE_COMBS[trace]
            trace_type = TRACE_TYPES[trace]
        
            result_filename = f"{RESULT_DIR}/{mitigation}/stats/{stat_str}_{trace}.txt"
            config_filename = f"{RESULT_DIR}/{mitigation}/configs/{stat_str}_{trace}.yaml"
            cmd_count_filename = f"{RESULT_DIR}/{mitigation}/cmd_count/{stat_str}_{trace}.cmd.count"
            latency_dump_filename = f"{RESULT_DIR}/{mitigation}/mem_latency/{stat_str}_{trace}.memlat.dump"
            config = copy.deepcopy(BASE_CONFIG)

            config["Frontend"]["lat_dump_path"] = latency_dump_filename 
            config["MemorySystem"][CONTROLLER]["plugins"][0]["ControllerPlugin"]["path"] = cmd_count_filename
            config["MemorySystem"][CONTROLLER]["RowPolicy"]["cap"] = COLUMN_CAP 
            config["MemorySystem"][CONTROLLER]["plugins"].append({
                "ControllerPlugin": {
                    "impl": "Throttler",
                    "throttle_type": throttle_type,
                    "throttle_flat_thresh": flat_thresh,
                    "throttle_dynamic_thresh": dynamic_thresh,
                    "window_period_ns": 64000000, 
                    "snapshot_clk": -1,
                    "blacklist_max_mshr": 5,
                    "blacklist_mshr_decrement": 1,
                    "breakhammer_plus": True
                }
            })

            traces = []
            no_wait_traces = []
            for idx in range(len(trace_type)):
                cur_type = trace_type[idx]
                cur_trace = f"{TRACE_DIR}/{trace_comb[idx]}"
                if cur_type != "A":
                    traces.append(cur_trace)
                else:
                    no_wait_traces.append(cur_trace)
                
            config["Frontend"]["traces"] = traces
            if len(no_wait_traces) > 0:
                config["Frontend"]["no_wait_traces"] = no_wait_traces

            add_mitigation(config, mitigation, tRH)

            config_file = open(config_filename, "w")
            yaml.dump(config, config_file, default_flow_style=False)
            config_file.close()

            cmd = f"{BASE_CMD} -f {config_filename} > {result_filename} 2>&1"           
            run_commands.append(cmd)

    return run_commands


mitigation_list = ["Hydra", "RFM"]
# List of evaluated RowHammer thresholds
# tRH_list = [4096, 2048, 1024, 512, 256, 128, 64]
tRH_list = [1024]
# BreakHammer parameters
flat_thresh_list = [32]
dynamic_thresh_list = [0.65]
thresh_type_list = ["MEAN"]
cache_only_list = [False]

params_list = [
    mitigation_list,
    thresh_type_list,
    cache_only_list,
    tRH_list,
    flat_thresh_list,
    dynamic_thresh_list
]
# single_cmds = get_singlecore_run_commands()
single_cmds = []

BASE_CONFIG["Frontend"]["alternate_d"] = True

RESULT_DIR = BASE_DIR+ "/alternate_BH"
create_dirs(RESULT_DIR)
multi_cmds = get_multicore_run_commands() # alternate and BH
with open("run.sh", "w") as f:
    for cmd in single_cmds + multi_cmds:
        f.write(f"{cmd}\n")


BASE_CONFIG["Frontend"]["alternate_d"] = False
RESULT_DIR = BASE_DIR+ "/no_alternate_BH" # no alternate + BH
create_dirs(RESULT_DIR)

multi_cmds = get_multicore_run_commands()
with open("run.sh", "a") as f:
    for cmd in single_cmds + multi_cmds:
        f.write(f"{cmd}\n")

BASE_CONFIG["Frontend"]["alternate_d"] = False
RESULT_DIR = BASE_DIR+ "/no_alternate_noBH" # no alternate no BH

tRH_list = [1024]
# BreakHammer parameters
flat_thresh_list = [0]
dynamic_thresh_list = [0.0]
thresh_type_list = ["NONE"]
cache_only_list = [False]

params_list = [
    mitigation_list,
    thresh_type_list,
    cache_only_list,
    tRH_list,
    flat_thresh_list,
    dynamic_thresh_list
]

create_dirs(RESULT_DIR)
multi_cmds = get_multicore_run_commands()
with open("run.sh", "a") as f:
    for cmd in single_cmds + multi_cmds:
        f.write(f"{cmd}\n")


os.system("chmod uog+x run.sh")