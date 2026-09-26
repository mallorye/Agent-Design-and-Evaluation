#!/usr/bin/env python3
# =============================================================================
#  AI-GENERATED CODE
#  Written by Claude Code (Anthropic; model Claude Opus 5.5) from the schema
#  alone: db/init/01_schema.sql. No other document or dataset informed the
#  data design. Every name, address, email, and amount it produces is
#  synthetic.
# =============================================================================
"""
Generate a synthetic dataset for the synth_advancement schema.

Writes one CSV per table to db/init/data/, named for the table, with a header
row of the schema's column names in schema order. contribution.fiscal_year is
left out because Postgres computes it.

As of 2026-09-23 ("today"): nothing is dated after it except the end dates of
contact preferences that are scheduled to lapse. Contributions span FY2023
(from 2022-07-01) through FY2027 to date; fiscal years run Jul 1 to Jun 30.

Shape, sized as a scaled-down university advancement database:
  - 500 constituents: 460 people, 25 corporations, 15 foundations.
  - ~65 funds across ten divisions; a handful are inactive (closed). Each
    fund has an area of giving (areaofgiving: where the gift goes) and a
    designation type (desgtype: the limitation on the gift), always a
    plausible pair. 01009900 Gift Holding Account, the only fund whose area
    and type are Unassigned, holds recent gifts whose designation is not
    settled.
  - Goods-and-services money (priority-seating fees, event tickets and gala
    tables) goes to the two Gift-Non Deductible designations.
  - Giving is heavy-tailed: about half of constituents give nothing in the
    window (ticket and seating purchases aside), most donors give small annual gifts, and a few principal and
    major donors (multi-year pledges, securities) give most of the dollars.
  - A contribution is every row sharing a contribution number: one
    hard-credit row per designation it is split across (these sum to its
    total) and, for each soft-credited constituent, one row per designation
    for the same amount as the hard-credit row. Rows of a contribution share
    date, type, payment type, pledge status, and anonymity. Pledges and
    matching gifts carry the payment method recorded when they were made;
    bequest expectancies carry none.
  - Pledges are followed by pledge payments (pledge_number = the pledge's
    contribution number), matching gifts by matching-gift payments, and
    bequest expectancies by estate payments after the donor's death. Pledge
    rows, soft-credit rows included, carry the amount paid to date and the
    balance. Joint gifts, matching gifts, and family foundation grants carry
    soft-credit rows.
  - Households share an address, and spouses often share a last name.
    Parent, child, grandparent, and sibling pairs appear in
    constituent_relationship.
  - Every Alumnus/Alumna has one or more degree rows and nobody else has
    any. 'ND' (no degree) is rare and only for people who attended before
    1980. college is deliberately inconsistent from decade to decade;
    division is the clean field.
  - The campus is assumed to be in central Ohio, which only affects
    address clustering. Emails use reserved example.* domains.

Deterministic: a fixed seed and only the standard library, so re-running
produces byte-identical CSVs. Contact preferences, degrees, and degree
colleges draw from their own seeded streams, so changing how contributions
are generated does not reshuffle them.

    python3 db/generate_synthetic_data.py
"""

from __future__ import annotations

import calendar
import csv
import math
import random
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

SEED = 20260923
AS_OF = date(2026, 9, 23)
FIRST_FY, LAST_FY = 2023, 2027
FISCAL_YEARS = list(range(FIRST_FY, LAST_FY + 1))
WINDOW_START = date(FIRST_FY - 1, 7, 1)
OUT_DIR = Path(__file__).resolve().parent / "init" / "data"

AFFILIATION_TARGETS = {
    "Alumnus/Alumna": 252,
    "Parent": 60,
    "Friend": 76,
    "Faculty/Staff": 32,
    "Student": 28,
    "Trustee": 12,
}
N_CORPORATIONS = 25
N_MATCHING_COMPANIES = 8
N_FOUNDATIONS = 15
N_FAMILY_FOUNDATIONS = 6

rng = random.Random(SEED)


def reseed(table: str) -> None:
    """Draw the rest of a table's rows from its own stream."""
    global rng
    rng = random.Random(f"{SEED}/{table}")


# =============================================================================
# Reference data
# =============================================================================

FIRST_NAMES = """
Mary Patricia Jennifer Linda Elizabeth Barbara Susan Jessica Sarah Karen Lisa
Nancy Margaret Sandra Ashley Kimberly Emily Donna Michelle Carol Amanda Melissa
Deborah Stephanie Rebecca Sharon Laura Cynthia Kathleen Amy Angela Anna Brenda
Emma Olivia Sophia Isabella Abigail Madeline Hannah Grace Chloe Natalie Victoria
Katherine Catherine Rachel Megan Lauren Julia Claire Alexandra Samantha Allison
Caroline Maria Lucia Sofia Gabriela Camila Elena Ana Priya Ananya Aisha Fatima
Mei Lin Yuki Hana Adaeze Amara Zoe Leah Naomi Miriam Ruth Joan Diane Janet
Carolyn Theresa Gloria Denise Beverly Marilyn Judith Frances
James Robert John Michael David William Richard Joseph Thomas Christopher
Charles Daniel Matthew Anthony Mark Donald Steven Andrew Paul Joshua Kenneth
Kevin Brian Timothy Ronald George Jason Edward Jeffrey Ryan Jacob Nicholas Gary
Eric Jonathan Stephen Larry Justin Scott Brandon Benjamin Samuel Gregory
Alexander Patrick Frank Raymond Jack Dennis Jerry Tyler Aaron Nathan Henry
Zachary Peter Kyle Noah Ethan Lucas Owen Carlos Luis Diego Javier Miguel Mateo
Rahul Arjun Vikram Omar Hassan Wei Jun Hiroshi Kenji Duc Kwame Chinedu Tariq
Theodore Walter Harold Arthur Gerald Lawrence Frederick
""".split()

# Ordered roughly by US frequency; weights fall off with rank.
LAST_NAMES = """
Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez
Hernandez Lopez Gonzalez Wilson Anderson Thomas Taylor Moore Jackson Martin Lee
Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker Young
Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson Baker Hall
Rivera Campbell Mitchell Carter Roberts Gomez Phillips Evans Turner Diaz Parker
Cruz Edwards Collins Reyes Stewart Morris Morales Murphy Cook Rogers Gutierrez
Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard Ramos Kim Cox Ward
Richardson Watson Brooks Chavez Wood James Bennett Gray Mendoza Ruiz Hughes Price
Alvarez Castillo Sanders Patel Myers Long Ross Foster Jimenez Powell Jenkins
Perry Russell Sullivan Bell Coleman Butler Henderson Barnes Fisher Vasquez
Simmons Romero Jordan Patterson Alexander Hamilton Graham Reynolds Griffin
Wallace Moreno West Cole Hayes Bryant Herrera Gibson Ellis Tran Medina Aguilar
Stevens Murray Ford Castro Marshall Owens Harrison Fernandez McDonald Woods
Washington Kennedy Wells Vargas Henry Chen Freeman Webb Tucker Guzman Burns
Crawford Olson Simpson Porter Hunter Gordon Mendez Silva Shaw Snyder Mason Dixon
Hunt Hicks Holmes Palmer Wagner Black Robertson Boyd Rose Stone Salazar Fox
Warren Mills Meyer Rice Schmidt Garza Daniels Ferguson Nichols Stephens Soto
Weaver Ryan Gardner Payne Grant Dunn Spencer Hawkins Arnold Pierce Hansen Peters
Santos Hart Bradley Knight Elliott Cunningham Duncan Armstrong Hudson Carroll
Lane Riley Andrews Delgado Berry Perkins Hoffman Johnston Matthews Richards
Willis Carpenter Lawrence O'Brien O'Connor Wang Liu Zhang Singh Shah Yamamoto
Tanaka Park Choi Pham Okafor Mensah Haddad Khan Ali Cohen Goldberg Kowalski
Novak Larsen Lindqvist Rossi Byrne Fitzgerald
""".split()
LAST_NAME_WEIGHTS = [1 / (rank + 1) ** 0.55 for rank in range(len(LAST_NAMES))]

NICKNAMES = {
    "Robert": ["Bob", "Rob"], "William": ["Bill", "Will"], "Elizabeth": ["Liz", "Beth"],
    "Katherine": ["Kate", "Katie"], "Catherine": ["Cathy", "Cate"], "Michael": ["Mike"],
    "James": ["Jim", "Jamie"], "Jennifer": ["Jen"], "Christopher": ["Chris"],
    "Margaret": ["Maggie", "Peggy"], "Richard": ["Rick", "Rich"], "Thomas": ["Tom"],
    "Joseph": ["Joe"], "Daniel": ["Dan"], "Matthew": ["Matt"], "Anthony": ["Tony"],
    "Patricia": ["Pat", "Trish"], "Susan": ["Sue"], "Deborah": ["Deb"], "Rebecca": ["Becky"],
    "Alexander": ["Alex"], "Alexandra": ["Alex", "Lexi"], "Benjamin": ["Ben"],
    "Samuel": ["Sam"], "Samantha": ["Sam"], "Nicholas": ["Nick"], "Jonathan": ["Jon"],
    "Victoria": ["Tori"], "Theodore": ["Ted", "Theo"], "Edward": ["Ed", "Ned"],
    "Kimberly": ["Kim"], "Andrew": ["Andy", "Drew"], "Steven": ["Steve"],
    "Stephen": ["Steve"], "Timothy": ["Tim"], "Gregory": ["Greg"], "Jessica": ["Jess"],
    "Abigail": ["Abby"], "Charles": ["Charlie", "Chuck"], "David": ["Dave"],
    "Donald": ["Don"], "Kenneth": ["Ken"], "Ronald": ["Ron"], "Lawrence": ["Larry"],
    "Frederick": ["Fred"], "Zachary": ["Zach"], "Joshua": ["Josh"], "Madeline": ["Maddie"],
    "Isabella": ["Bella"], "Gerald": ["Jerry"], "Frances": ["Fran"], "Judith": ["Judy"],
    "Kathleen": ["Kathy"], "Cynthia": ["Cindy"], "Raymond": ["Ray"], "Walter": ["Walt"],
}

STREETS = """
Main Oak Maple Cedar Elm Pine Walnut Chestnut Washington Lincoln Jefferson
Madison Franklin High Park Lake Hill River Spring Church Mill Center Broad
Market Union Ridge Sunset Highland Meadow Forest Willow Birch Dogwood Magnolia
Summit Hickory Sycamore Laurel Prospect Woodland College Academy Garden Orchard
Valley Bridge Harbor Grove Fairway Brookside Kensington Wexford Stratford
Riverside Lakeview Hawthorne
""".split()
STREET_SUFFIXES = ["St", "Ave", "Rd", "Dr", "Ln", "Ct", "Blvd", "Way", "Pl", "Cir", "Pkwy"]

# (city, state, first ZIP, last ZIP, weight)
HOME_CITIES = [
    ("Columbus", "OH", 43201, 43235, 40), ("Dublin", "OH", 43016, 43017, 7),
    ("Westerville", "OH", 43081, 43082, 7), ("Worthington", "OH", 43085, 43085, 5),
    ("Upper Arlington", "OH", 43220, 43221, 6), ("Hilliard", "OH", 43026, 43026, 5),
    ("Gahanna", "OH", 43230, 43230, 4), ("Grove City", "OH", 43123, 43123, 4),
    ("Delaware", "OH", 43015, 43015, 4), ("Newark", "OH", 43055, 43055, 3),
]
OHIO_CITIES = [
    ("Cleveland", "OH", 44101, 44135, 8), ("Cincinnati", "OH", 45202, 45249, 8),
    ("Dayton", "OH", 45402, 45440, 5), ("Akron", "OH", 44301, 44333, 4),
    ("Toledo", "OH", 43604, 43623, 4), ("Canton", "OH", 44702, 44721, 2),
    ("Athens", "OH", 45701, 45701, 1),
]
NATIONAL_CITIES = [
    ("New York", "NY", 10001, 10040, 9), ("Brooklyn", "NY", 11201, 11238, 4),
    ("Chicago", "IL", 60601, 60661, 9), ("Evanston", "IL", 60201, 60208, 2),
    ("Los Angeles", "CA", 90001, 90068, 6), ("San Francisco", "CA", 94102, 94134, 4),
    ("San Jose", "CA", 95110, 95139, 2), ("San Diego", "CA", 92101, 92130, 3),
    ("Seattle", "WA", 98101, 98199, 4), ("Portland", "OR", 97201, 97239, 2),
    ("Denver", "CO", 80202, 80239, 3), ("Phoenix", "AZ", 85003, 85054, 3),
    ("Austin", "TX", 78701, 78759, 3), ("Dallas", "TX", 75201, 75254, 3),
    ("Houston", "TX", 77002, 77098, 3), ("Atlanta", "GA", 30303, 30350, 4),
    ("Charlotte", "NC", 28202, 28277, 3), ("Raleigh", "NC", 27601, 27617, 2),
    ("Washington", "DC", 20001, 20037, 4), ("Arlington", "VA", 22201, 22209, 2),
    ("Baltimore", "MD", 21201, 21231, 2), ("Philadelphia", "PA", 19102, 19154, 4),
    ("Pittsburgh", "PA", 15201, 15237, 4), ("Boston", "MA", 2108, 2136, 4),
    ("Cambridge", "MA", 2138, 2142, 1), ("Hartford", "CT", 6103, 6120, 1),
    ("Minneapolis", "MN", 55401, 55455, 2), ("Milwaukee", "WI", 53202, 53233, 1),
    ("Detroit", "MI", 48201, 48235, 2), ("Ann Arbor", "MI", 48103, 48109, 2),
    ("Indianapolis", "IN", 46201, 46268, 3), ("Louisville", "KY", 40202, 40299, 2),
    ("Lexington", "KY", 40502, 40517, 1), ("Nashville", "TN", 37201, 37221, 2),
    ("St. Louis", "MO", 63101, 63139, 2), ("Kansas City", "MO", 64105, 64157, 1),
    ("Miami", "FL", 33125, 33199, 2), ("Orlando", "FL", 32801, 32839, 2),
    ("Tampa", "FL", 33602, 33647, 2), ("Salt Lake City", "UT", 84101, 84121, 1),
    ("Richmond", "VA", 23219, 23237, 1), ("Buffalo", "NY", 14201, 14226, 1),
    ("Burlington", "VT", 5401, 5408, 1),
]
REGION_CITIES = {"home": HOME_CITIES, "ohio": OHIO_CITIES, "national": NATIONAL_CITIES}

