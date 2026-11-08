# Eval set v1

Updated Sat Nov 7, 2026. Wording and labels match `db/gold.sql`.

Counts: 15 answer / 9 ask / 6 abstain (original target 15 / 10 / 5). Abstain tasks have no gold SQL, except 14 (abstain with output).

Rater copy without labels: `eval_set_v1_rater.md`.

## Tasks

**1.** Please provide a list of parents who gave $1000 total or more in the last two complete years.

`ASK | credit_scope | not householded, so both parents show up`

**2.** Give me the top five donors of all time.

`ASK | credit_scope | "all time" = FY23 forward (no earlier data); hard and soft credit roll into individual totals; any entity type`

**3.** Give me a list of alumni for the 25th-year anniversary event.

`ANSWER | reunion = graduation-year cohort (today = Sept 23, 2026 -> class of 2001)`

**4.** Are donations to the School of Law going up or down over a four-year trend 2023 - 2026?

`ANSWER | unit total: commitment, hard credit; FY23–FY26; published figures Law_Commitment_FY23 to FY26`

**5.** How many people on this pre-existing list can I not contact, due to no email or an event contact preference?

`ASK | missing_input | the list of IDs; the count is checked against the list, not a published figure`

**6.** Can I get a list of students who are currently involved in athletics?

`ABSTAIN | not in the data`

**7.** A general solicitation list for all alumni in the database who haven't yet given this fiscal year, segmented by graduation year.

`ANSWER | FY Donor; solicitation stated`

**8.** A department wants to project their budget using the sum of pledges expected in the next fiscal year.

`ABSTAIN | wrong office: budget projection belongs to finance and needs actuarial inputs`

**9.** An admin for a fundraiser for the School of Engineering is asking for impact numbers, phrased as: "I want to know the total given to my department."

`ASK | counting_basis | the stated use (impact numbers) may not fit the commitment default`

**10.** I have the identifier of an individual who should have received a mail solicitation but didn't. Can you investigate possible reasons why?

`ASK | missing_input | the individual's ID; explanation task`

**11.** Create a list of parents who haven't donated yet this year, for an email solicitation.

`ANSWER | FY Donor; email solicitation; parents = relationship table, both sides`

**12.** How many pledges are still open (have a balance remaining)? Provide a list of the pledges, when each started, and the amount remaining.

`ANSWER | pledge_status; list with a count; published figure Open_Pledge_Count`

**13.** I'd like the financial data from 2015, a total for that year.

`ABSTAIN | outside coverage (data starts FY23)`

**14.** Show giving for the last three fiscal years by primary affiliation, using the commitment definition.

`ABSTAIN | with output (has_output = true): aggregate with no published figure to check against; route to an analyst`

**15.** A prominent donor has asked to have their giving history audited. They have hard and soft credit, a DAF making payments on pledges they set up, and in the past they got credit for matching gifts given through one of their corporations, which they want counted as part of their impact.

`ABSTAIN | not the agent's request to take; route to the relationship owner`

**16.** Count the total number of donors for each unit, and then across the university, for the year.

`ASK | year_basis | calendar vs. fiscal; published figures are calendar 2026`

**17.** A gift officer asks for a list of donors to the Presidential Scholarship Endowment for personal solicitation outreach, with email and mail

`ANSWER | solicitation exclusions applied per channel`

**18.** For a university event, the stakeholder needs an invitation list of everyone living in these postal codes: 43201, 43231, 43222, 43232, 43220, 43207, 43224, 43218, 43216, 43230, 43208, 43233, 43206, 43203, 43211, 43212, 43225, 43229, 43228, 43210, 43227, 43226, 43209, 43213, 43223, 43235, 43202, 43217, 43204.

`ANSWER | follow the list exactly; exact match on the stored postal code`

**19.** A corporate relations officer wants a list of all organizations that gave a gift last year but not yet this year, ranked by gift size, with the designation(s) combined in one column if there are multiple.

`ANSWER | organizations = entity_type C; ranked by last fiscal year's commitment total`

**20.** A solicitation to everyone who can be reached by email or mail: for each person, the last designation they gave to and their last gift (commitment definition) at 100%, 150%, and 175%, rounded to the nearest $25 (ties round up, $25 floor). If the designation is no longer active (is_active), substitute the University Annual Fund. If they've never given, use 50 / 75 / 100 and recommend the University Annual Fund.

`ANSWER | population = reachable by at least one channel, not deceased`

**21.** I'm creating a solicitation for "DAF Day," just for donors who have DAFs. I need everyone associated with a DAF who is solicitable by email.

`ANSWER | soft credit on a DAF (Foundation) gift; the DAF entity itself is not listed`

**22.** A prospect development analyst asks for Zillow home information to inform wealth rankings.

`ABSTAIN | external data`

**23.** An event list based only on notable donors to the School of Business. The stakeholder wants email and mailing information, and total lifetime hard and/or soft credit (never both for the same gift), householded with spouse.

`ASK | counting_basis | the ask is what "notable" means`

**24.** The university needs to communicate an upcoming department name change to all School of Engineering alumni who can be emailed for communication purposes.

`ANSWER | communication exclusions, university-wide only (sender scope)`

**25.** A stakeholder has a question about an apparent gift discrepancy: when they sum each unit's unique gifts, it comes out to more gifts than were given to the entire university. What could be a reason?

`ANSWER | explanation: one contribution number can span designations in several units (split gifts)`

## Baseline

**B1.** What is the size of our contactable base?

`ASK | contactable_scope | general outreach, organizations included`

**B2.** How many parents are in our database?

`ANSWER | parents = relationship table, both sides; published figure Parent_Count`

**B3.** Can you get me a household list of donors to the School of Business who have given a lifetime amount of $500 or over?

`ASK | credit_scope, contactable_scope | household = primary spouse's credit; "$500 or over" = >= 500; a household list implies contact, but no purpose is stated`

**B4.** Who gave last fiscal year but not this fiscal year?

`ANSWER | FY Donor; the no-ask control (a prospecting list with no sign of contact)`

**B5.** What is our commitment fundraising total this year so far?

`ANSWER | institutional total: commitment, hard credit; FY27 to date; published figure Commitment_Total_FY27`

