/***********************************************************************************/
-- 'Golden' sql for the Eval set v1 minus abstain
-- Mallory Berg
-- 25 tasks: 16 Answer, 9 Ask. Abstain tasks (6, 8, 13, 15, 22) have no SQL.14 is abstain but has sql.
-- Header fields: label | dimension (Ask only) | type: aggregate / list / explanation
-- Ask tasks also carry: reply = what the simulator says back; reading = the clarified spec.


/*--------------------------------------------------------------------------/
  1 - Please provide a list of parents who gave $1000 total or more in the last two complete years.
  ASK | credit_scope | type: list
  reply: Commitment, hard or soft credit
  reading:  Not a householded list so both parents should show up
  ------------------------------------------------------------------------*/
with parents as(
    select distinct person1_id from synth_advancement.constituent_relationship 
    where person1_role = 'Parent' 
    union 
    select distinct person2_id from synth_advancement.constituent_relationship 
    where person2_role = 'Parent' 
),
last_two_years_1000 as(
    select c.constituent_id, 
    sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as "Amount Given"
    from synth_advancement.contribution c 
    where c.fiscal_year in (2025,2026)
    and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
    group by c.constituent_id
    having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) >= 1000 
)
select c.first_name, c.last_name , t.*
from synth_advancement.constituent c
inner join parents p on c.constituent_id = p.person1_id
inner join last_two_years_1000 t on t.constituent_id = p.person1_id;


/*--------------------------------------------------------------------------/
  2 - Give me the top five donors of all time.
  ASK | credit_scope | type: list
  reply: Use commitment giving, hard and soft credit 
  reading: since database only goes back to 2023, that is 'all time'. Soft and hard credit rolls into individual total calc. Assume any entity type unless specified directly.
  ------------------------------------------------------------------------*/
select cc.constituent_id, cc.first_name, cc.last_name,
sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as total
from synth_advancement.contribution c
left join  synth_advancement.constituent cc on cc.constituent_id = c.constituent_id
where c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
and c.amount > 0
group by cc.constituent_id, cc.first_name, cc.last_name
order by total desc
limit 5;



/*--------------------------------------------------------------------------/
  3 - Give me a list of alumni for the 25th-year anniversary event.
  ANSWER | type: list
  ------------------------------------------------------------------------*/

with degree_holders as (select distinct d.constituent_id 
from synth_advancement.degree d where d.graduation_year = 2026-25),

email_event_contactable as (select * from synth_advancement.contact_preference cp
 where restriction_type = 'Exclude' and preference_type = 'Event Invitations' and department is null
 and (contact_method = 'Email' or contact_method = 'All')
 and (end_date is null or end_date >= '2026-09-23')),

 mail_event_contactable as (select * from synth_advancement.contact_preference
 where restriction_type = 'Exclude' and preference_type = 'Event Invitations' and department is null
and (contact_method = 'Letter' or contact_method = 'All')
 and (end_date is null or end_date >= '2026-09-23'))

 select 
 d.constituent_id,
 c.first_name,
 c.last_name,
 c.address_line1,
 c.address_city,
 c.address_state,
 c.address_postal_code,
 c.email,
 case when ec.constituent_id is null then 'Yes' else 'No' end as "Email Invitable",
 case when mc.constituent_id is null then 'Yes' else 'No' end  as "Mail Invitable"
 from degree_holders d 
 inner join synth_advancement.constituent c on d.constituent_id = c.constituent_id
 left join email_event_contactable ec on d.constituent_id = ec.constituent_id
 left join mail_event_contactable mc on d.constituent_id = mc.constituent_id
 where not c.is_deceased;



/*--------------------------------------------------------------------------/
  4 - Are donations to the School of Law going up or down over a four-year trend 2023 - 2026?
  ANSWER | type: aggregate
  ------------------------------------------------------------------------*/
 select c.fiscal_year,
sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as total
from synth_advancement.contribution c
left join synth_advancement.designation d on c.designation_code = d.designation_code
where
d.division = 'School of Law'
and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
and c.fiscal_year >= 2023 and c.fiscal_year < 2027
and c.credit = 'Hard'
group by c.fiscal_year