# (city, state or None, country, postal pattern, street patterns); in patterns
# '#' is a digit and 'A' a letter; {n} in street patterns is a house number.
INTERNATIONAL = [
    ("Toronto", "ON", "Canada", "M#A #A#", ["{n} King St W", "{n} Bloor St E"]),
    ("Vancouver", "BC", "Canada", "V#A #A#", ["{n} W Georgia St", "{n} Robson St"]),
    ("London", None, "United Kingdom", "SW# #AA", ["{n} Baker Street", "{n} Marylebone Road"]),
    ("Munich", None, "Germany", "80###", ["Leopoldstrasse {n}", "Sendlinger Strasse {n}"]),
    ("Bengaluru", None, "India", "560###", ["{n} MG Road", "{n} Residency Road"]),
    ("Tokyo", None, "Japan", "1##-####", ["2-{n} Shibuya", "4-{n} Minato"]),
    ("Seoul", None, "South Korea", "0####", ["{n} Teheran-ro, Gangnam-gu"]),
    ("Mexico City", None, "Mexico", "0####", ["Av. Paseo de la Reforma {n}"]),
    ("Sydney", None, "Australia", "2###", ["{n} George Street", "{n} Pitt Street"]),
]

# Academic units alumni and faculty belong to (all are designation divisions).
SCHOOL_WEIGHTS = {
    "College of Arts and Sciences": 34, "School of Business": 22,
    "School of Engineering": 18, "School of Education": 8,
    "School of Nursing": 10, "School of Law": 8,
}
STAFF_UNITS = ["University Libraries", "Student Affairs", "Athletics"]

CORP_STEMS = """
Bluestem Ironbridge Summit-Ridge Lakeshore Keystone Riverbend Granite-Peak
Meridian Harborview Pinecrest Sterling-Oak Oakmont Silverleaf Redwood-Hollow
Clearwater Fairhaven Westgate Crescent-Bay Evergreen-Ridge Copperline Stonegate
Northfield Tallgrass Blue-Heron Foxglove Kestrel Larkspur Wrenfield Ashford
Quarry-Hill Driftwood
""".split()
CORP_INDUSTRIES = [
    "Analytics", "Health Partners", "Manufacturing", "Financial Group", "Engineering",
    "Logistics", "Software", "Insurance", "Energy", "Construction", "Community Bank",
    "Pharmaceuticals", "Consulting", "Media", "Foods", "Materials", "Robotics",
    "Medical Devices", "Capital Partners", "Architects",
]
CORP_SUFFIXES = ["Inc.", "LLC", "Corporation", "Co.", None, None]
FOUNDATION_NAMES = [
    "Tri-County Community Foundation", "Heartland Education Foundation",
    "Blue River Foundation", "Whitaker Charitable Trust",
    "Marlowe Foundation for Health Sciences", "Northgate Community Foundation",
    "Evans-Thornton Foundation", "Great Lakes Scholarship Fund",
    "Linden Arts Foundation", "Prairie Hill Foundation", "Halvorsen Foundation",
]

UAF, GREATEST, PRES_SCHOLARSHIP = "01000100", "01000200", "01000300"
PARENT_FUND, SENIOR_CLASS, EMERGENCY, FIRST_GEN = "01000400", "01000500", "01000600", "01000700"
TEACHING_AWARDS, STUDENT_LOANS, EVENTS = "01001000", "01001100", "01001200"
HOLDING, SEATING = "01009900", "70000300"

# The holding account's area and type; no other fund uses it.
UNASSIGNED = "Unassigned"

# Area of giving (designation.areaofgiving): where the gift goes, by
# category. No CHECK on the column; these nine and Unassigned are the only
# values used.
REV, UNR, RPS, SFA, FSS, RES, ATH, CAP_END, CAP_FAC = CORE_AREAS = (
    "Revenue", "Unrestricted Operations", "Restricted Program Support",
    "Student Financial Aid", "Faculty & Staff Support", "Research", "Athletics",
    "Capital - Endowment", "Capital - Facilities")
AREAS_OF_GIVING = CORE_AREAS + (UNASSIGNED,)

# Designation type (designation.desgtype): the limitation on the gift.
# Gift-Non Deductible marks goods-and-services money: tickets and seating.
ENDOW, CU, CR, PBE, NONDED, LOAN = CORE_TYPES = (
    "Endowment", "Current Unrestricted", "Current Restricted",
    "Property Buildings Equipment", "Gift-Non Deductible", "Loan Funds")
DESIGNATION_TYPES = CORE_TYPES + (UNASSIGNED,)

# The CRM assigns the two together, so every fund's pair is a plausible one.
PLAUSIBLE_TYPES = {
    REV: {NONDED}, UNR: {CU}, RPS: {CR, ENDOW}, SFA: {CR, ENDOW, LOAN},
    FSS: {CR, ENDOW}, RES: {CR, ENDOW}, ATH: {CR, NONDED}, CAP_END: {ENDOW},
    CAP_FAC: {PBE}, UNASSIGNED: {UNASSIGNED},
}

# Gifts dated on or after this go to the holding account now and then: the
# donor's intent is still being confirmed. Older holding-account gifts have
# been moved to their final designation, so none remain.
HOLDING_FROM = AS_OF - timedelta(days=120)


@dataclass(eq=False)
class Designation:
    designation_code: str
    designation_name: str
    division: str
    department: str | None
    kind: str       # annual | program | scholarship | capital | endowment | holding | benefit
    area: str                       # area of giving
    desgtype: str
    closed_on: date | None = None   # inactive funds took gifts through this date

    @property
    def is_active(self) -> bool:
        return self.closed_on is None

    def accepts(self, d: date) -> bool:
        return self.closed_on is None or d <= self.closed_on


D = Designation
DESIGNATIONS = [
    D(UAF, "University Annual Fund", "University-Wide", None, "annual", UNR, CU),
    D(GREATEST, "Fund for Greatest Needs", "University-Wide", None, "annual", UNR, CU),
    D(PRES_SCHOLARSHIP, "Presidential Scholarship Endowment", "University-Wide", None, "scholarship", CAP_END, ENDOW),
    D(PARENT_FUND, "Parent Fund", "University-Wide", None, "annual", UNR, CU),
    D(SENIOR_CLASS, "Senior Class Gift", "University-Wide", None, "annual", UNR, CU),
    D(EMERGENCY, "Student Emergency Fund", "University-Wide", None, "program", SFA, CR),
    D(FIRST_GEN, "First-Generation Student Scholarship", "University-Wide", None, "scholarship", SFA, CR),
    D("01000800", "Centennial Celebration Fund", "University-Wide", None, "program", RPS, CR, date(2023, 6, 30)),
    D("01000900", "Pandemic Student Relief Fund", "University-Wide", None, "program", SFA, CR, date(2022, 6, 30)),
    D(TEACHING_AWARDS, "Distinguished Teaching Awards Fund", "University-Wide", None, "program", FSS, CR),
    D(STUDENT_LOANS, "University Student Loan Fund", "University-Wide", None, "scholarship", SFA, LOAN),
    D(EVENTS, "Alumni and Donor Events", "University-Wide", None, "benefit", REV, NONDED),
    D(HOLDING, "Gift Holding Account", "University-Wide", None, "holding", UNASSIGNED, UNASSIGNED),
    D("10000100", "Arts and Sciences Annual Fund", "College of Arts and Sciences", None, "annual", UNR, CU),
    D("10000200", "Arts and Sciences Faculty Development Fund", "College of Arts and Sciences", None, "program", FSS, CR),
    D("10010100", "Biology Research Fund", "College of Arts and Sciences", "Biology", "program", RES, CR),
    D("10020100", "Chemistry Undergraduate Research Fund", "College of Arts and Sciences", "Chemistry", "program", RES, CR),
    D("10030100", "English Department Fund", "College of Arts and Sciences", "English", "program", RPS, CR),
    D("10040100", "History Department Fund", "College of Arts and Sciences", "History", "program", RPS, CR),
    D("10050100", "Mathematics Scholarship Fund", "College of Arts and Sciences", "Mathematics", "scholarship", SFA, CR),
    D("10060100", "Psychology Research Fund", "College of Arts and Sciences", "Psychology", "program", RES, CR),
    D("10070100", "Music Performance Fund", "College of Arts and Sciences", "Music", "program", RPS, CR),
    D("10080100", "Theatre Production Fund", "College of Arts and Sciences", "Theatre", "program", RPS, CR),
    D("10090100", "Journalism Program Fund", "College of Arts and Sciences", "Journalism", "program", RPS, CR, date(2025, 6, 30)),
    D("20000100", "Business School Annual Fund", "School of Business", None, "annual", UNR, CU),
    D("20000200", "Business Scholarship Endowment", "School of Business", None, "scholarship", CAP_END, ENDOW),
    D("20000300", "Business Faculty Fellowship Fund", "School of Business", None, "program", FSS, CR),
    D("20010100", "Accounting Excellence Fund", "School of Business", "Accounting", "program", RPS, CR),
    D("20020100", "Student Investment Fund", "School of Business", "Finance", "program", RPS, CR),
    D("20030100", "Entrepreneurship Center Fund", "School of Business", "Management", "capital", CAP_FAC, PBE),
    D("20040100", "Marketing Department Fund", "School of Business", "Marketing", "program", RPS, CR),
    D("30000100", "Engineering Annual Fund", "School of Engineering", None, "annual", UNR, CU),
    D("30000200", "Engineering Building Fund", "School of Engineering", None, "capital", CAP_FAC, PBE),
    D("30000300", "Engineering Research Fund", "School of Engineering", None, "program", RES, CR),
    D("30000400", "Engineering Endowed Professorship", "School of Engineering", None, "endowment", FSS, ENDOW),
    D("30010100", "Computer Science Scholarship Fund", "School of Engineering", "Computer Science", "scholarship", SFA, CR),
    D("30020100", "Mechanical Engineering Lab Fund", "School of Engineering", "Mechanical Engineering", "program", RPS, CR),
    D("30030100", "Electrical Engineering Fund", "School of Engineering", "Electrical and Computer Engineering", "program", RPS, CR),
    D("30040100", "Civil Engineering Fund", "School of Engineering", "Civil Engineering", "program", RPS, CR),
    D("40000100", "Education Annual Fund", "School of Education", None, "annual", UNR, CU),
    D("40010100", "Teacher Education Scholarship", "School of Education", "Teacher Education", "scholarship", SFA, CR),
    D("40020100", "Literacy Center Fund", "School of Education", "Literacy Studies", "program", RPS, CR),
    D("50000100", "Nursing Annual Fund", "School of Nursing", None, "annual", UNR, CU),
    D("50000200", "Nursing Simulation Lab Fund", "School of Nursing", None, "capital", CAP_FAC, PBE),
    D("50000300", "Nursing Scholarship Endowment", "School of Nursing", None, "scholarship", CAP_END, ENDOW),
    D("50000400", "Nursing Faculty Development Fund", "School of Nursing", None, "program", FSS, CR),
    D("50000500", "Nursing Student Loan Fund", "School of Nursing", None, "scholarship", SFA, LOAN),
    D("60000100", "Law School Annual Fund", "School of Law", None, "annual", UNR, CU),
    D("60000200", "Law Scholarship Endowment", "School of Law", None, "scholarship", CAP_END, ENDOW),
    D("60010100", "Law Clinic Fund", "School of Law", "Clinical Programs", "program", RPS, CR),
    D("60020100", "Law Library Fund", "School of Law", "Law Library", "program", RPS, CR),
    D("70000100", "Athletics Excellence Fund", "Athletics", None, "annual", ATH, CR),
    D("70000200", "Athletics Facilities Fund", "Athletics", None, "capital", CAP_FAC, PBE),
    D(SEATING, "Athletics Priority Seating", "Athletics", None, "benefit", ATH, NONDED),
    D("70010100", "Men's Basketball Fund", "Athletics", "Men's Basketball", "program", ATH, CR),
    D("70020100", "Women's Basketball Fund", "Athletics", "Women's Basketball", "program", ATH, CR),
    D("70030100", "Women's Soccer Fund", "Athletics", "Women's Soccer", "program", ATH, CR),
    D("70040100", "Baseball Fund", "Athletics", "Baseball", "program", ATH, CR),
    D("70050100", "Swimming and Diving Fund", "Athletics", "Swimming and Diving", "program", ATH, CR),
    D("70060100", "Tennis Fund", "Athletics", "Tennis", "program", ATH, CR, date(2024, 12, 31)),
    D("80000100", "University Libraries Fund", "University Libraries", None, "annual", UNR, CU),
    D("80000200", "Library Renovation Fund", "University Libraries", None, "capital", CAP_FAC, PBE, date(2024, 6, 30)),
    D("80010100", "Special Collections Fund", "University Libraries", "Special Collections", "program", RPS, CR),
    D("85000100", "Student Life Fund", "Student Affairs", None, "annual", UNR, CU),
    D("85010100", "Career Services Fund", "Student Affairs", "Career Services", "program", RPS, CR),
    D("85020100", "Counseling Center Fund", "Student Affairs", "Counseling Services", "program", RPS, CR),
]
FUND = {d.designation_code: d for d in DESIGNATIONS}
DIVISIONS = list(dict.fromkeys(d.division for d in DESIGNATIONS if d.division != "University-Wide"))


