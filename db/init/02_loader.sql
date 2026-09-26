/* =============================================================================
   Advancement — Synthetic Dataset Loader
   -----------------------------------------------------------------------------
   Context : PostgreSQL 15+ 
          
             Tested on PostgreSQL 18
   Purpose : Loads CSVs into the tables created by 01_schema.sql
   Tables  : designation              (lookup)
             constituent              (hub)
             contribution             (fact; FKs to constituent + designation)
             contact_preference       (1:N from constituent)
             constituent_relationship (self-referencing M:N on constituent)
             degree
   
   ============================================================================= */

-- Parent table: Designation
--66
COPY synth_advancement.designation (designation_code,designation_name,division,department,is_active,desgtype,areaofgiving)
FROM  '/docker-entrypoint-initdb.d/data/designation.csv' 
WITH (FORMAT csv, HEADER MATCH);

--500
COPY synth_advancement.constituent (constituent_id,entity_type,first_name,preferred_name,last_name,org_name,primary_affiliation,email,address_line1,address_city,address_state,address_postal_code,address_country,constituent_status,is_deceased,deceased_date)
FROM  '/docker-entrypoint-initdb.d/data/constituent.csv' 
WITH (FORMAT csv, HEADER MATCH);

--3328
COPY synth_advancement.contribution (contribution_number,constituent_id,credit,designation_code,contribution_date,contribution_type,amount,pledge_number,pledge_status,pledge_amount_paid,pledge_balance,payment_type,is_anonymous)
FROM  '/docker-entrypoint-initdb.d/data/contribution.csv' 
WITH (FORMAT csv, HEADER MATCH);

--185
COPY synth_advancement.contact_preference (contact_preference_id,constituent_id,preference_type,restriction_type,contact_method,department,end_date)
FROM  '/docker-entrypoint-initdb.d/data/contact_preference.csv' 
WITH (FORMAT csv, HEADER MATCH);

--141
COPY synth_advancement.constituent_relationship (person1_id,person1_role,person2_id,person2_role)
FROM  '/docker-entrypoint-initdb.d/data/constituent_relationship.csv' 
WITH (FORMAT csv, HEADER MATCH);

--310
COPY synth_advancement.degree (constituent_id,division,department,college,major,degree_awarded,graduation_date,graduation_year)
FROM  '/docker-entrypoint-initdb.d/data/degree.csv' 
WITH (FORMAT csv, HEADER MATCH);


--- Identity Reset -- Constituent & contact_preference
SELECT setval(pg_get_serial_sequence('synth_advancement.constituent','constituent_id'),
            (SELECT max(constituent_id) from synth_advancement.constituent));

SELECT setval(pg_get_serial_sequence('synth_advancement.contact_preference','contact_preference_id'),
            (SELECT max(contact_preference_id) from synth_advancement.contact_preference));
