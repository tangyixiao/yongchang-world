"""Pure foundation-arc scheduler metadata and adapter snippet renderer."""
from __future__ import annotations
import re
from typing import Any

_KIND_PRIORITY={"normal":0,"notice36":1,"notice12":2}
_TOKEN=re.compile(r"^[a-z][a-z0-9_]*$")
_EVENT_ID=re.compile(r"^[a-z][a-z0-9_]*\.([0-9]+)$")
_JOURNAL_FIELDS={"id","title","desc","script","goal","exit_conditions"}
_EVENT_FIELDS={"id","title","desc","trigger","immediate","options","purpose","reads","writes"}

def _inner(block:Any,label:str)->str:
    if not isinstance(block,str): raise ValueError(f"{label} must be a Clausewitz block")
    value=block.strip()
    if len(value)<2 or value[0]!="{" or value[-1]!="}": raise ValueError(f"{label} must be wrapped in braces")
    depth=0; quoted=False; escaped=False
    for i,ch in enumerate(value):
        if escaped: escaped=False; continue
        if ch=="\\": escaped=True; continue
        if ch=='"': quoted=not quoted
        elif not quoted:
            if ch=="{": depth+=1
            elif ch=="}":
                depth-=1
                if depth==0 and i!=len(value)-1: raise ValueError(f"{label} has trailing text")
                if depth<0: raise ValueError(f"{label} has unbalanced braces")
    if depth or quoted: raise ValueError(f"{label} has unbalanced braces or quotes")
    return value[1:-1].strip()

def _token(value:Any,label:str)->str:
    if not isinstance(value,str) or not _TOKEN.fullmatch(value): raise ValueError(f"{label} must be a lowercase script identifier")
    return value