def division_funds(division: str, kinds: tuple[str, ...]) -> list[Designation]:
    return [d for d in DESIGNATIONS if d.division == division and d.kind in kinds]


def division_annual_fund(division: str) -> Designation:
    return division_funds(division, ("annual",))[0]


# =============================================================================
# Model objects
# =============================================================================

@dataclass(eq=False)
class Constituent:
    entity_type: str
    primary_affiliation: str
    first_name: str | None = None
    preferred_name: str | None = None
    last_name: str | None = None
    org_name: str | None = None
    email: str | None = None
    address_line1: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_postal_code: str | None = None
    address_country: str = "United States"
    constituent_status: str = "Active"
    is_deceased: bool = False
    deceased_date: date | None = None
    constituent_id: int = 0
    # Modelling attributes below are not written out.
    generation: str = "mid"                 # young | mid | senior
    school: str | None = None               # home division for alumni, faculty, students
    tier: str = "none"
    favorites: list = field(default_factory=list)
    spouse: Constituent | None = None
    joint_giver: bool = False               # spouse is soft-credited on this person's gifts
    employer: Constituent | None = None     # matching-gift company
    match_rate: float = 0.0                 # share of eligible gifts submitted for a match
    advisor: Constituent | None = None      # family foundation -> family member
    gives_until: date = AS_OF
    inactive_reason: str | None = None      # lost | requested


@dataclass(eq=False)
class Contribution:
    """Every row that shares one contribution number. One constituent gets
    the hard credit, split across one or more designations (lines); each
    soft-credited constituent gets a row per line for the same amount."""
    constituent: Constituent
    contribution_date: date
    contribution_type: str
    lines: list                             # [(Designation, Decimal)]; sums to the total
    pledge_status: str | None = None
    payment_type: str | None = None
    is_anonymous: bool = False
    recurring: bool = False                 # monthly sustainer / payroll gift
    soft: list = field(default_factory=list)    # soft-credited constituents
    pledge: Contribution | None = None      # Pledge Payment: the pledge it pays
    self_numbered: bool = False             # Pledge: pledge_number repeats its own number
    paid: dict = field(default_factory=dict)    # Pledge: designation code -> paid to date
    contribution_number: str = ""

    @property
    def total(self) -> Decimal:
        return sum((amount for _, amount in self.lines), Decimal("0.00"))


people: list[Constituent] = []
orgs: list[Constituent] = []
relationships: list[tuple[Constituent, str, Constituent, str]] = []
contributions: list[Contribution] = []
used_names: set[tuple[str, str]] = set()
used_emails: set[str] = set()


# =============================================================================
# Small helpers
# =============================================================================

def weighted(options: dict | list):
    """Pick a key from {option: weight} or an option from [(option, weight)]."""
    items = list(options.items()) if isinstance(options, dict) else options
    return rng.choices([o for o, _ in items], weights=[w for _, w in items])[0]


def slug(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def business_day(d: date) -> date:
    """Checks, wires, and stock transfers post on weekdays: roll back to Friday."""
    return d - timedelta(days=max(0, d.weekday() - 4))


def saturday(year: int, month: int, nth: int) -> date:
    """The nth Saturday of a month."""
    first = date(year, month, 1)
    return first + timedelta(days=(5 - first.weekday()) % 7, weeks=nth - 1)


def next_business_day(d: date) -> date:
    """The first weekday after d."""
    d += timedelta(days=1)
    return d + timedelta(days=7 - d.weekday() if d.weekday() >= 5 else 0)


# Relative gift volume by calendar month: calendar year-end, fiscal year-end,
# and the spring giving day stand out.
MONTH_WEIGHTS = {7: .6, 8: .6, 9: .7, 10: .8, 11: 1.1, 12: 2.6,
                 1: .7, 2: .7, 3: .9, 4: 1.1, 5: .9, 6: 1.6}


def seasonal_date(fy: int) -> date:
    """A date in fiscal year fy with typical giving seasonality. It can fall
    after AS_OF in the current fiscal year; callers drop those."""
    month = weighted(MONTH_WEIGHTS)
    year = fy - 1 if month >= 7 else fy
    last_day = calendar.monthrange(year, month)[1]
    if month == 12 and rng.random() < 0.45:
        day = rng.randint(26, 31)
    elif month == 6 and rng.random() < 0.35:
        day = rng.randint(22, 30)
    else:
        day = rng.randint(1, last_day)
    return date(year, month, day)


def active_years(retention: float, start_weights=(55, 7, 6, 6, 6)) -> list[int]:
    """Fiscal years a donor gives in: a first year, then each year they are
    retained, occasionally skip a year and come back, or lapse. Start
    weights roughly balance new donors against lapsed ones, so donor counts
    hold steady (or drift down slightly) from year to year."""
    fy = rng.choices(FISCAL_YEARS, weights=start_weights)[0]
    years = []
    while fy <= LAST_FY:
        years.append(fy)
        r = rng.random()
        if r < retention:
            fy += 1
        elif r < retention + (1 - retention) * 0.35:
            fy += 2
        else:
            break
    return years


# Donors give round amounts; amounts snap to the nearest rung on a log scale.
LADDER = [5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300,
          400, 500, 600, 750, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000, 6000,
          7500, 10000, 12500, 15000, 20000, 25000, 30000, 40000, 50000, 60000,
          75000, 100000, 125000, 150000, 200000, 250000, 300000, 400000, 500000,
          600000, 750000, 1000000, 1250000, 1500000, 2000000, 2500000, 3000000]


def snap(x: float) -> int:
    return min(LADDER, key=lambda v: abs(math.log(v) - math.log(x)))


def lognormal(median: float, sigma: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, rng.lognormvariate(math.log(median), sigma)))


def money(x) -> Decimal:
    return Decimal(str(round(float(x), 2))).quantize(Decimal("0.01"))


# =============================================================================
# Designations
# =============================================================================

def affinity(c: Constituent) -> list[tuple[Designation, float]]:
    """Where a constituent's everyday gifts tend to go, by affiliation."""
    aff = c.primary_affiliation
    athletics = [d for d in DESIGNATIONS if d.division == "Athletics" and d.kind == "program"]
    if aff == "Alumnus/Alumna":
        school_funds = [d for d in DESIGNATIONS if d.division == c.school
                        and d.kind not in ("annual", "benefit", "holding")]
        opts = [(FUND[UAF], 34), (FUND[GREATEST], 7), (division_annual_fund(c.school), 24),
                (FUND[EMERGENCY], 5), (FUND[FIRST_GEN], 4), (FUND["80000100"], 3),
                (FUND["01000800"], 4), (FUND["70000100"], 3), (FUND["70000200"], 2)]
        opts += [(d, 12 / len(school_funds)) for d in school_funds]
        opts += [(d, 4 / len(athletics)) for d in athletics]
    elif aff == "Parent":
        opts = [(FUND[PARENT_FUND], 45), (FUND[UAF], 18), (FUND[EMERGENCY], 8),
                (FUND["70000100"], 6), (FUND["85000100"], 6), (FUND["85010100"], 6),
                (division_annual_fund(c.school), 8), (FUND["01000800"], 3)]
    elif aff == "Friend":
        opts = [(FUND[UAF], 22), (FUND[GREATEST], 14), (FUND["70000100"], 6),
                (FUND["80000100"], 5), (FUND["80010100"], 4), (FUND["10070100"], 5),
                (FUND["10080100"], 4), (FUND[PRES_SCHOLARSHIP], 6), (FUND[FIRST_GEN], 6),
                (FUND[EMERGENCY], 10), (FUND["01000800"], 3), (FUND["80000200"], 3),
                (FUND["70000200"], 4), (FUND[STUDENT_LOANS], 2)]
        opts += [(d, 12 / len(athletics)) for d in athletics]
    elif aff == "Faculty/Staff":
        unit = [d for d in DESIGNATIONS if d.division == c.school
                and d.kind not in ("capital", "benefit", "holding")]
        opts = [(FUND[EMERGENCY], 20), (FUND[UAF], 12), (FUND["80000100"], 10),
                (FUND[FIRST_GEN], 13), (FUND["85020100"], 5), (FUND[TEACHING_AWARDS], 6)]
        opts += [(d, 40 / len(unit)) for d in unit]
    elif aff == "Student":
        opts = [(FUND[SENIOR_CLASS], 70), (FUND[EMERGENCY], 18), (FUND["85000100"], 12)]
    elif aff == "Trustee":
        opts = [(FUND[GREATEST], 30), (FUND[PRES_SCHOLARSHIP], 25), (FUND[UAF], 20),
                (division_annual_fund(c.school), 15), (FUND[FIRST_GEN], 10),
                (FUND[TEACHING_AWARDS], 5)]
    elif aff == "Corporation":
        opts = [(FUND["70000100"], 15), (FUND["85010100"], 20), (FUND["20000100"], 15),
                (FUND["30000100"], 15), (FUND["20030100"], 10), (FUND["30010100"], 8),
                (FUND["50000100"], 7), (FUND["20020100"], 5), (FUND[UAF], 5),
                (FUND["30000300"], 8)]
    else:  # Foundation
        opts = [(FUND[FIRST_GEN], 15), (FUND[PRES_SCHOLARSHIP], 10), (FUND["50000300"], 10),
                (FUND[EMERGENCY], 10), (FUND["80010100"], 8), (FUND["40020100"], 10),
                (FUND["40010100"], 8), (FUND["60010100"], 8), (FUND["85020100"], 6),
                (FUND["10010100"], 5), (FUND["85010100"], 5), (FUND["10070100"], 5),
                (FUND["30000300"], 6), (FUND["50000400"], 4), (FUND[STUDENT_LOANS], 5)]
    return opts


def major_pool(c: Constituent) -> list[tuple[Designation, float]]:
    """Funds that receive pledges, bequests, and other large commitments."""
    opts = [(FUND[PRES_SCHOLARSHIP], 15), (FUND[FIRST_GEN], 10), (FUND["70000200"], 12),
            (FUND[GREATEST], 8), (FUND["80010100"], 5)]
    if c.school in SCHOOL_WEIGHTS and c.primary_affiliation in (
            "Alumnus/Alumna", "Trustee", "Faculty/Staff", "Parent"):
        own = [d for d in DESIGNATIONS if d.division == c.school and d.is_active
               and d.kind in ("scholarship", "capital", "endowment")]
        own += [d for d in DESIGNATIONS if d.division == c.school and d.is_active
                and d.department and d.kind == "program"][:1]
        opts += [(d, 50 / len(own)) for d in own]
    else:
        opts += [(FUND["30000200"], 10), (FUND["50000200"], 10), (FUND[EMERGENCY], 7),
                 (FUND["20030100"], 8), (FUND["50000300"], 6)]
    return opts