order by c.fiscal_year desc
;

/*--------------------------------------------------------------------------/
  5 - How many people on this pre-existing list can I not contact, due to no email
      or an event contact preference?
  ASK | missing_input | type: aggregate
  reply: 1,2,35,67,88,30,20,46,10,14,23,29,34
  reading: No email or no event by email contact preference, even though it's an aggregate it's compared against the list not a published number.
  ------------------------------------------------------------------------*/

with removal as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Event Invitations'
and department is null
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23')

union all 

select c.constituent_id 
from synth_advancement.constituent c where c.email is null)

select count (distinct constituent_id) from removal where constituent_id in (1,2,35,67,88,30,20,46,10,14,23,29,34);

/*--------------------------------------------------------------------------/
  7 - A general solicitation list for all alumni in the database who haven't yet
      given this fiscal year, segmented by graduation year.
  ANSWER | type: list
  ------------------------------------------------------------------------*/
with donor_thisfiscalyear as (
  select c.constituent_id from synth_advancement.contribution c 
  where c.fiscal_year = 2027
  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0
),

graduation_year as (select d.constituent_id, min(d.graduation_year) as "graduation_year" 
from synth_advancement.degree d group by d.constituent_id
),

no_email_solict as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and department is null
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23')),


no_mail_solicit as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and department is null
and c.contact_method in ('All','Letter')
and (c.end_date is null or c.end_date >= '2026-09-23'))

select
c.constituent_id,
c.first_name,
c.last_name,
y.graduation_year,
c.address_line1,
c.address_city,
c.address_state,
c.address_postal_code,
c.email,
case when ye.constituent_id is null then 'Yes' else 'No' end as "Solicitable By E-mail",
case when xm.constituent_id is null then 'Yes' else 'No' end as "Solicitable By Mail"
from synth_advancement.constituent c 
join graduation_year y on y.constituent_id = c.constituent_id
left join no_mail_solicit xm on c.constituent_id = xm.constituent_id
left join no_email_solict ye on c.constituent_id = ye.constituent_id

where

c.constituent_id not in (select constituent_id from donor_thisfiscalyear)
and not c.is_deceased;

/*--------------------------------------------------------------------------/
  9 - An admin for a fundraiser for the School of Engineering is asking for impact numbers, phrased as:
      "I want to know the total given to my department."
  ASK | counting_basis | type: aggregate
  reply: Cash 
  reading: time period in database, no filter needed
  ------------------------------------------------------------------------*/


select 
sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as total
from synth_advancement.contribution c
left join synth_advancement.designation d on c.designation_code = d.designation_code
where
d.division = 'School of Engineering'
and c.credit = 'Hard'
and c.contribution_type in ('Pledge Payment', 'Matching Gift Payment', 'Gift','Bequest Expectancy Payment');



/*--------------------------------------------------------------------------/
  10 - I have the identifier of an individual who should have received a mail
       solicitation but didn't. Can you investigate possible reasons why?
  ASK | missing_input | type: explanation
  reply: ID: 30
  reading: 30 both doesn't have address on file and has a communication exclusion
  ------------------------------------------------------------------------*/


select * from synth_advancement.contact_preference where constituent_id = 30;

select address_line1, is_deceased from synth_advancement.constituent where constituent_id = 30;

/*--------------------------------------------------------------------------/
  11 - Create a list of parents who haven't donated yet this year, for an email
       solicitation.
  ANSWER | type: list
  ------------------------------------------------------------------------*/

with parents as(
    select distinct person1_id from synth_advancement.constituent_relationship 
    where person1_role = 'Parent' 
    union 
    select distinct person2_id from synth_advancement.constituent_relationship 
    where person2_role = 'Parent' 
),

donor_thisfiscalyear as (
  select c.constituent_id from synth_advancement.contribution c 
  where c.fiscal_year = 2027
  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0
),

