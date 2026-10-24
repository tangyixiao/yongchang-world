"""TIB inline source contract. Public registration is intentionally RED on this baseline."""
from __future__ import annotations
import copy, hashlib, json, re, shutil, tempfile, unittest
from contextlib import contextmanager
from pathlib import Path
from tests.clausewitz_harness import parse
from tools.v03_inline_delivery_adapter import (_kor_source_binding, _kor_direct_adds,
    children, direct_values, parse_block, validate_inline_catalog, render_inline_country_adapters)


ROOT=Path(__file__).resolve().parents[1]
CATALOG_PATH=ROOT/'data/content/v03/countries/tib.json'
JOURNAL_PATH=ROOT/'yongchang_world/common/journal_entries/ywc_v03_country_tib_journal.txt'
EVENT_PATH=ROOT/'yongchang_world/events/ywc_v03_country_tib_events.txt'
EFFECTS_PATH=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_tib_effects.txt'
TRIGGERS_PATH=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_tib_triggers.txt'
JE_IDS={j["id"] for a in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["arcs"] for j in a["journals"]}
ARC_IDS={a["slug"] for a in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["arcs"]}

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

def _is_exact_snapshot_check(node,native,private_prefix='ywc_v03_tib_inline_',pair=None):
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
        if pair is not None:
            presence,value=pair
            present_required={('has_variable','=',presence),('has_variable','=',value),('var:'+presence,'=','1'),('var:'+native,'=','var:'+value)}
            absent_required={('has_variable','=',presence),('has_variable','=',value),('var:'+presence,'=','0'),('var:'+value,'=','0')}
            if present_required<=positive and absent_required<=absent_atoms: return True
            continue
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


def _has_present_snapshot(limit,native,pair):
    presence,value=pair
    required={('has_variable','=',native),('has_variable','=',presence),
              ('has_variable','=',value),('var:'+presence,'=','1'),
              ('var:'+native,'=','var:'+value)}
    return required<=set(_positive_conjunct_triples(limit))


def _snapshot_guard_covers(limit,native,pair):
    """Prove exact captured equality on every applicable Boolean guard arm."""
    if _has_present_snapshot(limit,native,pair): return True
    for term in _positive_guard_terms(limit):
        if _is_exact_snapshot_check(term,native,pair=pair): return True
        if term.key=='OR' and isinstance(term.value,tuple) and children(term):
            if all(_snapshot_guard_covers((arm,),native,pair) for arm in children(term)): return True
    return False


def _assert_complete_snapshot_guard(testcase,limit,mapping,label):
    testcase.assertIsInstance(mapping,dict,'snapshot guards require the actual sender capture mapping')
    testcase.assertTrue(mapping,(label,'nonempty actual sender capture mapping'))
    testcase.assertEqual(len({v for pair in mapping.values() for v in pair}),2*len(mapping),
                         (label,'distinct private presence/value field for every native source field'))
    for native,pair in sorted(mapping.items()):
        testcase.assertTrue(_snapshot_guard_covers(limit,native,pair),
                            (label,'complete exact sender-bound native snapshot guard',native,pair))


def _assert_complete_native_snapshots(testcase,definition,mapping,label):
    _outer,limit,_effects=_helper_guard_and_effects(definition,label)
    _assert_complete_snapshot_guard(testcase,limit,mapping,label)


def _assert_sender_snapshot_capture(testcase,pre,names,label):
    """Derive immutable P's real native -> private pair from sender commands.

    Each direct presence branch reads its own native value and owns distinct
    private fields. Unconditional zero initialization before that branch is the
    actual absent path; exact write counts prevent aliasing or later recapture.
    No adapter registration or output is constructed by this assertion.
    """
    pre=_nodes(pre); mapping={}; occupied=set()
    last_native=max((i for i,n in enumerate(pre) if _native_mutation((n,))),default=-1)
    all_writes=_setvar_writes(pre)
    def plain_capture_write(node):
        if node.key!='set_variable' or node.op!='=' or not isinstance(node.value,tuple): return False
        fields=children(node)
        return len(fields)==2 and {n.key for n in fields}=={'name','value'} and all(n.op=='=' and isinstance(n.value,str) for n in fields)
    for native in sorted(names):
        matches=[]
        for index,node in enumerate(pre):
            if node.key!='if' or not isinstance(node.value,tuple): continue
            fields=children(node); limits=_direct(fields,'limit')
            if len(limits)!=1: continue
            if _rows(_positive_guard_terms(limits[0]))!=[('has_variable','=',native)]: continue
            body=[n for n in fields if n.key!='limit']
            writes=_setvar_writes(body)
            if len(writes)==2 and len(body)==2 and all(plain_capture_write(n) for n in body): matches.append((index,node,writes))
        testcase.assertEqual(len(matches),1,(label,native,'one real direct presence/value capture'))
        index,node,writes=matches[0]
        values=[(name,value) for name,value,_ in writes]
        value_fields=[name for name,value in values if value=='var:'+native]
        testcase.assertEqual(len(value_fields),1,(label,native,'capture reads matching native field'))
        value=value_fields[0]; flags=[name for name,raw in values if raw=='1']
        testcase.assertEqual(len(flags),1,(label,native,'one present flag'))
        flag=flags[0]; testcase.assertNotEqual(flag,value)
        testcase.assertTrue(all(name.startswith('ywc_v03_tib_inline_') for name in (flag,value)),label)
        testcase.assertFalse({flag,value}&occupied,(label,native,'cross-field capture alias'))
        occupied.update((flag,value)); mapping[native]=(flag,value)
        for target,present_value in ((flag,'1'),(value,'var:'+native)):
            initial=[(i,n) for i,n in enumerate(pre) if plain_capture_write(n) and
                     [(k,v) for k,v,_ in _setvar_writes((n,))]==[(target,'0')]]
            testcase.assertEqual(len(initial),1,(label,native,target,'unconditional absent-path zero'))
            testcase.assertGreater(initial[0][0],last_native,(label,native,'P follows complete native pre'))
            testcase.assertLess(initial[0][0],index,(label,native,'absent initialization before present override'))
            testcase.assertEqual([(name,raw) for name,raw,_ in all_writes if name==target],
                                 [(target,'0'),(target,present_value)],(label,native,target,'immutable capture write path'))
    return mapping