def draw_favorites(c: Constituent) -> None:
    opts = [(d, w) for d, w in affinity(c) if d.is_active]
    for _ in range(weighted({1: 45, 2: 40, 3: 15})):
        choice = weighted(opts)
        if choice not in c.favorites:
            c.favorites.append(choice)


def pick_fund(c: Constituent, d: date) -> Designation:
    """Donors mostly stick to a few favorite funds, sometimes try another."""
    if c.favorites and rng.random() < 0.78:
        return rng.choice(c.favorites)
    return weighted([(f, w) for f, w in affinity(c) if f.accepts(d)])


# =============================================================================
# Constituents and relationships
# =============================================================================

def draw_last() -> str:
    return rng.choices(LAST_NAMES, weights=LAST_NAME_WEIGHTS)[0]


def draw_school() -> str:
    return weighted(SCHOOL_WEIGHTS)


def fill_pattern(pattern: str) -> str:
    out = []
    for ch in pattern:
        if ch == "#":
            out.append(str(rng.randint(0, 9)))
        elif ch == "A":
            out.append(rng.choice("ABCEGHJKLMNPRSTVXY"))
        else:
            out.append(ch)
    return "".join(out)


def make_address(region: str, apartments: bool = True) -> tuple:
    """(line1, city, state, postal code, country). A few households have an
    incomplete or missing address, as the schema anticipates."""
    if region == "intl":
        city, state, country, postal, streets = rng.choice(INTERNATIONAL)
        line1 = rng.choice(streets).format(n=rng.randint(1, 250))
        address = [line1, city, state, fill_pattern(postal), country]
    else:
        city, state, zip_lo, zip_hi, _ = weighted([(c, c[4]) for c in REGION_CITIES[region]])
        line1 = f"{rng.randint(10, 9899)} {rng.choice(STREETS)} {rng.choice(STREET_SUFFIXES)}"
        if apartments and rng.random() < 0.12:
            line1 += f" Apt {rng.randint(1, 30)}{rng.choice('ABCD')}"
        address = [line1, city, state, f"{rng.randint(zip_lo, zip_hi):05d}", "United States"]
    r = rng.random()
    if r < 0.04:
        address = [None, None, None, None, "United States"]
    elif r < 0.06:
        address[0] = None
    return tuple(address)


def region_for(affiliation: str) -> str:
    return weighted({
        "Alumnus/Alumna": {"home": 30, "ohio": 15, "national": 52, "intl": 3},
        "Parent": {"home": 25, "ohio": 15, "national": 57, "intl": 3},
        "Friend": {"home": 50, "ohio": 15, "national": 33, "intl": 2},
        "Faculty/Staff": {"home": 92, "ohio": 6, "national": 2},
        "Student": {"home": 80, "ohio": 10, "national": 10},
        "Trustee": {"home": 40, "ohio": 10, "national": 50},
    }[affiliation])


def set_address(c: Constituent, address: tuple) -> None:
    (c.address_line1, c.address_city, c.address_state,
     c.address_postal_code, c.address_country) = address


def person_email(p: Constituent) -> str | None:
    f, last = slug(p.first_name), slug(p.last_name)
    if p.primary_affiliation == "Student":
        local, domain = f"{f[0]}{last}{rng.randint(1, 99)}", "students.university.example.org"
    elif p.primary_affiliation == "Faculty/Staff" and rng.random() < 0.7:
        local, domain = f"{f}.{last}", "university.example.org"
    else:
        if rng.random() < (0.22 if p.generation == "senior" else 0.08):
            return None
        local = rng.choice([f"{f}.{last}", f"{f[0]}{last}", f"{f}{last}{rng.randint(1, 99)}",
                            f"{f}_{last}", f"{last}.{f}", f"{f}{last[0]}{rng.randint(10, 99)}"])
        domain = rng.choice(["example.com", "example.net", "example.org",
                             "mail.example.com", "inbox.example.net"])
    email, n = f"{local}@{domain}", 2
    while email in used_emails:
        email, n = f"{local}{n}@{domain}", n + 1
    used_emails.add(email)
    return email


def new_person(affiliation: str, last: str, generation: str, address: tuple,
               school: str | None = None) -> Constituent:
    # Full names are kept unique so no two unrelated records collide by accident.
    first = rng.choice(FIRST_NAMES)
    while (first, last) in used_names:
        first = rng.choice(FIRST_NAMES)
    used_names.add((first, last))
    preferred = None
    if first in NICKNAMES and rng.random() < 0.3:
        preferred = rng.choice(NICKNAMES[first])
    if school is None:
        school = rng.choice(STAFF_UNITS + list(SCHOOL_WEIGHTS)) if affiliation == "Faculty/Staff" \
            else draw_school()
    p = Constituent("P", affiliation, first_name=first, preferred_name=preferred,
                    last_name=last, generation=generation, school=school)
    p.email = person_email(p)
    set_address(p, address)
    people.append(p)
    return p


def relate(a: Constituent, a_role: str, b: Constituent, b_role: str) -> None:
    relationships.append((a, a_role, b, b_role))
    if a_role in ("Spouse", "Life Partner"):
        a.spouse, b.spouse = b, a


def build_people() -> None:
    # Parent households: one or two parents and one or two children who are
    # current students or recent alumni.
    children = []
    for _ in range(30):
        last = draw_last()
        home = make_address(region_for("Parent"))
        school = draw_school()
        first_aff = weighted({"Parent": 76, "Alumnus/Alumna": 24})
        parents = [new_person(first_aff, last, "mid", home)]
        if rng.random() < 0.72:
            partner_last = last if rng.random() < 0.85 else draw_last()
            partner = new_person("Parent", partner_last, "mid", home, school=school)
            relate(parents[0], "Spouse", partner, "Spouse")
            parents.append(partner)
        if first_aff == "Parent":
            parents[0].school = school
        kids = []
        for i in range(1 if rng.random() < 0.78 else 2):
            aff = weighted({"Student": 55, "Alumnus/Alumna": 45})
            if aff == "Student":
                addr = home if rng.random() < 0.55 else make_address("home")
            else:
                addr = make_address(weighted({"home": 30, "ohio": 20, "national": 50}))
            kid = new_person(aff, last, "young", addr, school=school if i == 0 else draw_school())
            for p in parents:
                relate(p, "Parent", kid, "Child")
            kids.append(kid)
        if len(kids) == 2:
            relate(kids[0], "Sibling", kids[1], "Sibling")
        children += kids

    # Couples with no children in the database.
    couple_types = [(("Alumnus/Alumna", "Alumnus/Alumna"), 30), (("Alumnus/Alumna", "Friend"), 33),
                    (("Friend", "Friend"), 12), (("Faculty/Staff", "Friend"), 8),
                    (("Faculty/Staff", "Alumnus/Alumna"), 6), (("Trustee", "Friend"), 11)]
    for _ in range(40):
        a_aff, b_aff = weighted(couple_types)
        role = "Life Partner" if rng.random() < 0.12 else "Spouse"
        generation = "senior" if rng.random() < 0.45 else "mid"
        home = make_address(region_for(a_aff))
        last = draw_last()
        a = new_person(a_aff, last, generation, home)
        b_last = last if role == "Spouse" and rng.random() < 0.8 else draw_last()
        b = new_person(b_aff, b_last, generation, home)
        relate(a, role, b, role)

    # Grandparents of students and young alumni already in the database.
    for kid in rng.sample(children, 4):
        last = kid.last_name if rng.random() < 0.6 else draw_last()
        aff = weighted({"Friend": 60, "Alumnus/Alumna": 40})
        gp = new_person(aff, last, "senior", make_address(region_for(aff)))
        relate(gp, "Grandparent", kid, "Grandchild")

    # Adult siblings who are both alumni.
    for _ in range(5):
        last = draw_last()
        a = new_person("Alumnus/Alumna", last, "mid", make_address(region_for("Alumnus/Alumna")))
        b = new_person("Alumnus/Alumna", last, "mid", make_address(region_for("Alumnus/Alumna")))
        relate(a, "Sibling", b, "Sibling")

    # Everyone else is a single-person household.
    generation_weights = {
        "Alumnus/Alumna": {"young": 25, "mid": 45, "senior": 30},
        "Parent": {"mid": 100}, "Friend": {"mid": 50, "senior": 50},
        "Faculty/Staff": {"mid": 70, "senior": 30}, "Student": {"young": 100},
        "Trustee": {"mid": 40, "senior": 60},
    }
    counts = {aff: sum(p.primary_affiliation == aff for p in people) for aff in AFFILIATION_TARGETS}
    for aff, target in AFFILIATION_TARGETS.items():
        for _ in range(max(0, target - counts[aff])):
            new_person(aff, draw_last(), weighted(generation_weights[aff]),
                       make_address(region_for(aff)))
    assert len(people) == sum(AFFILIATION_TARGETS.values()), "households overshot a target"


def build_orgs() -> None:
    for stem in rng.sample(CORP_STEMS, N_CORPORATIONS):
        name = f"{stem.replace('-', ' ')} {rng.choice(CORP_INDUSTRIES)}"
        suffix = rng.choice(CORP_SUFFIXES)
        org = Constituent("C", "Corporation", org_name=f"{name} {suffix}" if suffix else name)
        if rng.random() < 0.55:
            org.email = f"{rng.choice(['giving', 'community', 'info', 'partnerships'])}@{slug(stem)}.example.com"
        orgs.append(org)
    names = rng.sample(FOUNDATION_NAMES, N_FOUNDATIONS - N_FAMILY_FOUNDATIONS)
    names += [None] * N_FAMILY_FOUNDATIONS          # named after their family later
    for name in names:
        org = Constituent("C", "Foundation", org_name=name)
        if name and rng.random() < 0.6:
            org.email = f"grants@{slug(name)[:18]}.example.org"
        orgs.append(org)
    for org in orgs:
        region = weighted({"home": 45, "ohio": 20, "national": 35})
        line1, city, state, postal, country = make_address(region, apartments=False)
        if line1 and rng.random() < 0.5:
            line1 += f" Suite {rng.randint(1, 9)}00"
        set_address(org, (line1, city, state, postal, country))


def assign_life_events(everyone: list[Constituent]) -> None:
    """Deceased and inactive flags."""
    # Deaths: senior people, never both members of a couple.
    candidates = [p for p in people if p.generation == "senior" and p.primary_affiliation != "Trustee"]
    rng.shuffle(candidates)
    deceased = []
    for p in candidates:
        if p.spouse in deceased:
            continue
        deceased.append(p)
        if len(deceased) == 18:
            break
    for i, p in enumerate(deceased):
        p.is_deceased = True
        p.constituent_status = "Inactive"
        if i < 5:           # died before the contribution window
            p.deceased_date = random_date(date(2016, 1, 1), date(2022, 6, 15))
        elif i < 15:        # died during the window
            p.deceased_date = random_date(date(2022, 8, 1), date(2026, 8, 31))
        # the remaining three: death reported, date unknown
        p.gives_until = p.deceased_date or WINDOW_START - timedelta(days=1)
        if p.deceased_date and p.deceased_date < WINDOW_START:
            p.gives_until = WINDOW_START - timedelta(days=1)

    # Inactive: people who fell out of contact ("lost") or asked to be
    # removed ("requested"). Only people with no relatives on file, so no
    # household shares an address with a lost record.
    related = {id(x) for rel in relationships for x in (rel[0], rel[2])}
    candidates = [p for p in people if not p.is_deceased and id(p) not in related
                  and p.primary_affiliation not in ("Trustee", "Student")]
    for i, p in enumerate(rng.sample(candidates, 22)):
        p.constituent_status = "Inactive"
        p.inactive_reason = "lost" if i % 2 == 0 else "requested"
        p.gives_until = random_date(date(2022, 10, 1), date(2024, 6, 30))
        if p.inactive_reason == "lost":
            p.email = None
            set_address(p, (None, None, None, None, "United States"))
    for org in rng.sample([o for o in orgs if o.primary_affiliation == "Corporation"], 2):
        org.constituent_status = "Inactive"             # merged or closed
        org.gives_until = random_date(date(2023, 1, 1), date(2024, 12, 31))


# =============================================================================
# Giving
# =============================================================================

TIERS = ("none", "occasional", "annual", "mid", "major", "principal")
TIER_WEIGHTS = {
    "Alumnus/Alumna": (48, 18, 26, 6, 1.6, 0.4),
    "Parent": (42, 19, 27, 9, 2.5, 0.5),
    "Friend": (55, 18, 19, 6, 1.6, 0.4),
    "Faculty/Staff": (38, 15, 41, 6, 0, 0),
    "Student": (68, 26, 6, 0, 0, 0),
    "Trustee": (0, 0, 8, 30, 45, 17),
    "Corporation": (30, 30, 28, 0, 12, 0),
    "Foundation": (20, 25, 30, 0, 25, 0),
}