no_email_solict as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and department is null
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23'))

select
c.constituent_id,
c.first_name,
c.last_name,
c.address_line1,
c.address_city,
c.address_state,
c.address_postal_code,
c.email,
case when ye.constituent_id is null then 'Yes' else 'No' end as "Solicitable By E-mail"

from synth_advancement.constituent c 
inner join parents p on c.constituent_id = p.person1_id
left join no_email_solict ye on c.constituent_id = ye.constituent_id

where
c.constituent_id not in (select constituent_id from donor_thisfiscalyear)
and not c.is_deceased;


/*--------------------------------------------------------------------------/
  12 - How many pledges are still open (have a balance remaining)? Provide a list
       of the pledges, when each started, and the amount remaining.
  ANSWER | type: list (with a count)
  ------------------------------------------------------------------------*/

select distinct c.contribution_number, c.contribution_date, sum(c.pledge_balance) as "Pledge Balance"
from synth_advancement.contribution c 
where
c.contribution_type = 'Pledge'
and  c.pledge_status = 'Open'
and c.credit = 'Hard'
group by c.contribution_number, c.contribution_date;

/*--------------------------------------------------------------------------/
  14 - Show giving for the last three fiscal years by primary affiliation, using
       the commitment definition.
  ABSTAIN | type: aggregate
  ------------------------------------------------------------------------*/

select c.fiscal_year, 
cc.primary_affiliation,
sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as total
from synth_advancement.contribution c
left join synth_advancement.constituent cc on c.constituent_id = cc.constituent_id
where
c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
and c.credit = 'Hard'
and c.fiscal_year >= 2024 and c.fiscal_year < 2027
group by c.fiscal_year, cc.primary_affiliation

;

/*--------------------------------------------------------------------------/
  16 - Count the total number of donors for each unit, and then across the
       university, for the year for end of year receipting purposes.
  ASK | year_basis | type: aggregate
  reply: Calendar Year 2026
  reading: "2026 to date", union results
  ------------------------------------------------------------------------*/

-- By Unit
select 
d.division,
count(distinct c.constituent_id) as donors
from synth_advancement.contribution c
left join synth_advancement.designation d on d.designation_code = c.designation_code
where c.contribution_date between '2026-01-01' and '2026-09-23'
and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
group by d.division
having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0

union all
-- By University
select 
'University' as division,
count(distinct c.constituent_id) as donors
from synth_advancement.contribution c
left join synth_advancement.designation d on d.designation_code = c.designation_code
where c.contribution_date between '2026-01-01' and '2026-09-23'
and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0;

/*--------------------------------------------------------------------------/
  17 - A gift officer asks for a list of donors to the Presidential Scholarship
       Endowment for personal solicitation outreach, with email and mail
  ANSWER | type: list
  ------------------------------------------------------------------------*/

with presidential_scholarship_donor as 
(select distinct constituent_id from 
synth_advancement.contribution c
where designation_code = '01000300' -- Endowment designation code
),


no_email_solict as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and department is null
and c.preference_type = 'Solicitations'
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23')),


no_mail_solicit as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and department is null
and c.preference_type = 'Solicitations'
and c.contact_method in ('All','Letter')
and (c.end_date is null or c.end_date >= '2026-09-23'))

select
c.constituent_id,
c.first_name,
c.last_name,
c.address_line1,
c.address_city,
c.address_state,
c.address_postal_code,
c.email,
case when ye.constituent_id is null then 'Yes' else 'No' end as "Solicitable By E-mail",
case when xm.constituent_id is null then 'Yes' else 'No' end as "Solicitable By Mail"
from 
presidential_scholarship_donor ps
inner join synth_advancement.constituent c on ps.constituent_id = c.constituent_id
left join no_mail_solicit xm on c.constituent_id = xm.constituent_id
left join no_email_solict ye on c.constituent_id = ye.constituent_id
where not c.is_deceased;


