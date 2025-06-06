#include <functional>
#include <limits>

#include "base/utils.h"
#include "frontend/frontend.h"
#include "translation/translation.h"
#include "frontend/impl/processor/bhO3/bhO3.h"
#include "frontend/impl/processor/bhO3/bhcore.h"
#include "frontend/impl/processor/bhO3/bhllc.h"

namespace Ramulator {

void BHO3::init() {
  m_clock_ratio = param<uint>("clock_ratio").required();
  
  // Core params
  std::vector<std::string> empty_trace;
  std::vector<std::string> trace_list = param<std::vector<std::string>>("traces").desc("A list of traces.").required();
  std::vector<std::string> no_wait_trace_list = param<std::vector<std::string>>("no_wait_traces").desc("Traces that do not block program termination.").default_val(empty_trace);
  m_num_cores = trace_list.size() + no_wait_trace_list.size();
  m_num_blocking_cores = trace_list.size();
  
  bool def_traces_cache_only = param<bool>("trace_cache_only").default_val(false);
  bool no_wait_traces_cache_only = param<bool>("no_wait_trace_cache_only").default_val(false);

  int ipc   = param<int>("ipc").desc("IPC of the SimpleO3 core.").default_val(4);
  int depth = param<int>("inst_window_depth").desc("Instruction window size of the SimpleO3 core.").default_val(128);

  int lat_hist_sensitivity = param<int>("lat_hist_sensitivity").default_val(5);
  std::string lat_dump_path = param<std::string>("lat_dump_path").default_val(std::string(""));

  alternate   = param<bool>("alternate_d").desc("Alternating attacker?").default_val(false);
  std::cout << "alternate" << alternate << std::endl;

  // LLC params
  int llc_latency           = param<int>("llc_latency").desc("Aggregated latency of the LLC.").default_val(47);
  int llc_linesize_bytes    = param<int>("llc_linesize").desc("LLC cache line size in bytes.").default_val(64);
  int llc_associativity     = param<int>("llc_associativity").desc("LLC set associativity.").default_val(8);
  int llc_capacity_per_core = parse_capacity_str(param<std::string>("llc_capacity_per_core").desc("LLC capacity per core.").default_val("2MB"));
  int llc_num_mshr_per_core = param<int>("llc_num_mshr_per_core").desc("Number of LLC MSHR entries per core.").default_val(16);
  
  llc_serialize = param<bool>("llc_serialize").desc("Whether to serialize the LLC.").default_val(false);
  llc_serialization_filename = param<std::string>("llc_serialization_filename").desc("Filename to serialize the LLC.").default_val("llc_serialization");
  llc_deserialize = param<bool>("llc_deserialize").desc("Whether to deserialize the LLC.").default_val(false);
  llc_deserialization_filename = param<std::string>("llc_deserialization_filename").desc("Filename to deserialize the LLC.").default_val("llc_serialization");

  // Simulation parameters
  m_num_expected_insts = param<int>("num_expected_insts").desc("Number of instructions that the frontend should execute.").required();
  m_num_max_cycles = param<uint64_t>("num_max_cycles").desc("Number of cycles the frontend is allowed to execute.").default_val(std::numeric_limits<uint64_t>::max());

  // Create address translation module
  m_translation = create_child_ifce<ITranslation>();

  // Create the LLC
  m_llc = new BHO3LLC(llc_latency, llc_capacity_per_core * m_num_cores, llc_linesize_bytes, llc_associativity, llc_num_mshr_per_core * m_num_cores, m_num_cores);
  if (llc_deserialize) {
    if (!std::filesystem::exists(llc_deserialization_filename)) {
      throw std::runtime_error("LLC deserialization file not found.");
    }
    m_llc->deserialize(llc_deserialization_filename);
  }

  // Create the cores
  std::cout << "Trace ID - Name Mapping:" << std::endl;
  for (int id = 0; id < m_num_cores; id++) {
    bool is_blocking = id < m_num_blocking_cores;
    bool is_attacker = !is_blocking;
    bool is_cache_only = is_blocking ? def_traces_cache_only : no_wait_traces_cache_only;
    Request::SpecType spec_type = is_cache_only ? Request::SpecType::CacheOnly : Request::SpecType::Basic;
    auto& active_list = is_blocking ? trace_list : no_wait_trace_list;
    auto active_id = is_blocking ? id : (id - m_num_blocking_cores);
    auto* cur_translate = is_blocking ? m_translation : nullptr;
    // auto* cur_translate = m_translation;
    std::cout << "name_trace_" << id << ": " << active_list[active_id] << std::endl;
    BHO3Core* core = new BHO3Core(id, ipc, depth,
      m_num_expected_insts, m_num_max_cycles, active_list[active_id],
      cur_translate, m_llc, lat_hist_sensitivity, lat_dump_path, is_attacker, spec_type);
    core->m_callback = [this](Request& req){return this->receive(req);} ;
    m_cores.push_back(core);
  }

   for(int i=0; i<m_cores.size();i++){
    if(m_cores[i]->m_is_attacker){
      m_cores[i]->m_is_allowed = true;
      std::cout << "core" << i << "is allowed attacker " << std::endl;
      break;
    }
   }

  m_logger = Logging::create_logger("BHO3");

  // Register the stats
  register_stat(m_num_expected_insts).name("num_expected_insts");
  register_stat(m_llc->s_llc_eviction).name("llc_eviction");
  register_stat(m_llc->s_llc_read_access).name("llc_read_access");
  register_stat(m_llc->s_llc_write_access).name("llc_write_access");
  register_stat(m_llc->s_llc_read_misses).name("llc_read_misses");
  register_stat(m_llc->s_llc_write_misses).name("llc_write_misses");
  register_stat(m_llc->s_llc_mshr_unavailable).name("llc_mshr_unavailable");
  register_stat(m_llc->s_llc_mshr_blacklisted).name("llc_mshr_blacklisted");
  
  for (int core_id = 0; core_id < m_cores.size(); core_id++) {
    register_stat(m_cores[core_id]->s_cycles_recorded).name("cycles_recorded_core_{}", core_id);
    register_stat(m_cores[core_id]->s_insts_recorded).name("insts_recorded_core_{}", core_id);
    register_stat(m_cores[core_id]->s_mem_access_cycles).name("memory_access_cycles_recorded_core_{}", core_id);
    register_stat(m_cores[core_id]->s_mem_requests_issued).name("memory_requests_recorded_core_{}", core_id);
  }
}

void BHO3::tick() {
  m_clk++;

  if(m_clk % 10000000 == 0) {
    m_logger->info("Processor Heartbeat {} cycles.", m_clk);
  }

  m_llc->tick();
  if(alternate){
    // loop over cores and trun off allowed attacker if reached max
    bool atacker_switch = false;
    int prev_attacker_ndx = -1;
    for(int i=0; i<m_cores.size();i++){
      if(m_cores[i]->m_is_attacker && m_cores[i]->m_is_allowed && !(m_cores[i]->s_insts_recorded % 1000)){
        // allowed attacker reached max
        // std::cout << "core" << i << "reached max attacker " << std::endl;
        atacker_switch = true;
        prev_attacker_ndx = i;
        m_cores[i]->m_is_allowed=false;
        break;
      }
    }
    int ndx = (prev_attacker_ndx+1) %m_cores.size();
    while(ndx != prev_attacker_ndx){
      if(m_cores[ndx]->m_is_attacker){
        m_cores[ndx]->m_is_allowed = true;
        // std::cout << "core" << ndx << "is allowed attacker " << std::endl;
        break;
      }
      ndx = (ndx+1) %m_cores.size();
    }
    if(ndx == prev_attacker_ndx){
      m_cores[ndx]->m_is_allowed = true;
      // std::cout << "core" << ndx << "is allowed attacker " << std::endl;
    }
  }
  // if we just turned off an attacker, loop over cores, starting from prev attacker and turn on the first new attacker encounter
  for (auto core : m_cores) { // can change the alternating here. if core is attacker and done, singal to other attacker to go ahead
    // if core is attacker and running and reached max allowed insts, turn off
    core->tick();
  }
}

void BHO3::receive(Request& req) {
  m_llc->receive(req);

  // TODO: LLC latency for the core to receive the request?
  for (auto r : m_llc->m_receive_requests[req.addr]) {
    r.arrive = req.arrive;
    r.depart = req.depart;
    m_cores[r.source_id]->receive(r);
  }
  m_llc->m_receive_requests[req.addr].clear();
}

bool BHO3::is_finished() {
  for (int i = 0; i < m_num_blocking_cores; i++) {
    auto core = m_cores[i];
    if (!(core->reached_expected_num_insts)) {
      return false;
    }
  }
  if (llc_serialize)
    m_llc->serialize(llc_serialization_filename);
  return true;
}

void BHO3::connect_memory_system(IMemorySystem* memory_system) {
  m_llc->connect_memory_system(memory_system);
};

int BHO3::get_num_cores() {
  return m_num_cores;
};

// BH Changes Begin
BHO3LLC* BHO3::get_llc() {
  return m_llc;
}

std::vector<BHO3Core*>& BHO3::get_cores() {
  return m_cores;
}

}        // namespace Ramulator