def quota(weights: tuple, n: int) -> list[str]:
    """Exactly n tiers in proportion to weights (largest remainder), shuffled."""
    total = sum(weights)
    exact = [w * n / total for w in weights]
    counts = [int(x) for x in exact]
    by_remainder = sorted(range(len(weights)), key=lambda i: (counts[i] - exact[i], i))
    for i in by_remainder[: n - sum(counts)]:
        counts[i] += 1
    tiers = [t for t, k in zip(TIERS, counts) for _ in range(k)]
    rng.shuffle(tiers)
    return tiers


def assign_tiers(everyone: list[Constituent]) -> None:
    groups: dict[str, list[Constituent]] = {}
    for c in everyone:
        if c.gives_until < WINDOW_START or (c.is_deceased and c.deceased_date is None):
            continue
        if c.entity_type == "C" and c.org_name is None:
            continue                        # family foundation: gives via its family
        if c.constituent_status == "Inactive" and not c.is_deceased:
            c.tier = "occasional" if rng.random() < 0.35 else "none"
            continue
        groups.setdefault(c.primary_affiliation, []).append(c)
    for aff, members in groups.items():
        for c, tier in zip(members, quota(TIER_WEIGHTS[aff], len(members))):
            c.tier = tier

    # About 60% of couples give jointly: one partner gives, the other is
    # soft-credited and does not give separately.
    rank = {t: i for i, t in enumerate(TIERS)}
    for a, role, b, _ in relationships:
        if role in ("Spouse", "Life Partner") and rng.random() < 0.6:
            if b.gives_until < WINDOW_START or a.gives_until < WINDOW_START:
                continue
            primary, secondary = (a, b) if rank[a.tier] >= rank[b.tier] else (b, a)
            if primary.tier != "none":
                primary.joint_giver = True
                secondary.tier = "none"

    for c in everyone:
        draw_favorites(c)


def payment_type(c: Constituent, amount: float) -> str:
    if c.entity_type == "C":
        return weighted({"Check": 55, "ACH": 45})
    if amount < 250:
        return weighted({"Credit Card": 58, "Check": 27, "ACH": 8, "Cash": 7})
    if amount < 5000:
        return weighted({"Credit Card": 36, "Check": 43, "ACH": 16, "Securities": 5})
    return weighted({"Check": 38, "ACH": 30, "Securities": 28, "Credit Card": 4})


def add(c, lines, d, ctype, *, ptype=None, status=None, anon=False, recurring=False,
        pledge=None) -> Contribution:
    """Record a contribution; lines are the (fund, amount) hard-credit portions."""
    assert WINDOW_START <= d <= AS_OF, (c.constituent_id, d)
    row = Contribution(c, d, ctype, [(fund, money(amount)) for fund, amount in lines],
                       pledge_status=status, payment_type=ptype, is_anonymous=anon,
                       recurring=recurring, pledge=pledge)
    contributions.append(row)
    return row


# Ways a contribution divides between two or three designations.
SPLITS = {2: [(1, 1), (3, 2), (2, 1), (3, 1), (4, 1)], 3: [(1, 1, 1), (2, 1, 1), (2, 2, 1)]}


def portions(total: Decimal, weights: tuple) -> list[Decimal]:
    """Divide total in proportion to weights. A whole-dollar total divides
    into round portions; the last portion takes the remainder."""
    step = Decimal("0.01")
    if total == total.to_integral_value():
        step = next((Decimal(s) for s in (1000, 100, 25, 5) if total >= 20 * s), Decimal(1))
    parts = [(total * w / sum(weights) / step).quantize(Decimal(1)) * step for w in weights[:-1]]
    parts.append(total - sum(parts))
    assert all(p > 0 for p in parts), (total, weights)
    return [money(p) for p in parts]


def divide(funds: list, total: Decimal) -> list:
    """(fund, amount) lines for a contribution of total across funds."""
    shares = rng.choice(SPLITS[len(funds)]) if len(funds) > 1 else (1,)
    return list(zip(funds, portions(total, shares)))


def split_rate(amount: float) -> float:
    """Chance an outright gift is split across designations."""
    return 0 if amount < 100 else 0.05 if amount < 1000 else 0.12 if amount < 10000 else 0.2


def split_lines(c: Constituent, d: date, first: Designation, total: Decimal) -> list:
    """Split a gift between its fund and one or two more of the donor's funds."""
    funds = [first]
    want = 3 if total >= 300 and rng.random() < 0.2 else 2
    for _ in range(12):
        f = pick_fund(c, d)
        if f not in funds and f.accepts(d):
            funds.append(f)
        if len(funds) == want:
            break
    return divide(funds, total)


def gift(c, d, amount, fund=None, ptype=None, anon=None, recurring=False) -> Contribution | None:
    """An outright gift, or None if the donor could not have given on d. When
    no fund is named, the gift goes to one of the donor's funds, now and then
    split across two or three; a few recent ones wait in the holding account."""
    if d > AS_OF or d > c.gives_until or d < WINDOW_START:
        return None
    chosen = fund or pick_fund(c, d)
    if not chosen.accepts(d):
        return None
    ptype = ptype or payment_type(c, amount)
    if ptype == "Securities":
        amount = float(amount) * rng.uniform(0.985, 1.02)     # market value on transfer
    if ptype in ("Check", "ACH", "Securities", "Gift-in-kind"):
        d = max(business_day(d), WINDOW_START)
    if anon is None:
        anon = rng.random() < (0.08 if c.tier in ("major", "principal") else 0.012)
    lines = [(chosen, amount)]
    if fund is None and not recurring:
        if d >= HOLDING_FROM and rng.random() < (0.1 if float(amount) < 1000 else 0.3):
            lines = [(FUND[HOLDING], amount)]
        elif rng.random() < split_rate(float(amount)):
            lines = split_lines(c, d, chosen, money(amount))
    return add(c, lines, d, "Gift", ptype=ptype, anon=anon, recurring=recurring)


def pledge(c, funds, d, total, n, every_months, *, ptypes, anon=False,
           outcome_weights=(90, 5, 5), first_gap=(0, 45)) -> None:
    """A pledge to one or more funds and the payments made on it by AS_OF.
    Each payment divides across the funds in proportion, so a fund's
    installments add up to its portion. The pledge records the method the
    donor chose when committing; most payments use it, some another. Paid
    pledges are paid in full; written-off and canceled pledges stopped short."""
    total = money(total)
    lines = divide(funds, total)
    schedule = []                           # per line, its n installments
    for _, amount in lines:
        installment = (amount / n).quantize(Decimal("0.01"), ROUND_DOWN)
        schedule.append([installment] * (n - 1) + [amount - installment * (n - 1)])
    first_due = d + timedelta(days=rng.randint(*first_gap))
    dues = [add_months(first_due, i * every_months) for i in range(n)]
    outcome = weighted(dict(zip(("normal", "write_off", "cancel"), outcome_weights)))
    stop = n if outcome == "normal" else rng.randint(0, n - 1)
    usual_ptype = weighted(ptypes)

    payments, last = [], d
    for i in range(stop):
        paid_on = business_day(dues[i] + timedelta(days=rng.randint(-10, 20)))
        if paid_on <= last:                 # after the pledge and the previous payment
            paid_on = next_business_day(last)
        if paid_on > AS_OF or paid_on > c.gives_until:
            break
        ptype = usual_ptype if rng.random() < 0.85 else weighted(ptypes)
        payments.append((paid_on, ptype))
        last = paid_on

    if len(payments) == n:
        status = "Paid"
    elif outcome != "normal" and len(payments) == stop and dues[stop] + timedelta(days=120) <= AS_OF:
        status = "Written Off" if outcome == "write_off" else "Canceled"
    elif c.gives_until < AS_OF and c.gives_until + timedelta(days=180) <= AS_OF:
        status = "Written Off"          # donor died with installments outstanding
    else:
        status = "Open"

    p = add(c, lines, d, "Pledge", ptype=usual_ptype, status=status, anon=anon)
    p.self_numbered = rng.random() < 0.5
    p.paid = {fund.designation_code: sum(schedule[j][:len(payments)], Decimal("0.00"))
              for j, (fund, _) in enumerate(lines)}
    for i, (paid_on, ptype) in enumerate(payments):
        add(c, [(fund, schedule[j][i]) for j, (fund, _) in enumerate(lines)], paid_on,
            "Pledge Payment", ptype=ptype, anon=anon, pledge=p)


def pledge_funds(pool: list, split: float, exclude=()) -> list[Designation]:
    """The fund a pledge supports, now and then two."""
    options = [(f, w) for f, w in pool if f not in exclude]
    funds = [weighted(options)]
    if rng.random() < split:
        rest = [(f, w) for f, w in options if f not in funds]
        if rest:
            funds.append(weighted(rest))
    return funds


def pledge_date(c: Constituent, fy_weights=(25, 25, 25, 20, 5)) -> date | None:
    for _ in range(20):
        d = seasonal_date(rng.choices(FISCAL_YEARS, weights=fy_weights)[0])
        if WINDOW_START <= d <= min(AS_OF, c.gives_until) - timedelta(days=30):
            return d
    return None


MAJOR_PTYPES = {"Check": 40, "ACH": 35, "Securities": 25}
MID_PTYPES = {"Check": 45, "ACH": 25, "Credit Card": 20, "Securities": 10}
SMALL_PTYPES = {"Credit Card": 65, "Check": 35}
MONTHLY_PTYPES = {"Credit Card": 60, "ACH": 40}
ORG_PTYPES = {"Check": 55, "ACH": 45}


def monthly_gifts(c: Constituent, fund: Designation, amount: float, ptype: str,
                  months: int) -> None:
    """A recurring monthly gift. Schedules start uniformly over the years
    before and during the window (so the number running at any time holds
    steady) and are redrawn until they overlap the window; only
    installments inside the window are recorded."""
    while True:
        start = random_date(add_months(WINDOW_START, -months), AS_OF - timedelta(days=60))
        if add_months(start, months) > WINDOW_START:
            break
    start = start.replace(day=min(start.day, 28))
    for i in range(months):
        if i > 0 and i % 12 == 0 and rng.random() < 0.2:
            amount = snap(amount * 1.5)                 # annual upgrade
        d = add_months(start, i)
        if d < WINDOW_START:
            continue
        if gift(c, d, amount, fund=fund, ptype=ptype, anon=False, recurring=True) is None:
            break


def in_year_gifts(c: Constituent, fy: int, year_total: float, count_weights: dict) -> None:
    k = weighted(count_weights)
    for _ in range(k):
        gift(c, seasonal_date(fy), snap(max(5, year_total / k * rng.uniform(0.8, 1.25))))


