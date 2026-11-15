"""Narrow current native market/country/treaty facts, not a market story model.

The native helper AST below is from the installed Victoria3 source:
common/scripted_triggers/00_diplomacy_triggers.txt:81-96.
Directed trade_privilege is defined in common/treaty_articles/25_trade_privilege.txt.
No treaty is ratified here; ``treaties`` contains only already-current treaties.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import copy
import re

from clausewitz_harness import parse
from shu_kor_strict_review_runtime import Strict


def market_test_facts():
    """Concrete current engine facts; no business result or qualification flags."""
    countries = {}
    for tag, market in (("DMG", "m_dmg"), ("PHI", "m_phi"), ("SPA", "m_phi"),
                        ("JHG", "m_jhg"), ("LAN", "m_lan")):
        countries[tag] = {"market_id": market, "alive": True, "laws": [],
                          "junior_in_customs_union": False, "is_at_war": False,
                          "states": []}
    office = {"type": "building_government_administration", "occupancy": .8,
              "shortage": False, "groups": []}
    port = {"type": "building_port", "occupancy": .9,
            "shortage": False, "groups": []}
    countries["DMG"]["states"] = [{"owner": "DMG", "region": "s:STATE_LUZON",
        "market_access": .8, "buildings": [office], "pops": [
            {"type": "bureaucrats", "primary": False, "acceptance": 5,
             "employed": True, "wealth": 25, "literacy": .5, "workplace": office}]}]
    countries["PHI"]["states"] = [{"owner": "PHI", "region": "s:STATE_LUZON",
        "market_access": .95, "buildings": [port], "pops": [
            {"type": "laborers", "primary": False, "acceptance": 5,
             "employed": True, "wealth": 20, "literacy": .4, "workplace": port}]}]
    return {"countries": countries, "markets": {
        "m_dmg": {"owner": "DMG", "imports_reliance": {"m_phi": .02}},
        "m_phi": {"owner": "SPA", "imports_reliance": {}},
        "m_jhg": {"owner": "JHG", "imports_reliance": {}},
        "m_lan": {"owner": "LAN", "imports_reliance": {}}},
        "treaties": [], "draft_treaties": [], "wars": set(), "pacts": set(),
        "relations": {("DMG", "PHI"): 20}}


NATIVE_TRADE_PRIVILEGE_AST = parse("""
custom_description = {
 text = has_treaty_trade_privilege_with_trigger
 subject = this
 object = $TARGET$
 hidden_trigger = {
  any_scope_treaty = {
   binds = $TARGET$
   any_scope_article = { has_type = trade_privilege source_country = $TARGET$ }
  }
 }
}
""")
# common/scripted_triggers/00_ep2_victoria_scripted_triggers.txt:173-177.
NATIVE_ISOLATION_AST = parse("""OR = {
 has_law = law_type:law_isolationism
 has_law = law_type:law_sakoku
}""")


@dataclass(frozen=True)
class _Object:
    kind: str
    identity: str


class DmgMarketWorld(Strict):
    """Extend only native fact interpretation; inherited business ASTs stay real."""

    _scope_names = ("state_scope", "pop_scope", "building_scope", "good_scope",
                    "market_scope", "treaty_scope", "article_scope", "_object_scope")
    _country_keys = {
        "is_country_alive", "is_junior_in_customs_union", "is_at_war",
        "has_war_with", "has_diplomatic_pact", "has_law", "has_law_or_variant",
        "country_has_isolationism_or_sakoku", "has_treaty_trade_privilege_with",
        "net_fixed_income", "bureaucracy", "gold_reserves", "yearly_gross_income",
        "scaled_debt", "army_size", "navy_size", "legitimacy", "authority",
        "in_default", "is_subject", "country_has_voting_franchise",
        "has_variable", "has_modifier", "has_journal_entry", "institution_investment_level",
        "any_interest_group",
    }
    _pop_keys = {"is_pop_type", "is_employed", "pop_has_primary_culture",
                 "pop_acceptance", "wealth"}
    _building_keys = {"is_building_type", "is_building_group", "occupancy",
                      "building_has_goods_shortage"}

    def __init__(self, tag="dmg", *, load_inline=True, markets=None, treaties=None,
                 draft_treaties=None, wars=None, pacts=None, relations=None):
        # Root may use this only after production sources are stable. Literal
        # tests deliberately use __new__ + TibWorldFacts.__init__ instead.
        super().__init__(tag, load_inline=load_inline)
        self.configure_market_facts(markets=markets, treaties=treaties,
            draft_treaties=draft_treaties, wars=wars, pacts=pacts, relations=relations)

    def configure_market_facts(self, *, markets=None, treaties=None, draft_treaties=None,
                               wars=None, pacts=None, relations=None):
        self._root_tag = self.tag
        self.markets = copy.deepcopy(markets) if markets is not None else {}
        self.treaties = copy.deepcopy(treaties) if treaties is not None else []
        self.draft_treaties = copy.deepcopy(draft_treaties) if draft_treaties is not None else []
        self.wars = copy.deepcopy(wars) if wars is not None else set()
        self.pacts = copy.deepcopy(pacts) if pacts is not None else set()
        self.relations = copy.deepcopy(relations) if relations is not None else {}
        self.market_scope = self.treaty_scope = self.article_scope = None
        self._object_scope = None

    @staticmethod
    def _require(condition, detail):
        if not condition:
            raise AssertionError(detail)

    def _finite(self, value, detail, *, text=False):
        if text:
            self._require(isinstance(value, str), ("numeric_query_not_text", detail, value))
        else:
            self._require(isinstance(value, (int, float)) and not isinstance(value, bool),
                          ("numeric_fact_not_number", detail, value))
        return self._number(value, detail)

    def _numeric(self, actual, op, expected, detail):
        self._require(op in self._comparison_ops, ("bad_numeric_operator", detail))
        return self.compare(self._finite(actual, detail), op,
                            self._finite(expected, detail, text=True))

    def _bool(self, actual, op, expected, detail):
        self._require(op == "=" and expected in ("yes", "no") and isinstance(actual, bool),
                      ("bad_native_boolean", detail, actual))
        return actual == (expected == "yes")

    def _kind(self):
        for name, kind in (("article_scope", "article"), ("treaty_scope", "treaty"),
                           ("building_scope", "building"), ("pop_scope", "pop"),
                           ("state_scope", "state"), ("market_scope", "market")):
            if getattr(self, name, None) is not None:
                return kind
        return "country"

    @contextmanager
    def _scope(self, kind, identity, *, state=None, pop=None, building=None,
               treaty=None, article=None):
        saved = {name: getattr(self, name, None) for name in self._scope_names}
        for name in self._scope_names:
            setattr(self, name, None)
        self.state_scope, self.pop_scope, self.building_scope = state, pop, building
        self.treaty_scope, self.article_scope = treaty, article
        if kind in ("country", "market"):
            self._object_scope = _Object(kind, identity)
        if kind == "market":
            self.market_scope = identity
        try:
            yield
        finally:
            for name, old in saved.items():
                setattr(self, name, old)

    def _path(self, expression, context=None):
        self._require(isinstance(expression, str), ("object_reference_not_text", expression))
        parts = expression.split(".")
        context = context or self._kind()
        if parts[0] in ("ROOT", "root"):
            base, kind = ("root", None), "country"
            parts = parts[1:]
        elif re.fullmatch(r"c:[A-Z][A-Z0-9_]+", parts[0]):
            base, kind = ("country", parts[0][2:]), "country"
            parts = parts[1:]
        elif parts[0] == "this":
            self._require(context in ("country", "market"), ("this_object_scope", context))
            base, kind = ("current", None), context
            parts = parts[1:]
        else:
            self._require(parts[0] in ("market", "market_capital"),
                          ("unknown_object_reference", expression))
            self._require(context in ("country", "market"), ("market_link_scope", context))
            base, kind = ("current", None), context
            if context == "market" and parts[0] == "market":
                parts = parts[1:]
        links = []
        while parts:
            if kind == "country" and parts[0] == "market_capital":
                self._require(parts[:2] == ["market_capital", "market"],
                              ("unsupported_market_capital_link", expression))
                links.append("market")
                parts, kind = parts[2:], "market"
            elif kind == "country" and parts[0] == "market":
                links.append("market")
                parts, kind = parts[1:], "market"
            elif kind == "market" and parts[0] == "owner":
                links.append("owner")
                parts, kind = parts[1:], "country"
            else:
                raise AssertionError(("unknown_object_link", expression, parts, kind))
        return base, links, kind

    def _looks_object(self, key):
        return key in ("ROOT", "root", "this", "market", "market_capital.market") or key.startswith(
            ("c:", "ROOT.", "root.", "this.", "market.", "market_capital."))

    def _market(self, market_id):
        self._require(isinstance(self.markets, dict) and isinstance(market_id, str)
                      and market_id in self.markets, ("missing_market_fact", market_id))
        data = self.markets[market_id]
        self._require(isinstance(data, dict) and set(data) == {"owner", "imports_reliance"},
                      ("malformed_market_fact", market_id, data))
        self._require(isinstance(data["owner"], str) and data["owner"] in self.countries,
                      ("unknown_market_owner", market_id, data["owner"]))
        self._require(isinstance(data["imports_reliance"], dict), ("bad_imports_facts", market_id))
        return data

    def _resolve(self, expression, tag):
        base, links, _ = self._path(expression)
        if base[0] == "root":
            obj = _Object("country", self._root_tag)
        elif base[0] == "country":
            obj = _Object("country", base[1]) if base[1] in self.countries else None
        elif self._kind() == "market":
            obj = _Object("market", self.market_scope)
        else:
            obj = _Object("country", tag)
        for link in links:
            if obj is None:
                return None
            if link == "market":
                country = self.countries[obj.identity]
                self._require("market_id" in country, ("missing_market_id", obj.identity))
                market_id = country["market_id"]
                if market_id is None:
                    return None
                self._market(market_id)
                obj = _Object("market", market_id)
            else:
                obj = _Object("country", self._market(obj.identity)["owner"])
        return obj

    def _country_ref(self, expression, tag):
        self._require(self._path(expression)[2] == "country", ("expected_country_reference", expression))
        return self._resolve(expression, tag)

    @staticmethod
    def _fields(nodes, names, detail):
        if not isinstance(nodes, list) or len(nodes) != len(names):
            raise AssertionError(("wrong_native_argument_shape", detail, nodes))
        result = {}
        for item in nodes:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise AssertionError(("malformed_native_argument", detail, item))
            key, op, value = item
            if key not in names or key in result:
                raise AssertionError(("unknown_or_duplicate_native_argument", detail, item))
            result[key] = (op, value)
        return result

    def _validate_ast(self, nodes, context):
        self._require(isinstance(nodes, list), ("condition_block_not_list", nodes))
        for node in nodes:
            self._require(isinstance(node, (tuple, list)) and len(node) == 3,
                          ("malformed_condition_node", node))
            k, op, value = node
            if k in ("AND", "OR", "NOT", "NOR", "hidden_trigger"):
                self._require(op == "=" and isinstance(value, list) and value,
                              ("invalid_logic_block", node))
                self._validate_ast(value, context)
            elif k == "custom_description":
                fields = self._fields(value, {"text", "subject", "object", "hidden_trigger"}, node)
                self._require(op == "=" and all(fields[x][0] == "=" and isinstance(fields[x][1], str)
                              for x in ("text", "subject", "object")), ("bad_ui_metadata", node))
                self._require(fields["hidden_trigger"][0] == "=", ("bad_hidden_trigger", node))
                self._validate_ast(fields["hidden_trigger"][1], context)
            elif k in ("has_diplomatic_pact", "market_imports_reliance", "has_treaty_trade_privilege_with"):
                names = ({"who", "type"} if k == "has_diplomatic_pact" else
                         {"target", "value"} if k == "market_imports_reliance" else {"TARGET"})
                f = self._fields(value, names, node)
                self._require(op == "=", ("bad_native_query_operator", node))
                required_scope = "market" if k == "market_imports_reliance" else "country"
                self._require(context == required_scope, ("wrong_native_query_scope", node, context))
                reference = f["target" if k == "market_imports_reliance" else "who" if k == "has_diplomatic_pact" else "TARGET"]
                self._require(reference[0] == "=", ("bad_native_target_operator", node))
                self._require(self._path(reference[1], context)[2] == required_scope,
                              ("wrong_target_object_type", node))
                if k == "has_diplomatic_pact":
                    self._require(f["type"] == ("=", "embargo"), ("unsupported_pact_type", node))
                if k == "market_imports_reliance":
                    self._require(f["value"][0] in self._comparison_ops, ("bad_reliance_operator", node))
                    self._finite(f["value"][1], node, text=True)
            elif k in ("any_scope_treaty", "any_scope_article", "any_scope_state", "any_scope_pop", "any_scope_building", "workplace"):
                expected = {"any_scope_treaty": "country", "any_scope_article": "treaty",
                            "any_scope_state": "country", "any_scope_pop": "state",
                            "any_scope_building": "state", "workplace": "pop"}[k]
                dest = {"any_scope_treaty": "treaty", "any_scope_article": "article",
                        "any_scope_state": "state", "any_scope_pop": "pop",
                        "any_scope_building": "building", "workplace": "building"}[k]
                self._require(context == expected and op == ("?=" if k == "workplace" else "=")
                              and isinstance(value, list) and value, ("invalid_native_scope", node, context))
                self._validate_ast(value, dest)
            elif k in ("binds", "has_type", "source_country", "target_country"):
                expected = "treaty" if k == "binds" else "article"
                self._require(context == expected and op == "=" and isinstance(value, str),
                              ("invalid_treaty_article_predicate", node, context))
                if k != "has_type":
                    self._require(self._path(value, context)[2] == "country", ("expected_country", node))
            elif k == "owner":
                self._require(context in ("state", "market") and op in ("=", "?=", "!="),
                              ("invalid_owner_scope_or_operator", node, context))
                if isinstance(value, list):
                    self._require(op in ("=", "?="), ("invalid_owner_block_operator", node))
                    self._validate_ast(value, "country")
                else:
                    self._require(self._path(value, context)[2] == "country", ("invalid_owner_target", node))
            elif ".relations:" in k:
                left, right = k.split(".relations:")
                self._require(self._path(left, context)[2] == self._path(right, context)[2] == "country"
                              and op in self._comparison_ops, ("bad_relations_query", node))
                self._finite(value, node, text=True)
            elif self._looks_object(k) and not k.startswith("ROOT.modifier:"):
                dest = self._path(k, context)[2]
                self._require(op in ("=", "?=", "!="), ("invalid_object_operator", node))
                if isinstance(value, list):
                    self._require(op in ("=", "?="), ("invalid_object_block_operator", node))
                    self._validate_ast(value, dest)
                else:
                    self._require(self._path(value, context)[2] == dest, ("object_type_mismatch", node))
            elif k in self._country_keys:
                self._require(context == "country", ("country_fact_outside_country", node, context))
                if k in ("is_country_alive", "is_junior_in_customs_union", "country_has_isolationism_or_sakoku", "is_at_war"):
                    self._require(op == "=" and value in ("yes", "no"), ("invalid_boolean_query", node))
                elif k == "has_war_with":
                    self._require(op == "=" and self._path(value, context)[2] == "country", ("bad_war_query", node))
                elif k in ("has_law", "has_law_or_variant"):
                    self._require(op == "=" and isinstance(value, str), ("bad_law_query", node))
            elif k in ("market_access", "state_region", "has_building"):
                self._require(context == "state", ("state_fact_outside_state", node))
                if k == "market_access":
                    self._require(op in self._comparison_ops, ("invalid_state_numeric_operator", node))
                    self._finite(value, node, text=True)
                else:
                    self._require(op == "=" and isinstance(value, str), ("invalid_state_fact", node))
            elif k in self._pop_keys or k in self._building_keys:
                self._require(context == ("pop" if k in self._pop_keys else "building"),
                              ("invalid_fact_scope", node, context))
                if k in ("occupancy", "wealth", "pop_acceptance"):
                    self._require(op in self._comparison_ops, ("invalid_fact_comparison", node))
                else:
                    self._require(op == "=" and isinstance(value, str), ("invalid_fact_predicate", node))
            elif k in self.trigger_defs:
                self._require(op == "=" and value in ("yes", "no"), ("bad_scripted_trigger_call", node))
            elif k in ("always", "exists", "literacy_rate", "average_sol", "radical_fraction") or k.startswith(("var:", "scope:", "modifier:", "ROOT.modifier:")):
                pass  # The existing strict adapter validates its own native subset.
            else:
                raise AssertionError(("unsupported_native_condition", node))

    def conditions(self, nodes, tag):
        self._validate_ast(nodes, self._kind())
        # Eager evaluation prevents a false sibling from hiding malformed facts.
        return all([self.condition(node, tag) for node in nodes])

    def _treaty_records(self):
        self._require(isinstance(self.treaties, list), ("current_treaties_not_list", self.treaties))
        for treaty in self.treaties:
            self._require(isinstance(treaty, dict) and {"participants", "articles"} <= set(treaty)
                          and set(treaty) <= {"id", "participants", "articles"}, ("bad_treaty_fact", treaty))
            people = treaty["participants"]
            self._require(isinstance(people, (tuple, list)) and len(people) == 2
                          and all(isinstance(x, str) and x in self.countries for x in people)
                          and people[0] != people[1], ("bad_treaty_participants", treaty))
            self._require(isinstance(treaty["articles"], list), ("bad_article_list", treaty))
            for article in treaty["articles"]:
                self._require(isinstance(article, dict) and set(article) == {"type", "source_country", "target_country"},
                              ("bad_article_fact", article))
                self._require(isinstance(article["type"], str) and article["type"]
                              and article["source_country"] in people and article["target_country"] in people
                              and article["source_country"] != article["target_country"], ("bad_directed_article_roles", article))
        return self.treaties

    def _pairs(self, values, label):
        self._require(isinstance(values, (set, list, tuple)), ("bad_pair_collection", label))
        result = []
        for pair in values:
            self._require(isinstance(pair, (tuple, list, frozenset)) and len(pair) == 2
                          and all(isinstance(x, str) and x in self.countries for x in pair)
                          and len(set(pair)) == 2, ("bad_country_pair", label, pair))
            result.append(frozenset(pair))
        return result

    def _relation(self, left, right):
        self._require(isinstance(self.relations, dict), ("bad_relations_facts", self.relations))
        seen = {}
        for pair, value in self.relations.items():
            key = self._pairs([pair], "relations")[0]
            number = self._finite(value, ("relations", pair))
            self._require(key not in seen or seen[key] == number, ("asymmetric_relation_fact", pair))
            seen[key] = number
        return seen.get(frozenset((left, right)), 0)

    def condition(self, node, tag):
        self._validate_ast([node], self._kind())
        k, op, value = node
        if k in ("AND", "OR", "NOT", "NOR", "hidden_trigger"):
            result = [self.condition(child, tag) for child in value]
            return {"AND": all(result), "OR": any(result), "NOT": not all(result),
                    "NOR": not any(result), "hidden_trigger": all(result)}[k]
        if k == "custom_description":
            body = next(v for key, _, v in value if key == "hidden_trigger")
            return self.conditions(body, tag)
        if k == "has_treaty_trade_privilege_with":
            target = self._country_ref(self._fields(value, {"TARGET"}, node)["TARGET"][1], tag)
            if target is None:
                return False
            def substitute(nodes):
                return [(key, cmp, substitute(val) if isinstance(val, list) else
                         "c:" + target.identity if val == "$TARGET$" else val)
                        for key, cmp, val in nodes]
            return self.conditions(substitute(NATIVE_TRADE_PRIVILEGE_AST), tag)
        if k == "country_has_isolationism_or_sakoku":
            return self.conditions(NATIVE_ISOLATION_AST, tag) == (value == "yes")
        if k in ("has_law", "has_law_or_variant"):
            laws = self.countries[tag].get("laws")
            self._require(isinstance(laws, (list, set, tuple)) and all(isinstance(x, str) for x in laws), ("bad_law_facts", tag))
            return value.removeprefix("law_type:") in laws
        if k in ("is_country_alive", "is_junior_in_customs_union"):
            field = "alive" if k == "is_country_alive" else "junior_in_customs_union"
            return self._bool(self.countries[tag].get(field), op, value, node)
        if k == "has_war_with":
            target = self._country_ref(value, tag)
            pairs = self._pairs(self.wars, "wars")
            return target is not None and frozenset((tag, target.identity)) in pairs
        if k == "is_at_war":
            actual = self.countries[tag].get("is_at_war", False)
            self._require(isinstance(actual, bool), ("bad_war_boolean", tag, actual))
            pairs = self._pairs(self.wars, "wars")
            actual = actual or any(tag in pair for pair in pairs)
            return self._bool(actual, op, value, node)
        if k == "has_diplomatic_pact":
            target = self._country_ref(self._fields(value, {"who", "type"}, node)["who"][1], tag)
            self._require(isinstance(self.pacts, (set, list, tuple)), ("bad_pact_facts", self.pacts))
            pairs = set()
            for pact in self.pacts:
                self._require(isinstance(pact, (tuple, list)) and len(pact) == 3 and pact[2] == "embargo",
                              ("malformed_embargo_fact", pact))
                self._pairs([pact[:2]], "pacts")
                pairs.add(tuple(pact))
            return target is not None and (tag, target.identity, "embargo") in pairs
        if ".relations:" in k:
            left, right = k.split(".relations:")
            a, b = self._country_ref(left, tag), self._country_ref(right, tag)
            return False if a is None or b is None else self._numeric(self._relation(a.identity, b.identity), op, value, node)
        if k == "market_imports_reliance":
            f = self._fields(value, {"target", "value"}, node)
            target = self._resolve(f["target"][1], tag)
            data = self._market(self.market_scope)["imports_reliance"]
            for mid, reliance in data.items():
                self._require(isinstance(mid, str) and mid in self.markets, ("unknown_reliance_market", mid))
                number = self._finite(reliance, ("imports_reliance", mid))
                self._require(0 <= number <= 1, ("reliance_outside_fraction", mid, number))
            return False if target is None else self._numeric(data.get(target.identity, 0), *f["value"], node)
        if k == "any_scope_treaty":
            matches = []
            for treaty in self._treaty_records():
                if tag not in treaty["participants"]:
                    continue
                with self._scope("treaty", "", treaty=treaty):
                    matches.append(self.conditions(value, tag))
            return any(matches)
        if k == "any_scope_article":
            matches = []
            for article in self.treaty_scope["articles"]:
                with self._scope("article", "", treaty=self.treaty_scope, article=article):
                    matches.append(self.conditions(value, tag))
            return any(matches)
        if k == "binds":
            target = self._country_ref(value, tag)
            return target is not None and target.identity in self.treaty_scope["participants"]
        if k == "has_type":
            return self.article_scope["type"] == value
        if k in ("source_country", "target_country"):
            target = self._country_ref(value, tag)
            return target is not None and self.article_scope[k] == target.identity
        if k == "owner":
            actual = self.state_scope["owner"] if self._kind() == "state" else self._market(self.market_scope)["owner"]
            self._require(isinstance(actual, str) and actual in self.countries, ("bad_state_owner", actual))
            obj = _Object("country", actual)
            return self._object_condition(obj, op, value, tag)
        if self._looks_object(k) and not k.startswith("ROOT.modifier:"):
            return self._object_condition(self._resolve(k, tag), op, value, tag)
        if k == "exists" and isinstance(value, str) and self._looks_object(value):
            self._require(op == "=", ("bad_exists_operator", node))
            return self._resolve(value, tag) is not None
        if k in ("any_scope_state", "any_scope_pop", "any_scope_building", "workplace"):
            return self._scoped_local_query(k, value, tag)
        if k in ("market_access", "occupancy"):
            data = self.state_scope if k == "market_access" else self.building_scope
            self._require(isinstance(data, dict) and k in data, ("missing_scoped_numeric", node))
            number = self._finite(data[k], node)
            self._require(0 <= number <= 1, ("bad_scoped_fraction", node, number))
            return self._numeric(number, op, value, node)
        if k in ("is_employed", "pop_has_primary_culture", "building_has_goods_shortage"):
            data, field = (self.pop_scope, "employed") if k == "is_employed" else (self.pop_scope, "primary") if k == "pop_has_primary_culture" else (self.building_scope, "shortage")
            return self._bool(data.get(field), op, value, node)
        if k == "pop_acceptance":
            self._require(re.fullmatch(r"acceptance_status_[1-5]", value) is not None, ("bad_acceptance_tier", node))
            tier = self._finite(self.pop_scope.get("acceptance"), node)
            self._require(tier in (1, 2, 3, 4, 5), ("acceptance_fact_not_tier", tier))
            return self.compare(tier, op, int(value[-1]))
        if k == "wealth":
            actual = self._finite(self.pop_scope.get("wealth"), node)
            target = self._finite(self.countries[self._root_tag].get(value[5:], 0), node) if value.startswith("ROOT.modifier:") else self._finite(value, node, text=True)
            return self.compare(actual, op, target)
        return super().condition(node, tag)

    def _object_condition(self, obj, op, value, tag):
        if obj is None:
            return False
        if isinstance(value, list):
            with self._scope(obj.kind, obj.identity):
                return self.conditions(value, obj.identity if obj.kind == "country" else tag)
        target = self._resolve(value, tag)
        if target is None:
            return False
        self._require(obj.kind == target.kind, ("object_type_mismatch", obj, target))
        return obj != target if op == "!=" else obj == target

    def _scoped_local_query(self, key, body, tag):
        if key == "any_scope_state":
            items = self.countries[tag].get("states", [])
            self._require(isinstance(items, list), ("bad_state_list", tag))
            matches = []
            for state in items:
                self._require(isinstance(state, dict) and isinstance(state.get("owner"), str)
                              and state["owner"] in self.countries, ("bad_state_fact", state))
                with self._scope("state", "", state=state):
                    matches.append(self.conditions(body, tag))
            return any(matches)
        if key == "any_scope_pop":
            items, kind = self.state_scope.get("pops", []), "pop"
        elif key == "any_scope_building":
            items, kind = self.state_scope.get("buildings", []), "building"
        else:
            workplace = self.pop_scope.get("workplace")
            if workplace is None:
                return False
            items, kind = [workplace], "building"
        self._require(isinstance(items, list), ("bad_scoped_fact_list", key))
        matches = []
        for item in items:
            self._require(isinstance(item, dict), ("bad_scoped_fact", key, item))
            with self._scope(kind, "", state=self.state_scope,
                             pop=item if kind == "pop" else self.pop_scope,
                             building=item if kind == "building" else None):
                matches.append(self.conditions(body, tag))
        return any(matches)
