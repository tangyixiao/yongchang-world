"""JHG inline source contract. Public registration is intentionally RED on this baseline."""
from __future__ import annotations
import copy, hashlib, json, re, shutil, tempfile, unittest
from contextlib import contextmanager
from pathlib import Path
from tests.clausewitz_harness import parse
from tools.v03_inline_delivery_adapter import (_kor_source_binding, _kor_direct_adds,
    children, direct_values, parse_block, validate_inline_catalog, render_inline_country_adapters)
from tests import test_v03_jhg_foundation as foundation

ROOT=Path(__file__).resolve().parents[1]
CATALOG_PATH=ROOT/'data/content/v03/countries/jhg.json'
JOURNAL_PATH=ROOT/'yongchang_world/common/journal_entries/ywc_v03_country_jhg_journal.txt'
EVENT_PATH=ROOT/'yongchang_world/events/ywc_v03_country_jhg_events.txt'
EFFECTS_PATH=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_jhg_effects.txt'
TRIGGERS_PATH=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_jhg_triggers.txt'
JE_IDS=set(foundation.JE_IDS)
ARC_IDS=set(foundation.SLUGS)

def catalog(): return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
def _native_journals():
    from tools import build_v03_content
    return {k:b for k,_,b in parse(build_v03_content._render_journal_file(catalog(),None))}
def _nodes(value):
    """Normalize a block Node or Node sequence; reject ambiguous scalar shapes."""
    if hasattr(value,'key') and hasattr(value,'value'):
        if not isinstance(value.value,tuple): raise TypeError('expected a Clausewitz block Node')
        return list(children(value))
    if isinstance(value,(list,tuple)) and all(hasattr(n,'key') and hasattr(n,'value') for n in value):
        return list(value)
    raise TypeError(f'expected a Clausewitz Node or Node sequence, got {type(value).__name__}')
def _rows(nodes): return [(n.key,n.op,_rows(n.value) if isinstance(n.value,tuple) else n.value) for n in _nodes(nodes)]
def _walk(nodes):
    for n in _nodes(nodes):
        yield n
        if isinstance(n.value,tuple): yield from _walk(n.value)
def _setvar_names(nodes):
    found=[]
    for n in _walk(nodes):
        if n.key=='set_variable' and isinstance(n.value,tuple):
            names=[x.value for x in n.value if x.key=='name']
            found.extend(names)
    return found
def _triples(nodes):
    """Return every scalar AST atom as exact (key, operator, string value)."""
    return [(key,op,str(value)) for key,op,value in _scalar_rows(nodes)]
def _positive_conjunct_triples(nodes):
    """Collect positive atoms, traversing AND but never OR/NOT subtrees."""
    found=[]
    def visit(sequence):
        for node in _nodes(sequence):
            if node.key in {'OR','NOT','NOR'}: continue
            if node.key=='AND' and isinstance(node.value,tuple): visit(children(node)); continue
            if isinstance(node.value,tuple): continue
            found.append((node.key,node.op,str(node.value)))
    visit(nodes)
    return found
def _positive_guard_terms(nodes):
    """Conjunction members; OR subtrees stay intact for snapshot validation."""
    result=[]
    for node in _nodes(nodes):
        if node.key=='AND' and isinstance(node.value,tuple): result.extend(_positive_guard_terms(node))
        else: result.append(node)
    return result

def _negative_presence(nodes):
    result=set()
    for node in _positive_guard_terms(nodes):
        if node.key=='NOT' and isinstance(node.value,tuple):
            inside=_positive_guard_terms(node)
            if len(inside)==1 and inside[0].key=='has_variable' and not isinstance(inside[0].value,tuple):
                result.add(inside[0].value)
    return result

def _is_exact_snapshot_check(node,native,private_prefix='ywc_v03_jhg_inline_'):
    """Recognize guarded presence/value equality, including the absent case.

    Accept either stored 0/1 presence or paired absent private snapshots. Order
    and nested AND layout are immaterial. This is a static shape proof; runtime
    capture values and P/R/B transformations remain B/C responsibilities.
    """
    if node.key!='OR' or not isinstance(node.value,tuple): return False
    arms=children(node)
    if len(arms)!=2 or any(arm.key!='AND' for arm in arms): return False
    for present,absent in (arms,tuple(reversed(arms))):
        positive=set(_positive_conjunct_triples(present))
        negative=_negative_presence(absent)
        absent_atoms=set(_positive_conjunct_triples(absent))
        if ('has_variable','=',native) not in positive or native not in negative: continue
        values=[v[4:] for key,op,v in positive if key=='var:'+native and op=='=' and
                v.startswith('var:'+private_prefix)]
        for value in values:
            if ('has_variable','=',value) not in positive: continue
            flags=[key[4:] for key,op,v in positive if key.startswith('var:'+private_prefix) and
                   op=='=' and v=='1' and key[4:]!=value and ('has_variable','=',key[4:]) in positive]
            for flag in flags:
                if {('has_variable','=',flag),('has_variable','=',value),
                    ('var:'+flag,'=','0'),('var:'+value,'=','0')}<=absent_atoms: return True
            # Existing native adapters also use absent/present private snapshot pairs.
            if value in negative:
                pair={v for key,op,v in positive if key=='has_variable' and op=='=' and
                      v.startswith(private_prefix) and v!=value}
                if pair & negative: return True
    return False

def _assert_no_delivery_recheck(testcase,limit,label):
    testcase.assertFalse(any(node.key.startswith('ywc_v03_can_deliver') for node in _walk(limit)),
                         (label,'owned post-dispatch guard cannot recheck can_deliver'))


def _assert_native_context(testcase,limit,context,name):
    _assert_no_delivery_recheck(testcase,limit,name)
    positive=set(_positive_conjunct_triples(limit))
    terms=_positive_guard_terms(limit)
    for atom in context:
        native=atom[0][4:] if atom[0].startswith('var:') else atom[2]
        testcase.assertTrue(atom in positive or any(_is_exact_snapshot_check(term,native) for term in terms),
                            (name,'native context must be a positive atom or exact presence/value snapshot',atom))


def _has_present_snapshot(limit,native):
    atoms=set(_positive_conjunct_triples(limit))
    if ('has_variable','=',native) not in atoms: return False
    for key,op,value in atoms:
        if key!='var:'+native or op!='=' or not value.startswith('var:ywc_v03_jhg_inline_'): continue
        captured=value[4:]
        if ('has_variable','=',captured) not in atoms: continue
        for flag_key,flag_op,flag_value in atoms:
            if (flag_key.startswith('var:ywc_v03_jhg_inline_') and flag_op=='=' and flag_value=='1'
                and flag_key[4:]!=captured and ('has_variable','=',flag_key[4:]) in atoms): return True
    return False


def _assert_complete_native_snapshots(testcase,definition,names,label):
    _outer,limit,_effects=_helper_guard_and_effects(definition,label)
    terms=_positive_guard_terms(limit)
    for native in sorted(names):
        testcase.assertTrue(_has_present_snapshot(limit,native) or any(_is_exact_snapshot_check(term,native) for term in terms),
                            (label,'complete source context presence/value snapshot',native))


def _direct(nodes,key): return direct_values(_nodes(nodes),key)
def _helper_guard_and_effects(definition,name):
    top=_nodes(definition)
    guards=[node for node in top if node.key=='if']
    if len(guards)!=1 or len(top)!=1: raise AssertionError((name,'must be one owned outer if',[(n.key,n.op) for n in top]))
    if guards[0].op!='=' or not isinstance(guards[0].value,tuple):
        raise AssertionError((name,'owned if must be an equals block'))
    fields=children(guards[0]); limits=[n for n in fields if n.key=='limit']
    if len(limits)!=1 or fields[0] is not limits[0]:
        raise AssertionError((name,'outer if needs one leading direct limit',[(n.key,n.op) for n in fields]))
    if limits[0].op!='=' or not isinstance(limits[0].value,tuple):
        raise AssertionError((name,'owned limit must be an equals block'))
    effects=fields[1:]
    if any(n.key=='effect' for n in effects):
        raise AssertionError((name,'scripted if effects must be direct children'))
    return guards[0],limits[0],effects
def _assert_witness_immediate(testcase,generated_fields,authored_fields,witness,label):
    generated=_direct(generated_fields,'immediate')
    authored=_direct(authored_fields,'immediate')
    testcase.assertEqual(len(generated),1,label)
    testcase.assertLessEqual(len(authored),1,label)
    native=_nodes(authored[0]) if authored else []
    actual=_nodes(generated[0])
    testcase.assertEqual(_rows(actual[:len(native)]),_rows(native),(label,'complete native immediate prefix'))
    testcase.assertEqual(_rows(actual[len(native):]),
        _rows(parse_block('{ set_variable = { name = '+witness+' value = 1 } }')),
        (label,'one live witness write after native body'))