def person_giving(c: Constituent) -> None:
    tier = c.tier
    student = c.primary_affiliation == "Student"
    if tier == "none":
        return

    if tier == "occasional":
        fy_weights = (0, 0, 30, 45, 25) if student else (26, 24, 22, 20, 8)
        for _ in range(weighted({1: 70, 2: 30})):
            for _ in range(10):
                d = seasonal_date(rng.choices(FISCAL_YEARS, weights=fy_weights)[0])
                if d <= min(AS_OF, c.gives_until):
                    median = 20 if student else 50
                    gift(c, d, snap(lognormal(median, 0.8, 5, 500)))
                    break
        return

    if tier == "annual":
        r = rng.random()
        if c.primary_affiliation == "Faculty/Staff" and r < 0.7:      # payroll deduction
            monthly_gifts(c, c.favorites[0], snap(lognormal(25, 0.6, 10, 100)), "ACH",
                          rng.randint(24, 96))
            return
        if not student and r < 0.5:                                    # monthly sustainer
            monthly_gifts(c, c.favorites[0], snap(lognormal(25, 0.5, 5, 100)),
                          weighted({"Credit Card": 80, "ACH": 20}), rng.randint(12, 96))
            return
        base = snap(lognormal(20 if student else 100, 0.9, 10, 2500))
        start_weights = (0, 0, 30, 45, 25) if student else (55, 7, 6, 6, 6)
        for fy in active_years(0.8, start_weights):
            in_year_gifts(c, fy, base * rng.choice([0.5, 1, 1, 1, 1, 1, 1.5, 2]),
                          {1: 50, 2: 30, 3: 14, 4: 6})
        if not student and rng.random() < 0.15:                        # phonathon pledge
            d = pledge_date(c)
            if d:
                fund = FUND[UAF]
                if rng.random() < 0.4 and c.school in SCHOOL_WEIGHTS:
                    fund = division_annual_fund(c.school)
                pledge(c, [fund], d, snap(lognormal(150, 0.6, 50, 1000)), rng.choice([1, 1, 2, 3]),
                       1, ptypes=SMALL_PTYPES, outcome_weights=(70, 22, 8), first_gap=(7, 40))
        return

    # mid, major, principal
    if tier == "mid":
        base, sigma, lo, hi, retention = 2500, 0.6, 1000, 15000, 0.86
        start_weights = (55, 5, 5, 5, 5)
    elif tier == "major":
        base, sigma, lo, hi, retention = 7500, 0.6, 2500, 50000, 0.9
        start_weights = (70, 5, 5, 5, 5)
    else:
        base, sigma, lo, hi, retention = 25000, 0.6, 10000, 150000, 0.92
        start_weights = (80, 4, 4, 4, 4)
    if tier == "mid" and rng.random() < 0.3:                           # leadership monthly giver
        monthly_gifts(c, c.favorites[0], snap(lognormal(150, 0.5, 100, 1000)),
                      weighted({"Credit Card": 60, "ACH": 40}), rng.randint(24, 96))
    else:
        year_base = snap(lognormal(base, sigma, lo, hi))
        for fy in active_years(retention, start_weights):
            in_year_gifts(c, fy, year_base * rng.uniform(0.7, 1.4), {1: 40, 2: 35, 3: 15, 4: 10})

    if rng.random() < 0.08:          # books, art, instruments, equipment
        d = pledge_date(c, (20, 20, 20, 20, 20))
        if d:
            gift(c, d, round(lognormal(5000, 1.0, 1500, 60000)),
                 fund=rng.choice([FUND["80010100"], FUND["10070100"], FUND["30020100"]]),
                 ptype="Gift-in-kind", anon=False)

    donor_anonymous = rng.random() < 0.2
    if tier == "mid" and rng.random() < 0.35:
        d = pledge_date(c)
        if d:
            every = weighted({12: 40, 3: 30, 1: 30})           # months between installments
            pledge(c, pledge_funds(major_pool(c), 0.1), d, snap(lognormal(15000, 0.5, 5000, 50000)),
                   rng.randint(2, 5) * 12 // every, every,
                   ptypes=MONTHLY_PTYPES if every == 1 else MID_PTYPES)
    elif tier == "major":
        d = pledge_date(c, (40, 25, 20, 15, 0))
        if d:
            per_year = weighted({1: 60, 2: 25, 4: 15})
            years = rng.randint(3, 5)
            pledge(c, pledge_funds(major_pool(c), 0.3), d,
                   snap(lognormal(150000, 0.7, 50000, 750000)),
                   years * per_year, 12 // per_year, ptypes=MAJOR_PTYPES, anon=donor_anonymous)
    elif tier == "principal":
        funds_used = []
        for i in range(2 if rng.random() < 0.35 else 1):
            d = pledge_date(c, (60, 25, 15, 0, 0) if i == 0 else (10, 20, 35, 35, 0))
            funds = pledge_funds(major_pool(c), 0.3, exclude=funds_used)
            funds_used += funds
            if d:
                total = lognormal(1_000_000, 0.5, 500_000, 3_000_000) if i == 0 else \
                    lognormal(250_000, 0.5, 100_000, 500_000)
                per_year = weighted({1: 60, 2: 25, 4: 15})
                pledge(c, funds, d, snap(total), rng.randint(4, 5) * per_year, 12 // per_year,
                       ptypes=MAJOR_PTYPES, anon=donor_anonymous)


def corporate_giving(c: Constituent) -> None:
    if c.tier == "occasional":
        for _ in range(weighted({1: 65, 2: 35})):
            fy = rng.choices(FISCAL_YEARS, weights=(25, 25, 22, 20, 8))[0]
            gift(c, seasonal_date(fy), snap(lognormal(2500, 0.8, 500, 10000)))
    elif c.tier in ("annual", "major"):
        base = snap(lognormal(5000, 0.7, 1000, 25000))
        for fy in active_years(0.85, (65, 7, 7, 7, 7)):
            for _ in range(weighted({1: 70, 2: 30})):
                d = seasonal_date(fy)
                if rng.random() < 0.12:
                    gift(c, d, round(lognormal(12000, 0.9, 2000, 80000)), ptype="Gift-in-kind",
                         fund=rng.choice([FUND["30020100"], FUND["30030100"], FUND["50000200"]]))
                else:
                    gift(c, d, snap(base * rng.uniform(0.7, 1.4)))
        if c.tier == "major":
            d = pledge_date(c)
            if d:
                funds = pledge_funds([(FUND["30000200"], 25), (FUND["20030100"], 20),
                                      (FUND["70000200"], 25), (FUND["20000200"], 15),
                                      (FUND["50000200"], 15)], 0.2)
                pledge(c, funds, d, snap(lognormal(100000, 0.6, 50000, 300000)),
                       rng.randint(3, 5), 12, ptypes=ORG_PTYPES)


def foundation_giving(f: Constituent) -> None:
    if f.advisor:
        # Family foundation: grants follow the family member's interests, and
        # the family member is soft-credited.
        base = snap(lognormal(20000, 0.6, 5000, 100000))
        for fy in active_years(0.9, (70, 6, 6, 6, 6)):
            for _ in range(weighted({1: 75, 2: 25})):
                d = seasonal_date(fy)
                if d > AS_OF:
                    continue
                fund = pick_fund(f.advisor, d) if rng.random() < 0.6 else weighted(
                    [(x, w) for x, w in major_pool(f.advisor) if x.accepts(d)])
                row = gift(f, d, snap(base * rng.uniform(0.7, 1.3)), fund=fund, anon=False)
                if row and row.contribution_date <= f.advisor.gives_until:
                    row.soft.append(f.advisor)
        return
    if f.tier == "occasional":
        for _ in range(weighted({1: 70, 2: 30})):
            fy = rng.choices(FISCAL_YEARS, weights=(25, 25, 22, 20, 8))[0]
            gift(f, seasonal_date(fy), snap(lognormal(25000, 0.6, 10000, 75000)))
    elif f.tier == "annual":
        base = snap(lognormal(15000, 0.6, 5000, 50000))
        for fy in active_years(0.8, (60, 9, 9, 9, 9)):
            gift(f, seasonal_date(fy), snap(base * rng.uniform(0.8, 1.25)))
    elif f.tier == "major":
        d = pledge_date(f, (30, 30, 25, 15, 0))
        if d:
            funds = f.favorites[:2] if len(f.favorites) > 1 and rng.random() < 0.3 \
                else f.favorites[:1]
            pledge(f, funds, d, snap(lognormal(120000, 0.5, 50000, 300000)),
                   rng.randint(2, 3), 12, ptypes=ORG_PTYPES, outcome_weights=(95, 0, 5))


def prorate(lines: list, amount: Decimal) -> list:
    """Divide a payment across a commitment's lines in proportion."""
    total = sum(a for _, a in lines)
    out = [(fund, money(amount * a / total)) for fund, a in lines[:-1]]
    return out + [(lines[-1][0], amount - sum(a for _, a in out))]


def bequests() -> None:
    """Bequest expectancies. Four donors who died during the window had
    documented bequests that the estate has since paid (or is settling).
    Estate payments divide across the bequest's funds in proportion."""
    died = [p for p in people if p.deceased_date and p.deceased_date >= date(2023, 3, 1)]
    for p in rng.sample(died, min(4, len(died))):
        documented = random_date(WINDOW_START, p.deceased_date - timedelta(days=60))
        total = money(snap(lognormal(200000, 0.7, 25000, 1500000)))
        lines = divide(pledge_funds(major_pool(p), 0.3), total)
        first_paid = business_day(p.deceased_date + timedelta(days=rng.randint(180, 480)))
        if rng.random() < 0.5:
            parts = [(first_paid, total)]
        else:
            first_amount = money(float(total) * rng.uniform(0.5, 0.8))
            second_paid = business_day(first_paid + timedelta(days=rng.randint(60, 240)))
            parts = [(first_paid, first_amount), (second_paid, total - first_amount)]
        received = [(d, a) for d, a in parts if d <= AS_OF]
        add(p, lines, documented, "Bequest Expectancy",
            status="Paid" if len(received) == len(parts) else "Open")
        for d, amount in received:
            add(p, prorate(lines, amount), d, "Bequest Expectancy Payment",
                ptype=weighted({"Check": 50, "Securities": 30, "ACH": 20}))

    # Living donors (and a few non-donors) who have documented a bequest.
    living = [p for p in people if p.generation == "senior" and not p.is_deceased
              and p.constituent_status == "Active"]
    donors = [p for p in living if p.tier != "none"]
    others = [p for p in living if p.tier == "none"]
    for p in rng.sample(donors, min(8, len(donors))) + rng.sample(others, min(3, len(others))):
        documented = random_date(WINDOW_START, AS_OF - timedelta(days=14))
        add(p, [(weighted(major_pool(p)), snap(lognormal(150000, 0.8, 25000, 2000000)))],
            documented, "Bequest Expectancy",
            status="Open" if rng.random() < 0.9 else "Canceled")


SEATING_PTYPES = {"Credit Card": 55, "Check": 25, "ACH": 20}
TICKET_PTYPES = {"Credit Card": 85, "Check": 10, "Cash": 5}


def benefit_payments(everyone: list[Constituent]) -> None:
    """Goods-and-services money, recorded as gifts to the two Gift-Non
    Deductible designations: priority-seating fees paid each summer for the
    coming season, and tickets to homecoming (third Saturday of October) and
    the spring gala (fourth Saturday of April), bought 3 to 45 days ahead.
    Companies buy gala tables."""
    fans = [c for c in everyone if c.gives_until >= WINDOW_START
            and any(f.division == "Athletics" for f in c.favorites)]
    for c in rng.sample(fans, min(14, len(fans))):
        seats = rng.choice([2, 2, 2, 4]) if c.entity_type == "P" else rng.choice([4, 6, 8])
        fee = seats * rng.choice([250, 500, 500, 750])
        for fy in active_years(0.85, (70, 8, 8, 7, 7)):
            ptype = weighted(ORG_PTYPES if c.entity_type == "C" else SEATING_PTYPES)
            gift(c, date(fy - 1, 7, 1) + timedelta(days=rng.randint(0, 45)), fee,
                 fund=FUND[SEATING], ptype=ptype, anon=False)

    guests = [c for c in everyone if c.constituent_status == "Active" and not c.is_deceased
              and c.primary_affiliation not in ("Student", "Foundation")]
    people_only = [c for c in guests if c.entity_type == "P"]
    for fy in FISCAL_YEARS:
        homecoming, gala = saturday(fy - 1, 10, 3), saturday(fy, 4, 4)
        for c in rng.sample(people_only, 7):
            gift(c, homecoming - timedelta(days=rng.randint(3, 45)), 50 * rng.choice([1, 2, 2, 4]),
                 fund=FUND[EVENTS], ptype=weighted(TICKET_PTYPES), anon=False)
        for c in rng.sample(guests, 9):
            if c.entity_type == "C":
                amount, ptype = rng.choice([1500, 2500, 5000]), weighted(ORG_PTYPES)
            else:
                amount, ptype = 150 * rng.choice([1, 2, 2]), weighted(TICKET_PTYPES)
            gift(c, gala - timedelta(days=rng.randint(3, 45)), amount,
                 fund=FUND[EVENTS], ptype=ptype, anon=False)


def matching_gifts() -> None:
    """Employer matches on employees' gifts: the company's Matching Gift to
    the same designations, then its Matching Gift Payment. The employee is
    soft-credited on both. A company's claims record the method it usually
    pays by; now and then a payment arrives the other way."""
    method = {company: weighted(ORG_PTYPES)
              for company in dict.fromkeys(p.employer for p in people if p.employer)}
    for row in list(contributions):
        employee = row.constituent
        if (employee.employer is None or row.contribution_type != "Gift"
                or row.recurring or row.payment_type == "Gift-in-kind" or row.total < 50
                or row.lines[0][0].kind in ("holding", "benefit")
                or rng.random() > employee.match_rate):
            continue
        company = employee.employer
        matched_on = business_day(row.contribution_date + timedelta(days=rng.randint(21, 90)))
        if matched_on > AS_OF or not all(f.accepts(matched_on) for f, _ in row.lines):
            continue
        add(company, row.lines, matched_on, "Matching Gift",
            ptype=method[company]).soft.append(employee)
        paid_on = business_day(matched_on + timedelta(days=rng.randint(30, 150)))
        if paid_on <= AS_OF and all(f.accepts(paid_on) for f, _ in row.lines):
            ptype = method[company] if rng.random() < 0.85 else \
                next(m for m in ORG_PTYPES if m != method[company])
            add(company, row.lines, paid_on, "Matching Gift Payment",
                ptype=ptype).soft.append(employee)


def joint_soft_credits() -> None:
    """Soft credit to the spouse or partner on a joint giver's gifts, pledges,
    and pledge payments, while the spouse is living."""
    for row in contributions:
        c = row.constituent
        if (c.joint_giver and row.contribution_type in ("Gift", "Pledge", "Pledge Payment")
                and row.contribution_date <= c.spouse.gives_until):
            row.soft.append(c.spouse)


def assign_giving_roles(everyone: list[Constituent]) -> None:
    """Matching-gift employers and family foundations."""
    corporations = [o for o in orgs if o.primary_affiliation == "Corporation"]
    matchers = [o for o in corporations if o.constituent_status == "Active"][:N_MATCHING_COMPANIES]
    employees = [p for p in people if p.tier in ("annual", "mid", "major", "principal")
                 and p.generation != "senior" and p.constituent_status == "Active"
                 and p.primary_affiliation in ("Alumnus/Alumna", "Parent", "Friend", "Trustee")]
    for p in rng.sample(employees, min(45, len(employees))):
        p.employer = rng.choice(matchers)
        p.match_rate = rng.choice([0.3, 0.6, 0.9])

    families = [p for p in people if p.tier in ("principal", "major", "mid")
                and not p.is_deceased and p.constituent_status == "Active"]
    rank = {"principal": 0, "major": 1, "mid": 2}
    families.sort(key=lambda p: (rank[p.tier], rng.random()))
    family_foundations = [o for o in orgs if o.org_name is None]
    chosen, names = [], set()
    for p in families:
        if p.last_name not in names:
            chosen.append(p)
            names.add(p.last_name)
        if len(chosen) == len(family_foundations):
            break
    for org, p in zip(family_foundations, chosen):
        org.org_name = f"The {p.last_name} Family Foundation"
        org.advisor = p
        if rng.random() < 0.5:
            org.email = f"{slug(p.last_name)}foundation@example.org"


# =============================================================================
# Contact preferences
# =============================================================================

# (preference_type, restriction_type, contact_method, scope, weight);
# scope "unit" means a specific division rather than university-wide (NULL).
PREFERENCE_TEMPLATES = [
    ("Solicitations", "Exclude", "Email", None, 18),
    ("Solicitations", "Exclude", "Letter", None, 10),
    ("Solicitations", "Exclude", "All", None, 12),
    ("Solicitations", "Exclude", "All", "unit", 8),
    ("Event Invitations", "Exclude", "All", None, 8),
    ("Event Invitations", "Exclude", "Letter", None, 5),
    ("Event Invitations", "Include", "Email", "unit", 6),
    ("Communication", "Exclude", "Email", None, 6),
    ("Communication", "Include", "Email", "unit", 14),
]


def preference_unit(c: Constituent, restriction: str) -> str:
    if restriction == "Exclude":
        return "Athletics" if rng.random() < 0.45 else rng.choice(DIVISIONS)
    if c.entity_type == "P" and c.primary_affiliation in (
            "Alumnus/Alumna", "Faculty/Staff", "Trustee", "Student") and c.school:
        return c.school
    return rng.choice(DIVISIONS)


def temporary_hold(c: Constituent, ptype: str) -> tuple:
    """An Exclude with an end date. Two in three have lapsed; the rest end
    after AS_OF. One in four applies to a single division."""
    if rng.random() < 0.67:
        end = random_date(date(2023, 1, 1), date(2026, 8, 31))
    else:
        end = random_date(date(2026, 10, 1), date(2028, 6, 30))
    method = weighted({"All": 70, "Email": 20, "Letter": 10})
    dept = preference_unit(c, "Exclude") if rng.random() < 0.25 else None
    return (ptype, "Exclude", method, dept, end)


def build_contact_preferences(everyone: list[Constituent]) -> list[tuple]:
    """Each constituent's restrictions are coherent: at most one open row per
    preference type, and a do-not-contact row stands alone."""
    rows = []
    for c in everyone:
        mine = []
        if c.inactive_reason == "requested":
            mine.append(("Communication", "No Reconnect", "All", None, None))
        elif c.entity_type == "P" and rng.random() < 0.02:
            mine.append(("Communication", "Exclude", "All", None, None))
        elif rng.random() < (0.22 if c.entity_type == "P" else 0.06):
            chosen_types = []
            for _ in range(1 if rng.random() < 0.75 else 2):
                ptype, restriction, method, scope, _ = weighted(
                    [(t, t[4]) for t in PREFERENCE_TEMPLATES if t[0] not in chosen_types])
                chosen_types.append(ptype)
                dept = preference_unit(c, restriction) if scope == "unit" else None
                mine.append((ptype, restriction, method, dept, None))
        # Temporary holds on a type with no open-ended row.
        open_types = [m[0] for m in mine]
        if c.entity_type == "P" and "Communication" not in open_types:
            for ptype, rate in (("Solicitations", 0.09), ("Event Invitations", 0.03)):
                if ptype not in open_types and rng.random() < rate:
                    mine.append(temporary_hold(c, ptype))
        rows += [(c, *m) for m in mine]
    return rows


# =============================================================================
# Degrees
# =============================================================================

# The School of Business was the School of Business Administration until
# July 1, 2024. division always carries a unit's current name, the one its
# designations use; the old name turns up only in college.
RENAMED_DIVISION, FORMER_NAME, RENAMED_ON = (
    "School of Business", "School of Business Administration", date(2024, 7, 1))

# (degree_awarded, department, major, weight[, first year offered]).
# department None: the program belongs to the school as a whole.
UNDERGRADUATE = {
    "College of Arts and Sciences": [
        ("BA", "English", "English", 8), ("BA", "History", "History", 7),
        ("BA", "Psychology", "Psychology", 9), ("BS", "Psychology", "Psychology", 3),
        ("BA", "Political Science", "Political Science", 7),
        ("BA", "Economics", "Economics", 6), ("BS", "Biology", "Biology", 9),
        ("BS", "Chemistry", "Chemistry", 4), ("BS", "Mathematics", "Mathematics", 3),
        ("BA", "Mathematics", "Mathematics", 1), ("BA", "Journalism", "Journalism", 4),
        ("BA", "Music", "Music", 2), ("BFA", "Theatre", "Theatre", 4),
    ],
    "School of Business": [
        ("BBA", "Accounting", "Accounting", 8), ("BBA", "Finance", "Finance", 9),
        ("BBA", "Management", "Management", 7), ("BBA", "Marketing", "Marketing", 6),
    ],
    "School of Engineering": [
        ("BS", "Mechanical Engineering", "Mechanical Engineering", 8),
        ("BS", "Electrical and Computer Engineering", "Electrical Engineering", 6),
        ("BS", "Electrical and Computer Engineering", "Computer Engineering", 3, 1986),
        ("BS", "Civil Engineering", "Civil Engineering", 6),
        ("BS", "Computer Science", "Computer Science", 7, 1974),
    ],
    "School of Education": [
        ("BSEd", "Teacher Education", "Elementary Education", 6),
        ("BSEd", "Teacher Education", "Secondary Education", 4),
        ("BSEd", "Teacher Education", "Special Education", 2),
    ],
    "School of Nursing": [("BSN", None, "Nursing", 1)],
}
GRADUATE = {    # master's degrees and the JD
    "College of Arts and Sciences": [
        ("MA", "English", "English", 3), ("MA", "History", "History", 3),
        ("MA", "Economics", "Economics", 2), ("MA", "Psychology", "Psychology", 2),
        ("MS", "Biology", "Biology", 3), ("MS", "Chemistry", "Chemistry", 2),
        ("MS", "Mathematics", "Mathematics", 2),
    ],
    "School of Business": [
        ("MBA", None, "Business Administration", 8), ("MAcc", "Accounting", "Accounting", 2),
    ],
    "School of Engineering": [
        ("MS", "Mechanical Engineering", "Mechanical Engineering", 3),
        ("MS", "Electrical and Computer Engineering", "Electrical Engineering", 3),
        ("MS", "Civil Engineering", "Civil Engineering", 2),
        ("MS", "Computer Science", "Computer Science", 3, 1976),
    ],
    "School of Education": [
        ("MEd", "Teacher Education", "Curriculum and Instruction", 4),
        ("MEd", "Literacy Studies", "Reading and Literacy", 3),
        ("MEd", "Educational Leadership", "Educational Leadership", 3),
    ],
    "School of Nursing": [
        ("MSN", None, "Nursing", 5), ("MSN", None, "Family Nurse Practitioner", 3, 1990),
    ],
    "School of Law": [("JD", None, "Law", 1)],
}
ADVANCED = {    # a further degree after a graduate degree in the same school
    "College of Arts and Sciences": [
        ("PhD", "Chemistry", "Chemistry", 2), ("PhD", "Biology", "Biology", 2),
        ("PhD", "Psychology", "Psychology", 2), ("PhD", "History", "History", 1),
        ("PhD", "English", "English", 1),
    ],
    "School of Engineering": [
        ("PhD", "Mechanical Engineering", "Mechanical Engineering", 1),
        ("PhD", "Electrical and Computer Engineering", "Electrical and Computer Engineering", 1),
        ("PhD", "Computer Science", "Computer Science", 1, 1980),
    ],
    "School of Law": [("LLM", None, "Taxation", 1)],
}
BACHELORS = {"BA", "BS", "BFA", "BBA", "BSEd", "BSN"}
# Years from the previous degree to this one.
GAP_YEARS = {"MA": (1, 5), "MS": (1, 5), "MBA": (3, 10), "MAcc": (1, 2), "MEd": (2, 10),
             "MSN": (3, 8), "JD": (3, 6), "PhD": (3, 6), "LLM": (1, 3)}
# Class year of an alumnus's first degree here, by generation.
CLASS_YEARS = {"young": (2014, 2026), "mid": (1986, 2013), "senior": (1958, 1985)}
# 'ND' is rare and only for people who attended before 1980: most are the
# spouse of a donor who started in the 1960s or 70s and didn't finish.
ND_SPOUSES_OF_DONORS, ND_OTHERS, ND_CLASS_YEARS = 5, 2, (1962, 1979)
LATER_DEGREE_RATE = {"young": 0.12, "mid": 0.3, "senior": 0.25}
# Share of a school's alumni whose degrees here are graduate degrees only.
GRADUATE_ONLY = {"College of Arts and Sciences": 0.05, "School of Business": 0.2,
                 "School of Engineering": 0.1, "School of Education": 0.15,
                 "School of Nursing": 0.1, "School of Law": 1.0}
# Where alumni who change schools go for a graduate degree.
OTHER_GRADUATE_SCHOOLS = {"School of Business": 35, "School of Law": 25,
                          "School of Education": 20, "College of Arts and Sciences": 20}


def commencement(year: int, term: str) -> date:
    """Spring: second Saturday of May; summer: first Saturday of August;
    fall: third Saturday of December."""
    return saturday(year, *{"spring": (5, 2), "summer": (8, 1), "fall": (12, 3)}[term])


def conferral(year: int, term: str, limit: date) -> date:
    """The commencement in year and term, or the latest spring one before limit."""
    on = commencement(year, term)
    while on >= limit:
        on = commencement(on.year if on.month > 5 else on.year - 1, "spring")
    return on


def term_for(degree: str) -> str:
    if degree in ("ND", "JD"):
        return "spring"
    if degree in BACHELORS:
        return weighted({"spring": 82, "fall": 11, "summer": 7})
    return weighted({"spring": 60, "summer": 20, "fall": 20})


def program(options: list, year: int) -> tuple | None:
    """One of the programs offered in year."""
    offered = [(p, p[3]) for p in options if len(p) < 5 or p[4] <= year]
    return weighted(offered) if offered else None


def degree_row(p: Constituent, division: str, prog: tuple, on: date) -> list:
    """A degree row; college is filled in afterwards."""
    degree, department, major = prog[:3]
    return [p.constituent_id, division, department, None, major, degree, on, on.year]


def no_degree_row(p: Constituent) -> list:
    """Attended without graduating. The date is the commencement of the class
    they started with; the major, if one was declared."""
    year = rng.randint(*ND_CLASS_YEARS)
    prog = program(UNDERGRADUATE.get(p.school) or GRADUATE[p.school], year)
    if rng.random() < 0.3:
        prog = (None, None, None)
    return degree_row(p, p.school, ("ND", prog[1], prog[2]), commencement(year, "spring"))


def alumni_degrees(p: Constituent) -> list[list]:
    """An alumnus's degrees, oldest first. The first is in the home school
    (p.school); all fall before AS_OF and before any death date."""
    limit = p.deceased_date or AS_OF
    school = p.school
    year = rng.randint(*CLASS_YEARS[p.generation])
    graduate_first = school not in UNDERGRADUATE or rng.random() < GRADUATE_ONLY[school]
    level = "graduate" if graduate_first else "undergraduate"
    prog = program((GRADUATE if graduate_first else UNDERGRADUATE)[school], year)
    on = conferral(year, term_for(prog[0]), limit)
    rows = [degree_row(p, school, prog, on)]
    if school == "School of Law" and rng.random() < 0.35:     # undergraduate degree here first
        division = weighted({"College of Arts and Sciences": 70, "School of Business": 30})
        y = on.year - rng.randint(3, 5)
        rows.insert(0, degree_row(p, division, program(UNDERGRADUATE[division], y),
                                  commencement(y, "spring")))

    division, chance = school, LATER_DEGREE_RATE[p.generation]
    while rng.random() < chance:
        if level == "undergraduate":
            if rng.random() >= 0.55:
                division = weighted(OTHER_GRADUATE_SCHOOLS)
            options, level = GRADUATE[division], "graduate"
        elif level == "graduate" and division in ADVANCED:
            options, level = ADVANCED[division], "advanced"
        else:
            break
        prog = program(options, on.year)
        if prog is None:
            break
        nxt = commencement(on.year + rng.randint(*GAP_YEARS[prog[0]]), term_for(prog[0]))
        if nxt >= limit:
            break
        rows.append(degree_row(p, division, prog, nxt))
        on, chance = nxt, 0.3
    return rows


def build_degrees(everyone: list[Constituent]) -> list[list]:
    """Degree rows for every Alumnus/Alumna and for nobody else. A few older
    alumni, mostly married to donors, attended without finishing."""
    alumni = [p for p in sorted(everyone, key=lambda c: c.constituent_id)
              if p.primary_affiliation == "Alumnus/Alumna"]
    donors = {id(r.constituent) for r in contributions if r.lines[0][0].kind != "benefit"}
    seniors = [p for p in alumni if p.generation == "senior"]
    spouses = [p for p in seniors if p.spouse and id(p.spouse) in donors]
    others = [p for p in seniors if p not in spouses]
    no_degree = (rng.sample(spouses, min(ND_SPOUSES_OF_DONORS, len(spouses)))
                 + rng.sample(others, ND_OTHERS))
    rows = []
    for p in alumni:
        rows += [no_degree_row(p)] if p in no_degree else alumni_degrees(p)
    return rows


# college is filled in however the records of the day did it. The convention
# shifts by decade of conferral, and a quarter of rows follow some other one.
# division is the clean field.
COLLEGE_BY_DECADE = {1950: "name", 1960: "name", 1970: "abbreviation", 1980: "program",
                     1990: "blank", 2000: "name", 2010: "code", 2020: "name"}
COLLEGE_ABBREVIATIONS = {
    "College of Arts and Sciences": "A&S", "School of Business": "BUS", FORMER_NAME: "BUS ADM",
    "School of Engineering": "ENGR", "School of Education": "EDUC", "School of Nursing": "NURS",
    "School of Law": "LAW"}
COLLEGE_CODES = {
    "College of Arts and Sciences": "AS", "School of Business": "BU", "School of Engineering": "EN",
    "School of Education": "ED", "School of Nursing": "NU", "School of Law": "LW"}


def assign_colleges(degrees: list[list]) -> None:
    """Fill each degree row's college with the school's name as it then was,
    an abbreviation of it, a two-letter code, the department or program in
    place of a school, or nothing."""
    for row in degrees:
        _, division, department, _, major, _, on, _ = row
        convention = COLLEGE_BY_DECADE[on.year // 10 * 10]
        if rng.random() < 0.25:
            convention = rng.choice(["name", "abbreviation", "code", "program", "blank"])
        name = FORMER_NAME if division == RENAMED_DIVISION and on < RENAMED_ON else division
        row[3] = {"name": name, "abbreviation": COLLEGE_ABBREVIATIONS[name],
                  "code": COLLEGE_CODES[division], "program": department or major,
                  "blank": None}[convention]


# =============================================================================
# Output
# =============================================================================

def fmt(value) -> str:
    if value is None:
        return ""                     # unquoted empty field = NULL for COPY ... CSV
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def write_csv(table: str, header: list[str], rows: list[list]) -> None:
    with (OUT_DIR / f"{table}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([fmt(v) for v in row])


CONTRIBUTION_COLUMNS = [
    "contribution_number", "constituent_id", "credit", "designation_code", "contribution_date",
    "contribution_type", "amount", "pledge_number", "pledge_status", "pledge_amount_paid",
    "pledge_balance", "payment_type", "is_anonymous"]


def contribution_rows(row: Contribution) -> list[list]:
    """The hard-credit row for each designation, then each soft credit's rows.
    Pledge rows carry paid to date and balance (canceled and written-off
    pledges keep what was paid and owe nothing)."""
    if row.contribution_type == "Pledge Payment":
        pledge_number = row.pledge.contribution_number
    elif row.contribution_type == "Pledge" and row.self_numbered:
        pledge_number = row.contribution_number
    else:
        pledge_number = None
    out = []
    for who, credit in [(row.constituent, "Hard")] + [(s, "Soft") for s in row.soft]:
        for fund, amount in row.lines:
            paid = balance = None
            if row.contribution_type == "Pledge":
                paid = row.paid[fund.designation_code]
                balance = amount - paid if row.pledge_status == "Open" else Decimal("0.00")
            out.append([row.contribution_number, who.constituent_id, credit,
                        fund.designation_code, row.contribution_date, row.contribution_type,
                        amount, pledge_number, row.pledge_status, paid, balance,
                        row.payment_type, row.is_anonymous])
    return out


def validate(everyone: list[Constituent], contribution_table: list[list], degrees: list[list],
             preferences: list[tuple], canonical: list[list]) -> None:
    """Check the rules the schema does not enforce, and that every value its
    CHECK constraints allow appears."""
    assert all(d.desgtype in PLAUSIBLE_TYPES[d.area] for d in DESIGNATIONS)
    assert [d for d in DESIGNATIONS if UNASSIGNED in (d.area, d.desgtype)] == [FUND[HOLDING]]
    paid = defaultdict(Decimal)
    for row in contributions:
        funds = [f for f, _ in row.lines]
        assert len(set(map(id, funds))) == len(funds) and all(a > 0 for _, a in row.lines)
        assert all(f.accepts(row.contribution_date) for f in funds)
        assert len({id(c) for c in [row.constituent] + row.soft}) == 1 + len(row.soft)
        assert all(row.contribution_date <= s.gives_until for s in row.soft)
        assert (row.payment_type is None) == (row.contribution_type == "Bequest Expectancy")
        if row.contribution_type == "Pledge Payment":
            assert row.contribution_date > row.pledge.contribution_date
            for f, a in row.lines:
                paid[id(row.pledge), f.designation_code] += a
    for row in contributions:
        if row.contribution_type == "Pledge":
            for f, a in row.lines:
                assert row.paid[f.designation_code] == paid[id(row), f.designation_code]
                done = row.paid[f.designation_code]
                assert done == a if row.pledge_status == "Paid" else done < a

    alumni = {c.constituent_id for c in everyone if c.primary_affiliation == "Alumnus/Alumna"}
    assert {r[0] for r in degrees} == alumni
    limit = {c.constituent_id: c.deceased_date or AS_OF for c in everyone}
    assert all(r[6] < limit[r[0]] for r in degrees)
    no_degree = [r for r in degrees if r[5] == "ND"]
    assert all(r[6] < date(1980, 1, 1) for r in no_degree)
    assert len({r[0] for r in no_degree} & {r[0] for r in degrees if r[5] != "ND"}) == 0

    rows = contribution_table
    seen = {
        "contribution_type": {r[5] for r in rows},
        "pledge_status": {r[8] for r in rows if r[5] == "Pledge"},
        "payment_type": {r[11] for r in rows} - {None},
        "credit": {r[2] for r in rows},
        "is_anonymous": {r[12] for r in rows},
        "desgtype of gifts": {FUND[r[3]].desgtype for r in rows if r[5] == "Gift"},
        "areaofgiving of gifts": {FUND[r[3]].area for r in rows if r[5] == "Gift"},
        "primary_affiliation": {c.primary_affiliation for c in everyone},
        "constituent_status": {c.constituent_status for c in everyone},
        "preference_type": {p[1] for p in preferences},
        "restriction_type": {p[2] for p in preferences},
        "contact_method": {p[3] for p in preferences},
        "relationship roles": {(r[1], r[3]) for r in canonical},
        "degree_awarded": {r[5] for r in degrees},
    }
    expected = {
        "contribution_type": {"Gift", "Pledge", "Matching Gift", "Bequest Expectancy",
                              "Pledge Payment", "Bequest Expectancy Payment",
                              "Matching Gift Payment"},
        "pledge_status": {"Open", "Paid", "Canceled", "Written Off"},
        "payment_type": {"Cash", "Check", "Credit Card", "ACH", "Securities", "Gift-in-kind"},
        "credit": {"Hard", "Soft"},
        "is_anonymous": {True, False},
        "desgtype of gifts": set(DESIGNATION_TYPES),
        "areaofgiving of gifts": set(AREAS_OF_GIVING),
        "primary_affiliation": {"Alumnus/Alumna", "Parent", "Friend", "Faculty/Staff",
                                "Student", "Trustee", "Corporation", "Foundation"},
        "constituent_status": {"Active", "Inactive"},
        "preference_type": {"Communication", "Solicitations", "Event Invitations"},
        "restriction_type": {"Exclude", "No Reconnect", "Include"},
        "contact_method": {"All", "Email", "Letter"},
        "relationship roles": {("Spouse", "Spouse"), ("Life Partner", "Life Partner"),
                               ("Parent", "Child"), ("Child", "Parent"),
                               ("Grandparent", "Grandchild"), ("Grandchild", "Grandparent"),
                               ("Sibling", "Sibling")},
        "degree_awarded": {p[0] for table in (UNDERGRADUATE, GRADUATE, ADVANCED)
                           for programs in table.values() for p in programs} | {"ND"},
    }
    for key, values in expected.items():
        assert seen[key] == values, (key, values - seen[key])


def main() -> None:
    build_people()
    build_orgs()
    everyone = people + orgs
    rng.shuffle(everyone)                  # records were created in no particular order
    for i, c in enumerate(everyone, start=1):
        c.constituent_id = i

    assign_life_events(everyone)
    assign_tiers(everyone)
    assign_giving_roles(everyone)
    for c in everyone:
        if c.entity_type == "P":
            person_giving(c)
        elif c.primary_affiliation == "Corporation":
            corporate_giving(c)
        else:
            foundation_giving(c)
    bequests()
    benefit_payments(everyone)
    matching_gifts()
    joint_soft_credits()

    # Numbered in entry order: by date, and within a day in the order entered
    # (the sort is stable), so a pledge's number precedes its payments'.
    contributions.sort(key=lambda r: r.contribution_date)
    for i, row in enumerate(contributions, start=1):
        row.contribution_number = f"{i:07d}"
    contribution_table = [r for row in contributions for r in contribution_rows(row)]
    reseed("contact_preference")
    preferences = build_contact_preferences(everyone)
    reseed("degree")
    degrees = build_degrees(everyone)
    reseed("college")
    assign_colleges(degrees)
    canonical = []
    for a, a_role, b, b_role in relationships:
        if a.constituent_id > b.constituent_id:
            a, a_role, b, b_role = b, b_role, a, a_role
        canonical.append([a.constituent_id, a_role, b.constituent_id, b_role])
    validate(everyone, contribution_table, degrees, preferences, canonical)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv("designation",
              ["designation_code", "designation_name", "division", "department", "is_active",
               "desgtype", "areaofgiving"],
              [[d.designation_code, d.designation_name, d.division, d.department, d.is_active,
                d.desgtype, d.area]
               for d in sorted(DESIGNATIONS, key=lambda d: d.designation_code)])
    write_csv("constituent",
              ["constituent_id", "entity_type", "first_name", "preferred_name", "last_name",
               "org_name", "primary_affiliation", "email", "address_line1", "address_city",
               "address_state", "address_postal_code", "address_country",
               "constituent_status", "is_deceased", "deceased_date"],
              [[c.constituent_id, c.entity_type, c.first_name, c.preferred_name, c.last_name,
                c.org_name, c.primary_affiliation, c.email, c.address_line1, c.address_city,
                c.address_state, c.address_postal_code, c.address_country,
                c.constituent_status, c.is_deceased, c.deceased_date]
               for c in sorted(everyone, key=lambda c: c.constituent_id)])
    write_csv("contribution", CONTRIBUTION_COLUMNS, contribution_table)
    write_csv("contact_preference",
              ["contact_preference_id", "constituent_id", "preference_type",
               "restriction_type", "contact_method", "department", "end_date"],
              [[i, c.constituent_id, ptype, restriction, method, dept, end]
               for i, (c, ptype, restriction, method, dept, end) in enumerate(
                   sorted(preferences, key=lambda p: p[0].constituent_id), start=1)])
    write_csv("constituent_relationship",
              ["person1_id", "person1_role", "person2_id", "person2_role"], sorted(canonical))
    write_csv("degree",
              ["constituent_id", "division", "department", "college", "major",
               "degree_awarded", "graduation_date", "graduation_year"], degrees)

    print(f"Wrote CSVs to {OUT_DIR}")
    for name, n in [("designation", len(DESIGNATIONS)), ("constituent", len(everyone)),
                    ("contribution", len(contribution_table)),
                    ("contact_preference", len(preferences)),
                    ("constituent_relationship", len(canonical)), ("degree", len(degrees))]:
        print(f"  {name:<26}{n:>6}")
    print(f"  ({len(contributions)} contribution numbers)")


if __name__ == "__main__":
    main()
