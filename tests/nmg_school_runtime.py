"""Narrow current-fact composition for NMG school native-source scenarios.

LanPublicWorld supplies same-IG and literal employed-pop/workplace queries;
NmgPartnerWorld supplies actual NMG source, typed country/state references and
the Gregorian calendar. No business readiness, payment or observation is added.
"""
from datetime import date
import math

from lan_public_runtime import LanPublicWorld
from test_v03_nmg_partner_response import NmgPartnerWorld


class NmgSchoolWorld(LanPublicWorld, NmgPartnerWorld):
    def __init__(self, countries, *, start_date=date(1836, 1, 1)):
        if not isinstance(countries, dict) or not isinstance(countries.get("NMG"), dict):
            raise AssertionError("NMG school facts require an explicit NMG country")
        NmgPartnerWorld.__init__(self, countries, start_date=start_date)

    def condition(self, node, tag):
        if node[0] == "is_employed":
            if not isinstance(self.pop_scope, dict) or type(self.pop_scope.get("employed")) is not bool:
                raise AssertionError(("invalid_native_employment_fact", self.pop_scope))
        if node[0] == "occupancy":
            amount = self.building_scope.get("occupancy") if isinstance(self.building_scope, dict) else None
            if (type(amount) not in (int, float) or not math.isfinite(amount)
                    or amount < 0):
                raise AssertionError(("invalid_native_occupancy_fact", amount))
        if node[0] == "institution_investment_level":
            institutions = self.countries[tag].get("institutions")
            if not isinstance(institutions, dict):
                raise AssertionError(("missing_or_malformed_institution_facts", tag))
            # An explicitly empty institution dictionary represents no current
            # school investment. Business variables retain PartnerWorld's
            # strict undefined-variable behavior without a numeric default.
            amount = institutions.get("institution_schools", 0)
            if (type(amount) not in (int, float) or not math.isfinite(amount)
                    or amount < 0):
                raise AssertionError(("invalid_native_school_investment", amount))
        return super().condition(node, tag)
