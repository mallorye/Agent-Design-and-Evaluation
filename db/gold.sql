/***********************************************************************************/
-- 'Golden' sql for the Eval set v1 minus abstain
-- Mallory Berg
-- WIP: gold SQL, task 1 of 25




--  Please provide a list of parents who gave $1,000 in the last two years.
with parents as(
    select distinct person1_id from synth_advancement.constituent_relationship 
    where person1_role = 'Parent' 
),

last_two_years_1000 as(
    select c.constituent_id, 
    sum(case when c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) 
    from synth_advancement.contribution c 
    where c.fiscal_year in (2025,2026)
    and c.contribution_type in ('Pledge', 'Matching Gift', 'Gift','Bequest Expectancy')
    group by c.constituent_id
    having sum(case when c.pledge_status = 'Canceled' then c.pledge_amount_paid else c.amount END) >= 1000 
   
)

select c.first_name, c.last_name , t.*
from synth_advancement.constituent c
inner join parents p on c.constituent_id = p.person1_id
inner join last_two_years_1000 t on t.constituent_id = p.person1_id


