#!/usr/bin/python
# Author: Trevor Nogues, Mania Abdi

# Schedulers abstraction 
from collections import defaultdict
import random
import sched, threading, time
import copy
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import time
import utils.requester as requester
import colorama
from colorama import Fore, Style

start_t = 0
debug_sleep = 5 # second
# B-level (PIG) schedule helper 
def gang_schedule_helper(g, stage_to_be_executed = -1, priority = 0, timesUsed = [], dataset_stats = [], elapsed_time=0):
    s = sched.scheduler(time.time, time.sleep)
    priority += 1
    currentIndex = 0
    stage_index = stage_to_be_executed + 1
    if stage_index not in g.stages:
        print(Fore.RED, 'I should notify end of DAG', Style.RESET_ALL)
        return

    requester.notify_stage_start(g, stage_index)
    stage_to_be_executed += 1
    currentIndex = 0
    priority = 1
    requester.notify_stage_start(g, stage_to_be_executed)
    time.sleep(debug_sleep)
    cached_inpus = {}
    if g.plans_container:
        cache_plans = g.plans_container.get_stage_cache_plans(stage_to_be_executed)
        for p in cache_plans:
            plan = cache_plans[p]
            if not requester.is_plan_cached(plan):
                print(Fore.LIGHTYELLOW_EX,'\tPlan: ', plan, ' is not cached', Style.RESET_ALL)
                break
            print(Fore.LIGHTGREEN_EX,'\tPlan: ', plan, ' is cached', Style.RESET_ALL)
            for f in plan.data:
                cached_inpus[f] = cached_inpus[f] if f in cached_inpus and plan.data[f]['size'] < cached_inpus[f] else plan.data[f]['size']
            g.update_runtime(plan)

    stage_runtime = g.stages[stage_to_be_executed].get_runtime()
    count = 1
    start = time.time()
    start_t = start
    dataset_stats.append({'stage': stage_to_be_executed, 'inputs' : g.stages[stage_to_be_executed].stage_inputs, 'cached_inputs': cached_inpus})
    timesUsed.append(stage_runtime)
        
    print(Fore.LIGHTMAGENTA_EX, "\tSchedule stage ", stage_to_be_executed, " for execution. Estimated runtime: ", stage_runtime, ', elapsed time: ', elapsed_time, Style.RESET_ALL)
    elapsed_time += stage_runtime
    #currentLevel -= 1
    #timesUsed.append(currentMaxTime)
    s.enter(15, priority, gang_schedule_helper, argument=(g, stage_to_be_executed, priority, timesUsed, dataset_stats, elapsed_time))
    s.run()


# B-level Gang scheduler (PIG)
def gang_scheduler(g):
    global start_t
    s = sched.scheduler(time.time, time.sleep)
    timesUsed = []
    dataset_stats = []
    
    if not g.schedule:
        build_stages(g)

    stage_to_be_executed = 0
    currentIndex = 0
    priority = 1
    requester.notify_stage_start(g, stage_to_be_executed)
    time.sleep(debug_sleep)
    cached_inpus = {}
    if g.plans_container:
        cache_plans = g.plans_container.get_stage_cache_plans(stage_to_be_executed)
        for p in cache_plans:
            plan = cache_plans[p]
            if not requester.is_plan_cached(plan):
                print(Fore.LIGHTYELLOW_EX,'\tPlan: ', plan, ' is not cached', Style.RESET_ALL)
                break
            print(Fore.LIGHTGREEN_EX,'\tPlan: ', plan, ' is cached', Style.RESET_ALL)
            for f in plan.data:
                cached_inpus[f] = cached_inpus[f] if f in cached_inpus and plan.data[f]['size'] < cached_inpus[f] else plan.data[f]['size']             
            g.update_runtime(plan)
    
    stage_runtime = g.stages[stage_to_be_executed].get_runtime()
    count = 1
    start = time.time()
    start_t = start
    dataset_stats.append({'stage': stage_to_be_executed, 'inputs' : g.stages[stage_to_be_executed].stage_inputs, 'cached_inputs': cached_inpus})    
    timesUsed.append(stage_runtime)
    elapsed_time = stage_runtime
    print(Fore.LIGHTMAGENTA_EX, "\tSchedule stage ", stage_to_be_executed, " for execution. Estimated runtime: ", stage_runtime, ', elapsed time: ', elapsed_time, Style.RESET_ALL)
    s.enter(15, priority, gang_schedule_helper, argument=(g, stage_to_be_executed, priority, timesUsed, dataset_stats, elapsed_time))
    s.run()
    end = time.time()
    print(Fore.LIGHTGREEN_EX, "Total time", sum(timesUsed), Style.RESET_ALL)
    requester.complete(g)
    requester.clear_cache();
    return sum(timesUsed), timesUsed, dataset_stats