def _object(value:Any,required:set[str],optional:set[str],label:str)->dict:
    if not isinstance(value,dict): raise ValueError(f"{label} must be an object")
    missing=required-set(value); unknown=set(value)-required-optional
    if missing or unknown: raise ValueError(f"{label} fields invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value

def _ids(items:Any,label:str,fields:set[str],pattern:re.Pattern|None=None)->list[str]:
    if not isinstance(items,list) or not items: raise ValueError(f"{label} must be a nonempty list")
    result=[]
    for item in items:
        _object(item,{"id"},fields-{"id"},label+" item")
        val=item["id"]
        if not isinstance(val,str) or (pattern and not pattern.fullmatch(val)): raise ValueError(f"{label} has invalid ID: {val}")
        result.append(val)
    if len(result)!=len(set(result)): raise ValueError(f"{label} contains duplicate IDs")
    return result

def _candidates(arc:dict)->list[tuple[dict,dict]]:
    return [(q,c) for q in arc["delivery_adapter"]["queues"] for c in q["candidates"]]

def validate_catalogue_adapters(catalogue:dict[str,Any])->None:
    _object(catalogue,{"key","runtime_tags","arcs"},{"layer"},"catalogue")
    key=_token(catalogue["key"],"catalogue.key")
    tags=catalogue["runtime_tags"]
    if not isinstance(tags,list) or len(tags)!=1 or type(tags[0]) is not str or not re.fullmatch(r"[A-Z0-9]+",tags[0]): raise ValueError("catalogue.runtime_tags must contain one uppercase country tag")
    if not isinstance(catalogue["arcs"],list): raise ValueError("catalogue.arcs must be a list")
    active=[a for a in catalogue["arcs"] if isinstance(a,dict) and a.get("era")=="foundation"]
    if len(active)!=3: raise ValueError(f"{key} must declare exactly three foundation arcs")
    slugs=[]; journal_owner={}; event_owner={}; variable_roles={}
    for arc in active:
        _object(arc,{"slug","era","journals","events","delivery_adapter"},{"participants","depends_on","outcomes","legacy_links"},"foundation arc")
        slug=_token(arc["slug"],"arc.slug"); slugs.append(slug)
        js=_ids(arc["journals"],f"{slug}.journals",_JOURNAL_FIELDS)
        es=_ids(arc["events"],f"{slug}.events",_EVENT_FIELDS,_EVENT_ID)
        for jid in js:
            if jid in journal_owner: raise ValueError(f"journal ID owned more than once: {jid}")
            journal_owner[jid]=slug
        for eid in es:
            if eid in event_owner: raise ValueError(f"event ID owned more than once: {eid}")
            event_owner[eid]=slug
    if len(slugs)!=len(set(slugs)): raise ValueError("duplicate arc slug")
    internal_vars=[f"ywc_v03_{key}_delivery_round",f"ywc_v03_{key}_reservation_arc",f"ywc_v03_{key}_reservation_candidate",f"ywc_v03_{key}_reservation_timer"]
    for slug in slugs:
        internal_vars.extend((f"ywc_v03_scheduler_served_{slug}",f"ywc_v03_scheduler_turn_{slug}"))
    for var in internal_vars:
        if var in variable_roles: raise ValueError(f"scheduler internal variable aliases source role: {var}")
        variable_roles[var]=("internal",key,var)
    for arc in active:
        slug=arc["slug"]
        ad=_object(arc["delivery_adapter"],{"owner_started","owner_settled","source_dispatch_effect","live_phases","queues"},set(),f"{slug}.delivery_adapter")
        _token(ad["source_dispatch_effect"],f"{slug}.source_dispatch_effect")
        for f in ("owner_started","owner_settled"):
            v=_token(ad[f],f"{slug}.{f}")
            if v in variable_roles: raise ValueError(f"variable aliases another role: {v}")
            variable_roles[v]=("owner",slug,f)
        phases=ad["live_phases"]
        if not isinstance(phases,list) or not phases: raise ValueError(f"{slug} needs live_phases")
        seen_phase=[]
        for ph in phases:
            _object(ph,{"journal","predicate"},{"live_witness"},f"{slug}.phase")
            jid=ph["journal"]
            if journal_owner.get(jid)!=slug: raise ValueError(f"{slug} phase references a foreign journal: {jid}")
            if jid in seen_phase: raise ValueError(f"{slug} repeats live phase: {jid}")
            seen_phase.append(jid)
            pred=_inner(ph["predicate"],f"{slug}.phase.{jid}")
            if "live_witness" in ph:
                witness=_token(ph["live_witness"],f"{slug}.phase.{jid}.live_witness")
                if witness in variable_roles: raise ValueError(f"variable aliases another role: {witness}")
                variable_roles[witness]=("witness",slug,jid)
            if "ywc_v03_can_deliver_major" in pred or "ywc_v03_major_event_cooldown" in pred: raise ValueError(f"{slug} phase guard must not contain shared cooldown")
        queues=ad["queues"]
        if not isinstance(queues,list) or not queues: raise ValueError(f"{slug} needs queues")
        queue_names=[]; candidate_keys=[]; mapped=[]
        for q in queues:
            _object(q,{"kind","variable","candidates"},set(),f"{slug}.queue")
            if q["kind"] not in _KIND_PRIORITY: raise ValueError(f"{slug} has unsupported queue kind: {q['kind']}")
            var=_token(q["variable"],f"{slug}.queue.variable"); queue_names.append(var)
            role=variable_roles.get(var)
            if role is None:
                variable_roles[var]=("queue",slug,var)
            elif role[0]!="queue" or role[1]!=slug:
                raise ValueError(f"queue variable aliases another role or arc: {var}")
            cs=q["candidates"]
            if not isinstance(cs,list) or not cs: raise ValueError(f"{slug}.{var} needs candidates")
            for c in cs:
                _object(c,{"key","event_id","value","guard"},{"acknowledgement","kind","source_journals","receipt_variable","receipt_value"},f"{slug}.{var}.candidate")
                ck=_token(c["key"],f"{slug}.candidate.key"); candidate_keys.append(ck)
                for internal in (f"ywc_v03_scheduler_candidate_{slug}_{ck}",f"ywc_v03_scheduler_turn_{slug}_{ck}",f"ywc_v03_scheduler_dispatch_{slug}_{ck}"):
                    if internal in variable_roles: raise ValueError(f"scheduler internal variable aliases source role: {internal}")
                    variable_roles[internal]=("internal",slug,ck)
                kind=c.get("kind",q["kind"])
                if kind not in _KIND_PRIORITY: raise ValueError(f"{slug}.{ck} has unsupported candidate kind: {kind}")
                sources=c.get("source_journals",[ph["journal"] for ph in phases])
                if not isinstance(sources,list) or not sources or any(type(j) is not str or journal_owner.get(j)!=slug for j in sources) or len(sources)!=len(set(sources)):
                    raise ValueError(f"{slug}.{ck}.source_journals must be distinct journals owned by this arc")
                eid=c["event_id"]
                if event_owner.get(eid)!=slug: raise ValueError(f"{slug} candidate references foreign event: {eid}")
                if type(c["value"]) is not int or c["value"]<0: raise ValueError(f"{slug}.{ck} value must be a nonnegative integer")
                guard=_inner(c["guard"],f"{slug}.{ck}.guard")
                if "ywc_v03_can_deliver_major" in guard or "ywc_v03_major_event_cooldown" in guard: raise ValueError(f"{slug} candidate guard must not contain shared cooldown")
                actions=c.get("acknowledgement",[])
                if not isinstance(actions,list): raise ValueError(f"{slug}.{ck}.acknowledgement must be a list")
                for act in actions:
                    _object(act,{"op","variable"},{"value"},f"{slug}.{ck}.acknowledgement")
                    if act["op"] not in ("set","remove"): raise ValueError(f"{slug}.{ck} invalid acknowledgement operation")
                    _token(act["variable"],f"{slug}.{ck}.ack.variable")
                    if act["op"]=="set" and ("value" not in act or type(act["value"]) is not int): raise ValueError(f"{slug}.{ck} set acknowledgement needs integer value")
                    if act["op"]=="remove" and "value" in act: raise ValueError(f"{slug}.{ck} remove acknowledgement cannot have value")
                has_rv="receipt_variable" in c; has_rvalue="receipt_value" in c
                if has_rv!=has_rvalue: raise ValueError(f"{slug}.{ck} receipt variable/value must be provided together")
                if has_rv:
                    receipt=_token(c["receipt_variable"],f"{slug}.{ck}.receipt_variable")
                    if type(c["receipt_value"]) is not int: raise ValueError(f"{slug}.{ck}.receipt_value must be an integer")
                    role=variable_roles.get(receipt)
                    if role is None:
                        variable_roles[receipt]=("receipt",slug,receipt)
                    elif role[0]!="receipt" or role[1]!=slug:
                        raise ValueError(f"receipt variable aliases another role or arc: {receipt}")
                mapped.append(eid)
        if len(candidate_keys)!=len(set(candidate_keys)): raise ValueError(f"{slug} repeats candidate key")
        if set(mapped)!=set(e for e,owner in event_owner.items() if owner==slug): raise ValueError(f"{slug} candidate/event ownership mismatch")
    # Queue variable ownership is global, not just per-arc.
    owner_by_queue={}
    for arc in active:
        for q in arc["delivery_adapter"]["queues"]:
            var=q["variable"]
            if var in owner_by_queue and owner_by_queue[var]!=arc["slug"]: raise ValueError(f"queue variable owned by multiple arcs: {var}")
            owner_by_queue[var]=arc["slug"]

def _candidate(slug:str,key:str)->str: return f"ywc_v03_scheduler_candidate_{slug}_{key}"
def _arc_turn(slug:str)->str: return f"ywc_v03_scheduler_turn_{slug}"
def _candidate_turn(slug:str,key:str)->str: return f"ywc_v03_scheduler_turn_{slug}_{key}"
def _dispatch(slug:str,key:str)->str: return f"ywc_v03_scheduler_dispatch_{slug}_{key}"

def render_country_adapters(catalogue:dict[str,Any])->dict[str,str]:
    """Render candidate, per-candidate turn, dispatch and reservation snippets."""
    validate_catalogue_adapters(catalogue)
    arcs=[a for a in catalogue["arcs"] if a.get("era")=="foundation"]
    key=catalogue["key"]; roundv=f"ywc_v03_{key}_delivery_round"; ra=f"ywc_v03_{key}_reservation_arc"; rk=f"ywc_v03_{key}_reservation_candidate"; rt=f"ywc_v03_{key}_reservation_timer"
    trigs=[]; effects=[]; defs=[]; uid={}; arcpos={a["slug"]:i for i,a in enumerate(arcs,1)}; n=0
    for arc in arcs:
        slug=arc["slug"]; ad=arc["delivery_adapter"]
        for q in ad["queues"]:
            for c in q["candidates"]:
                n+=1; uid[(slug,c["key"])]=n; cn=_candidate(slug,c["key"]); defs.append((arc,q,c,cn))
                allowed=set(c.get("source_journals",[ph["journal"] for ph in ad["live_phases"]]))
                phases=[]
                for ph in ad["live_phases"]:
                    if ph["journal"] in allowed: phases.append(_inner(ph["predicate"],"phase"))
                phase=" OR = { "+" ".join("AND = { "+p+" }" for p in phases)+" } "
                trigs.append(f"{cn} = {{ AND = {{ has_variable = {ad['owner_started']} NOT = {{ has_variable = {ad['owner_settled']} }} {phase} has_variable = {q['variable']} var:{q['variable']} = {c['value']} {_inner(c['guard'],'guard')} }} }}")
    # Candidate-specific turns ensure a high-priority due candidate cannot lend
    # its arc's turn to an ordinary candidate. Cross-arc blockers must still owe service.
    for arc,q,c,cn in defs:
        slug=arc["slug"]; candturn=_candidate_turn(slug,c["key"]); rank=_KIND_PRIORITY[c.get("kind",q["kind"])]; blockers=[]
        for oa,oq,oc,on in defs:
            if oa["slug"]==slug: continue
            otherpos=arcpos[oa["slug"]]
            other_rank=_KIND_PRIORITY[oc.get("kind",oq["kind"])]
            if other_rank>rank or (other_rank==rank and otherpos<arcpos[slug]):
                blockers.append(f"AND = {{ {on} = yes NOT = {{ var:ywc_v03_scheduler_served_{oa['slug']} = var:{roundv} }} }}")
        # Higher candidate within the same arc wins before this arc is marked served.
        for oa,oq,oc,on in defs:
            if oa["slug"]==slug and _KIND_PRIORITY[oc.get("kind",oq["kind"])]>rank:
                blockers.append(f"{on} = yes")
        conditions=[f"{cn} = yes",f"NOT = {{ var:ywc_v03_scheduler_served_{slug} = var:{roundv} }}",f"NOT = {{ has_variable = {ra} }}","NOT = { has_variable = ywc_v03_major_event_cooldown }"]
        if blockers: conditions.append("NOT = { OR = { "+" ".join(blockers)+" } }")
        trigs.append(f"{candturn} = {{ AND = {{ "+" ".join(conditions)+" } }")
        # Exact reserved candidate can reach its original event trigger; otherwise it needs its turn.
        trigs.append(f"{_dispatch(slug,c['key'])} = {{ AND = {{ {cn} = yes OR = {{ AND = {{ var:{ra} = {arcpos[slug]} var:{rk} = {uid[(slug,c['key'])]} has_variable = {rt} }} {candturn} = yes }} }} }}")
    for slug in arcpos:
        arc_defs=[(q,c,cn) for a,q,c,cn in defs if a["slug"]==slug]
        trigs.append(f"{_arc_turn(slug)} = {{ OR = {{ "+" ".join(f"{_candidate_turn(slug,c['key'])} = yes" for _,c,_ in arc_defs)+" } }")
    # Expired or stale reservations are cleared before scheduling. A reservation is
    # valid only while its exact candidate, phase, owner and one-day timer remain live.
    prep=[f"ywc_v03_scheduler_prepare_{key} = {{","    if = { limit = { NOT = { has_variable = "+roundv+" } } set_variable = { name = "+roundv+" value = 1 } }"]
    for arc,q,c,cn in defs:
        pos=arcpos[arc["slug"]]; idv=uid[(arc["slug"],c["key"])]
        prep.append(f"    if = {{ limit = {{ var:{ra} = {pos} var:{rk} = {idv} NOT = {{ has_variable = {rt} }} }} remove_variable = {ra} remove_variable = {rk} }}")
        prep.append(f"    if = {{ limit = {{ var:{ra} = {pos} var:{rk} = {idv} has_variable = {rt} NOT = {{ {cn} = yes }} }} remove_variable = {ra} remove_variable = {rk} remove_variable = {rt} }}")
    any_live=" OR = { "+" ".join(cn+" = yes" for _,_,_,cn in defs)+" } "
    all_arcs=[]
    for arc in arcs:
        slug=arc["slug"]; names=[cn for a,_,_,cn in defs if a["slug"]==slug]
        all_arcs.append("OR = { NOT = { OR = { "+" ".join(n+" = yes" for n in names)+" } } var:ywc_v03_scheduler_served_"+slug+" = var:"+roundv+" }")
    prep.append(f"    if = {{ limit = {{ {any_live} AND = {{ "+" ".join(all_arcs)+" } } change_variable = { name = "+roundv+" add = 1 } }")
    prep.append("}"); effects.append("\n".join(prep))
    for arc,q,c,cn in defs:
        slug=arc["slug"]; ad=arc["delivery_adapter"]; pos=arcpos[slug]; idv=uid[(slug,c["key"])]; candturn=_candidate_turn(slug,c["key"])
        reserve=f"ywc_v03_scheduler_reserve_{slug}_{c['key']}"
        effects.append(f"{reserve} = {{ if = {{ limit = {{ {candturn} = yes {cn} = yes NOT = {{ has_variable = {ra} }} }} set_variable = {{ name = {ra} value = {pos} }} set_variable = {{ name = {rk} value = {idv} }} set_variable = {{ name = {rt} value = 1 days = 1 }} }} }}")
        ack=f"ywc_v03_scheduler_ack_{slug}_{c['key']}"
        ack_checks=[f"var:{ra} = {pos}",f"var:{rk} = {idv}",f"has_variable = {rt}",f"has_variable = {ad['owner_started']}",f"NOT = {{ has_variable = {ad['owner_settled']} }}",f"has_variable = {q['variable']}",f"var:{q['variable']} = {c['value']}"]
        allowed=set(c.get("source_journals",[ph["journal"] for ph in ad["live_phases"]]))
        ack_phases=[_inner(ph["predicate"],"phase") for ph in ad["live_phases"] if ph["journal"] in allowed]
        ack_checks.append("OR = { "+" ".join("AND = { "+phase+" }" for phase in ack_phases)+" }")
        if "receipt_variable" in c:
            ack_checks.append(f"has_variable = {c['receipt_variable']}")
            ack_checks.append(f"var:{c['receipt_variable']} = {c['receipt_value']}")
        lines=[f"{ack} = {{","    if = {","        limit = { "+" ".join(ack_checks)+" }" ]
        # Only after the whole exact reservation/phase/queue contract is validated do
        # source acknowledgement writes run, then queue consumption and service commit.
        for act in c.get("acknowledgement",[]):
            lines.append(f"        { 'set_variable = { name = '+act['variable']+' value = '+str(act['value'])+' }' if act['op']=='set' else 'remove_variable = '+act['variable'] }")
        lines += [f"        remove_variable = {q['variable']}",f"        set_variable = {{ name = ywc_v03_scheduler_served_{slug} value = var:{roundv} }}",f"        remove_variable = {ra}",f"        remove_variable = {rk}",f"        remove_variable = {rt}","    }","}"]
        effects.append("\n".join(lines))
    # Every live OIR JE pulse runs the same bounded recipient scan. Candidate
    # predicates carry the actual owner/phase/queue proof, so a caller from one
    # arc can serve another currently-live arc without importing its business
    # evaluation or creating an extra monthly pulse.
    journal_calls={}
    for arc in arcs:
        for phase in arc["delivery_adapter"]["live_phases"]:
            journal_calls[phase["journal"]]=defs
    callers=[]
    for jid, entries in journal_calls.items():
        body=[f"ywc_v03_scheduler_dispatch_from_{jid.removeprefix('ywc_je_v03_')} = {{","    ywc_v03_scheduler_prepare_"+key+" = yes"]
        for arc,q,c,cn in entries:
            slug=arc["slug"]; reserve=f"ywc_v03_scheduler_reserve_{slug}_{c['key']}"; dispatch=_dispatch(slug,c["key"])
            body += [f"    if = {{ limit = {{ {_candidate_turn(slug,c['key'])} = yes }} {reserve} = yes }}",
                     f"    if = {{ limit = {{ {dispatch} = yes }} trigger_event = {{ id = {c['event_id']} }} }}"]
        body.append("}"); callers.append("\n".join(body))
    event_hooks={}; ack_hooks={}
    for arc,q,c,cn in defs:
        event_hooks.setdefault(c["event_id"],[]).append(_dispatch(arc["slug"],c["key"]))
        ack_hooks.setdefault(c["event_id"],[]).append(f"ywc_v03_scheduler_ack_{arc['slug']}_{c['key']}")
    return {"triggers":"\n\n".join(trigs)+"\n","effects":"\n\n".join(effects+callers)+"\n","event_hooks":event_hooks,"ack_hooks":ack_hooks,"journal_calls":{jid:f"ywc_v03_scheduler_dispatch_from_{jid.removeprefix('ywc_je_v03_')}" for jid in journal_calls}}

def choose_next_dispatch(order:tuple[str,...]|list[str],round_number:int,served_rounds:dict[str,int],eligible:dict[str,list[dict[str,Any]]])->tuple[int,str|None,dict[str,Any]|None]:
    """Pure reference selection over actual current candidates; unknown state fails closed."""
    if type(round_number) is not int or round_number<1: raise ValueError("round_number must be a positive integer")
    if not isinstance(order,(tuple,list)) or any(type(s) is not str for s in order) or len(order)!=len(set(order)): raise ValueError("pulse order must have distinct arc slugs")
    if not isinstance(served_rounds,dict) or set(served_rounds)-set(order): raise ValueError("served state has unknown arc")
    if any(type(v) is not int or v<0 for v in served_rounds.values()): raise ValueError("served round must be a nonnegative integer")
    if not isinstance(eligible,dict) or set(eligible)-set(order): raise ValueError("eligible arcs are absent from pulse order")
    for slug,cs in eligible.items():
        if not isinstance(cs,list): raise ValueError(f"eligible candidates for {slug} must be a list")
        for c in cs:
            if not isinstance(c,dict) or set(c)-{"kind","event_id","key"} or not {"kind","event_id"}<=set(c) or c["kind"] not in _KIND_PRIORITY or type(c["event_id"]) is not str or ("key" in c and type(c["key"]) is not str): raise ValueError(f"invalid eligible candidate for {slug}: {c}")
    active=[s for s in order if eligible.get(s)]
    if not active:return round_number,None,None
    if all(served_rounds.get(s,0)==round_number for s in active): round_number+=1
    open_arcs=[s for s in active if served_rounds.get(s,0)!=round_number]
    if not open_arcs:return round_number,None,None
    idx={s:i for i,s in enumerate(order)}
    slug=min(open_arcs,key=lambda s:(-max(_KIND_PRIORITY[c["kind"]] for c in eligible[s]),idx[s]))
    return round_number,slug,min(eligible[slug],key=lambda c:-_KIND_PRIORITY[c["kind"]])