/*--------------------------------------------------------------------------/
  18 - For a university event, the stakeholder needs an invitation list of
       everyone living in these postal codes: 43201, 43231, 43222, 43232, 43220,
       43207, 43224, 43218, 43216, 43230, 43208, 43233, 43206, 43203, 43211,
       43212, 43225, 43229, 43228, 43210, 43227, 43226, 43209, 43213, 43223,
       43235, 43202, 43217, 43204.
  ANSWER | type: list
  ------------------------------------------------------------------------*/
 with event_email_remove as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Event Invitations'
and department is null
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23')),

event_mail_remove as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Event Invitations'
and department is null
and c.contact_method in ('All','Letter')
and (c.end_date is null or c.end_date >= '2026-09-23')
)
select
c.constituent_id,
c.first_name,
c.last_name,
c.address_line1,
c.address_city,
c.address_state,
c.address_postal_code,
c.email,
case when eer.constituent_id is null then 'Yes' else 'No' end as "Event Invtable By E-mail",
case when emr.constituent_id is null then 'Yes' else 'No' end as "Event Invtable By Mail"
from 
synth_advancement.constituent c
left join event_email_remove eer on c.constituent_id = eer.constituent_id
left join event_mail_remove emr on c.constituent_id = emr.constituent_id
where address_postal_code  in ('43201', '43231', '43222', '43232', '43220',
'43207', '43224', '43218', '43216', '43230', '43208', '43233', '43206', '43203', '43211',
'43212', '43225', '43229', '43228', '43210', '43227', '43226', '43209', '43213', '43223',
'43235', '43202', '43217', '43204')
and not c.is_deceased;


/*--------------------------------------------------------------------------/
  19 - A corporate relations officer wants a list of all organizations that gave
       a gift last year but not yet this year, ranked by gift size, with the
       designation(s) combined in one column if there are multiple.
  ANSWER | type: list
  ------------------------------------------------------------------------*/

with ly as (
  select c.constituent_id, 
  string_agg(distinct d.designation_name, ', ' order by d.designation_name)as "Designation(s)",
  sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as "Last_Year_Amount"
  from synth_advancement.contribution c 
  left join synth_advancement.designation d on d.designation_code = c.designation_code
  where c.fiscal_year = 2026
  and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0
),


ty as (
   select c.constituent_id 
  from synth_advancement.contribution c 
  where c.fiscal_year = 2027
  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0
)

select c.constituent_id, 
c.org_name,
l."Designation(s)",
l."Last_Year_Amount" 
from ly l
inner join synth_advancement.constituent c on c.constituent_id = l.constituent_id
where entity_type = 'C'
and l.constituent_id not in (select constituent_id from ty)
order by l."Last_Year_Amount" desc
;
/*--------------------------------------------------------------------------/
  20 - A solicitation to everyone who can be reached by email or mail: for each
       person, the last designation they gave to and their last gift (commitment
       definition) at 100%, 150%, and 175%, rounded to the nearest $25 (ties
       round up, $25 floor). If the designation is no longer active (is_active),
       substitute the University Annual Fund. If they've never given, use
       50 / 75 / 100 and recommend the University Annual Fund.
  ANSWER | type: list
  ------------------------------------------------------------------------*/

with last_give_1 as (
  select 
  c.constituent_id,
  c.contribution_number,
  (case when d.is_active then d.designation_code else '01000100' end) as "designation_choice",
  (case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as "amount",
  row_number() over (partition by constituent_id order by contribution_date desc, contribution_number desc) as "row"
  from synth_advancement.contribution c
  left join synth_advancement.designation d on c.designation_code = d.designation_code
  where c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')

),

last_give as (
  select 
  c.constituent_id,
  c.contribution_number,
  c.designation_choice,
  c.amount
  from last_give_1 c
  where c.row  = 1
),

no_email_solict as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and department is null
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23')),

no_mail_solicit as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and department is null
and c.contact_method in ('All','Letter')
and (c.end_date is null or c.end_date >= '2026-09-23'))