def _sender_capture_mapping(testcase,generated,ident,names):
    source_return=f'ywc_v03_tib_inline_source_return_{ident}'
    calls=[n for n in _walk(generated) if n.key==source_return and n.value=='yes']
    testcase.assertEqual(len(calls),1,(ident,'one actual source return'))
    parents=[n for n in _walk(generated) if isinstance(n.value,tuple) and calls[0] in children(n)]
    testcase.assertEqual(len(parents),1,(ident,'one sender parent'))
    fields=children(parents[0]); triggers=[i for i,n in enumerate(fields) if n.key=='trigger_event']
    testcase.assertEqual(len(triggers),1,(ident,'one actual source dispatch'))
    return _assert_sender_snapshot_capture(testcase,fields[:triggers[0]],names,source_return)


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
    required=[('var:ywc_v03_tib_inline_reservation','=','%s'%ident),
      ('var:ywc_v03_tib_inline_epoch','>','0'),
      ('var:ywc_v03_tib_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value))]
    for atom in required: testcase.assertIn(atom,guard,(name,'guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    counterpart='source' if '_body_completed_' in stamp else 'body'
    forbidden={f'ywc_v03_tib_inline_{counterpart}_completed_{ident}',
               f'ywc_v03_tib_inline_{counterpart}_completed_epoch_{ident}'}
    if counterpart=='body': forbidden.add('ywc_v03_major_event_cooldown')
    for node in _walk(limit):
        testcase.assertFalse(node.key.startswith('ywc_v03_can_deliver'),(name,'receipt cannot recheck delivery availability'))
        testcase.assertFalse(node.key.removeprefix('var:') in forbidden or
                             (isinstance(node.value,str) and node.value.removeprefix('var:') in forbidden),
                             (name,'independent receipt guard',node.key,node.value))
    writes=_setvar_writes(effect)
    stamps=[(n,v,node) for n,v,node in writes if n in {stamp,stamp_epoch}]
    testcase.assertEqual({n for n,_,_ in stamps},{stamp,stamp_epoch},name)
    testcase.assertEqual([(n,v) for n,v,_ in stamps],[(stamp,'1'),(stamp_epoch,'var:ywc_v03_tib_inline_reservation_epoch')],
                         (name,'writes only its own completed receipt and reservation epoch'))
    unexpected=[n for n,_,_ in writes if ('_source_completed_' in n or '_body_completed_' in n) and n not in {stamp,stamp_epoch}]
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
    required=[('var:ywc_v03_tib_inline_reservation','=','%s'%ident),
      ('var:ywc_v03_tib_inline_epoch','>','0'),
      ('var:ywc_v03_tib_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value)),
      ('var:ywc_v03_tib_inline_source_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_tib_inline_source_completed_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:ywc_v03_tib_inline_body_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_tib_inline_body_completed_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:ywc_v03_tib_inline_callback_%s'%ident,'=','1'),
      ('var:ywc_v03_tib_inline_callback_candidate_%s'%ident,'=','%s'%ident),
      ('var:ywc_v03_tib_inline_callback_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:ywc_v03_tib_inline_callback_queue_%s'%ident,'=','var:'+queue)]
    for atom in required: testcase.assertIn(atom,guard,(name,'join guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    calls=[n for n in _walk(effect) if n.key==f'ywc_v03_tib_inline_ack_{ident}' and n.op=='=' and n.value=='yes']
    testcase.assertEqual(len(calls),1,(name,'ACK call'))
    testcase.assertIn(calls[0],_nodes(effect),(name,'ACK must be a direct guarded effect'))
    return guard,effect
def _assert_callback_contract(testcase,definition,name,ident,queue,value,witness,native_context):
    _guard,limit,effect=_helper_guard_and_effects(definition,name)
    guard=_positive_conjunct_triples(limit)
    for atom in [('var:ywc_v03_tib_inline_reservation','=',str(ident)),
      ('var:ywc_v03_tib_inline_epoch','>','0'),('var:ywc_v03_tib_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value))]:
        testcase.assertIn(atom,guard,(name,'callback guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    expected={f'ywc_v03_tib_inline_callback_{ident}':'1',
      f'ywc_v03_tib_inline_callback_candidate_{ident}':str(ident),
      f'ywc_v03_tib_inline_callback_epoch_{ident}':'var:ywc_v03_tib_inline_reservation_epoch',
      f'ywc_v03_tib_inline_callback_queue_{ident}':'var:'+queue}
    writes=_setvar_writes(effect)
    for key,value in expected.items():
        selected=[(actual,node) for written,actual,node in writes if written==key]
        testcase.assertEqual(len(selected),1,(name,key,'exactly one callback field write'))
        testcase.assertEqual(selected[0][0],value,(name,key))
        testcase.assertIn(selected[0][1],_nodes(effect),(name,key,'direct guarded write'))
    calls=[n for n in _walk(effect) if n.key==f'ywc_v03_tib_inline_join_{ident}' and n.op=='=' and n.value=='yes']
    testcase.assertEqual(len(calls),1,(name,'one shared join wake'))
    positions={node.start:i for i,node in enumerate(_nodes(effect))}
    testcase.assertIn(calls[0].start,positions,(name,'direct join wake'))
    for written,_value,node in writes:
        if written in expected: testcase.assertLess(positions[node.start],positions[calls[0].start],(name,'callback fields before join'))
    return guard,effect
def _assert_ack_guard(testcase,definition,name,ident,queue,value,witness,native_context):
    _guard,limit,effect=_helper_guard_and_effects(definition,name)
    guard=_positive_conjunct_triples(limit)
    for atom in [('var:ywc_v03_tib_inline_reservation','=',str(ident)),
      ('var:ywc_v03_tib_inline_epoch','>','0'),('var:ywc_v03_tib_inline_reservation_epoch','>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'>','0'),
      ('var:ywc_v03_tib_inline_candidate_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:'+witness,'=','1'),('var:'+queue,'=',str(value)),
      ('var:ywc_v03_tib_inline_source_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_tib_inline_source_completed_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:ywc_v03_tib_inline_body_completed_%s'%ident,'=','1'),
      ('var:ywc_v03_tib_inline_body_completed_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:ywc_v03_tib_inline_callback_%s'%ident,'=','1'),
      ('var:ywc_v03_tib_inline_callback_candidate_%s'%ident,'=',str(ident)),
      ('var:ywc_v03_tib_inline_callback_epoch_%s'%ident,'=','var:ywc_v03_tib_inline_reservation_epoch'),
      ('var:ywc_v03_tib_inline_callback_queue_%s'%ident,'=','var:'+queue)]:
        testcase.assertIn(atom,guard,(name,'ACK guard atom',atom,guard))
    _assert_native_context(testcase,limit,native_context,name)
    return guard,effect
def _native_mutation(nodes):
    for node in _walk(nodes):
        if node.key.startswith('ywc_tib_') and node.op=='=' and node.value=='yes': return True
        if node.key in {'remove_variable','clear_variable'} and isinstance(node.value,str) and node.value.startswith('ywc_tib_'): return True
        if node.key in {'set_variable','change_variable','clamp_variable'} and isinstance(node.value,tuple):
            if any(n.key=='name' and isinstance(n.value,str) and n.value.startswith('ywc_tib_') for n in children(node)): return True
    return False


def _native_tib_variable_refs(nodes):
    refs=set()
    for n in _walk(nodes):
        if n.key.startswith('var:ywc_tib_'): refs.add(n.key[4:])
        elif n.key=='has_variable' and isinstance(n.value,str) and n.value.startswith('ywc_tib_'): refs.add(n.value)
        elif n.key in {'remove_variable','clear_variable'} and isinstance(n.value,str) and n.value.startswith('ywc_tib_'): refs.add(n.value)
        elif n.key in {'set_variable','change_variable'} and isinstance(n.value,tuple):
            refs.update(x.value for x in n.value if x.key=='name' and isinstance(x.value,str) and x.value.startswith('ywc_tib_'))
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
        if not all(enabled): raise AssertionError('partial TIB inline metadata')
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
    temp=Path(tempfile.mkdtemp(prefix='tib-inline-build-')).resolve()
    owned_temp=temp
    temp_parent=Path(tempfile.gettempdir()).resolve()
    (temp/'data/content').mkdir(parents=True,exist_ok=True)
    (temp/'yongchang_world/common').mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'data/content/v03',temp/'data/content/v03')
    for folder in ('scripted_effects','scripted_triggers'):
        source=ROOT/f'yongchang_world/common/{folder}'
        target=temp/f'yongchang_world/common/{folder}'
        shutil.copytree(source,target)
    catalog_rel=Path('data/content/v03/countries/tib.json')
    (temp/catalog_rel).write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest_path=temp/'data/content/v03/manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    required=('common/scripted_effects/ywc_v03_delivery_tib_effects.txt',
              'common/scripted_triggers/ywc_v03_delivery_tib_triggers.txt')
    for rel in required:
        if rel not in manifest['owned_outputs']: manifest['owned_outputs'].append(rel)
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try: yield temp
    finally:
        target=temp.resolve()
        if target!=owned_temp or target.parent!=temp_parent or not target.name.startswith('tib-inline-build-'):
            raise AssertionError(('refusing non-owned temporary directory cleanup',str(target)))
        shutil.rmtree(target)
def _queue_candidates(src):
    root=parse_block('{ '+src+' }')
    if len(root)!=1 or root[0].key not in {'if','else_if'}: raise ValueError('TIB sender must be one conditional branch')
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
            elif not neg and n.key.startswith('var:ywc_tib_') and n.key.endswith(('_pending_event','_notice_12_event','_notice_36_event')) and n.op=='=' and type(n.value) is str and n.value.isdigit():
                q=n.key[4:]; kind='notice12' if q.endswith('_notice_12_event') else 'notice36' if q.endswith('_notice_36_event') else 'normal'
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

def _v2_catalog_from_formal_tib_source():
    result=copy.deepcopy(catalog())
    for arc in result['arcs']:
        phases=[]; branches=[]
        for je in arc['journals']:
            suffix=je['id'].removeprefix('ywc_je_v03_tib_')
            phases.append({'journal':je['id'],'live_witness':f'ywc_v03_tib_inline_live_{suffix}',
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
    candidate=_v2_catalog_from_formal_tib_source()
    try:
        validate_inline_catalog(candidate); rendered=render_inline_country_adapters(candidate)
    except ValueError as exc:
        if 'inline adapter is currently enabled only for registered inline countries' in str(exc):
            testcase.fail(f'TIB inline adapter feature is not registered: {exc}')
        raise
    if len(rendered.get('event_hooks',{}))!=24: testcase.fail('TIB must guard all 24 events')
    return rendered

def _all_native_context_names():
    names=set()
    for arc in catalog()['arcs']:
        for je in arc['journals']:
            for row in _binding(je['id'],je['script']):
                names.update(c['queue'] for c in row['candidates'])
                branch=next(n for n in _walk(parse_block(je['script'])) if n.start==row['start'] and n.end==row['end'])
                names.update(_native_tib_variable_refs(branch))
    return names

def _assert_live_owner(testcase,limit,jid,witness,ident,label):
    atoms=set(_positive_conjunct_triples(limit))
    for atom in [('has_journal_entry','=',jid),('has_variable','=','ywc_v03_tib_inline_timer'),
                 ('var:'+witness,'=','1'),('var:ywc_v03_tib_inline_epoch','>','0'),
                 ('var:ywc_v03_tib_inline_reservation_epoch','>','0'),
                 ('var:ywc_v03_tib_inline_reservation_epoch','=','var:ywc_v03_tib_inline_epoch'),
                 (f'var:ywc_v03_tib_inline_candidate_epoch_{ident}','=','var:ywc_v03_tib_inline_reservation_epoch')]:
        testcase.assertIn(atom,atoms,(label,'positive actual owner guard',atom))

def _assert_frozen_invocation(testcase,limit,ident,label):
    atoms=set(_positive_conjunct_triples(limit))
    for atom in [('exists','=','scope:ywc_v03_tib_inline_dispatch_candidate'),
                 ('scope:ywc_v03_tib_inline_dispatch_candidate','=',str(ident)),
                 ('exists','=','scope:ywc_v03_tib_inline_dispatch_epoch'),
                 ('scope:ywc_v03_tib_inline_dispatch_epoch','=','var:ywc_v03_tib_inline_reservation_epoch')]:
        testcase.assertIn(atom,atoms,(label,'frozen invocation',atom))

def _assert_source_boundary_owner(testcase,definition,ident,label):
    """Pure continuation ownership; never native eligibility or live JE state."""
    prefix='ywc_v03_tib_inline_'
    reservation=prefix+'reservation'; current=prefix+'epoch'; epoch=prefix+'reservation_epoch'
    candidate=prefix+f'candidate_epoch_{ident}'
    required={('has_variable','=',name) for name in (reservation,current,epoch,candidate)}
    required.update({('var:'+reservation,'=',str(ident)),('var:'+current,'>','0'),
                     ('var:'+epoch,'>','0'),('var:'+epoch,'=','var:'+current),
                     ('var:'+candidate,'>','0'),('var:'+candidate,'=','var:'+epoch)})
    _assert_frozen_invocation(testcase,definition,ident,label)
    atoms=set(_positive_conjunct_triples(definition))
    testcase.assertTrue(required<=atoms,(label,'current/reservation/candidate ownership',required-atoms))
    allowed=required|{('exists','=','scope:'+prefix+'dispatch_candidate'),
                      ('scope:'+prefix+'dispatch_candidate','=',str(ident)),
                      ('exists','=','scope:'+prefix+'dispatch_epoch'),
                      ('scope:'+prefix+'dispatch_epoch','=','var:'+epoch)}
    for node in _walk(definition):
        if isinstance(node.value,tuple):
            testcase.assertIn(node.key,{'AND','OR','NOT','NOR'},(label,'unsupported owner block dependency',node.key))
            testcase.assertEqual(node.op,'=',label)
        else:
            testcase.assertIn((node.key,node.op,str(node.value)),allowed,
                              (label,'pure owner rejects every hidden native/JE/witness/queue/cooldown dependency'))

def _assert_boundary_dispatch(testcase,definition,ident):
    terms=_positive_guard_terms(definition)
    body=f'ywc_v03_tib_inline_body_completed_{ident}'
    boundary=f'ywc_v03_tib_inline_source_boundary_{ident}'
    epoch=f'ywc_v03_tib_inline_source_boundary_epoch_{ident}'
    testcase.assertTrue({body,body.replace('_completed_','_completed_epoch_')}<=_negative_presence(definition),
                        'dispatch rejects any prior body receipt field')
    alternatives=[n for n in terms if n.key=='OR' and isinstance(n.value,tuple)]
    valid=[]
    for node in alternatives:
        arms=children(node)
        if len(arms)!=2 or any(n.key!='AND' for n in arms): continue
        for pre,post in (arms,tuple(reversed(arms))):
            if {boundary,epoch}<=_negative_presence(pre):
                positive=set(_positive_conjunct_triples(post))
                required={(f'var:{boundary}','=',str(ident)),(f'var:{epoch}','=','var:ywc_v03_tib_inline_reservation_epoch'),
                          (f'var:ywc_v03_tib_inline_source_completed_{ident}','=','1'),
                          (f'var:ywc_v03_tib_inline_source_completed_epoch_{ident}','=','var:ywc_v03_tib_inline_reservation_epoch')}
                if required<=positive: valid.append(node)
    testcase.assertEqual(len(valid),1,'P fallback requires BOTH boundary fields absent; reached/partial boundary cannot reopen P')

class TibInlineStaticContract(unittest.TestCase):
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
            if event_id not in {f'ywc_tib.{n}' for n in [*range(1000,1010),*range(1010,1018),*range(1020,1026)]}: continue
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
                                               if any(b['candidates'][0]['kind']=='notice12' for b in _binding(j['id'],j['script'])))
        real_branch=next(b for b in _binding(real_je['id'],real_je['script']) if b['candidates'][0]['kind']=='notice12')
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
                witness='ywc_v03_tib_inline_live_'+je['id'].removeprefix('ywc_je_v03_tib_')
                # A local expected AST projection of the contract, never installed as adapter output.
                expected=parse_block('{ immediate = { set_variable = { name = '+witness+' value = 1 } } }')
                from dataclasses import replace
                projected=[replace(expected[0],value=tuple(native+_nodes(expected[0])))]
                _assert_witness_immediate(self,projected,authored,witness,je['id'])
                with self.assertRaises(AssertionError):
                    _assert_witness_immediate(self,expected,authored,witness+'_wrong',je['id'])
        self.assertEqual((nonempty,empty),(6,0))
        with self.assertRaisesRegex(TypeError,'block Node'):
            _nodes(parse_block('{ scalar = yes }')[0])

    def test_native_source_inventory_and_real_queue_candidates(self):
        cat=catalog(); self.assertEqual(cat['key'],'country_tib'); self.assertEqual({a['slug'] for a in cat['arcs']},ARC_IDS)
        native=_native_journals(); counts={}; kinds={'normal':0,'notice12':0,'notice36':0}; events=[]
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
        self.assertEqual(kinds,{'normal':40,'notice12':12,'notice36':6})
        self.assertEqual(len(events),58); self.assertEqual(len(set(events)),24)
    def test_all_24_event_layout_positives_are_canonical_and_leave_bound_journals_untouched(self):
        candidate=_v2_catalog_from_formal_tib_source()
        journal_sources={j['id']:j['script'] for arc in candidate['arcs'] for j in arc['journals']}
        events=[e for arc in candidate['arcs'] for e in arc['events']]
        self.assertEqual(len(events),24)
        for event in events:
            for field in ('trigger','immediate'):
                original=event[field]
                formatted='{ # legal layout comment\n '+original[1:-1].replace(' ','\n  ')+'\n}'
                self.assertEqual(_rows(parse_block(formatted)),_rows(parse_block(original)),(event['id'],field))
                self.assertNotEqual(formatted,original)
                self.assertEqual({j['id']:j['script'] for arc in candidate['arcs'] for j in arc['journals']},journal_sources)
    def test_bound_journal_layout_mutation_invalidates_raw_binding_without_weakened_hash(self):
        candidate=_v2_catalog_from_formal_tib_source()
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
    def test_all_native_tib_helper_ast_mutation_controls_are_scoped(self):
        helpers=((EFFECTS_PATH,set(_builder_defs(EFFECTS_PATH.read_text(encoding='utf-8-sig')))),(TRIGGERS_PATH,set(_builder_defs(TRIGGERS_PATH.read_text(encoding='utf-8-sig')))))
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
                self.assertEqual(_rows(_direct(native,'immediate')[0]),[('ywc_v03_mark_major_delivered','=','yes')])
        self.assertEqual(len(native_journals),6)
        self.assertEqual({e['id'] for a in cat['arcs'] for e in a['events']},
                         {f'ywc_tib.{n}' for n in [*range(1000,1010),*range(1010,1018),*range(1020,1026)]})
        if adapter is None:
            self.assertEqual({k:(_rows(v) if isinstance(v,tuple) else v) for k,v in actual_journals.items()},{k:(_rows(v) if isinstance(v,tuple) else v) for k,v in native_journals.items()})
            self.assertEqual({k:(_rows(v) if isinstance(v,tuple) else v) for k,v in actual_events.items()},{k:(_rows(v) if isinstance(v,tuple) else v) for k,v in native_events.items()})
        # After genuine opt-in, registered_full_body... pins every wrapper,
        # source continuation, witness suffix and whole native event prefix.

    def test_all_54_non_tib_generated_outputs_remain_byte_exact(self):
        from tools import build_v03_content
        catalogs=build_v03_content.load_catalogs(ROOT)
        rendered=build_v03_content.render_all(ROOT)
        paths=[p for key,cat in catalogs.items() if key!='country_tib' for p in build_v03_content._catalog_outputs(cat)]
        self.assertEqual(len(paths),54); self.assertEqual(len(set(paths)),54)
        for path in paths:
            with self.subTest(output=path.as_posix()):
                expected=b'\xef\xbb\xbf'+rendered[path].encode('utf-8')
                self.assertEqual((ROOT/'yongchang_world'/path).read_bytes(),expected)
    def test_recursive_numeric_type_alias_controls_are_real_and_value_preserving(self):
        valid=_v2_catalog_from_formal_tib_source()
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
        valid=_v2_catalog_from_formal_tib_source()
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
        # Raw-bound journal source layout edits must fail with stale metadata.
        stale=copy.deepcopy(valid); je=stale['arcs'][0]['journals'][0]
        je['script']=je['script'].replace('trigger_event =',' # layout-only comment\n trigger_event =',1)
        self.assertEqual(_rows(parse_block(je['script'])),_rows(parse_block(valid['arcs'][0]['journals'][0]['script'])))
        with self.assertRaises(ValueError): validate_inline_catalog(stale)
        # Formatting positives live on independent event ASTs and native helper
        # source, never on a journal branch carrying raw source bindings.
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
        cat=_v2_catalog_from_formal_tib_source()
        self.assertEqual(len(adapter['event_hooks']),24)
        self.assertEqual(set(adapter['event_hooks']),{e['id'] for a in cat['arcs'] for e in a['events']})
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
                instrumented={'immediate','on_monthly_pulse','on_complete','on_fail'}
                native_complete=[*authored_fields,*parse_block('{ complete = '+je0['goal']+' fail = '+je0['exit_conditions']+' }')]
                self.assertEqual(_rows([n for n in body if n.key not in instrumented]),_rows([n for n in native_complete if n.key not in instrumented]),(je0['id'],'all untouched business fields'))
                source_pulse=_direct(_direct(authored_fields,'on_monthly_pulse')[0],'effect')[0]
                built_pulse=_direct(_direct(body,'on_monthly_pulse')[0],'effect')[0]
                def ordinary_top(pulse):
                    return [n for n in children(pulse) if n.key not in ('if','else_if','else') and not n.key.startswith('ywc_v03_tib_inline_')]
                self.assertEqual(_rows(ordinary_top(built_pulse)),_rows(ordinary_top(source_pulse)),(je0['id'],'native monthly review before sender chain'))
                source_order=[(r['branch_kind'],r['event']) for r in _binding(je0['id'],je0['script'])]
                built_order=[(n.key,_direct(_direct(n,'trigger_event')[0],'id')[0].value) for n in children(built_pulse) if n.key in ('if','else_if') and len(_direct(n,'trigger_event'))==1]
                self.assertEqual(built_order,source_order,'complete authored chain priority and repeated branch identities')
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
                                 if n.key.startswith('ywc_v03_tib_inline_body_return_') and n.op=='=' and n.value=='yes']
                self.assertEqual(body_return_ids,[ident for ident,_,_ in bound],event['id'])
                for ident,je,b in bound:
                    body_helper=f'ywc_v03_tib_inline_body_return_{ident}'
                    self.assertIn(body_helper,effects)
                    queue=b['candidates'][0]['queue']; witness=adapter['live_witnesses'][je['id']]
                    native_branch=next(n for n in _walk(parse_block(je['script'])) if n.start==b['start'] and n.end==b['end'])
                    native_limit=_direct(native_branch,'limit')
                    native_context=sorted(set(_positive_conjunct_triples(native_limit[0])))
                    native_context=[atom for atom in native_context if (atom[0].startswith('var:ywc_tib_') and atom[0]!='var:'+queue) or
                                    (atom[0]=='has_variable' and atom[2].startswith('ywc_tib_') and atom[2]!=queue)]
                    receipt=f'ywc_v03_tib_inline_body_completed_{ident}'
                    receipt_epoch=f'ywc_v03_tib_inline_body_completed_epoch_{ident}'
                    _assert_guarded_stamp(self,effects[body_helper],body_helper,ident,queue,b['candidates'][0]['value'],
                                          witness,native_context,receipt,receipt_epoch,f'ywc_v03_tib_inline_join_{ident}')
                    callback=adapter['ack_hooks'][event['id']][[row[0] for row in bound].index(ident)]
                    self.assertIn(callback,effects)
                    _assert_callback_contract(self,effects[callback],callback,ident,queue,b['candidates'][0]['value'],
                                              witness,native_context)
                    callback_defs=_reachable_effects(callback,effects)
                    callback_writes=[name for helper in callback_defs for name,_,_ in _setvar_writes(effects[helper])]
                    self.assertFalse(any('_source_completed_' in name or '_body_completed_' in name for name in callback_writes),
                                     (callback,'callback closure cannot mint completion receipts'))
                    callback_calls=[n.key for n in _walk(effects[callback]) if n.op=='=' and n.value=='yes'
                                    and n.key==f'ywc_v03_tib_inline_join_{ident}']
                    self.assertEqual(callback_calls,[f'ywc_v03_tib_inline_join_{ident}'],callback)
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
                    self.assertTrue(candidates,(je['id'],branch['branch_index'],event_id,candidate_source))
                    same=[b for b in _binding(je['id'],je['script']) if b['event']==event_id and b['candidates']==branch['candidates']]
                    self.assertEqual(len(candidates),len(same))
                    generated_branch=candidates[same.index(branch)]; generated_children=children(generated_branch)
                    native_limit=_direct(source_branch,'limit')[0]; built_limit=_direct(generated_branch,'limit')[0]
                    native_terms=_positive_guard_terms(native_limit); generated_terms=_positive_guard_terms(built_limit)
                    self.assertEqual(_rows(generated_terms[:len(native_terms)]),_rows(native_terms),'full native source limit retained before owned admission guard')
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
                    positions=[i for i,n in enumerate(generated_children[:gen_triggers[0]]) if _native_mutation((n,))]
                    snapshots=[i for i,n in enumerate(generated_children[:gen_triggers[0]]) if any(v.startswith('ywc_v03_tib_inline_snapshot_') for v in _setvar_names((n,)))]
                    self.assertTrue(snapshots,'full P capture required before dispatch')
                    if positions: self.assertGreater(min(snapshots),max(positions),'immutable P follows all native pre writes')
                    generated_tail=generated_children[gen_triggers[0]+1:]
                    self.assertGreaterEqual(len(generated_tail),len(source_tail))
                    self.assertEqual(_rows(generated_tail[:len(source_tail)]),_rows(source_tail),
                                     'complete native post-fragment must precede continuation')
                    continuation_tail=generated_tail[len(source_tail):]
                    sender_helper=f'ywc_v03_tib_inline_source_return_{all_id}'
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
                    native_context=[atom for atom in native_context if (atom[0].startswith('var:ywc_tib_') and atom[0]!='var:'+queue) or
                                    (atom[0]=='has_variable' and atom[2].startswith('ywc_tib_') and atom[2]!=queue)]
                    witness=adapter['live_witnesses'][je['id']]
                    sender_receipt=f'ywc_v03_tib_inline_source_completed_{all_id}'
                    sender_epoch=f'ywc_v03_tib_inline_source_completed_epoch_{all_id}'
                    _assert_guarded_stamp(self,effects[sender_helper],sender_helper,all_id,queue,
                      branch['candidates'][0]['value'],witness,native_context,sender_receipt,sender_epoch,
                      f'ywc_v03_tib_inline_join_{all_id}')
                    body_helper=f'ywc_v03_tib_inline_body_return_{all_id}'
                    self.assertIn(body_helper,effects)
                    body_receipt=f'ywc_v03_tib_inline_body_completed_{all_id}'
                    body_epoch=f'ywc_v03_tib_inline_body_completed_epoch_{all_id}'
                    _assert_guarded_stamp(self,effects[body_helper],body_helper,all_id,queue,
                      branch['candidates'][0]['value'],witness,native_context,body_receipt,body_epoch,
                      f'ywc_v03_tib_inline_join_{all_id}')
                    body_guard=_helper_guard_and_effects(effects[body_helper],body_helper)[1]
                    self.assertNotIn(('var:ywc_v03_tib_inline_source_completed_'+str(all_id),'=','1'),
                                     _positive_conjunct_triples(body_guard),'body-first stamp must not wait for sender receipt')
                    for marker_name in post_markers:
                        self.assertNotIn(marker_name,_native_tib_variable_refs(body_guard),
                                         'body receipt must be stampable before native postmarker exists')
                    join_name=f'ywc_v03_tib_inline_join_{all_id}'
                    self.assertIn(join_name,effects)
                    join_guard,join_effect=_assert_receipt_join(self,effects[join_name],join_name,all_id,queue,
                      branch['candidates'][0]['value'],witness,native_context)
                    join_receipt_writes=[name for name,_,_ in _setvar_writes(join_effect)
                                         if '_source_completed_' in name or '_body_completed_' in name]
                    self.assertEqual(join_receipt_writes,[],(join_name,'join checks but never mints either receipt'))
                    ack_name=f'ywc_v03_tib_inline_ack_{all_id}'
                    self.assertIn(ack_name,effects)
                    _assert_ack_guard(self,effects[ack_name],ack_name,all_id,queue,
                                      branch['candidates'][0]['value'],witness,native_context)
                    snapshot_mapping=_assert_sender_snapshot_capture(self,generated_children[:gen_triggers[0]],_all_native_context_names(),je['id'])
                    _assert_complete_native_snapshots(self,effects[join_name],snapshot_mapping,join_name)
                    _assert_complete_native_snapshots(self,effects[ack_name],snapshot_mapping,ack_name)
                    ack_reachable=_reachable_effects(ack_name,effects)
                    ack_writes=[name for helper in ack_reachable for name,_,_ in _setvar_writes(effects[helper])]
                    self.assertFalse(any('_source_completed_' in name or '_body_completed_' in name for name in ack_writes),
                                     (je['id'],all_id,'ACK closure cannot mint receipts'))
                    ack_queue_removals=[n for n in _walk(effects[ack_name]) if n.key=='remove_variable' and n.value==queue]
                    self.assertEqual(len(ack_queue_removals),1,(je['id'],all_id,queue))
                    native_changes=[n for n in _nodes(_helper_guard_and_effects(effects[ack_name],ack_name)[2]) if _native_mutation((n,))]
                    self.assertEqual(_rows(native_changes),[('remove_variable','=',queue)],'ACK mutates only selected native queue')
    def test_registered_public_builders_map_exact_six_tib_outputs_in_temp_root(self):
        assert_inline_supported(self)
        from tools import build_v03_content, build_v03_country
        candidate=_v2_catalog_from_formal_tib_source()
        expected={Path('events/ywc_v03_country_tib_events.txt'),
          Path('common/journal_entries/ywc_v03_country_tib_journal.txt'),
          Path('localization/simp_chinese/ywc_v03_country_tib_l_simp_chinese.yml'),
          Path('localization/english/ywc_v03_country_tib_l_english.yml'),
          Path('common/scripted_effects/ywc_v03_delivery_tib_effects.txt'),
          Path('common/scripted_triggers/ywc_v03_delivery_tib_triggers.txt')}
        with _isolated_build_root(candidate) as isolated:
            output_map=build_v03_content.render_all(isolated)
            tib_paths={p for p in output_map if p in expected}
            self.assertEqual(tib_paths,expected)
            country_map=build_v03_country.render_country(isolated,'country_tib')
            self.assertEqual(set(country_map),expected)
            self.assertEqual(country_map,{path:output_map[path] for path in expected},
                             'independent country renderer must agree with global render map')
            errors=build_v03_content.build(isolated)
            self.assertEqual(errors,[])
            self.assertEqual(build_v03_country.build_country(isolated,'country_tib'),[])
            self.assertEqual(build_v03_country.check_country(isolated,'country_tib'),[])
            for rel in expected:
                actual=(isolated/'yongchang_world'/rel).read_bytes()
                self.assertEqual(actual,b'\xef\xbb\xbf'+output_map[rel].encode('utf-8'),rel)
            non_tib=[p for p in output_map if p not in expected]
            self.assertEqual(len(non_tib),54)
            for rel in non_tib:
                self.assertEqual((isolated/'yongchang_world'/rel).read_bytes(),
                                 (ROOT/'yongchang_world'/rel).read_bytes(),rel)
    def test_phase_metadata_is_real_and_registration_is_feature_red(self):
        candidate=_v2_catalog_from_formal_tib_source()
        self.assertEqual(sum(len(a['inline_delivery_adapter']['branches']) for a in candidate['arcs']),58)
        self.assertEqual(sum(len(a['inline_delivery_adapter']['live_phases']) for a in candidate['arcs']),6)
        self.assertEqual({p['live_witness'] for a in candidate['arcs'] for p in a['inline_delivery_adapter']['live_phases']},
                         {f"ywc_v03_tib_inline_live_{jid.removeprefix('ywc_je_v03_tib_')}" for jid in JE_IDS})
        # This is intentionally a failing feature assertion on the current baseline.
        # It must become green only after TIB has genuine public registration.
        assert_inline_supported(self)

    def test_actual_tib_branch_identity_priority_empty_post_and_negative_queue_controls(self):
        queues=set(); kinds=[]
        for arc in catalog()['arcs']:
            for je in arc['journals']:
                rows=_binding(je['id'],je['script'])
                self.assertEqual([r['candidates'][0]['kind'] for r in rows[:3]],['notice12','notice36','notice12'])
                self.assertEqual(rows[0]['event'],rows[2]['event'])
                self.assertNotEqual(rows[0]['sha256'],rows[2]['sha256'])
                self.assertNotEqual(rows[0]['chain_sha256'],rows[2]['chain_sha256'])
                for row in rows:
                    branch=next(n for n in _walk(parse_block(je['script'])) if n.start==row['start'] and n.end==row['end'])
                    fields=children(branch); at=next(i for i,n in enumerate(fields) if n.key=='trigger_event')
                    self.assertEqual(_rows(fields[at+1:]),[], 'current R(P)=P: full actual native post is empty')
                    candidate=row['candidates'][0]; queues.add(candidate['queue']); kinds.append(candidate['kind'])
                    native=je['script'][row['start']:row['end']]
                    needle='var:'+candidate['queue']+' = '+str(candidate['value'])
                    self.assertIn(needle,native)
                    for negative in ('NOT = { '+needle+' }','OR = { '+needle+' always = yes }'):
                        with self.assertRaises(ValueError): _queue_candidates(native.replace(needle,negative,1))
                    writes=[(name,value) for name,value,_ in _setvar_writes(fields[:at])]
                    marker=[(name,value) for name,value in writes if name.endswith('_notice_last_delivered')]
                    expected=[] if candidate['kind']=='normal' else [(candidate['queue'].rsplit('_notice_',1)[0]+'_notice_last_delivered','1' if candidate['kind']=='notice12' else '2')]
                    self.assertEqual(marker,expected)
        self.assertEqual(len(queues),9); self.assertEqual(len(kinds),58)
        # Ownership inside OR and NOT never counts as a required positive guard.
        self.assertNotIn(('var:owner','=','1'),_positive_conjunct_triples(parse_block('{ OR = { var:owner = 1 always = yes } NOT = { var:owner = 1 } }')))
    def test_registered_boundary_snapshots_invocation_and_private_expiry_contract(self):
        rendered=assert_inline_supported(self)
        effects=_builder_defs(rendered['effects']); triggers=_builder_defs(rendered['triggers'])
        ident=0; native_names=_all_native_context_names()
        self.assertEqual(len([q for q in native_names if q.endswith(('_pending_event','_notice_12_event','_notice_36_event'))]),9)
        for arc in catalog()['arcs']:
            for je in arc['journals']:
                generated=parse_block(rendered['journal_scripts'][je['id']])
                for row in _binding(je['id'],je['script']):
                    ident+=1; prefix='ywc_v03_tib_inline_'; witness=rendered['live_witnesses'][je['id']]
                    candidate_definition=triggers[f'{prefix}candidate_{ident}']
                    self.assertIn(('has_journal_entry','=',je['id']),_positive_conjunct_triples(candidate_definition),'admission requires actual active JE')
                    for atom in _walk(candidate_definition):
                        self.assertFalse('source_boundary' in atom.key or isinstance(atom.value,str) and 'source_boundary' in atom.value,'native validity cannot depend on source-return history')
                    snapshot_mapping=_sender_capture_mapping(self,generated,ident,native_names)
                    dispatch=triggers[f'{prefix}dispatch_{ident}']
                    _assert_complete_snapshot_guard(self,dispatch,snapshot_mapping,'dispatch')
                    _assert_boundary_dispatch(self,dispatch,ident)
                    _assert_live_owner(self,dispatch,je['id'],witness,ident,'dispatch')
                    _assert_frozen_invocation(self,dispatch,ident,'dispatch')
                    for suffix in ('source_return','body_return','callback','join','ack'):
                        name=f'{prefix}{suffix}_{ident}'; definition=effects[name]
                        _,limit,body=_helper_guard_and_effects(definition,name)
                        _assert_live_owner(self,limit,je['id'],witness,ident,name)
                        _assert_frozen_invocation(self,limit,ident,name)
                        _assert_complete_native_snapshots(self,definition,snapshot_mapping,name)
                        if suffix!='ack':
                            immutable={field for pair in snapshot_mapping.values() for field in pair}
                            self.assertFalse(immutable&{target for target,_,_ in _setvar_writes(body)},(name,'P remains immutable through receipt/callback/join'))
                        if suffix in ('join','ack'):
                            for field in (f'{prefix}source_completed_{ident}',f'{prefix}source_completed_epoch_{ident}',f'{prefix}body_completed_{ident}',f'{prefix}body_completed_epoch_{ident}',f'{prefix}callback_{ident}',f'{prefix}callback_candidate_{ident}',f'{prefix}callback_epoch_{ident}',f'{prefix}callback_queue_{ident}'):
                                self.assertIn(('has_variable','=',field),_positive_conjunct_triples(limit),(name,field,'explicit presence'))
                    owner=triggers[f'{prefix}source_boundary_owner_{ident}']
                    _assert_source_boundary_owner(self,owner,ident,'boundary owner')
                    source_return=f'{prefix}source_return_{ident}'
                    calls=[n for n in _walk(generated) if n.key==source_return and n.value=='yes']
                    self.assertEqual(len(calls),1)
                    parent=next(n for n in _walk(generated) if isinstance(n.value,tuple) and calls[0] in children(n))
                    tail=children(parent); at=tail.index(calls[0]); self.assertGreater(at,0)
                    boundary=tail[at-1]; self.assertEqual(boundary.key,'if')
                    _,limit,body=_helper_guard_and_effects((boundary,),'actual source boundary')
                    self.assertEqual(_rows(limit),[(f'{prefix}source_boundary_owner_{ident}','=','yes')])
                    self.assertEqual([(n,v) for n,v,_ in _setvar_writes(body)],[(f'{prefix}source_boundary_{ident}',str(ident)),(f'{prefix}source_boundary_epoch_{ident}',f'var:{prefix}reservation_epoch')])
                    before=[n for n in tail[:at-1] if n.key=='trigger_event']; self.assertEqual(len(before),1)
                    frozen=[n for n in tail[:tail.index(before[0])] if n.key=='save_scope_value_as']
                    self.assertEqual([_rows(n) for n in frozen],[_rows(n) for n in parse_block('{ save_scope_value_as = { name = ywc_v03_tib_inline_dispatch_candidate value = var:ywc_v03_tib_inline_reservation } save_scope_value_as = { name = ywc_v03_tib_inline_dispatch_epoch value = var:ywc_v03_tib_inline_reservation_epoch } }')])
        # Any cleanup helper reachable from prepare may mutate only private state;
        # selected ACK is separately proven by the exact source contract above.
        prepare='ywc_v03_tib_inline_prepare'
        for name in _reachable_effects(prepare,effects):
            for n in _walk(effects[name]):
                if n.key in ('remove_variable','clear_variable') and isinstance(n.value,str): self.assertTrue(n.value.startswith('ywc_v03_tib_inline_'),(name,'private expiry',n.value))
                for target,_,_ in _setvar_writes((n,)): self.assertTrue(target.startswith('ywc_v03_tib_inline_'),(name,'private cleanup',target))

    def test_registered_native_helper_abi_and_public_builder_source_mutants(self):
        assert_inline_supported(self)
        from tools import build_v03_content, build_v03_country, v03_inline_delivery_adapter
        validator=getattr(v03_inline_delivery_adapter,'validate_tib_native_helper_source',None)
        self.assertTrue(callable(validator),'public TIB native helper ABI validator required')
        valid=_v2_catalog_from_formal_tib_source()
        effects=EFFECTS_PATH.read_text(encoding='utf-8-sig'); triggers=TRIGGERS_PATH.read_text(encoding='utf-8-sig')
        validator(effects,triggers)
        shared=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_effects.txt'
        def variants(source,name):
            wrapped='{ '+source+' }'; node=next(n for n in parse_block(wrapped) if n.key==name)
            start,end=node.start-2,node.end-2; definition=source[start:end]
            return [('missing',source[:start]+source[end:]),('changed',_mutate_one_helper_definition(source,name)),
                    ('duplicate',source+'\n'+definition)]
        def reject_errors(errors,label):
            self.assertTrue(errors,label)
            self.assertFalse(any('not registered' in e or 'currently enabled only' in e or 'cannot read' in e for e in errors),(label,'must reject actual ABI, not unavailable feature/source',errors))
        with _isolated_build_root(valid) as temp:
            self.assertEqual(build_v03_content.validate_catalogs_at(temp,{'country_tib':valid}),[])
            self.assertTrue(build_v03_content.render_all(temp)); self.assertTrue(build_v03_country.render_country(temp,'country_tib'))
            self.assertEqual(build_v03_content.build(temp),[])
            self.assertEqual(build_v03_country.check_country(temp,'country_tib'),[])
            for path in (EFFECTS_PATH,TRIGGERS_PATH,shared):
                original=path.read_text(encoding='utf-8-sig'); relative=path.relative_to(ROOT); target=temp/relative
                names=set(_builder_defs(original)) if path!=shared else {'ywc_v03_mark_major_delivered'}
                # Positive legal trailing comments preserve whole source ABI.
                layout=original.replace(' = {',' = { # legal trailing comment\n')
                self.assertEqual(_rows(parse_block('{ '+layout+' }')),_rows(parse_block('{ '+original+' }')))
                target.write_text(layout,encoding='utf-8-sig')
                self.assertEqual(build_v03_content.validate_catalogs_at(temp,{'country_tib':valid}),[])
                self.assertTrue(build_v03_content.render_all(temp)); self.assertTrue(build_v03_country.render_country(temp,'country_tib'))
                target.write_text(original,encoding='utf-8-sig')
                for name in sorted(names):
                    for change,mutant in variants(original,name):
                        with self.subTest(helper=name,change=change):
                            if path!=shared:
                                args=(mutant,triggers) if path==EFFECTS_PATH else (effects,mutant)
                                with self.assertRaises(ValueError) as failure: validator(*args)
                                self.assertNotIn('currently enabled only',str(failure.exception))
                            target.write_text(mutant,encoding='utf-8-sig')
                            try:
                                reject_errors(build_v03_content.validate_catalogs_at(temp,{'country_tib':valid}),'validate_catalogs_at')
                                for render,args in ((build_v03_content.render_all,(temp,)),(build_v03_country.render_country,(temp,'country_tib'))):
                                    with self.assertRaises(ValueError) as failure: render(*args)
                                    self.assertNotIn('not registered',str(failure.exception)); self.assertNotIn('cannot read',str(failure.exception))
                                for run,args in ((build_v03_content.build,(temp,)),(build_v03_content.check_outputs,(temp,)),(build_v03_country.build_country,(temp,'country_tib')),(build_v03_country.check_country,(temp,'country_tib'))):
                                    reject_errors(run(*args),run.__name__)
                            finally: target.write_text(original,encoding='utf-8-sig')
                if path==shared:
                    native=_builder_defs(original)['ywc_v03_mark_major_delivered']
                    self.assertEqual(_rows(native),_rows(parse_block('{ if = { limit = { NOT = { has_variable = ywc_v03_major_event_cooldown } } set_variable = { name = ywc_v03_major_event_cooldown value = 1 days = 90 } } }')))
    def test_registered_no_partial_opt_in_and_renderer_integer_categories(self):
        assert_inline_supported(self)
        valid=_v2_catalog_from_formal_tib_source()
        for index in range(3):
            partial=copy.deepcopy(valid); partial['arcs'][index].pop('inline_delivery_adapter')
            for fn in (validate_inline_catalog,render_inline_country_adapters):
                with self.assertRaises(ValueError): fn(partial)
        # Validator exhaustively checks every actual integer metadata path in
        # the earlier method; renderer samples each structural path category.
        categories={}
        for path,value in _int_paths(valid):
            if 'inline_delivery_adapter' not in path: continue
            category=tuple('*' if type(part) is int else part for part in path)
            categories.setdefault(category,(path,value))
        self.assertTrue(categories)
        for path,value in categories.values():
            for alias in ([float(value),bool(value)] if value in (0,1) else [float(value)]):
                mutant=copy.deepcopy(valid); _path_set(mutant,path,alias)
                with self.subTest(path=path,alias=type(alias).__name__):
                    with self.assertRaises(ValueError): render_inline_country_adapters(mutant)

    def test_native_guard_projection_snapshot_recognizer_and_narrow_corruptions(self):
        from dataclasses import replace
        defs=_builder_defs(EFFECTS_PATH.read_text(encoding='utf-8-sig'))
        native=defs['ywc_tib_capture_register_fee']
        outer,limit,body=_helper_guard_and_effects(native,'actual native fee capture')
        self.assertEqual(_rows(body),_rows(children(outer)[1:]))
        self.assertEqual(_rows(limit),_rows(_direct(outer,'limit')[0]))
        self.assertTrue(_setvar_writes(body))
        with self.assertRaises(AssertionError): _helper_guard_and_effects(body,'unguarded actual source body')
        corrupt=replace(outer,value=tuple(reversed(children(outer))))
        with self.assertRaises(AssertionError): _helper_guard_and_effects((corrupt,),'limit reordered')
        # A local assertion-helper specimen uses a real native queue identity;
        # it is never adapter output, production state, or feature registration.
        queue=next(iter(sorted(_all_native_context_names())))
        private='ywc_v03_tib_inline_probe_'
        source='{ OR = { AND = { has_variable = '+queue+' has_variable = '+private+'present var:'+private+'present = 1 has_variable = '+private+'value var:'+queue+' = var:'+private+'value } AND = { NOT = { has_variable = '+queue+' } has_variable = '+private+'present has_variable = '+private+'value var:'+private+'present = 0 var:'+private+'value = 0 } } }'
        node=parse_block(source)[0]
        self.assertTrue(_is_exact_snapshot_check(node,queue))
        for target in (queue,private+'value'):
            def remove(sequence):
                return [replace(n,value=tuple(remove(children(n)))) if isinstance(n.value,tuple) else n for n in sequence if not (n.key=='has_variable' and n.value==target)]
            self.assertFalse(_is_exact_snapshot_check(replace(node,value=tuple(remove(children(node)))),queue))
        self.assertFalse(_is_exact_snapshot_check(node,queue+'_wrong'))

    def test_boundary_live_and_frozen_assertions_have_positive_and_atom_deletion_controls(self):
        from dataclasses import replace
        je=catalog()['arcs'][0]['journals'][0]; ident=1
        witness='ywc_v03_tib_inline_live_'+je['id'].removeprefix('ywc_je_v03_tib_')
        prefix='ywc_v03_tib_inline_'
        # Assertion-only specimen anchored to an actual JE identity. It is not
        # returned by the public renderer or installed in any source world.
        owned='has_journal_entry = '+je['id']+' has_variable = '+prefix+'timer var:'+witness+' = 1 var:'+prefix+'epoch > 0 var:'+prefix+'reservation_epoch > 0 var:'+prefix+'reservation_epoch = var:'+prefix+'epoch var:'+prefix+'candidate_epoch_1 = var:'+prefix+'reservation_epoch'
        frozen='exists = scope:'+prefix+'dispatch_candidate scope:'+prefix+'dispatch_candidate = 1 exists = scope:'+prefix+'dispatch_epoch scope:'+prefix+'dispatch_epoch = var:'+prefix+'reservation_epoch'
        guard=parse_block('{ '+owned+' '+frozen+' }')
        _assert_live_owner(self,guard,je['id'],witness,ident,'specimen')
        _assert_frozen_invocation(self,guard,ident,'specimen')
        for atom in guard:
            broken=tuple(n for n in guard if n is not atom)
            checker=(lambda:_assert_frozen_invocation(self,broken,ident,'deleted')) if atom.key in ('exists',) or atom.key.startswith('scope:') else (lambda:_assert_live_owner(self,broken,je['id'],witness,ident,'deleted'))
            with self.assertRaises(AssertionError): checker()
        boundary=prefix+'source_boundary_1'; epoch=prefix+'source_boundary_epoch_1'
        dispatch=parse_block('{ NOT = { has_variable = '+prefix+'body_completed_1 } NOT = { has_variable = '+prefix+'body_completed_epoch_1 } OR = { AND = { NOT = { has_variable = '+boundary+' } NOT = { has_variable = '+epoch+' } } AND = { var:'+boundary+' = 1 var:'+epoch+' = var:'+prefix+'reservation_epoch var:'+prefix+'source_completed_1 = 1 var:'+prefix+'source_completed_epoch_1 = var:'+prefix+'reservation_epoch } } }')
        _assert_boundary_dispatch(self,dispatch,1)
        def remove_atom(sequence,predicate):
            return [replace(n,value=tuple(remove_atom(children(n),predicate))) if isinstance(n.value,tuple) else n for n in sequence if not predicate(n)]
        for target in (boundary,epoch,prefix+'source_completed_1',prefix+'source_completed_epoch_1',prefix+'body_completed_1',prefix+'body_completed_epoch_1'):
            broken=remove_atom(dispatch,lambda n:n.key=='has_variable' and n.value==target or n.key=='var:'+target)
            with self.assertRaises(AssertionError): _assert_boundary_dispatch(self,broken,1)

    def test_sender_capture_mapping_and_all_guard_consumers_reject_narrow_corruptions(self):
        names=sorted(_all_native_context_names())
        self.assertEqual(len(names),12)
        je=catalog()['arcs'][0]['journals'][0]; row=_binding(je['id'],je['script'])[0]
        branch=next(n for n in _walk(parse_block(je['script'])) if n.start==row['start'] and n.end==row['end'])
        fields=children(branch); at=next(i for i,n in enumerate(fields) if n.key=='trigger_event')
        queue=row['candidates'][0]['queue']
        # Assertion-only capture/guard specimens use real native TIB fields and
        # prefragment AST, and never enter a world or a renderer return value.
        native_pre=' '.join(je['script'][n.start:n.end] for n in fields[:at] if n.key!='limit' and not (n.key=='remove_variable' and n.value==queue))
        expected={native:(f'ywc_v03_tib_inline_control_snapshot_{i}_present',f'ywc_v03_tib_inline_control_snapshot_{i}_value') for i,native in enumerate(names)}
        def capture(native,pair):
            presence,value=pair
            return 'set_variable = { name = '+presence+' value = 0 } set_variable = { name = '+value+' value = 0 } if = { limit = { has_variable = '+native+' } set_variable = { name = '+presence+' value = 1 } set_variable = { name = '+value+' value = var:'+native+' } }'
        chunks={native:capture(native,pair) for native,pair in expected.items()}
        source='{ '+native_pre+' '+' '.join(chunks.values())+' }'
        mapping=_assert_sender_snapshot_capture(self,parse_block(source),names,'actual-native-bound specimen')
        self.assertEqual(mapping,expected)
        one,other=names[:2]; p0,v0=expected[one]; p1,v1=expected[other]
        mutations={
            'missing capture':source.replace(chunks[other],'',1),
            'wrong source read':source.replace('value = var:'+other+' }','value = var:'+one+' }',1),
            'cross-field alias':source.replace(p1,p0).replace(v1,v0),
            'missing absent initialization':source.replace('set_variable = { name = '+v1+' value = 0 }','',1),
            'incorrect absent value':source.replace('name = '+v1+' value = 0','name = '+v1+' value = 7',1),
        }
        for label,mutant in mutations.items():
            with self.subTest(capture=label):
                with self.assertRaises(AssertionError): _assert_sender_snapshot_capture(self,parse_block(mutant),names,label)
        def guard(native,pair):
            presence,value=pair
            return 'OR = { AND = { has_variable = '+native+' has_variable = '+presence+' has_variable = '+value+' var:'+presence+' = 1 var:'+native+' = var:'+value+' } AND = { NOT = { has_variable = '+native+' } has_variable = '+presence+' has_variable = '+value+' var:'+presence+' = 0 var:'+value+' = 0 } }'
        checks={native:guard(native,pair) for native,pair in mapping.items()}
        full=' '.join(checks.values())
        for consumer in ('dispatch','source_return','body_return','callback','join','ack'):
            with self.subTest(consumer=consumer):
                if consumer=='dispatch':
                    # Both pre-R and reached-R alternatives must retain all P
                    # fields. Identity R=P can reuse exactly the same mapping.
                    valid=parse_block('{ OR = { AND = { '+full+' } AND = { '+full+' } } }')
                    _assert_complete_snapshot_guard(self,valid,mapping,consumer)
                    broken=parse_block('{ OR = { AND = { '+full.replace(checks[other],'',1)+' } AND = { '+full+' } } }')
                    with self.assertRaises(AssertionError): _assert_complete_snapshot_guard(self,broken,mapping,consumer)
                else:
                    valid=parse_block('{ if = { limit = { '+full+' } assertion_wake = yes } }')
                    _assert_complete_native_snapshots(self,valid,mapping,consumer)
                    broken=parse_block('{ if = { limit = { '+full.replace(checks[other],'',1)+' } assertion_wake = yes } }')
                    with self.assertRaises(AssertionError): _assert_complete_native_snapshots(self,broken,mapping,consumer)
        aliased={native:expected[one] for native in names}
        with self.assertRaises(AssertionError): _assert_complete_snapshot_guard(self,parse_block('{ '+full+' }'),aliased,'aliased mapping')
        wrong_guards=' '.join(guard(native,expected[one]) for native in names)
        with self.assertRaises(AssertionError): _assert_complete_snapshot_guard(self,parse_block('{ '+wrong_guards+' }'),mapping,'aliased guards')
    def test_pure_source_boundary_owner_requires_all_epochs_and_rejects_hidden_dependencies(self):
        from dataclasses import replace
        prefix='ywc_v03_tib_inline_'; ident=1
        source='{ has_variable = '+prefix+'reservation var:'+prefix+'reservation = 1 has_variable = '+prefix+'epoch var:'+prefix+'epoch > 0 has_variable = '+prefix+'reservation_epoch var:'+prefix+'reservation_epoch > 0 var:'+prefix+'reservation_epoch = var:'+prefix+'epoch has_variable = '+prefix+'candidate_epoch_1 var:'+prefix+'candidate_epoch_1 > 0 var:'+prefix+'candidate_epoch_1 = var:'+prefix+'reservation_epoch exists = scope:'+prefix+'dispatch_candidate scope:'+prefix+'dispatch_candidate = 1 exists = scope:'+prefix+'dispatch_epoch scope:'+prefix+'dispatch_epoch = var:'+prefix+'reservation_epoch }'
        valid=parse_block(source); _assert_source_boundary_owner(self,valid,ident,'minimal pure positive')
        for index,atom in enumerate(valid):
            with self.subTest(deleted=(atom.key,atom.op,atom.value)):
                with self.assertRaises(AssertionError): _assert_source_boundary_owner(self,valid[:index]+valid[index+1:],ident,'atom missing')
        jid=catalog()['arcs'][0]['journals'][0]['id']
        dependencies=('has_variable = ywc_tib_grain_pending_event','var:ywc_tib_grain_pending_event = 1010',
                      'has_journal_entry = '+jid,'var:'+prefix+'live_register_1 = 1',
                      'ywc_v03_can_deliver_major = yes','has_variable = ywc_v03_major_event_cooldown')
        for dependency in dependencies:
            for wrapper in ('NOT = { '+dependency+' }','OR = { '+dependency+' always = yes }','AND = { OR = { NOT = { '+dependency+' } } }'):
                with self.subTest(hidden=wrapper):
                    mutant=parse_block(source[:-1]+' '+wrapper+' }')
                    with self.assertRaises(AssertionError): _assert_source_boundary_owner(self,mutant,ident,'hidden native dependency')

if __name__=='__main__': unittest.main()