def _setvar_writes(nodes):
    writes=[]
    for node in _walk(nodes):
        if node.key!='set_variable' or not isinstance(node.value,tuple): continue
        names=direct_values(children(node),'name'); values=direct_values(children(node),'value')
        if len(names)==1 and len(values)==1: writes.append((names[0].value,values[0].value,node))
    return writes
def _called_effects(nodes,known):
    return {node.key for node in _walk(nodes) if node.op=='=' and node.value=='yes' and node.key in known}
def _reachable_effects(start,definitions):
    found=set(); pending=[start]
    while pending:
        name=pending.pop()
        if name in found: continue
        found.add(name); pending.extend(_called_effects(definitions[name],definitions)-found)
    return found
def _assert_guarded_stamp(testcase,definition,name,ident,queue,value,witness,native_context,stamp,stamp_epoch,join):
    _guard,limit,effect=_helper_guard_and_effects(definition,name)
    guard=_positive_conjunct_triples(limit)
    required=[('var:ywc_v03_jhg_inline_reservation','=','%s'%ident),
      ('var:ywc_v03_jhg_inline_epoch','>','0'),
      ('var:ywc_v03_jhg_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value))]
    for atom in required: testcase.assertIn(atom,guard,(name,'guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    counterpart='sender' if '_body_completed_' in stamp else 'body'
    forbidden={f'ywc_v03_jhg_inline_{counterpart}_completed_{ident}',
               f'ywc_v03_jhg_inline_{counterpart}_completed_epoch_{ident}'}
    if counterpart=='body': forbidden.add('ywc_v03_major_event_cooldown')
    for node in _walk(limit):
        testcase.assertFalse(node.key.startswith('ywc_v03_can_deliver'),(name,'receipt cannot recheck delivery availability'))
        testcase.assertFalse(node.key.removeprefix('var:') in forbidden or
                             (isinstance(node.value,str) and node.value.removeprefix('var:') in forbidden),
                             (name,'independent receipt guard',node.key,node.value))
    writes=_setvar_writes(effect)
    stamps=[(n,v,node) for n,v,node in writes if n in {stamp,stamp_epoch}]
    testcase.assertEqual({n for n,_,_ in stamps},{stamp,stamp_epoch},name)
    testcase.assertEqual([(n,v) for n,v,_ in stamps],[(stamp,'1'),(stamp_epoch,'var:ywc_v03_jhg_inline_reservation_epoch')],
                         (name,'writes only its own completed receipt and reservation epoch'))
    unexpected=[n for n,_,_ in writes if ('_sender_completed_' in n or '_body_completed_' in n) and n not in {stamp,stamp_epoch}]
    testcase.assertEqual(unexpected,[],(name,'return helper cannot mint counterpart receipt'))
    self_calls=[n for n in _walk(effect) if n.key==join and n.op=='=' and n.value=='yes']
    testcase.assertEqual(len(self_calls),1,(name,'join call'))
    positions={node.start:i for i,node in enumerate(_nodes(effect))}
    testcase.assertTrue(all(node.start in positions for _,_,node in stamps),(name,'receipt writes must be direct guarded effects'))
    testcase.assertIn(self_calls[0].start,positions,(name,'join must be a direct guarded effect'))
    for _n,_v,node in stamps: testcase.assertLess(positions[node.start],positions[self_calls[0].start],(name,'stamp before join'))
    return guard,effect
def _assert_receipt_join(testcase,definition,name,ident,queue,value,witness,native_context):
    _guard,limit,effect=_helper_guard_and_effects(definition,name)
    guard=_positive_conjunct_triples(limit)
    required=[('var:ywc_v03_jhg_inline_reservation','=','%s'%ident),
      ('var:ywc_v03_jhg_inline_epoch','>','0'),
      ('var:ywc_v03_jhg_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value)),
      ('var:ywc_v03_jhg_inline_sender_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_jhg_inline_sender_completed_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:ywc_v03_jhg_inline_body_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_jhg_inline_body_completed_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:ywc_v03_jhg_inline_callback_%s'%ident,'=','1'),
      ('var:ywc_v03_jhg_inline_callback_candidate_%s'%ident,'=','%s'%ident),
      ('var:ywc_v03_jhg_inline_callback_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:ywc_v03_jhg_inline_callback_queue_%s'%ident,'=','var:'+queue)]
    for atom in required: testcase.assertIn(atom,guard,(name,'join guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    calls=[n for n in _walk(effect) if n.key==f'ywc_v03_jhg_inline_ack_{ident}' and n.op=='=' and n.value=='yes']
    testcase.assertEqual(len(calls),1,(name,'ACK call'))
    testcase.assertIn(calls[0],_nodes(effect),(name,'ACK must be a direct guarded effect'))
    return guard,effect
def _assert_callback_contract(testcase,definition,name,ident,queue,value,witness,native_context):
    _guard,limit,effect=_helper_guard_and_effects(definition,name)
    guard=_positive_conjunct_triples(limit)
    for atom in [('var:ywc_v03_jhg_inline_reservation','=',str(ident)),
      ('var:ywc_v03_jhg_inline_epoch','>','0'),('var:ywc_v03_jhg_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value))]:
        testcase.assertIn(atom,guard,(name,'callback guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    expected={f'ywc_v03_jhg_inline_callback_{ident}':'1',
      f'ywc_v03_jhg_inline_callback_candidate_{ident}':str(ident),
      f'ywc_v03_jhg_inline_callback_epoch_{ident}':'var:ywc_v03_jhg_inline_reservation_epoch',
      f'ywc_v03_jhg_inline_callback_queue_{ident}':'var:'+queue}
    writes=_setvar_writes(effect)
    for key,value in expected.items():
        selected=[(actual,node) for written,actual,node in writes if written==key]
        testcase.assertEqual(len(selected),1,(name,key,'exactly one callback field write'))
        testcase.assertEqual(selected[0][0],value,(name,key))
        testcase.assertIn(selected[0][1],_nodes(effect),(name,key,'direct guarded write'))
    calls=[n for n in _walk(effect) if n.key==f'ywc_v03_jhg_inline_join_{ident}' and n.op=='=' and n.value=='yes']
    testcase.assertEqual(len(calls),1,(name,'one shared join wake'))
    positions={node.start:i for i,node in enumerate(_nodes(effect))}
    testcase.assertIn(calls[0].start,positions,(name,'direct join wake'))
    for written,_value,node in writes:
        if written in expected: testcase.assertLess(positions[node.start],positions[calls[0].start],(name,'callback fields before join'))
    return guard,effect
def _assert_ack_guard(testcase,definition,name,ident,queue,value,witness,native_context):
    _guard,limit,effect=_helper_guard_and_effects(definition,name)
    guard=_positive_conjunct_triples(limit)
    for atom in [('var:ywc_v03_jhg_inline_reservation','=',str(ident)),
      ('var:ywc_v03_jhg_inline_epoch','>','0'),('var:ywc_v03_jhg_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_jhg_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value)),
      ('var:ywc_v03_jhg_inline_sender_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_jhg_inline_sender_completed_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:ywc_v03_jhg_inline_body_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_jhg_inline_body_completed_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:ywc_v03_jhg_inline_callback_%s'%ident,'=','1'),
      ('var:ywc_v03_jhg_inline_callback_candidate_%s'%ident,'=',str(ident)),
      ('var:ywc_v03_jhg_inline_callback_epoch_%s'%ident,'=','var:ywc_v03_jhg_inline_reservation_epoch'),
      ('var:ywc_v03_jhg_inline_callback_queue_%s'%ident,'=','var:'+queue)]:
        testcase.assertIn(atom,guard,(name,'ACK guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    return guard,effect
def _native_mutation(nodes):
    for node in _walk(nodes):
        if node.key.startswith('ywc_jhg_') and node.op=='=' and node.value=='yes': return True
        if node.key in {'remove_variable','clear_variable'} and isinstance(node.value,str) and node.value.startswith('ywc_jhg_'): return True
        if node.key in {'set_variable','change_variable','clamp_variable'} and isinstance(node.value,tuple):
            if any(n.key=='name' and isinstance(n.value,str) and n.value.startswith('ywc_jhg_') for n in children(node)): return True
    return False


def _native_jhg_variable_refs(nodes):
    refs=set()
    for n in _walk(nodes):
        if n.key.startswith('var:ywc_jhg_'): refs.add(n.key[4:])
        elif n.key=='has_variable' and isinstance(n.value,str) and n.value.startswith('ywc_jhg_'): refs.add(n.value)
        elif n.key in {'remove_variable','clear_variable'} and isinstance(n.value,str) and n.value.startswith('ywc_jhg_'): refs.add(n.value)
        elif n.key in {'set_variable','change_variable'} and isinstance(n.value,tuple):
            refs.update(x.value for x in n.value if x.key=='name' and isinstance(x.value,str) and x.value.startswith('ywc_jhg_'))
    return refs
def _scalar_rows(nodes):
    for n in _walk(nodes):
        if not isinstance(n.value,tuple): yield n.key,n.op,n.value
def _builder_defs(text):
    out={}
    for node in parse_block('{\n'+text+'\n}'):
        if node.key in out: raise AssertionError(('duplicate builder definition',node.key))
        out[node.key]=node.value
    return out
def _formal_generated_projection(cat):
    """Actual formal outputs follow complete catalog opt-in through public APIs."""
    from tools import build_v03_content
    enabled=['inline_delivery_adapter' in arc for arc in cat['arcs']]
    adapter=None
    if any(enabled):
        if not all(enabled): raise AssertionError('partial JHG inline metadata')
        validate_inline_catalog(cat)
        adapter=render_inline_country_adapters(cat)
    return (adapter,_builder_defs(build_v03_content._render_journal_file(cat,adapter)),
            _builder_defs(build_v03_content._render_event_file(cat,ROOT,adapter)))


def _mutate_one_helper_definition(source,name):
    wrapped='{\n'+source+'\n}'
    matches=[node for node in parse_block(wrapped) if node.key==name]
    if len(matches)!=1: raise AssertionError(('native helper definition count',name,len(matches)))
    node=matches[0]; start=node.start-2; end=node.end-2
    definition=source[start:end]; opener=definition.find('{')
    if opener<0: raise AssertionError(('native helper block missing',name))
    mutant=source[:start]+definition[:opener+1]+' always = no '+definition[opener+1:]+source[end:]
    before=_builder_defs(source); after=_builder_defs(mutant)
    changed={key for key in before if _rows(before[key])!=_rows(after[key])}
    if changed!={name}: raise AssertionError(('helper mutant scope',name,changed))
    return mutant
def _contains_queue(node,queue,value):
    return any(n.key=='var:'+queue and n.op=='=' and n.value==str(value) for n in _walk((node,)))
def _locate_sender_branch(journal_script,event_id,queue,value):
    root=parse_block(journal_script); monthly=direct_values(root,'on_monthly_pulse')
    pulse=direct_values(children(monthly[0]),'effect')[0]
    matches=[]
    def visit(nodes):
        for node in nodes:
            if node.key in {'if','else_if'}:
                direct=children(node); ev=direct_values(direct,'trigger_event'); lim=direct_values(direct,'limit')
                ids=direct_values(children(ev[0]),'id') if len(ev)==1 else []
                if (len(ev)==1 and len(lim)==1 and len(ids)==1 and ids[0].value==event_id
                    and _contains_queue(lim[0],queue,value)):
                    matches.append(node)
            if isinstance(node.value,tuple): visit(node.value)
    visit(children(pulse))
    return matches
def _int_paths(value,path=()):
    if type(value) is int:
        yield path,value
    elif isinstance(value,dict):
        for key,item in value.items(): yield from _int_paths(item,path+(key,))
    elif isinstance(value,list):
        for i,item in enumerate(value): yield from _int_paths(item,path+(i,))
def _path_get(value,path):
    for part in path: value=value[part]
    return value
def _path_set(value,path,replacement):
    for part in path[:-1]: value=value[part]
    value[path[-1]]=replacement
@contextmanager
def _isolated_build_root(candidate):
    """Copy only builder inputs; public build writes exclusively under temp root."""
    temp=Path(tempfile.mkdtemp(prefix='jhg-inline-build-')).resolve()
    owned_temp=temp
    temp_parent=Path(tempfile.gettempdir()).resolve()
    (temp/'data/content').mkdir(parents=True,exist_ok=True)
    (temp/'yongchang_world/common').mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'data/content/v03',temp/'data/content/v03')
    for folder in ('scripted_effects','scripted_triggers'):
        source=ROOT/f'yongchang_world/common/{folder}'
        target=temp/f'yongchang_world/common/{folder}'
        shutil.copytree(source,target)
    catalog_rel=Path('data/content/v03/countries/jhg.json')
    (temp/catalog_rel).write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest_path=temp/'data/content/v03/manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    required=('common/scripted_effects/ywc_v03_delivery_jhg_effects.txt',
              'common/scripted_triggers/ywc_v03_delivery_jhg_triggers.txt')
    for rel in required:
        if rel not in manifest['owned_outputs']: manifest['owned_outputs'].append(rel)
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try: yield temp
    finally:
        target=temp.resolve()
        if target!=owned_temp or target.parent!=temp_parent or not target.name.startswith('jhg-inline-build-'):
            raise AssertionError(('refusing non-owned temporary directory cleanup',str(target)))
        shutil.rmtree(target)
def _queue_candidates(src):
    root=parse_block('{ '+src+' }')
    if len(root)!=1 or root[0].key not in {'if','else_if'}: raise ValueError('JHG sender must be one conditional branch')
    limits=direct_values(children(root[0]),'limit'); events=direct_values(children(root[0]),'trigger_event')
    if len(limits)!=1 or len(events)!=1 or not isinstance(events[0].value,tuple): raise ValueError('sender branch must bind one limit and event')
    ids=direct_values(children(events[0]),'id')
    if len(ids)!=1 or type(ids[0].value) is not str: raise ValueError('trigger_event needs one literal id')
    found=[]
    def walk(nodes,neg=False):
        for n in nodes:
            if n.key in {'OR','XOR','NOR'}: raise ValueError('unsupported queue boolean')
            if n.key=='NOT': walk(children(n),True)
            elif isinstance(n.value,tuple): walk(n.value,neg)
            elif not neg and n.key.startswith('var:ywc_jhg_') and n.op=='=' and type(n.value) is str and n.value.isdigit():
                q=n.key[4:]; kind='notice' if '_notice_pending_event' in q else 'normal'
                found.append({'queue':q,'kind':kind,'mode':'exact','value':int(n.value)})
    walk(children(limits[0]))
    if len(found)!=1: raise ValueError(f'expected one positive native queue: {found!r}')
    return found

def _binding(jid,script):
    bound=_kor_source_binding(jid,script,candidate_parser=_queue_candidates,exclusion_parser=lambda _s:[])
    root=parse_block(script); monthly=direct_values(root,'on_monthly_pulse')
    if len(monthly)!=1: raise ValueError(f'{jid}: one native monthly pulse required')
    effects=direct_values(children(monthly[0]),'effect')
    if len(effects)!=1: raise ValueError(f'{jid}: one pulse effect required')
    nodes=children(effects[0]); result=[]; chain_at={}; chain=-1; in_chain=False
    for ordinal,node in enumerate(nodes):
        if node.key=='if': chain+=1; in_chain=True
        elif node.key in {'else_if','else'} and in_chain: pass
        else: in_chain=False
        if node.key in {'if','else_if','else'} and in_chain: chain_at[ordinal]=chain
    for row in bound['branches']:
        node=next((n for n in nodes if n.start==row['start'] and n.end==row['end']),None)
        if node is None: raise ValueError(f'{jid}: sender AST binding lost')
        ordinal=nodes.index(node)
        if ordinal not in chain_at: raise ValueError(f'{jid}: sender is outside an authored if/else chain')
        result.append({**row,'statement_ordinal':ordinal,'chain_index':chain_at[ordinal],'branch_kind':node.key,
                       'candidates':_queue_candidates(script[node.start:node.end]),'queue_exclusions':[]})
    return result

def _v2_catalog_from_formal_jhg_source():
    result=copy.deepcopy(catalog())
    for arc in result['arcs']:
        phases=[]; branches=[]
        for je in arc['journals']:
            suffix=je['id'].removeprefix('ywc_je_v03_jhg_')
            phases.append({'journal':je['id'],'live_witness':f'ywc_v03_jhg_inline_live_{suffix}',
              'source_script_sha256':hashlib.sha256(je['script'].encode()).hexdigest(),
              'goal_sha256':hashlib.sha256(je['goal'].encode()).hexdigest(),
              'exit_sha256':hashlib.sha256(je['exit_conditions'].encode()).hexdigest()})
            for s in _binding(je['id'],je['script']):
                branches.append({'journal':je['id'],**{k:s[k] for k in ('branch_index','statement_ordinal','chain_index','branch_kind','event')},
                  'branch_sha256':s['sha256'],'limit_sha256':s['limit_sha256'],'chain_prior':s['chain_prior'],
                  'chain_sha256':s['chain_sha256'],'candidates':s['candidates'],'queue_exclusions':s['queue_exclusions']})
        arc['inline_delivery_adapter']={'schema':'v03.foundation_inline_adapter.v2','live_phases':phases,
             'branches':branches,'direct_adds':_kor_direct_adds(arc)}
    return result

def assert_inline_supported(testcase):
    candidate=_v2_catalog_from_formal_jhg_source()
    try:
        validate_inline_catalog(candidate); rendered=render_inline_country_adapters(candidate)
    except ValueError as exc:
        if 'inline adapter is currently enabled only for registered inline countries' in str(exc):
            testcase.fail(f'JHG inline adapter feature is not registered: {exc}')
        raise
    if len(rendered.get('event_hooks',{}))!=24: testcase.fail('JHG must guard all 24 events')
    return rendered

class JhgInlineStaticContract(unittest.TestCase):
    def test_ast_projection_helpers_accept_single_nodes_and_match_atomic_source_triples(self):
        self.assertEqual(len(JE_IDS),6)
        exercised=0
        from tools import build_v03_content
        journals=_builder_defs(build_v03_content._render_journal_file(catalog(),None))
        for jid in sorted(JE_IDS):
            parsed=journals[jid]
            for hook in ('immediate','on_complete','on_fail'):
                blocks=_direct(parsed,hook)
                for block in blocks:
                    self.assertIsInstance(_rows(block),list)
                    _setvar_names(block)
                    self.assertIsInstance(len(_nodes(block)),int)
                    exercised+=1
        events=_builder_defs(build_v03_content._render_event_file(catalog(),ROOT,None))
        for event_id,event in events.items():
            if event_id not in {f'ywc_jhg.{n}' for n in [*range(1000,1008),*range(1010,1020),*range(1020,1026)]}: continue
            for hook in ('immediate','option'):
                for block in _direct(event,hook):
                    self.assertIsInstance(_rows(block),list)
                    _setvar_names(block); len(_nodes(block)); exercised+=1
        self.assertGreaterEqual(exercised,60)
        source='''probe = { if = { limit = { AND = { var:epoch > 0 var:reservation = 17 OR = { var:context_a = 1 var:context_b = 1 } NOT = { var:disabled = 1 } } } set_variable = { name = receipt value = 1 } join_probe = yes } }'''
        definition=_builder_defs(source)['probe']; _guard,limit,effect=_helper_guard_and_effects(definition,'probe')
        atoms=_triples(definition)
        self.assertIn(('var:epoch','>','0'),atoms)
        self.assertIn(('var:reservation','=','17'),_positive_conjunct_triples(limit))
        positive=_positive_conjunct_triples(limit)
        self.assertNotIn(('var:context_a','=','1'),positive)
        self.assertNotIn(('var:disabled','=','1'),positive)
        writes=_setvar_writes(effect)
        self.assertEqual([(name,value) for name,value,_ in writes],[('receipt','1')])
        self.assertEqual(_called_effects(effect,{'join_probe'}),{'join_probe'})
        real_catalog=catalog(); real_je=next(j for arc in real_catalog['arcs'] for j in arc['journals']
                                               if any(b['candidates'][0]['kind']=='notice' for b in _binding(j['id'],j['script'])))
        real_branch=next(b for b in _binding(real_je['id'],real_je['script']) if b['candidates'][0]['kind']=='notice')
        real_source=real_je['script'][real_branch['start']:real_branch['end']]
        real_ast=parse_block('{ '+real_source+' }')[0]; real_limit=_direct(real_ast,'limit')[0]
        real_candidate=real_branch['candidates'][0]
        real_atom=('var:'+real_candidate['queue'],'=',str(real_candidate['value']))
        self.assertIn(real_atom,_triples(real_limit),'actual authored notice predicate projects to an atomic AST triple')
        changed_source=real_source.replace(f'var:{real_candidate["queue"]} = {real_candidate["value"]}',
                                           f'var:{real_candidate["queue"]} = {real_candidate["value"]+1}',1)
        changed_ast=parse_block('{ '+changed_source+' }')[0]
        self.assertNotIn(real_atom,_triples(_direct(changed_ast,'limit')[0]),
                         'the same structural proof rejects a source predicate mutation')
        with self.assertRaisesRegex(TypeError,'Node or Node sequence'):_nodes('not an AST')

    def test_all_six_native_immediate_prefixes_and_exact_witness_ast(self):
        nonempty=empty=0
        for arc in catalog()['arcs']:
            for je in arc['journals']:
                authored=parse_block(je['script'])
                blocks=_direct(authored,'immediate')
                native=_nodes(blocks[0]) if blocks else []
                nonempty+=bool(blocks); empty+=not bool(blocks)
                witness='ywc_v03_jhg_inline_live_'+je['id'].removeprefix('ywc_je_v03_jhg_')
                # A local expected AST projection of the contract, never installed as adapter output.
                expected=parse_block('{ immediate = { set_variable = { name = '+witness+' value = 1 } } }')
                from dataclasses import replace
                projected=[replace(expected[0],value=tuple(native+_nodes(expected[0])))]
                _assert_witness_immediate(self,projected,authored,witness,je['id'])
                with self.assertRaises(AssertionError):
                    _assert_witness_immediate(self,expected,authored,witness+'_wrong',je['id'])
        self.assertEqual((nonempty,empty),(3,3))
        with self.assertRaisesRegex(TypeError,'block Node'):
            _nodes(parse_block('{ scalar = yes }')[0])

    def test_real_native_guard_helper_projects_direct_effects_and_rejects_invalid_scope(self):
        definitions=_builder_defs(EFFECTS_PATH.read_text(encoding='utf-8-sig'))
        name='ywc_jhg_court_close_as_breach'
        definition=definitions[name]
        outer,limit,effects=_helper_guard_and_effects(definition,name)
        self.assertEqual(_rows(limit),_rows(_direct(outer,'limit')[0]))
        self.assertEqual(_rows(effects),_rows(children(outer)[1:]))
        self.assertEqual([node.key for node in effects],['set_variable','set_variable','ywc_jhg_court_finalize'])
        self.assertEqual(_called_effects(effects,definitions),{'ywc_jhg_court_finalize'})
        self.assertEqual(len(_setvar_writes(effects)),2)
        # Actual multi-if helper remains valid native source, but is not one owned stamp guard.
        with self.assertRaisesRegex(AssertionError,'one owned outer if'):
            _helper_guard_and_effects(definitions['ywc_jhg_court_close_as_established'],'native multi-if')
        with self.assertRaisesRegex(AssertionError,'direct children'):
            _helper_guard_and_effects(parse_block('{ if = { limit = { always = yes } effect = { always = yes } } }'),'wrapper')
        with self.assertRaisesRegex(AssertionError,'leading direct limit'):
            _helper_guard_and_effects(parse_block('{ if = { set_variable = { name = bad value = 1 } limit = { always = yes } } }'),'scope')

    def test_real_snapshot_boolean_guards_validate_presence_and_value_without_weakening_ownership(self):
        from tools import build_v03_content
        from dataclasses import replace
        outputs=build_v03_content.render_all(ROOT)
        source=outputs[Path('common/scripted_triggers/ywc_v03_delivery_mgl_triggers.txt')]
        definitions=_builder_defs(source)
        matches=[]
        for definition in definitions.values():
            for node in _walk(definition):
                if node.key!='OR' or not isinstance(node.value,tuple): continue
                for atom in _triples(node):
                    if atom[0].startswith('var:ywc_mgl_'):
                        native=atom[0][4:]
                        if _is_exact_snapshot_check(node,native,'ywc_v03_mgl_inline_'):
                            matches.append((node,native))
        self.assertTrue(matches,'actual public MGL snapshots are successful Boolean primitive controls')
        node,native=matches[0]
        self.assertFalse(_is_exact_snapshot_check(node,native+'_wrong','ywc_v03_mgl_inline_'))
        def remove_atom(sequence,predicate):
            result=[]
            for item in sequence:
                if predicate(item): continue
                result.append(replace(item,value=tuple(remove_atom(children(item),predicate))) if isinstance(item.value,tuple) else item)
            return result
        for predicate in (
            lambda item:item.key=='has_variable' and item.value==native,
            lambda item:item.key=='var:'+native,
            lambda item:item.key=='NOT'):
            broken=replace(node,value=tuple(remove_atom(children(node),predicate)))
            self.assertFalse(_is_exact_snapshot_check(broken,native,'ywc_v03_mgl_inline_'))
        # Ownership hidden in either OR arm is never promoted to a positive conjunct.
        self.assertNotIn(('var:owner','=','1'),_positive_conjunct_triples(
            parse_block('{ OR = { AND = { var:owner = 1 } AND = { always = yes } } }')))

    def test_native_source_inventory_and_real_queue_candidates(self):
        cat=catalog(); self.assertEqual(cat['key'],'country_jhg'); self.assertEqual({a['slug'] for a in cat['arcs']},ARC_IDS)
        native=_native_journals(); counts={}; kinds={'normal':0,'notice':0}; events=[]
        for arc in cat['arcs']:
            for je in arc['journals']:
                self.assertIn(je['id'],JE_IDS); self.assertIn(je['id'],native)
                branches=_binding(je['id'],je['script']); counts[je['id']]=len(branches)
                for index,row in enumerate(branches):
                    prior=[x for x in branches[:index] if x['chain_index']==row['chain_index']]
                    self.assertEqual([x['ordinal'] for x in row['chain_prior']],
                                     [x['statement_ordinal'] for x in prior],je['id'])
                    self.assertEqual([x['sha256'] for x in row['chain_prior']],
                                     [x['sha256'] for x in prior],je['id'])
                for row in branches:
                    self.assertEqual(len(row['candidates']),1); c=row['candidates'][0]
                    kinds[c['kind']]+=1; events.append(row['event'])
                    self.assertIn(c['value'],range(1000,1030))
        self.assertEqual(set(counts),JE_IDS)
        self.assertEqual(sum(counts.values()),58)
        self.assertEqual(kinds,{'normal':52,'notice':6})
        self.assertEqual(len(events),58); self.assertEqual(len(set(events)),24)
    def test_notice_pre_and_post_decisions_follow_distinct_native_predicates(self):
        cat=catalog(); noticed=[]
        for arc in cat['arcs']:
            for je in arc['journals']:
                for row in _binding(je['id'],je['script']):
                    c=row['candidates'][0]
                    if c['kind']!='notice': continue
                    source=je['script'][row['start']:row['end']]
                    self.assertIn(f'has_variable = {c["queue"].removesuffix("_notice_pending_event")}_36_notice',source)
                    self.assertIn(f'has_variable = {c["queue"].removesuffix("_notice_pending_event")}_notice_delivery_36',source)
                    self.assertIn('_notice_delivery_12 value = 1',source)
                    self.assertIn('_notice_delivery_36 value = 1',source)
                    self.assertIn('_12_notice_delivered value = 1',source)
                    self.assertIn('_36_notice_delivered value = 1',source)
                    # Native source clears its queue before dispatch. The adapter
                    # contract must defer that one clear until successful ACK.
                    self.assertIn(f'remove_variable = {c["queue"]}',source)
                    noticed.append(source)
        self.assertEqual(len(noticed),6)
    def test_native_sender_locator_uses_exact_candidate_not_first_shared_event(self):
        cat=catalog(); bound=[]
        for arc in cat['arcs']:
            for je in arc['journals']:
                for branch in _binding(je['id'],je['script']):
                    c=branch['candidates'][0]
                    matches=_locate_sender_branch(je['script'],branch['event'],c['queue'],c['value'])
                    self.assertEqual(len(matches),1,(je['id'],branch['branch_index'],branch['event'],c))
                    self.assertEqual((matches[0].start,matches[0].end),(branch['start'],branch['end']))
                    bound.append((branch['event'],c['queue'],je['id']))
        for event_id in ('ywc_jhg.1007','ywc_jhg.1018','ywc_jhg.1025'):
            rows=[row for row in bound if row[0]==event_id]
            self.assertGreaterEqual(len(rows),2,event_id)
            self.assertEqual(len(rows)%2,0,event_id)
            self.assertEqual({queue.endswith('_notice_pending_event') for _,queue,_ in rows},{True,False})
            by_journal={jid:{queue.endswith('_notice_pending_event') for _,queue,j in rows if j==jid}
                        for _,_,jid in rows}
            self.assertTrue(all(kinds=={True,False} for kinds in by_journal.values()),(event_id,by_journal))
            self.assertEqual(sum(len(kinds) for kinds in by_journal.values()),len(rows))
    def test_all_28_event_layout_positives_are_canonical_and_leave_bound_journals_untouched(self):
        candidate=_v2_catalog_from_formal_jhg_source()
        journal_sources={j['id']:j['script'] for arc in candidate['arcs'] for j in arc['journals']}
        events=[e for arc in candidate['arcs'] for e in arc['events']]
        self.assertEqual(len(events),28)
        for event in events:
            for field in ('trigger','immediate'):
                original=event[field]
                formatted='{ # legal layout comment\n '+original[1:-1].replace(' ','\n  ')+'\n}'
                self.assertEqual(_rows(parse_block(formatted)),_rows(parse_block(original)),(event['id'],field))
                self.assertNotEqual(formatted,original)
                self.assertEqual({j['id']:j['script'] for arc in candidate['arcs'] for j in arc['journals']},journal_sources)
    def test_bound_journal_layout_mutation_invalidates_raw_binding_without_weakened_hash(self):
        candidate=_v2_catalog_from_formal_jhg_source()
        arc=candidate['arcs'][0]; je=arc['journals'][0]
        metadata=arc['inline_delivery_adapter']; phase=next(x for x in metadata['live_phases'] if x['journal']==je['id'])
        branch=next(x for x in metadata['branches'] if x['journal']==je['id'])
        original=je['script']; original_ast=_rows(parse_block(original))
        altered=original.replace('trigger_event =',' # legal AST comment\n trigger_event =',1)
        self.assertEqual(_rows(parse_block(altered)),original_ast)
        self.assertNotEqual(hashlib.sha256(original.encode()).hexdigest(),hashlib.sha256(altered.encode()).hexdigest())
        self.assertNotEqual(branch['branch_sha256'],_binding(je['id'],altered)[0]['sha256'])
        self.assertNotEqual(phase['source_script_sha256'],hashlib.sha256(altered.encode()).hexdigest())
        self.assertEqual(je['script'],original,'the positive event-layout controls do not touch raw-bound JE text')
    def test_all_native_jhg_helper_ast_mutation_controls_are_scoped(self):
        helpers=((EFFECTS_PATH,foundation.REQUIRED_EFFECTS),(TRIGGERS_PATH,foundation.REQUIRED_TRIGGERS))
        for path,names in helpers:
            source=path.read_text(encoding='utf-8-sig')
            defs=_builder_defs(source)
            for name in names:
                with self.subTest(helper=name):
                    self.assertIn(name,defs)
                    mutant=_mutate_one_helper_definition(source,name)
                    original=_builder_defs(source); changed=_builder_defs(mutant)
                    self.assertEqual({key for key in original if _rows(original[key])!=_rows(changed[key])},{name})
    def test_native_builder_positive_control_binds_full_journal_and_event_asts(self):
        from tools import build_v03_content
        cat=catalog()
        native_journals=_builder_defs(build_v03_content._render_journal_file(cat,None))
        native_events=_builder_defs(build_v03_content._render_event_file(cat,ROOT,None))
        adapter,expected_journals,expected_events=_formal_generated_projection(cat)
        actual_journals=_builder_defs(JOURNAL_PATH.read_text(encoding='utf-8-sig'))
        actual_events=_builder_defs(EVENT_PATH.read_text(encoding='utf-8-sig'))
        self.assertEqual({k:(_rows(v) if isinstance(v,tuple) else v) for k,v in actual_journals.items()},
                         {k:(_rows(v) if isinstance(v,tuple) else v) for k,v in expected_journals.items()})
        self.assertEqual({k:(_rows(v) if isinstance(v,tuple) else v) for k,v in actual_events.items()},
                         {k:(_rows(v) if isinstance(v,tuple) else v) for k,v in expected_events.items()})
        for arc in cat['arcs']:
            for je in arc['journals']:
                native=native_journals[je['id']]
                expected=[*parse_block(je['script']),*parse_block('{ complete = '+je['goal']+' fail = '+je['exit_conditions']+' }')]
                self.assertEqual(_rows(native),_rows(expected),(je['id'],'complete bare native business AST'))
                # Fields outside the explicit source/witness/terminal instrumentation stay exact.
                for field in ('complete','fail','possible','is_shown_when_inactive','weight','icon'):
                    self.assertEqual([_rows(n) if isinstance(n.value,tuple) else (n.key,n.op,n.value) for n in _direct(native,field)],
                                     [_rows(n) if isinstance(n.value,tuple) else (n.key,n.op,n.value) for n in _direct(actual_journals[je['id']],field)],(je['id'],field))
            for event in arc['events']:
                native=native_events[event['id']]
                self.assertEqual([_rows(n) for n in _direct(native,'option')],
                                 [_rows(n) for n in _direct(actual_events[event['id']],'option')],event['id'])
                self.assertEqual(_rows(_direct(native,'immediate')[0]),_rows(parse_block(event['immediate'])))
                self.assertEqual(_rows(_direct(native,'trigger')[0]),_rows(parse_block(event['trigger'])))
                if event['id'] not in {'ywc_jhg.1026', 'ywc_jhg.1027', 'ywc_jhg.1030', 'ywc_jhg.1031'}:
                    self.assertEqual(_rows(_direct(native,'immediate')[0]),[('ywc_v03_mark_major_delivered','=','yes')])
        self.assertEqual(len(native_journals),6)
        self.assertEqual({e['id'] for a in cat['arcs'] for e in a['events']},
                         {f'ywc_jhg.{n}' for n in [*range(1000,1008),*range(1010,1020),*range(1020,1028),1030,1031]})
        if adapter is None:
            self.assertEqual({k:(_rows(v) if isinstance(v,tuple) else v) for k,v in actual_journals.items()},{k:(_rows(v) if isinstance(v,tuple) else v) for k,v in native_journals.items()})
            self.assertEqual({k:(_rows(v) if isinstance(v,tuple) else v) for k,v in actual_events.items()},{k:(_rows(v) if isinstance(v,tuple) else v) for k,v in native_events.items()})
        # After genuine opt-in, registered_full_body... pins every wrapper,
        # source continuation, witness suffix and whole native event prefix.

    def test_all_54_non_jhg_generated_outputs_remain_byte_exact(self):
        from tools import build_v03_content
        catalogs=build_v03_content.load_catalogs(ROOT)
        rendered=build_v03_content.render_all(ROOT)
        paths=[p for key,cat in catalogs.items() if key!='country_jhg' for p in build_v03_content._catalog_outputs(cat)]
        self.assertEqual(len(paths),54); self.assertEqual(len(set(paths)),54)
        for path in paths:
            with self.subTest(output=path.as_posix()):
                expected=b'\xef\xbb\xbf'+rendered[path].encode('utf-8')
                self.assertEqual((ROOT/'yongchang_world'/path).read_bytes(),expected)
    def test_recursive_numeric_type_alias_controls_are_real_and_value_preserving(self):
        valid=_v2_catalog_from_formal_jhg_source()
        paths=list(_int_paths(valid))
        self.assertTrue(paths)
        for path,value in paths:
            with self.subTest(path=path,alias='float'):
                mutant=copy.deepcopy(valid); _path_set(mutant,path,float(value))
                self.assertEqual(mutant,valid,'same numeric value must isolate a type alias')
                self.assertIs(type(_path_get(mutant,path)),float)
        for path,value in paths:
            if value not in (0,1): continue
            with self.subTest(path=path,alias='bool'):
                mutant=copy.deepcopy(valid); _path_set(mutant,path,bool(value))
                self.assertEqual(mutant,valid,'bool/int equality must not hide the alias')
                self.assertIs(type(_path_get(mutant,path)),bool)
    def test_registered_positive_then_metadata_source_helper_and_layout_mutants(self):
        # Every mutant family is gated by real support, so current unsupported
        # behavior cannot masquerade as successful rejection.
        assert_inline_supported(self)
        from tools.v03_inline_delivery_adapter import validate_jhg_native_helper_source
        valid=_v2_catalog_from_formal_jhg_source()
        validate_inline_catalog(valid)
        baseline=render_inline_country_adapters(valid)
        for path,value in _int_paths(valid):
            mutant=copy.deepcopy(valid); _path_set(mutant,path,float(value))
            with self.subTest(numeric_path=path,alias='float'):
                with self.assertRaises(ValueError): validate_inline_catalog(mutant)
        for path,value in _int_paths(valid):
            if value not in (0,1): continue
            mutant=copy.deepcopy(valid); _path_set(mutant,path,bool(value))
            with self.subTest(numeric_path=path,alias='bool'):
                with self.assertRaises(ValueError): validate_inline_catalog(mutant)
        self.assertEqual(len(baseline['event_hooks']),24)
        mutations=[]
        alias=copy.deepcopy(valid); alias['arcs'][0]['inline_delivery_adapter']['branches'][0]['branch_index']=True
        mutations.append(('bool integer alias',alias))
        alias_name=copy.deepcopy(valid); ad=alias_name['arcs'][0]['inline_delivery_adapter']; ad['branches'][0]['sha256']=ad['branches'][0].pop('branch_sha256')
        mutations.append(('metadata field alias',alias_name))
        unknown=copy.deepcopy(valid); unknown['arcs'][0]['inline_delivery_adapter']['invented']='yes'
        mutations.append(('unknown metadata',unknown))
        unknown_nested=copy.deepcopy(valid); unknown_nested['arcs'][0]['inline_delivery_adapter']['branches'][0]['candidates'][0]['extra']=1
        mutations.append(('unknown candidate field',unknown_nested))
        duplicate=copy.deepcopy(valid); ad=duplicate['arcs'][0]['inline_delivery_adapter']; ad['branches'][1]['branch_index']=ad['branches'][0]['branch_index']
        mutations.append(('duplicate source identity',duplicate))
        duplicate_event=copy.deepcopy(valid); ad=duplicate_event['arcs'][0]['inline_delivery_adapter']; ad['branches'][1]['event']=ad['branches'][0]['event']
        mutations.append(('duplicate event binding',duplicate_event))
        drift=copy.deepcopy(valid); je=drift['arcs'][0]['journals'][0]; row=_binding(je['id'],je['script'])[0]; c=row['candidates'][0]
        needle=f'var:{c["queue"]} = {c["value"]}'; self.assertIn(needle,je['script']); je['script']=je['script'].replace(needle,f'var:{c["queue"]} = {c["value"]+1}',1)
        mutations.append(('source drift',drift))
        for label,mutant in mutations:
            with self.subTest(mutant=label):
                with self.assertRaises(ValueError): validate_inline_catalog(mutant)
                with self.assertRaises(ValueError): render_inline_country_adapters(mutant)
        helper_effects=EFFECTS_PATH.read_text(encoding='utf-8-sig')
        helper_triggers=TRIGGERS_PATH.read_text(encoding='utf-8-sig')
        validate_jhg_native_helper_source(helper_effects,helper_triggers)
        for path,names in ((EFFECTS_PATH,foundation.REQUIRED_EFFECTS),(TRIGGERS_PATH,foundation.REQUIRED_TRIGGERS)):
            source=path.read_text(encoding='utf-8-sig')
            for name in names:
                mutant=_mutate_one_helper_definition(source,name)
                with self.subTest(native_helper=name,change='ABI'):
                    args=(mutant,helper_triggers) if path==EFFECTS_PATH else (helper_effects,mutant)
                    with self.assertRaises(ValueError): validate_jhg_native_helper_source(*args)
                ast=parse_block('{ '+source+' }'); target=next(node for node in ast if node.key==name)
                duplicate=source+'\n'+source[target.start-2:target.end-2]
                with self.subTest(native_helper=name,change='duplicate'):
                    args=(duplicate,helper_triggers) if path==EFFECTS_PATH else (helper_effects,duplicate)
                    with self.assertRaises(ValueError): validate_jhg_native_helper_source(*args)
        # Raw-bound journal source layout edits must fail with stale metadata.
        stale=copy.deepcopy(valid); je=stale['arcs'][0]['journals'][0]
        je['script']=je['script'].replace('trigger_event =',' # layout-only comment\n trigger_event =',1)
        self.assertEqual(_rows(parse_block(je['script'])),_rows(parse_block(valid['arcs'][0]['journals'][0]['script'])))
        with self.assertRaises(ValueError): validate_inline_catalog(stale)
        # Formatting positives live on independent event ASTs and native helper
        # source, never on a journal branch carrying raw source bindings.
        helper_source=helper_triggers
        helper_layout=helper_source.replace(' = {',' = { # helper layout comment\n',1)
        self.assertEqual(_rows(parse_block('{ '+helper_source+' }')),_rows(parse_block('{ '+helper_layout+' }')))
        validate_jhg_native_helper_source(helper_effects,helper_layout)
        for arc in valid['arcs']:
            for event in arc['events']:
                for field in ('trigger','immediate'):
                    formatted=copy.deepcopy(valid)
                    target=next(e for a in formatted['arcs'] for e in a['events'] if e['id']==event['id'])
                    original=target[field]
                    target[field]='{ # event layout comment\n '+original[1:-1].replace(' ','\n  ')+'\n}'
                    self.assertEqual(_rows(parse_block(target[field])),_rows(parse_block(original)),(event['id'],field))
                    validate_inline_catalog(formatted)
                    self.assertEqual(render_inline_country_adapters(formatted),baseline)
    def test_registered_full_body_guard_ack_and_source_continuation_order(self):
        adapter=assert_inline_supported(self)
        from tools import build_v03_content
        cat=_v2_catalog_from_formal_jhg_source()
        self.assertEqual(len(adapter['event_hooks']),24)
        unhooked={'ywc_jhg.1026', 'ywc_jhg.1027', 'ywc_jhg.1030', 'ywc_jhg.1031'}
        self.assertEqual(set(adapter['event_hooks']),{e['id'] for a in cat['arcs'] for e in a['events']} - unhooked)
        self.assertEqual(len(adapter['live_witnesses']),6)
        effects=_builder_defs(adapter['effects'])
        candidate_rows=[]
        for arc0 in cat['arcs']:
            for je0 in arc0['journals']:
                for branch0 in _binding(je0['id'],je0['script']):
                    candidate_rows.append((len(candidate_rows)+1,je0,branch0))
        self.assertEqual(len(candidate_rows),58)
        generated_journals=_builder_defs(build_v03_content._render_journal_file(cat,adapter))
        for arc0 in cat['arcs']:
            for je0 in arc0['journals']:
                witness=adapter['live_witnesses'][je0['id']]
                body=generated_journals[je0['id']]
                authored_fields=parse_block(je0['script'])
                _assert_witness_immediate(self,body,authored_fields,witness,je0['id'])
                for terminal in ('on_complete','on_fail'):
                    blocks=_direct(body,terminal)
                    self.assertEqual(len(blocks),1)
                    authored_terminal=_direct(authored_fields,terminal)
                    terminal_nodes=_nodes(blocks[0])
                    native_terminal_nodes=_nodes(authored_terminal[0]) if authored_terminal else []
                    self.assertEqual(_rows(terminal_nodes[:len(native_terminal_nodes)]),_rows(native_terminal_nodes),
                                     (je0['id'],terminal,'complete native terminal prefix'))
                    self.assertEqual(_rows(terminal_nodes[len(native_terminal_nodes):]),[('remove_variable','=',witness)],
                                     (je0['id'],terminal,'clear live witness after native terminal'))
        generated_events=_builder_defs(build_v03_content._render_event_file(cat,ROOT,adapter))
        source_events={k:v for k,v in _builder_defs(build_v03_content._render_event_file(cat,ROOT,None)).items() if k!='namespace'}
        for arc in cat['arcs']:
            for event in arc['events']:
                body=generated_events[event['id']]
                if event['id'] in unhooked:
                    self.assertEqual(_rows(body), _rows(source_events[event['id']]),
                                     (event['id'], 'foreign or hidden event stays native and unhooked'))
                    continue
                immediate=_direct(body,'immediate'); self.assertEqual(len(immediate),1)
                native=parse_block(event['immediate'])
                self.assertEqual(len(_nodes(immediate[0])),1)
                guarded=_nodes(immediate[0])[0]; self.assertEqual(guarded.key,'if')
                fields=children(guarded)
                self.assertEqual(fields[0].key,'limit')
                self.assertEqual(_rows(fields[0].value),_rows(parse_block('{ OR = { '+' '.join(x+' = yes' for x in adapter['event_hooks'][event['id']])+' } }')))
                native_nodes=_nodes(native)
                body_effects=fields[1:]
                self.assertEqual(_rows(body_effects[:len(native_nodes)]),_rows(native_nodes),
                                 (event['id'],'full authored native immediate prefix'))
                proofs=adapter['inline_proofs'][event['id']]
                acks=adapter['ack_hooks'][event['id']]
                self.assertTrue(proofs); self.assertEqual(len(acks),len(adapter['event_hooks'][event['id']]))
                expected_suffix=parse_block('{ '+' '.join(proofs)+' '+' '.join(h+' = yes' for h in acks)+' }')
                suffix=body_effects[len(native_nodes):]
                self.assertEqual(_rows(suffix),_rows(expected_suffix),
                                 (event['id'],'body receipts/proof then ACK callbacks'))
                native_helper_calls=[n for n in _walk(immediate[0]) if n.key=='ywc_v03_mark_major_delivered' and n.op=='=' and n.value=='yes']
                suffix_native_calls=[n for n in _walk(suffix) if n.key=='ywc_v03_mark_major_delivered']
                self.assertEqual(len(native_helper_calls),1,(event['id'],'native cooldown helper exactly once in whole immediate'))
                self.assertEqual(suffix_native_calls,[],(event['id'],'owned suffix cannot repeat native cooldown helper'))
                native_trigger=_direct(source_events[event['id']],'trigger')
                built_trigger=_direct(body,'trigger'); self.assertEqual(len(native_trigger),1); self.assertEqual(len(built_trigger),1)
                authored_trigger=parse_block(event['trigger'])
                expected_trigger=parse_block('{ AND = { '+event['trigger'][1:-1]+' OR = { '+' '.join(name+' = yes' for name in adapter['event_hooks'][event['id']])+' } } }')
                self.assertEqual(_rows(built_trigger[0]),_rows(expected_trigger))
                native_options=_direct(source_events[event['id']],'option')
                built_options=_direct(body,'option')
                self.assertEqual(len(native_options),len(built_options))
                self.assertEqual([_rows(v) for v in native_options],[_rows(v) for v in built_options])
                bound=[(ident,je,b) for ident,je,b in candidate_rows if b['event']==event['id']]
                body_return_ids=[int(n.key.rsplit('_',1)[1]) for n in _walk(suffix)
                                 if n.key.startswith('ywc_v03_jhg_inline_body_return_') and n.op=='=' and n.value=='yes']
                self.assertEqual(body_return_ids,[ident for ident,_,_ in bound],event['id'])
                for ident,je,b in bound:
                    body_helper=f'ywc_v03_jhg_inline_body_return_{ident}'
                    self.assertIn(body_helper,effects)
                    queue=b['candidates'][0]['queue']; witness=adapter['live_witnesses'][je['id']]
                    native_branch=_locate_sender_branch(je['script'],b['event'],queue,b['candidates'][0]['value'])[0]
                    native_limit=_direct(native_branch,'limit')
                    native_context=sorted(set(_positive_conjunct_triples(native_limit[0])))
                    native_context=[atom for atom in native_context if (atom[0].startswith('var:ywc_jhg_') and atom[0]!='var:'+queue) or
                                    (atom[0]=='has_variable' and atom[2].startswith('ywc_jhg_') and atom[2]!=queue)]
                    receipt=f'ywc_v03_jhg_inline_body_completed_{ident}'
                    receipt_epoch=f'ywc_v03_jhg_inline_body_completed_epoch_{ident}'
                    _assert_guarded_stamp(self,effects[body_helper],body_helper,ident,queue,b['candidates'][0]['value'],
                                          witness,native_context,receipt,receipt_epoch,f'ywc_v03_jhg_inline_join_{ident}')
                    callback=adapter['ack_hooks'][event['id']][[row[0] for row in bound].index(ident)]
                    self.assertIn(callback,effects)
                    _assert_callback_contract(self,effects[callback],callback,ident,queue,b['candidates'][0]['value'],
                                              witness,native_context)
                    callback_defs=_reachable_effects(callback,effects)
                    callback_writes=[name for helper in callback_defs for name,_,_ in _setvar_writes(effects[helper])]
                    self.assertFalse(any('_sender_completed_' in name or '_body_completed_' in name for name in callback_writes),
                                     (callback,'callback closure cannot mint completion receipts'))
                    callback_calls=[n.key for n in _walk(effects[callback]) if n.op=='=' and n.value=='yes'
                                    and n.key==f'ywc_v03_jhg_inline_join_{ident}']
                    self.assertEqual(callback_calls,[f'ywc_v03_jhg_inline_join_{ident}'],callback)
        # Generated source keeps the whole authored native postfragment ahead
        # of each owned source-return continuation. The exact helper ABI is
        # pinned here for later runtime contracts.
        all_id=0
        for arc in cat['arcs']:
            for je in arc['journals']:
                adapted=adapter['journal_scripts'][je['id']]
                for branch in _binding(je['id'],je['script']):
                    all_id+=1
                    source=je['script'][branch['start']:branch['end']]
                    native_nodes=parse_block('{ '+source+' }')
                    source_branch=native_nodes[0]
                    source_children=children(source_branch)
                    source_triggers=[i for i,n in enumerate(source_children) if n.key=='trigger_event']
                    self.assertEqual(len(source_triggers),1)
                    source_tail=source_children[source_triggers[0]+1:]
                    post_markers=[name for name in _setvar_names(source_tail) if name.endswith('_notice_delivered')]
                    generated_nodes=parse_block(adapter['journal_scripts'][je['id']])
                    event_id=branch['event']
                    candidate_source=branch['candidates'][0]
                    candidates=[]
                    for n in _walk(generated_nodes):
                        if n.key not in {'if','else_if'}: continue
                        direct=children(n)
                        triggers=[x for x in direct if x.key=='trigger_event']
                        limits=[x for x in direct if x.key=='limit']
                        if (len(triggers)==1 and len(limits)==1
                            and any(y.key=='id' and y.value==event_id for y in _walk((triggers[0],)))
                            and _contains_queue(limits[0],candidate_source['queue'],candidate_source['value'])):
                            candidates.append(n)
                    self.assertEqual(len(candidates),1,(je['id'],branch['branch_index'],event_id,candidate_source))
                    generated_branch=candidates[0]; generated_children=children(generated_branch)
                    gen_triggers=[i for i,n in enumerate(generated_children) if n.key=='trigger_event']
                    self.assertEqual(len(gen_triggers),1)
                    self.assertEqual(_rows([generated_children[gen_triggers[0]]]),
                                     _rows([source_children[source_triggers[0]]]),'complete native trigger_event AST')
                    native_pre=[n for n in source_children[:source_triggers[0]]
                                if n.key!='limit' and not (n.key=='remove_variable' and n.value==candidate_source['queue'])]
                    generated_native_pre=[n for n in generated_children[:gen_triggers[0]]
                                          if n.key!='limit' and _native_mutation((n,))]
                    self.assertEqual(_rows(generated_native_pre),_rows(native_pre),
                                     'all native prefragment writes/helpers retain complete AST and order')
                    generated_tail=generated_children[gen_triggers[0]+1:]
                    self.assertGreaterEqual(len(generated_tail),len(source_tail))
                    self.assertEqual(_rows(generated_tail[:len(source_tail)]),_rows(source_tail),
                                     'complete native post-fragment must precede continuation')
                    continuation_tail=generated_tail[len(source_tail):]
                    sender_helper=f'ywc_v03_jhg_inline_sender_return_{all_id}'
                    continuation_calls=[n for n in _walk(continuation_tail) if n.key==sender_helper and n.op=='=' and n.value=='yes']
                    self.assertEqual(len(continuation_calls),1,(je['id'],all_id,'one owned sender continuation'))
                    queue=branch['candidates'][0]['queue']
                    self.assertFalse(any(n.key=='remove_variable' and n.value==queue for n in _walk(generated_branch)),
                                     'selected queue clear is deferred to successful ACK')
                    self.assertIn(sender_helper,effects)
                    self.assertEqual([n.key for n in _nodes(continuation_tail) if n.op=='=' and n.value=='yes'],[sender_helper],
                                     (je['id'],all_id,'no fanout after authored postfragment'))
                    native_limit=_direct(source_branch,'limit')
                    native_context=sorted(set(_positive_conjunct_triples(native_limit[0])))
                    native_context=[atom for atom in native_context if (atom[0].startswith('var:ywc_jhg_') and atom[0]!='var:'+queue) or
                                    (atom[0]=='has_variable' and atom[2].startswith('ywc_jhg_') and atom[2]!=queue)]
                    witness=adapter['live_witnesses'][je['id']]
                    sender_receipt=f'ywc_v03_jhg_inline_sender_completed_{all_id}'
                    sender_epoch=f'ywc_v03_jhg_inline_sender_completed_epoch_{all_id}'
                    _assert_guarded_stamp(self,effects[sender_helper],sender_helper,all_id,queue,
                      branch['candidates'][0]['value'],witness,native_context,sender_receipt,sender_epoch,
                      f'ywc_v03_jhg_inline_join_{all_id}')
                    body_helper=f'ywc_v03_jhg_inline_body_return_{all_id}'
                    self.assertIn(body_helper,effects)
                    body_receipt=f'ywc_v03_jhg_inline_body_completed_{all_id}'
                    body_epoch=f'ywc_v03_jhg_inline_body_completed_epoch_{all_id}'
                    _assert_guarded_stamp(self,effects[body_helper],body_helper,all_id,queue,
                      branch['candidates'][0]['value'],witness,native_context,body_receipt,body_epoch,
                      f'ywc_v03_jhg_inline_join_{all_id}')
                    body_guard=_helper_guard_and_effects(effects[body_helper],body_helper)[1]
                    self.assertNotIn(('var:ywc_v03_jhg_inline_sender_completed_'+str(all_id),'=','1'),
                                     _positive_conjunct_triples(body_guard),'body-first stamp must not wait for sender receipt')
                    for marker_name in post_markers:
                        self.assertNotIn(marker_name,_native_jhg_variable_refs(body_guard),
                                         'body receipt must be stampable before native postmarker exists')
                    join_name=f'ywc_v03_jhg_inline_join_{all_id}'
                    self.assertIn(join_name,effects)
                    join_guard,join_effect=_assert_receipt_join(self,effects[join_name],join_name,all_id,queue,
                      branch['candidates'][0]['value'],witness,native_context)
                    join_receipt_writes=[name for name,_,_ in _setvar_writes(join_effect)
                                         if '_sender_completed_' in name or '_body_completed_' in name]
                    self.assertEqual(join_receipt_writes,[],(join_name,'join checks but never mints either receipt'))
                    ack_name=f'ywc_v03_jhg_inline_ack_{all_id}'
                    self.assertIn(ack_name,effects)
                    _assert_ack_guard(self,effects[ack_name],ack_name,all_id,queue,
                                      branch['candidates'][0]['value'],witness,native_context)
                    snapshot_names=_native_jhg_variable_refs(source_branch)
                    _assert_complete_native_snapshots(self,effects[join_name],snapshot_names,join_name)
                    _assert_complete_native_snapshots(self,effects[ack_name],snapshot_names,ack_name)
                    ack_reachable=_reachable_effects(ack_name,effects)
                    ack_writes=[name for helper in ack_reachable for name,_,_ in _setvar_writes(effects[helper])]
                    self.assertFalse(any('_sender_completed_' in name or '_body_completed_' in name for name in ack_writes),
                                     (je['id'],all_id,'ACK closure cannot mint receipts'))
                    ack_queue_removals=[n for n in _walk(effects[ack_name]) if n.key=='remove_variable' and n.value==queue]
                    self.assertEqual(len(ack_queue_removals),1,(je['id'],all_id,queue))
    def test_registered_public_builders_map_exact_six_jhg_outputs_in_temp_root(self):
        assert_inline_supported(self)
        from tools import build_v03_content, build_v03_country
        candidate=_v2_catalog_from_formal_jhg_source()
        expected={Path('events/ywc_v03_country_jhg_events.txt'),
          Path('common/journal_entries/ywc_v03_country_jhg_journal.txt'),
          Path('localization/simp_chinese/ywc_v03_country_jhg_l_simp_chinese.yml'),
          Path('localization/english/ywc_v03_country_jhg_l_english.yml'),
          Path('common/scripted_effects/ywc_v03_delivery_jhg_effects.txt'),
          Path('common/scripted_triggers/ywc_v03_delivery_jhg_triggers.txt')}
        with _isolated_build_root(candidate) as isolated:
            output_map=build_v03_content.render_all(isolated)
            jhg_paths={p for p in output_map if p in expected}
            self.assertEqual(jhg_paths,expected)
            country_map=build_v03_country.render_country(isolated,'country_jhg')
            self.assertEqual(set(country_map),expected)
            self.assertEqual(country_map,{path:output_map[path] for path in expected},
                             'independent country renderer must agree with global render map')
            errors=build_v03_content.build(isolated)
            self.assertEqual(errors,[])
            self.assertEqual(build_v03_country.build_country(isolated,'country_jhg'),[])
            self.assertEqual(build_v03_country.check_country(isolated,'country_jhg'),[])
            for rel in expected:
                actual=(isolated/'yongchang_world'/rel).read_bytes()
                self.assertEqual(actual,b'\xef\xbb\xbf'+output_map[rel].encode('utf-8'),rel)
            non_jhg=[p for p in output_map if p not in expected]
            self.assertEqual(len(non_jhg),54)
            for rel in non_jhg:
                self.assertEqual((isolated/'yongchang_world'/rel).read_bytes(),
                                 (ROOT/'yongchang_world'/rel).read_bytes(),rel)
    def test_phase_metadata_is_real_and_registration_is_feature_red(self):
        candidate=_v2_catalog_from_formal_jhg_source()
        self.assertEqual(sum(len(a['inline_delivery_adapter']['branches']) for a in candidate['arcs']),58)
        self.assertEqual(sum(len(a['inline_delivery_adapter']['live_phases']) for a in candidate['arcs']),6)
        self.assertEqual({p['live_witness'] for a in candidate['arcs'] for p in a['inline_delivery_adapter']['live_phases']},
                         {f"ywc_v03_jhg_inline_live_{jid.removeprefix('ywc_je_v03_jhg_')}" for jid in JE_IDS})
        # This is intentionally a failing feature assertion on the current baseline.
        # It must become green only after JHG has genuine public registration.
        assert_inline_supported(self)

if __name__=='__main__': unittest.main()