select
c.constituent_id,
l.contribution_number,
coalesce(l.designation_choice, '01000100') as designation_choice,
l.amount,
case when l.amount is null then 50 else greatest(25, floor((l.amount * 1.00 + 12.5) / 25) * 25) end as "100%",
case when l.amount is null then 75 else greatest(25, floor((l.amount * 1.50 + 12.5) / 25) * 25) end as "150%",
case when l.amount is null then 100 else greatest(25, floor((l.amount * 1.75 + 12.5) / 25) * 25) end as "175%",
c.first_name,
c.last_name,
c.address_line1,
c.address_city,
c.address_state,
c.address_postal_code,
case when ye.constituent_id is null then 'Yes' else 'No' end as "Solicitable By E-mail",
case when xm.constituent_id is null then 'Yes' else 'No' end as "Solicitable By Mail"
from 
synth_advancement.constituent c 
left join last_give l on l.constituent_id = c.constituent_id
left join no_mail_solicit xm on c.constituent_id = xm.constituent_id
left join no_email_solict ye on c.constituent_id = ye.constituent_id
where (ye.constituent_id is null or xm.constituent_id is null) and not c.is_deceased;


/*--------------------------------------------------------------------------/
  21 - I'm creating a solicitation for "DAF Day," just for donors who have DAFs.
       I need everyone associated with a DAF who is solicitable by email.
  ANSWER | type: list
  ------------------------------------------------------------------------*/


with hard_credit_daf as (
  select distinct c.constituent_id, c.contribution_number 
  from synth_advancement.contribution c 
  where c.credit = 'Hard' and c.constituent_id 
  in (select distinct  c.constituent_id
  from synth_advancement.constituent c 
  where c.primary_affiliation = 'Foundation')
),

soft_credit_donors as (
  select distinct c.constituent_id, c.contribution_number 
  from synth_advancement.contribution c 
  where c.credit = 'Soft'  and c.contribution_number in (select c.contribution_number from hard_credit_daf)
),

no_email_solicit as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and department is null
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23'))

select distinct c.constituent_id, c.first_name, c.last_name, c.email
from synth_advancement.constituent c
inner join soft_credit_donors d on c.constituent_id = d.constituent_id
where c.email is not null and c.constituent_id not in (select constituent_id from no_email_solicit)
and not c.is_deceased;

/*--------------------------------------------------------------------------/
  23 - An event list based only on notable donors to the School of Business.
       The stakeholder wants email and mailing information, and total lifetime
       hard and/or soft credit (never both for the same gift), householded with
       spouse.
  ASK | missing_input | type: list
  reply: lifetime giving of $25 or more to the School of Business, Commitment giving definition and provide a column to indicate donor loyalty -  number of fiscal years with any positive giving, Fy23-Fy27 to date, reported as a column
  reading: lifetime = FY23 forward, commitment basis, household = primary spouse’s credit per the dictionary, School of Business by designation division.
  ------------------------------------------------------------------------*/
with household as 
(select distinct person1_id, person2_id 
from synth_advancement.constituent_relationship 
where person1_role in ('Spouse','Life Partner')),

school_of_business as (
  select 
  c.constituent_id,
  sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as "Total Amount"
  from synth_advancement.contribution c 
  left join synth_advancement.designation d on c.designation_code = d.designation_code
  
  where d.division = 'School of Business'
  and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')

  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) >= 25
),

school_of_business_loyal as (
    select c.constituent_id,
         count(distinct c.fiscal_year) as years_given
  from synth_advancement.contribution c
  where (case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled'
              then c.pledge_amount_paid else c.amount end) > 0
  group by c.constituent_id

),
email_event_contactable as (select * from synth_advancement.contact_preference cp
 where restriction_type = 'Exclude' and preference_type = 'Event Invitations' and department is null
 and (contact_method = 'Email' or contact_method = 'All')
 and (end_date is null or end_date >= '2026-09-23')),

mail_event_contactable as (select * from synth_advancement.contact_preference
where restriction_type = 'Exclude' and preference_type = 'Event Invitations' and department is null
and (contact_method = 'Letter' or contact_method = 'All')
and (end_date is null or end_date >= '2026-09-23'))

