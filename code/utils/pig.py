#!/usr/bin/python
import math
import utils.plan as plan

def build_stages(g):
    blevels = g.blevel()
    scheduled = [False]*g.n_vertices
    stages = {}
    
    stages[0] = set(blevels[max(blevels)])
    cur_stage = plan.Stage(0)
    for j in stages[0]: 
        scheduled[j] = True
        g.jobs[j].slevel = 0
        cur_stage.add_job(g.jobs[j])  
    cur_stage.finish_add_jobs()
    cur_stage.stage_id = 0
    g.stages[0] = cur_stage
        
    for blvl in range(max(blevels), 0, -1):
        csi = max(blevels) - blvl # current stage index
        stg_jobs = blevels[blvl]
        new_stage = set()
        cur_stage = plan.Stage(csi)
        for j in blevels[blvl - 1]:
            if not scheduled[j]: new_stage.add(j) 
        for j in stg_jobs:
            for ch in g.jobs[j].children.keys():
                if scheduled[ch]: continue
                if g.jobs[j].blevel -1 > g.jobs[ch].blevel and len(g.jobs[ch].parents) > 1 : continue 
                new_stage.add(ch)
        for j in new_stage: 
            scheduled[j] = True
            g.jobs[j].slevel = csi + 1
            cur_stage.add_job(g.jobs[j])          
        stages[csi + 1] = new_stage
        cur_stage.finish_add_jobs()
        cur_stage.stage_id = csi+1 
        g.stages[csi+1] = cur_stage
    g.schedule = stages 
    return g;

def input_scaling(g, j, prefetch_plan):
    scale_factor = j['ctime']/(g.timeValue[j['job']] - g.cachedtimeValue[j['job']]); #csz : cache size
    pref_csz = {}
    i = 0
    
    for isz in g.inputSize[j['job']]: #isz: input size
        pref_sz = math.ceil(scale_factor*isz)
        if g.inputs[j['job']][i] in pref_csz:
            pref_sz = max(pref_csz[g.inputs[j['job']][i]], pref_sz)
        pref_csz[g.inputs[j['job']][i]] = pref_sz


def build_kariz_stage_priorities_helper(g, s, plans_container): # s stands for stage
    priority = 1;
    t_imprv = -1
    s.dag_id = g.dag_id
    plans_container.add_stage(s)
    while t_imprv:
        plan, t_imprv = s.get_next_plan(priority)
        if not t_imprv:
            break;
        plan.dag_id = g.dag_id
        plan.stage_id = s.stage_id
        plans_container.add_cache_plan(plan, s)
        priority = priority + 1
    return

def build_kariz_priorities(g):
    if not g.stages:
        build_stages(g)
    
    plans_container = plan.PlansContainer(g)
    for s in g.stages:
        stage = g.stages[s]
        build_kariz_stage_priorities_helper(g, stage, plans_container)
    
    #plans_container.assing_prefetch_plan_unlimitedbw()
    return plans_container;

def build_rcp_stage_priorities_helper(g, s, plans_container): # s stands for stage
    priority = 1;
    t_imprv = -1
    s.dag_id = g.dag_id
    plans_container.add_stage(s)
    while t_imprv:
        plan, t_imprv = s.get_rcp_next_plan(priority)
        if not t_imprv:
            break;
        plan.dag_id = g.dag_id
        plan.stage_id = s.stage_id
        plans_container.add_cache_plan(plan, s)
        plan.iscore = 1/plan.size
        plan.pscore = 0
        plan.sscore = 0
        plan.wscore = 0
        priority = priority + 1
    return


def build_rcp_priorities(g):
    if not g.stages:
        build_stages(g)
    
    plans_container = plan.PlansContainer(g)
    for s in g.stages:
        stage = g.stages[s]
        build_rcp_stage_priorities_helper(g, stage, plans_container)
    return plans_container;


def build_cp_stage_priorities_helper(g, s, plans_container): # s stands for stage
    s.dag_id = g.dag_id
    plans_container.add_stage(s)
    plan, t_imprv = s.get_criticalpath_plan()
    if plan:
        plan.dag_id = g.dag_id
        plan.stage_id = s.stage_id
        plans_container.add_cache_plan(plan, s)

def build_cp_priorities(g):
    if not g.stages:
        build_stages(g)
    
    plans_container = plan.PlansContainer(g)
    for s in g.stages:
        stage = g.stages[s]
        build_cp_stage_priorities_helper(g, stage, plans_container)
    
    plans_container.assing_prefetch_plan_unlimitedbw()
    return plans_container;



def build_mrd_priorities_helper(g, s, plans_container): # s stands for stage
    priority = 1;
    plans_container.add_stage(s) 
    
    for j in s.jobs:
        p = plan.Plan()
        p.priority = priority
        p.size = 0 
        for f in j.inputs:
            p.data[f] = {'size': j.inputs[f], 'score': -1}
            p.size += j.inputs[f]
        p.jobs.append({'job': j, 
                       'improvement': j.original_runtime - j.cached_runtime})
        plans_container.add_cache_plan(p, s)
        priority = priority + 1
    return

