"""TIB school opening AI rules against actual school-entry facts and source AST."""
import copy
import math
import unittest
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from clausewitz_harness import parse
import test_v03_tib_foundation_lifecycle as tib_lifecycle
from test_v03_tib_foundation_lifecycle import TibWorldFacts, field

OPS={"=","!=",">",">=","<","<="}
class StrictSchoolWorld(TibWorldFacts):
    """Local strict adapter; deliberately leaves the shared TIB facts class untouched."""
    def _number(self, value, context):
        try: result=float(value)
        except (TypeError,ValueError): raise AssertionError(("invalid_number",context,value))
        if not math.isfinite(result): raise AssertionError(("nonfinite_number",context,value))
        return result
    def _compare(self,left,op,right,context):
        if op not in OPS: raise AssertionError(("invalid_comparison",context,op))
        return self.compare(left,op,right)
    def _validate_gold(self,op,value,node):
        if op not in OPS: raise AssertionError(("invalid_gold_operator",node))
        if isinstance(value,str):
            raw=value
            if raw.startswith("var:"):
                if raw[4:] not in self.countries["TIB"]: raise AssertionError(("unknown_gold_variable",node))
            else:
                self._number(raw,node)
            return
        if not isinstance(value,list): raise AssertionError(("invalid_gold_value",node))
        seen=set()
        for child in value:
            if not isinstance(child,(tuple,list)) or len(child)!=3: raise AssertionError(("invalid_gold_child",node,child))
            key,cop,cv=child
            if key not in ("value","multiply") or key in seen: raise AssertionError(("unknown_or_duplicate_gold_child",node,child))
            seen.add(key)
            if cop!="=" or not isinstance(cv,str): raise AssertionError(("invalid_gold_child_shape",node,child))
            if key=="value" and cv.startswith("var:") and cv[4:] not in self.countries["TIB"]: raise AssertionError(("unknown_gold_variable",node,cv))
            if key=="multiply" or not cv.startswith("var:"): self._number(cv,node)
        if "value" not in seen: raise AssertionError(("missing_gold_value",node))
    def _validate_condition(self,node):
        if not isinstance(node,(tuple,list)) or len(node)!=3: raise AssertionError(("invalid_condition_node",node))
        key,op,value=node
        if key in ("AND","OR","NOT"):
            if op!="=" or not isinstance(value,list) or (key=="NOT" and len(value)!=1): raise AssertionError(("invalid_boolean_shape",node))
            for child in value: self._validate_condition(child)
            return
        if key in self.trigger_defs:
            if op!="=" or value!="yes": raise AssertionError(("invalid_scripted_trigger_call",node))
            for child in self.trigger_defs[key]: self._validate_condition(child)
            return
        if key=="has_variable":
            if op!="=" or not isinstance(value,str): raise AssertionError(("invalid_has_variable",node))
            return
        if key in ("net_fixed_income","literacy_rate","occupancy","market_access","average_sol","radical_fraction"):
            if op not in OPS: raise AssertionError(("invalid_numeric_predicate",node))
            self._number(value,node);return
        if key in ("in_default","has_modifier","has_law","has_law_or_variant","owner","is_owned_by","is_pop_type","is_employed","is_building_type"):
            if key=="owner" and (op!="=" or value!="ROOT"): raise AssertionError(("invalid_owner_predicate",node))
            if op not in ("=","?=") or not isinstance(value,str): raise AssertionError(("invalid_scalar_predicate",node))
            return
        if key in ("any_scope_state","any_scope_pop","any_scope_building"):
            if op!="=" or not isinstance(value,list): raise AssertionError(("invalid_scope_predicate",node))
            for child in value:self._validate_condition(child)
            return
        if key=="workplace":
            if op!="?=" or not isinstance(value,list): raise AssertionError(("invalid_workplace_predicate",node))
            for child in value:self._validate_condition(child)
            return
        if key=="institution_investment_level":
            if op!="=" or not isinstance(value,list): raise AssertionError(("invalid_institution_shape",node))
            seen=set()
            for child in value:
                if not isinstance(child,(tuple,list)) or len(child)!=3:raise AssertionError(("invalid_institution_child",node,child))
                ck,cop,cv=child
                if ck not in ("institution","value") or ck in seen:raise AssertionError(("unknown_or_duplicate_institution_child",node,child))
                seen.add(ck)
                if ck=="institution":
                    if cop!="=" or not isinstance(cv,str):raise AssertionError(("invalid_institution_name",node,child))
                else:
                    if cop not in OPS:raise AssertionError(("invalid_institution_operator",node,child))
                    self._number(cv,node)
            if seen!={"institution","value"}:raise AssertionError(("incomplete_institution",node))
            return
        if key=="is_pop_type" or key=="workplace":raise AssertionError(("unsupported_scope_predicate",node))
        if key=="any_interest_group":
            if op!="=" or not isinstance(value,list) or not value: raise AssertionError(("invalid_any_ig",node))
            seen=set()
            for child in value:
                if not isinstance(child,(tuple,list)) or len(child)!=3: raise AssertionError(("invalid_ig_child",node,child))
                ck,cop,cv=child
                if ck not in ("is_interest_group_type","ig_approval") or ck in seen: raise AssertionError(("unknown_or_duplicate_ig_child",node,child))
                seen.add(ck)
                if ck=="is_interest_group_type":
                    if cop!="=" or not isinstance(cv,str) or not cv.startswith("ig_"): raise AssertionError(("invalid_ig_type",node,child))
                else:
                    if cop not in OPS or not isinstance(cv,str): raise AssertionError(("invalid_ig_approval",node,child))
                    self._number(cv,node)
            return
        if key=="gold_reserves": self._validate_gold(op,value,node); return
        raise AssertionError(("unknown_ai_condition",node))
    def condition(self,node,tag):
        key,op,value=node
        if key=="any_interest_group":
            self._validate_condition(node)
            groups=self.countries[tag].get("igs",[])
            for group in groups:
                checks=[]
                for ck,cop,cv in value:
                    if ck=="is_interest_group_type": checks.append(group.get("type")==cv)
                    else: checks.append(self._compare(float(group["approval"]),cop,self._number(cv,node),node))
                if all(checks): return True
            return False
        if key=="gold_reserves":
            self._validate_gold(op,value,node)
            state=self.countries[tag]
            if isinstance(value,list):
                fields={k:v for k,_,v in value}; raw=fields["value"]
                right=(float(state[raw[4:]]) if raw.startswith("var:") else self._number(raw,node))
                if "multiply" in fields:right*=self._number(fields["multiply"],node)
            else: right=float(state[value[4:]]) if value.startswith("var:") else self._number(value,node)
            cash=float(state.get("gold_reserves",0))+float(self.treasury.get(tag,0))
            return self._compare(cash,op,right,node)
        if key=="has_variable" and (op!="=" or not isinstance(value,str)):
            raise AssertionError(("invalid_has_variable",node))
        return super().condition(node,tag)
    def weight(self,ai,tag="TIB"):
        if not isinstance(ai,list): raise AssertionError(("invalid_ai",ai))
        base=None;mods=[]
        for node in ai:
            if not isinstance(node,(tuple,list)) or len(node)!=3: raise AssertionError(("invalid_ai_node",node))
            key,op,value=node
            if op!="=": raise AssertionError(("invalid_ai_operator",node))
            if key=="base":
                if base is not None: raise AssertionError(("duplicate_ai_base",ai))
                base=self._number(value,node)
            elif key=="modifier":
                if not isinstance(value,list): raise AssertionError(("invalid_ai_modifier",node))
                fields={}
                for child in value:
                    if not isinstance(child,(tuple,list)) or len(child)!=3: raise AssertionError(("invalid_ai_modifier_child",node,child))
                    ck,cop,cv=child
                    if ck not in ("add","trigger") or ck in fields: raise AssertionError(("unknown_or_duplicate_ai_modifier_child",node,child))
                    if cop!="=": raise AssertionError(("invalid_ai_modifier_operator",node,child))
                    fields[ck]=cv
                if set(fields)!={"add","trigger"} or not isinstance(fields["trigger"],list): raise AssertionError(("incomplete_ai_modifier",node))
                self._number(fields["add"],node)
                for cond in fields["trigger"]: self._validate_condition(cond)
                mods.append(fields)
            else: raise AssertionError(("unknown_ai_node",node))
        if base is None: raise AssertionError(("missing_ai_base",ai))
        result=base
        for mod in mods:
            if self.conditions(mod["trigger"],tag): result+=self._number(mod["add"],ai)
        return result

class TibSchoolOpeningAITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tib_lifecycle.TibStrictLifecycleTest.setUpClass()
        cls.driver=tib_lifecycle.TibStrictLifecycleTest()
        cls.arc=cls.driver.arcs["v03_tib_shared_schools"]
    def world_at_opening(self,cash,devout):
        w=self.driver.world("schools",1,cash)
        w.__class__=StrictSchoolWorld
        w.countries["TIB"]["igs"]=[{"type":"ig_devout","approval":devout}]
        event_id=self.driver.entry(self.arc,w)
        self.assertEqual(event_id,"ywc_tib.1020")
        event=self.driver.deliver(w,self.arc,event_id)
        return w,event
    def weights(self,w,event):
        result={}
        for key,_,option in event:
            if key!="option" or not any(k=="ai_chance" for k,_,_ in option): continue
            name=field(option,"name").rsplit(".",1)[1]
            result[name]=w.weight(field(option,"ai_chance"))
        return result
    def legal(self,w,event,key):
        option=next(v for k,_,v in event if k=="option" and field(v,"name").endswith("."+key))
        return w.conditions(field(option,"trigger"),"TIB")
    def test_real_opening_weights_use_devout_and_captured_school_cost_headroom(self):
        scenarios=((200,-2,{"route_1":46,"route_2":39},True,True),
                   (250,2,{"route_1":34,"route_2":47},True,True),
                   (400,-2,{"route_1":54,"route_2":29},True,True),
                   (0,-2,{"route_1":34,"route_2":29},False,False))
        for cash,approval,expected,legal1,legal2 in scenarios:
            with self.subTest(cash=cash,devout=approval):
                w,event=self.world_at_opening(cash,approval)
                s=w.countries["TIB"]
                self.assertEqual(s["ywc_tib_schools_route_cost_1"],200)
                self.assertEqual(s["ywc_tib_schools_route_cost_2"],150)
                got=self.weights(w,event)
                self.assertEqual({k:got[k] for k in expected},expected)
                self.assertEqual(self.legal(w,event,"route_1"),legal1)
                self.assertEqual(self.legal(w,event,"route_2"),legal2)
    def test_both_routes_pay_once_and_complete_actual_school_lifecycle_at_cash_boundary(self):
        for route,cash,approval in ((1,200,-2),(2,150,2)):
            with self.subTest(route=route):
                w,event=self.world_at_opening(cash,approval)
                state=w.countries["TIB"]
                self.assertTrue(self.legal(w,event,f"route_{route}"))
                before=w.treasury["TIB"]
                self.driver.choose(w,self.arc,event,f"route_{route}")
                self.assertEqual(w.treasury["TIB"]-before,-cash)
                self.assertEqual(state["gold_reserves"]+w.treasury["TIB"],0)
                self.assertEqual(state["ywc_tib_schools_paid"],1)
                self.driver.implement(w,self.arc,route)
                self.driver.settle(w,self.arc,route)
                self.assertEqual(w.treasury["TIB"],-cash)
                self.assertEqual(state["ywc_v03_active_arc_count"],0)
    def test_gold_scalar_numeric_literal_is_still_supported(self):
        w,_=self.world_at_opening(400,-2)
        self.assertTrue(w.condition(("gold_reserves",">=","0"),"TIB"))
    def test_variable_presence_is_independent_of_numeric_value(self):
        w,_=self.world_at_opening(400,-2)
        state=w.countries["TIB"]
        state["fixture_zero_value_presence"]=0
        self.assertTrue(w.condition(("has_variable","=","fixture_zero_value_presence"),"TIB"))
        self.assertFalse(w.condition(("has_variable","=","fixture_absent"),"TIB"))
    def test_strict_ai_condition_and_modifier_shapes_fail_closed(self):
        w,_=self.world_at_opening(400,-2)
        bad_conditions=[
            [("any_interest_group","=",[("is_interest_group_type","=","ig_nonexistent"),("unknown_fact","=","yes")])],
            [("any_interest_group","=",[("ig_approval",">","999"),("unknown_fact","=","yes")])],
            [("any_interest_group","=",[("is_interest_group_type",">=","ig_devout")])],
            [("any_interest_group","!=",[("is_interest_group_type","=","ig_devout")])],
            [("any_interest_group","=",[("is_interest_group_type","=","ig_devout"),("unknown_fact","=","yes")])],
            [("any_interest_group","=",[("is_interest_group_type","=","ig_devout"),("ig_approval","<","0"),("ig_approval","<","5")])],
            [("gold_reserves",">=",[("value","=","1"),("unknown","=","yes")])],
            [("gold_reserves",">=",[("value","=","1"),("value","=","2")])],
            [("gold_reserves",">=",[("value",">=","1")])],
            [("gold_reserves",">=",[("value","=","1"),("multiply","!=","2")])],
        ]
        for cond in bad_conditions:
            with self.subTest(condition=cond),self.assertRaises(AssertionError):w.conditions(cond,"TIB")
        bad_ai=[[("base","=","1"),("base","=","2")],
                [("base","=","1"),("mystery","=","3")],
                [("base","=","1"),("modifier","=",[("add","=","2"),("add","=","3"),("trigger","=",[])])],
                [("base",">=","1")],
                [("base","=","1"),("modifier","=",[("add","=","2"),("trigger","=",[("has_variable","=","fixture_absent"),("gold_reserves",">=","not_a_supported_number_or_variable")])])]]
        for ai in bad_ai:
            with self.subTest(ai=ai),self.assertRaises(AssertionError):w.weight(ai)
        w.countries["TIB"]["igs"]=[]
        with self.assertRaises(AssertionError):w.conditions(bad_conditions[0],"TIB")
        empty_ig_then_bad_gold=[("base","=","1"),("modifier","=",[("add","=","2"),("trigger","=",[("any_interest_group","=",[("is_interest_group_type","=","ig_devout")]),("gold_reserves",">=","not_a_supported_number_or_variable")])])]
        with self.assertRaises(AssertionError):w.weight(empty_ig_then_bad_gold)

if __name__=="__main__":unittest.main()