select 
 b.constituent_id,
 c.first_name,
 c.last_name,
 c.org_name,
 spouse.constituent_id as "Spouse ID",
 spouse.first_name as "Spouse First Name",
 spouse.last_name as "Spouse Last Name",
 c.address_line1,
 c.address_city,
 c.address_state,
 c.address_postal_code,
 c.email,
 case when ec.constituent_id is null then 'Yes' else 'No' end as "Email Invitable",
 case when em.constituent_id is null then 'Yes' else 'No' end  as "Mail Invitable",
 b."Total Amount" as "Lifetime Giving to School of Business",
 loy.years_given
from school_of_business b 
inner join synth_advancement.Constituent c on b.constituent_id = c.constituent_id
left join household h on b.constituent_id = h.person1_id
left join email_event_contactable ec on b.constituent_id = ec.constituent_id
left join mail_event_contactable em on b.constituent_id = em.constituent_id
left join synth_advancement.constituent spouse on h.person2_id = spouse.constituent_id
left join school_of_business_loyal loy on b.constituent_id = loy.constituent_id
where b.constituent_id not in (select person2_id from household);


/*--------------------------------------------------------------------------/
  24 - The university needs to communicate an upcoming department name change
       to all School of Engineering alumni who can be emailed for communication
       purposes.
  ANSWER | type: list
  ------------------------------------------------------------------------*/
with email_communication_contactable as (select * from synth_advancement.contact_preference cp
 where restriction_type = 'Exclude' and preference_type = 'Communication' and department is null
 and (contact_method = 'Email' or contact_method = 'All')
 and (end_date is null or end_date >= '2026-09-23')),

 degree_engineering as (
  select constituent_id from synth_advancement.degree where division = 'School of Engineering'
 )

 select
 distinct d.constituent_id,
 c.first_name,
 c.last_name,
 c.email
 from degree_engineering d 
 left join synth_advancement.constituent c on d.constituent_id = c.constituent_id
 where c.email is not null and not c.is_deceased and d.constituent_id not in (select ec.constituent_id 
 from email_communication_contactable ec);


/*--------------------------------------------------------------------------/
  25 - A stakeholder has a question about an apparent gift discrepancy: when
       they sum each unit's unique gifts, it comes out to more gifts than were
       given to the entire university. What could be a reason?
  ANSWER | type: explanation (supporting query only; gold is the explanation)
  ------------------------------------------------------------------------*/

---One gift = what was given to one contribution number. Because gifts to multiple designations that map to different units can exist under one contribution number,
--- the university gift will show 1 where two divisions each were given a gift due to the designation mapping.

select c.contribution_number, count(distinct d.division)as "Unit Gifts" 
from synth_advancement.contribution c
left join synth_advancement.designation d on c.designation_code = d.designation_code
group by c.contribution_number
having count(distinct d.division) > 1;

/*--------------------------------------------------------------------------/
  B1 - What is the size of our contactable base?
  ASK | contactable_scope | type: aggregate
  reply: General outreach, not a solicitation. Everyone we could reach, including organizations.
reading: contactable = no in-force, university-wide Communication exclusion with contact_method 'All' (Exclude or No Reconnect); living, active, has an email or address; organizations included.
  ------------------------------------------------------------------------*/

with communication_contactable as
 (select cp.constituent_id from synth_advancement.contact_preference cp
 where restriction_type in('Exclude','No Reconnect')
 and  department is null and contact_method = 'All'
 and preference_type ='Communication'
 and (end_date is null or end_date >= '2026-09-23'))


 select count(distinct c.constituent_id) as "Size of Contactable Base"
 from  synth_advancement.constituent c
 where c.constituent_id not in (select cp.constituent_id from communication_contactable cp)
 and (c.email is not null or c.address_line1 is not null)
 and not c.is_deceased
 and c.constituent_status = 'Active';

/*--------------------------------------------------------------------------/
  B2 - How many parents are in our database?
  ANSWER | type: aggregate
  ------------------------------------------------------------------------*/