def build_mrd_priorities(g):
    blevels, orderednodes = g.bLevel()
    cur_blevel = max(blevels)
    csi = max(blevels) - cur_blevel # current stage index
    cur_stage = plan.Stage(csi)
    plans_container = plan.PlansContainer(g)
    
    # build priority plans for stage 
    ci = 0 # current index
    while ci < len(blevels):    
        if blevels[ci] != cur_blevel:
            cur_stage.finish_add_jobs()
            build_mrd_priorities_helper(g, cur_stage, plans_container)
            g.stages[csi] = cur_stage
            # prepare new stage
            cur_blevel = cur_blevel - 1
            csi = max(blevels) - cur_blevel 
            cur_stage = plan.Stage(csi)
        
        # build the job
        j = plan.Job(csi)
        j.id = orderednodes[ci]
        j.original_runtime = g.timeValue[orderednodes[ci]]
        j.improved_runtime = g.timeValue[orderednodes[ci]]
        j.cached_runtime = g.cachedtimeValue[orderednodes[ci]]
        # FIXME add inputs as well
        inputs = g.inputs[orderednodes[ci]]
        inputSize = g.inputSize[orderednodes[ci]]
        for i in range(0, len(inputs)):
            j.inputs[inputs[i]] = inputSize[i]
        
        cur_stage.add_job(j)
        ci = ci + 1

    cur_stage.finish_add_jobs()
    build_mrd_priorities_helper(g, cur_stage, plans_container)
    g.stages[csi] = cur_stage
    return plans_container


def build_stages2(g):
    blevels, orderednodes = g.bLevel()
    cur_blevel = max(blevels)
    csi = max(blevels) - cur_blevel # current stage index
    cur_stage = plan.Stage(csi)
    
    # build priority plans for stage 
    ci = 0 # current index
    while ci < len(blevels):    
        if blevels[ci] != cur_blevel:
            cur_stage.finish_add_jobs()
            g.stages[csi] = cur_stage 
            # prepare new stage
            cur_blevel = cur_blevel - 1
            csi = max(blevels) - cur_blevel 
            cur_stage = plan.Stage(csi)
        
        # build the job
        j = plan.Job(csi)
        j.id = orderednodes[ci]
        j.original_runtime = g.timeValue[orderednodes[ci]]
        j.improved_runtime = g.timeValue[orderednodes[ci]]
        j.cached_runtime = g.cachedtimeValue[orderednodes[ci]]
        # FIXME add inputs as well
        inputs = g.inputs[orderednodes[ci]]
        inputSize = g.inputSize[orderednodes[ci]]
        for i in range(0, len(inputs)):
            j.inputs[inputs[i]] = inputSize[i]
        
        
        cur_stage.add_job(j)
        ci = ci + 1

    cur_stage.finish_add_jobs()
    g.stages[csi] = cur_stage
    return g;


def build_lru_priorities_helper(g, s, plans_container): # s stands for stage
    priority = 1;
    plans_container.add_stage(s) 
    
    for j in s.jobs:
        p = plan.Plan()
        p.priority = priority
        p.size = 0 
        for f in j.inputs:
            p.data[f] = {'size': j.inputs[f], 'score': -1}
            p.size += j.inputs[f]
        p.jobs.append({'job': j, 
                       'improvement': j.original_runtime - j.cached_runtime})
        plans_container.add_cache_plan(p, s)
        priority = priority + 1
    return


def build_lru_priorities(g):
    blevels, orderednodes = g.bLevel()
    cur_blevel = max(blevels)
    csi = max(blevels) - cur_blevel # current stage index
    cur_stage = plan.Stage(csi)
    plans_container = plan.PlansContainer(g)
    
    # build priority plans for stage 
    ci = 0 # current index
    while ci < len(blevels):    
        if blevels[ci] != cur_blevel:
            cur_stage.finish_add_jobs()
            build_lru_priorities_helper(g, cur_stage, plans_container)
            g.stages[csi] = cur_stage
            # prepare new stage
            cur_blevel = cur_blevel - 1
            csi = max(blevels) - cur_blevel 
            cur_stage = plan.Stage(csi)
        
        # build the job
        j = plan.Job(csi)
        j.id = orderednodes[ci]
        j.original_runtime = g.timeValue[orderednodes[ci]]
        j.improved_runtime = g.timeValue[orderednodes[ci]]
        j.cached_runtime = g.cachedtimeValue[orderednodes[ci]]
        # FIXME add inputs as well
        inputs = g.inputs[orderednodes[ci]]
        inputSize = g.inputSize[orderednodes[ci]]
        for i in range(0, len(inputs)):
            print(i, inputs, inputSize)
            if len(inputSize) <= i:
                j.inputs[inputs[i]] = 0
            else:
                j.inputs[inputs[i]] = inputSize[i]
        
        cur_stage.add_job(j)
        ci = ci + 1

    cur_stage.finish_add_jobs()
    build_lru_priorities_helper(g, cur_stage, plans_container)
    g.stages[csi] = cur_stage
    return plans_container


def build_infinite_priorities(v):
    return None
