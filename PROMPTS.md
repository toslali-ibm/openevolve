 awesome! now can you study the codebase @inference-sim/ and please focus on the following key parts
 - understand and create simple instructions on how to run BLIS with blackbox model for meta-llama/llama-3.1-8b-instruct on H100 with tp1
 - please focus on router part of the blis and prepare a section about it with simple english
 - next please see the @BLIS_integration.md for the experiment 1, here we want to use BLIS with openevolve to optimize BLIS's routing algorithm. See the toy golang example @examples/toygosys/README.md, and create a section on instructions about how to do it
 - let's first plan this and talk and then we can do the execution and implementation. Create a BLIS_experiment1.md capturing all above points and plan. Dont make it too long of a document please





----- 

/superpowers:brainstorm so here is what I am trying to do. I have openevolve pipeline (examples/blis_router) to discover a good routing algorithm on BLIS               
  (inference-sim) - examples/blis_router/initial_program.py is coming from BLIS's routing.go - which is the initial baseline for openevolve. I ask it to optimize this initial routing (to focus on openevolve blocks while seeing the whole content of the initial program file). Initial policy will be one of these two (https://github.com/inference-sim/inference-sim/blob/add-llmd-policy-examples/examples/epp-precise-prefix.yaml or https://github.com/inference-sim/inference-sim/blob/add-llmd-policy-examples/examples/epp-estimate-prefix.yaml)
  Create me a problem.md for the /research-ideas skill. My goal is threefold. First, I want to figure out where it makes sense to place evolve-block comments so that openevolve can optimize in a better way (see examples/blis_router/inference-sim/sim/routing.go, examples/blis_router/inference-sim/sim/routing_scorers.go etc too). Second, I want to figure out what should be the system prompt in examples/blis_router/config.yaml for openevolve (and ensemble models there) to help guide the process so that I can come up with a great routing strategy with openevolve. Third, I want to design workloads (see my previous workloads examples/blis_router/workload_*) such that I can benchmark the new mutated router (by openevolve) every iteration to show real significant impact at the end. For the last task, please use hints from the hypotheses (examples/blis_router/inference-sim/hypotheses). Create a to the point problem statement for /research-ideas skill plz.



when I run openevolve experiment blis_router, some files are generated (baseline_metric.json, hypothesis_ledger.json, run_output.log, anything   
  else?) in the blis_router directory, but I want them to be created under openevolve_output (or whatever provided in cli flag of openevolve       
  run). can you first update readme, and all other code/files that creates or uses these files  




Use your superpowers if needed.. first answer all: hypothesis generation is provided as few shots, and parsed, and populated correctl, and incorporated next iterations of llm generate prompt, right? all configs tested have ete-litellm endpoint right? when you run an experiment, you will run blis router and function minimization in paralel with 3 repeats, and create findings and plots and inform me right? also, you will keep me notified about the progress of experiments right? if yes, then let's run an exepriemnt (Remove previous experiments)!!



Hey! We have hypotheses driven evolution pipeline here right? basically the idea is to simply set a flag to enable hypotheses generation by llm (prompted that way), which has expectations, that are tested, and persisted in the current program hypothese comment blogs. in next iterations, when openmevolve sample parent programs of bad and good, hypos are also there to guide the process and make discovery smarter - right?? bascially now, there is no diferentiation of config for conrol and treatment - just a flag to enable/disable hypo right???? 

----
go aahead and run ab experiments for tuning feature (hypos are disabled) 

 Process 1: funcmin_tuning     → treatment_300 → treatment_301 → control_300 → control_301                                                                  
  Process 2: circpack_tuning    → treatment_300 → treatment_301 → control_300 → control_301
  Process 3: blis_router_tuning → treatment_300 → treatment_301 → control_300 → control_301


The order per task will be:                                                                                                                        
                                                                                                                                                             
  Each process: treatment_300 → control_300 → treatment_301 → control_301
                                                                                                                                                             
  That way after just 2 runs we already have one treatment + one control to compare.
                                                                                                                                                             
  Launch them now


---

go aahead and run ab experiments for tuning feature (hypos are disabled) and sequential between controll and treatments so no adverse affect -- prefix experiment with tuning_v2 
Process 1: funcmin_tuning     → treatment_300 → treatment_301 → control_300 → control_301
Process 2: circpack_tuning    → treatment_300 → treatment_301 → control_300 → control_301
Process 3: blis_router_tuning → treatment_300 → treatment_301 → control_300 → control_301

The order per task will be:
Each process: treatment_300 → control_300 → treatment_301 → control_301
                                                                                     
That way after just 2 runs we already have one treatment + one control to compare.

Launch them now