with parents as(
    select distinct person1_id as Id from synth_advancement.constituent_relationship 
    where person1_role = 'Parent' 
    union 
    select distinct person2_id as Id from synth_advancement.constituent_relationship 
    where person2_role = 'Parent' 
)

select count(distinct p.Id) from parents p;

/*--------------------------------------------------------------------------/
  B3 - Can you get me a household list of donors to the School of Business who
       have given a lifetime amount of $500 or over?
  ASK | credit_scope, contactable_scope| type: list
  reply for credit_scope: Commitment hard or soft credit
  reply for contactable_scope: solicitation list
  reading: household = primary spouse's credit; "$500 or over" >= 500, School of Business is sending
  ------------------------------------------------------------------------*/
with household as 
(select distinct person1_id, person2_id 
from synth_advancement.constituent_relationship 
where person1_role in ('Spouse','Life Partner')),

school_of_business as (
  select 
  c.constituent_id,
  sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as "Total Amount"
  from synth_advancement.contribution c 
  left join synth_advancement.designation d on c.designation_code = d.designation_code
  
  where d.division = 'School of Business'
  and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')

  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) >= 500
),

no_email_solicit as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and (department = 'School of Business' or department is null)
and c.contact_method in ('All','Email')
and (c.end_date is null or c.end_date >= '2026-09-23')),

no_mail_solicit as (select c.constituent_id
from synth_advancement.contact_preference c 
where c.restriction_type = 'Exclude'
and c.preference_type = 'Solicitations'
and (department = 'School of Business' or department is null)
and c.contact_method in ('All','Letter')
and (c.end_date is null or c.end_date >= '2026-09-23'))

select 
 b.constituent_id,
 c.first_name,
 c.last_name,
 c.org_name,
 spouse.constituent_id as "Spouse ID",
 spouse.first_name as "Spouse First Name",
 spouse.last_name as "Spouse Last Name",
 c.address_line1,
 c.address_city,
 c.address_state,
 c.address_postal_code,
 c.email,
 b."Total Amount" as "Lifetime Giving to School of Business",
 case when ne.constituent_id is null then 'Yes' else 'No' END as SolicitableByEmail,
 case when nm.constituent_id is null then 'Yes' else 'No' END as SolicitableByMail

from school_of_business b 
inner join synth_advancement.Constituent c on b.constituent_id = c.constituent_id
left join household h on b.constituent_id = h.person1_id
left join synth_advancement.constituent spouse on h.person2_id = spouse.constituent_id
left join no_email_solicit ne on ne.constituent_id = b.constituent_id
left join no_mail_solicit nm on nm.constituent_id = b.constituent_id
where b.constituent_id not in (select person2_id from household)
and not c.is_deceased; 


/*--------------------------------------------------------------------------/
  B4 - Who gave last fiscal year but not this fiscal year?
  ANSWER | type: list
  ------------------------------------------------------------------------*/
with ly as (
  select c.constituent_id,
  sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as "Last_Year_Amount"
  from synth_advancement.contribution c 
  where c.fiscal_year = 2026
  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0
),


ty as (
   select c.constituent_id 
  from synth_advancement.contribution c 
  where c.fiscal_year = 2027
  group by c.constituent_id
  having sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) > 0
)

select c.constituent_id, 
c.first_name,
c.last_name,
c.org_name
from ly l
inner join synth_advancement.constituent c on c.constituent_id = l.constituent_id
where 
l.constituent_id not in (select constituent_id from ty)
;


/*--------------------------------------------------------------------------/
  B5 - What is our commitment fundraising total this year so far?
  ANSWER | type: aggregate | published figure: Commitment_Total_FY27
  ------------------------------------------------------------------------*/
select
sum(case when c.contribution_type = 'Pledge' and c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) as total
from synth_advancement.contribution c
where c.fiscal_year =  2027
and c.credit = 'Hard'
and c.contribution_type in ('Pledge','Gift','Bequest Expectancy','Matching Gift' );



