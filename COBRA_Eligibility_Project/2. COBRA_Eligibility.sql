/* =======================================================================
   COBRA Eligibility / Qualifying Event Extract (Compass Data Lake)
   -----------------------------------------------------------------------
   PURPOSE
   - Produces one flattened recordset containing:
       * Employee QB demographics + address + identifiers
       * Dependent demographics + identifiers (if any)
       * Qualifying Event classification (Termination/Retirement/Death/Age-26)
       * PlanName / CoverageLevel / PlanEndDate selection logic
       * Synthetic plans: EAP (always), SMKR (conditional)

   NOTES ON DIALECT
   - Uses Presto/Trino-like functions (date_format, date_sub, LAST_DAY, etc.)
   - Assumes Compass Data Lake tables/views:
       "WorkAssignment_COBRA_V2"
       "Employee_COBRA_V2"
       "EmployeeBenefit_COBRA_V2"
       "Dependent_COBRA_V2"
       etc.

   KEY BUSINESS RULES IMPLEMENTED
   - Only include events in last 21 days OR dependents who aged out (turned 26)
   - Always force EAP plan record (synthetic) for active employees
   - Add Tobacco Surcharge (SMKR) only when Eligibility = 2, then apply
     special suppression rules based on event type and dependent relationship
   ======================================================================= */

WITH
/* =======================================================================
   1) RankedContacts
   -----------------------------------------------------------------------
   - Some contact exports can have multiple rows per employee over time.
   - We keep the most recent contact row by EffectiveDate (rn = 1).
   ======================================================================= */
RankedContacts AS (
    SELECT
        c.*,
        ROW_NUMBER() OVER (
            PARTITION BY c."Employee"
            ORDER BY c."EffectiveDate" DESC
        ) AS rn
    FROM "EmployeeContactExport_COBRA_V2" AS c
),

/* =======================================================================
   2) RankedMedicalBenefits
   -----------------------------------------------------------------------
   - Used as the source for "EnrollmentDate" concept (the medical begin date).
   - Limits to "active-ish" rows where Status = 6 AND medical plan codes.
   - Then ranks newest medical coverage by DateRange.Begin (rn = 1).
   ======================================================================= */
RankedMedicalBenefits AS (
    SELECT
        b.*,
        ROW_NUMBER() OVER (
            PARTITION BY b."Employee"
            ORDER BY b."DateRange.Begin" DESC
        ) AS rn
    FROM "EmployeeBenefit_COBRA_V2" AS b
    WHERE b."Status" = 6
      AND b."BenefitPlan" IN ('BAS','BASN','CLA','CLAN','SAV','SAVN','SVN2','SAV2')
),

/* =======================================================================
   3) LatestMedicalEnd
   -----------------------------------------------------------------------
   - Finds the most recent MEDICAL end date per employee.
   - This is used later as the PlanEndDate for synthetic plans (EAP/SMKR),
     so they end when the employee’s medical ends.
   - Ranking logic:
       * Prefer rows with the latest DateRange.End (NULL treated as 9999-12-31)
       * Tie-breaker: latest DateRange.Begin
   ======================================================================= */
LatestMedicalEnd AS (
    SELECT
        b."Employee",
        b."DateRange.End" AS "MedicalEndDate",
        ROW_NUMBER() OVER (
            PARTITION BY b."Employee"
            ORDER BY
                COALESCE(CAST(b."DateRange.End" AS date), DATE '9999-12-31') DESC,
                CAST(b."DateRange.Begin" AS date) DESC
        ) AS rn
    FROM "EmployeeBenefit_COBRA_V2" b
    WHERE b."Status" = 6
      AND b."BenefitPlan" IN ('BAS','BASN','CLA','CLAN','SAV','SAVN','SVN2','SAV2')
),

/* =======================================================================
   4) LatestWaiveMedicalEnd
   -----------------------------------------------------------------------
   - Fallback path when no “real medical” end date exists.
   - Looks for WAIVE MEDICAL (or WMD) and ranks the latest end date similarly.
   ======================================================================= */
LatestWaiveMedicalEnd AS (
    SELECT
        b."Employee",
        b."DateRange.End" AS "WaiveMedicalEndDate",
        ROW_NUMBER() OVER (
            PARTITION BY b."Employee"
            ORDER BY
                COALESCE(CAST(b."DateRange.End" AS date), DATE '9999-12-31') DESC,
                CAST(b."DateRange.Begin" AS date) DESC
        ) AS rn
    FROM "EmployeeBenefit_COBRA_V2" b
    WHERE b."Status" = 6
      AND UPPER(TRIM(b."BenefitPlan")) IN ('WMD', 'WAIVE MEDICAL')
),

/* =======================================================================
   5) SynthPlanEndDate
   -----------------------------------------------------------------------
   - Establishes ONE end date per active employee for synthetic plans.
   - COALESCE preference:
       1) Most recent medical end date
       2) Else most recent waive-medical end date
   - Filters to active work assignments and excludes Position 3777.
   ======================================================================= */
SynthPlanEndDate AS (
    SELECT
        wa."Employee",
        COALESCE(m."MedicalEndDate", w."WaiveMedicalEndDate") AS "EndDate"
    FROM "WorkAssignment_COBRA_V2" wa
    LEFT JOIN (
        SELECT "Employee","MedicalEndDate"
        FROM LatestMedicalEnd
        WHERE rn = 1
    ) m
        ON m."Employee" = wa."Employee"
    LEFT JOIN (
        SELECT "Employee","WaiveMedicalEndDate"
        FROM LatestWaiveMedicalEnd
        WHERE rn = 1
    ) w
        ON w."Employee" = wa."Employee"
    WHERE wa."Active" = 1
      AND wa."Position" <> 3777
),

/* =======================================================================
   6) SmkrEligible
   -----------------------------------------------------------------------
   - Determines which employees should receive the synthetic SMKR plan.
   - Trigger rule: ANY Status=6 benefit row where Eligibility = 2.
   ======================================================================= */
SmkrEligible AS (
    SELECT DISTINCT
        b."Employee"
    FROM "EmployeeBenefit_COBRA_V2" b
    WHERE b."Status" = 6
      AND b."Eligibility" = 2
),

/* =======================================================================
   7) SmkrCoverage
   -----------------------------------------------------------------------
   - Derives SMKR coverage level from most recent medical coverage option.
   - CoverageOption mapping (as given):
       (3,4) => EE+SPOUSE   (note: 4 is often “family” elsewhere, but you
                           intentionally treat it as spouse here)
       (1,2) => EE
       else  => EE
   - Uses RankedMedicalBenefits rn=1 as “most recent medical”.
   ======================================================================= */
SmkrCoverage AS (
    SELECT
        rm."Employee",
        CASE
            WHEN rm."CoverageOption" IN (3, 4) THEN 'EE+SPOUSE'
            WHEN rm."CoverageOption" IN (1, 2) THEN 'EE'
            ELSE 'EE'
        END AS "SmkrCoverageLevel"
    FROM RankedMedicalBenefits rm
    WHERE rm.rn = 1
),

/* =======================================================================
   8) RankedPlanByName
   -----------------------------------------------------------------------
   GOAL: Return at most ONE plan row per employee PER carrier “bucket”.
   Carriers:
     - ANTHEM (vision)
     - CIGNA  (medical)
     - DELTA  (dental)
     - EAP    (synthetic)
     - SMKR   (synthetic)

   HOW IT WORKS
   - Builds a unioned dataset "x" with:
       A) Real benefit rows where Status=6, mapped to PlanName/CoverageLevel
       B) Forced EAP row for every active employee
       C) Conditional SMKR row for eligible employees
   - Adds SourceRank so “real plans” win when ranking, then EAP, then SMKR.
   - Applies ROW_NUMBER partitioned by (Employee, PlanCarrier) so we retain
     exactly one “best” row for each carrier group (rn=1).
   ======================================================================= */
RankedPlanByName AS (
    SELECT
        x."Employee",
        x."BenefitPlan",
        x."CoverageOption",
        x."DateRange.Begin",
        x."DateRange.End",
        x."PlanName",
        x."CoverageLevel",
        x."PlanCarrier",
        ROW_NUMBER() OVER (
            PARTITION BY x."Employee", x."PlanCarrier"
            ORDER BY
                x."SourceRank" ASC,
                COALESCE(CAST(x."DateRange.End" AS date), DATE '9999-12-31') DESC,
                CAST(x."DateRange.Begin" AS date) DESC
        ) AS rn
    FROM (
        /* ---------------------------------------------------------------
           8A) REAL benefit rows (Status=6)
           --------------------------------------------------------------- */
        SELECT
            b."Employee",
            b."BenefitPlan",
            b."CoverageOption",
            b."DateRange.Begin",
            b."DateRange.End",

            /* Map benefit codes to the vendor-required PlanName strings */
            CASE
                WHEN b."BenefitPlan" IN ('VIS1', 'VIS2')
                    THEN 'ANTHEM BLUE VIEW VISION PLAN'
                WHEN b."BenefitPlan" IN ('BAS', 'BASN')
                    THEN 'CIGNA BASIC MEDICAL PLAN WITH HRA'
                WHEN b."BenefitPlan" IN ('CLA', 'CLAN')
                    THEN 'CIGNA CLASSIC MEDICAL PLAN WITH HRA'
                WHEN b."BenefitPlan" IN ('SAV', 'SAVN', 'SVN2', 'SAV2')
                    THEN 'CIGNA SAVER MEDICAL PLAN'
                WHEN b."BenefitPlan" IN ('DEN5', 'DEN7')
                    THEN 'DELTA DENTAL BUY-UP PLAN #7714'
                WHEN b."BenefitPlan" IN ('DEN6', 'DEN8')
                    THEN 'DELTA STANDARD DENTAL PLAN #7716'
                ELSE NULL
            END AS "PlanName",

            /* Convert numeric CoverageOption to import CoverageLevel strings */
            CASE
                WHEN b."CoverageOption" = 1 THEN 'EE'
                WHEN b."CoverageOption" = 2 THEN 'EE+CHILDREN'
                WHEN b."CoverageOption" = 3 THEN 'EE+SPOUSE'
                WHEN b."CoverageOption" = 4 THEN 'EE+FAMILY'
                ELSE NULL
            END AS "CoverageLevel",

            /* Bucket into carrier groups (used for picking “one row per carrier”) */
            CASE
                WHEN b."BenefitPlan" IN ('VIS1', 'VIS2') THEN 'ANTHEM'
                WHEN b."BenefitPlan" IN ('BAS','BASN','CLA','CLAN','SAV','SAVN','SVN2','SAV2')
                    THEN 'CIGNA'
                WHEN b."BenefitPlan" IN ('DEN5','DEN7','DEN6','DEN8')
                    THEN 'DELTA'
                ELSE NULL
            END AS "PlanCarrier",

            /* SourceRank: real benefits take precedence */
            1 AS "SourceRank"
        FROM "EmployeeBenefit_COBRA_V2" AS b
        WHERE b."Status" = 6

        UNION ALL

        /* ---------------------------------------------------------------
           8B) FORCED EAP for EVERY employee (synthetic)
           --------------------------------------------------------------- */
        SELECT
            sp."Employee",
            CAST(NULL AS VARCHAR)  AS "BenefitPlan",
            CAST(NULL AS INTEGER)  AS "CoverageOption",
            CAST(NULL AS date)     AS "DateRange.Begin",
            CAST(sp."EndDate" AS date) AS "DateRange.End",
            'EMPLOYEE ASSISTANCE PROGRAM (EAP)' AS "PlanName",
            'EE+FAMILY' AS "CoverageLevel",
            'EAP' AS "PlanCarrier",
            2 AS "SourceRank"
        FROM SynthPlanEndDate sp

        UNION ALL

        /* ---------------------------------------------------------------
           8C) CONDITIONAL SMKR (synthetic): only when Eligibility = 2
           --------------------------------------------------------------- */
        SELECT
            sp."Employee",
            CAST(NULL AS VARCHAR)  AS "BenefitPlan",
            CAST(NULL AS INTEGER)  AS "CoverageOption",
            CAST(NULL AS date)     AS "DateRange.Begin",
            CAST(sp."EndDate" AS date) AS "DateRange.End",
            'Tobacco Surcharge' AS "PlanName",
            COALESCE(sc."SmkrCoverageLevel", 'EE') AS "CoverageLevel",
            'SMKR' AS "PlanCarrier",
            3 AS "SourceRank"
        FROM SynthPlanEndDate sp
        INNER JOIN SmkrEligible se
            ON se."Employee" = sp."Employee"
        LEFT JOIN SmkrCoverage sc
            ON sc."Employee" = sp."Employee"
    ) x
    WHERE x."PlanCarrier" IS NOT NULL
),

/* =======================================================================
   9) IneligibleDependents
   -----------------------------------------------------------------------
   - Identifies dependents who turned 26 within the last 21 days.
   - Also ensures:
       * dependent is NOT disabled (Disabled NULL/0/1 treated as not disabled)
       * employee RelationshipStatus in ('AR','AO','AS','LB')
   - Window logic supports year-boundary crossing (e.g., Dec/Jan).
   - Output: distinct (Employee, Dependent) pairs for later join.
   ======================================================================= */

IneligibleDependents AS (
    SELECT DISTINCT
        d."Employee",
        d."Dependent"
    FROM "Dependent_COBRA_V2" d
    JOIN "Employee_COBRA_V2" e
        ON e."Employee" = d."Employee"
    WHERE d."Dependent" IS NOT NULL
      AND d."Birthdate" IS NOT NULL

      /* ✅ Only age-out CHILD dependents */
      AND UPPER(TRIM(d."Relationship")) IN (
          'ADPDTR','ADPSN','DAUGHTER','DEC CHILD','LEGAL CUST',
          'NEPHEW','SON','SP EQUIV','STPDTR','STPSN'
      )

      /* ✅ Never allow these spouse-like codes under any circumstances */
      AND UPPER(TRIM(d."Relationship")) NOT IN ('SPOUSE-EE', 'CU PRTNR', 'SPOUSE')

      /* Existing rules */
      AND (d."Disabled" IS NULL OR d."Disabled" IN (0, 1))
      AND e."RelationshipStatus" IN ('AR','AO','AS','LB')
      AND (
            /* Case A: window does NOT cross year boundary */
            (
                CAST(date_format(date_sub(CURRENT_DATE, 21), 'MMdd') AS int)
                    <= CAST(date_format(CURRENT_DATE, 'MMdd') AS int)
                AND CAST(date_format(CAST(d."Birthdate" AS date), 'MMdd') AS int)
                    BETWEEN CAST(date_format(date_sub(CURRENT_DATE, 21), 'MMdd') AS int)
                        AND CAST(date_format(CURRENT_DATE, 'MMdd') AS int)
                AND (CAST(date_format(CAST(d."Birthdate" AS date), 'yyyy') AS int) + 26)
                    = CAST(date_format(CURRENT_DATE, 'yyyy') AS int)
            )
            OR
            /* Case B: window DOES cross year boundary */
            (
                CAST(date_format(date_sub(CURRENT_DATE, 21), 'MMdd') AS int)
                    > CAST(date_format(CURRENT_DATE, 'MMdd') AS int)
                AND (
                    /* B1: birthday falls in “end of prior year” */
                    (
                        CAST(date_format(CAST(d."Birthdate" AS date), 'MMdd') AS int)
                            >= CAST(date_format(date_sub(CURRENT_DATE, 21), 'MMdd') AS int)
                        AND (CAST(date_format(CAST(d."Birthdate" AS date), 'yyyy') AS int) + 26)
                            = CAST(date_format(date_sub(CURRENT_DATE, 21), 'yyyy') AS int)
                    )
                    OR
                    /* B2: birthday falls in “current year” */
                    (
                        CAST(date_format(CAST(d."Birthdate" AS date), 'MMdd') AS int)
                            <= CAST(date_format(CURRENT_DATE, 'MMdd') AS int)
                        AND (CAST(date_format(CAST(d."Birthdate" AS date), 'yyyy') AS int) + 26)
                            = CAST(date_format(CURRENT_DATE, 'yyyy') AS int)
                    )
                )
            )
      )
)

/* =======================================================================
   FINAL SELECT
   -----------------------------------------------------------------------
   - Produces output rows for employees with qualifying events in last 21 days,
     plus dependents aging out (ineligible dependents).
   - LEFT joining dependents means employees can appear multiple times:
       * one row per dependent (including NULL dependent row)
       * plus plan selection (limited by RankedPlanByName rn=1)
   - DISTINCT applied to reduce duplicates produced by joins.
   ======================================================================= */
SELECT DISTINCT
    /* -----------------------------
       Hard-coded client identifiers
       ----------------------------- */
    'COLORADO SPRINGS UTILITIES' AS "ClientName",
    'COLORADO SPRINGS UTILITIES' AS "ClientDivisionName",

    /* -----------------------------
       Employee QB identity fields
       ----------------------------- */
    NULLIF(TRIM(e."Name.GivenName"), '') AS "FirstName",
    NULLIF(TRIM(e."Name.FamilyName"), '') AS "LastName",
    REPLACE(id."IdentificationNumberDisplay", '-', '') AS "SSN",

    
    /* -----------------------------
      Employee address fields
      ----------------------------- */
    NULLIF(TRIM(e."Employee.CSUAddress1"), '') AS "Address1",
    NULLIF(TRIM(e."Employee.CSUAddress2"), '') AS "Address2",
    NULLIF(TRIM(e."Employee.CSUCity"), '') AS "City",
    NULLIF(TRIM(e."Employee.CSUState"), '') AS "StateOrProvince",
    NULLIF(TRIM(e."Employee.CSUZip"), '') AS "PostalCode",
    '' AS "Country",


    /* -----------------------------
       Employee demographic mappings
       ----------------------------- */
    CASE
        WHEN e."Gender" = 3 THEN 'M'
        WHEN e."Gender" = 2 THEN 'F'
        ELSE 'U'
    END AS "Sex",

    date_format(CAST(e."Birthdate" AS date), 'MM/dd/yyyy') AS "DOB",

    CASE
        WHEN e."Smoker" = 1 THEN 'YES'
        WHEN e."Smoker" = 0 THEN 'NO'
        ELSE 'UNKNOWN'
    END AS "TobaccoUse",

    /* EmployeeType is hardcoded UNKNOWN in this version */
    'UNKNOWN' AS "EmployeeType",

    CASE
        WHEN wa."ExemptFromOvertime" = 2 THEN 'EXEMPT'
        WHEN wa."ExemptFromOvertime" = 1 THEN 'NONEXEMPT'
        ELSE 'UNKNOWN'
    END AS "EmployeePayrollType",

    /* -----------------------------
       Import configuration fields
       ----------------------------- */
    'COUPONBOOK' AS "PremiumCouponType",
    'FALSE' AS "UsesHCTC",
    'TRUE' AS "Active",
    'TRUE' AS "AllowMemberSSO",

    /* ===================================================================
       EventType determination:
       - If dependent aged-out flagged => INELIGIBLEDEPENDENT
       - Else based on employee RelationshipStatus codes
       =================================================================== */
    CASE
        WHEN ao."Employee" IS NOT NULL THEN 'INELIGIBLEDEPENDENT'
        WHEN e."RelationshipStatus" = 'DE' THEN 'DEATH'
        WHEN e."RelationshipStatus" IN ('RI', 'RN', 'RE') THEN 'RETIREMENT'
        WHEN e."RelationshipStatus" IN ('SI', 'SP') THEN 'TERMINATION'
        ELSE NULL
    END AS "EventType",

    /* ===================================================================
       EventDate:
       - For ineligible dependents: last day of the month they turn 26
       - Otherwise: last day of the employee's termination month
       =================================================================== */
    CASE
        WHEN ao."Employee" IS NOT NULL
        THEN date_format(
                 LAST_DAY(
                     date_add('year', 26, CAST(d."Birthdate" AS date))
                 ),
                 'MM/dd/yyyy'
             )
        ELSE date_format(
                 LAST_DAY(CAST(e."TerminationDate" AS date)),
                 'MM/dd/yyyy'
             )
    END AS "EventDate",

    /* Enrollment date concept sourced from most recent medical begin date */
    date_format(CAST(rm."DateRange.Begin" AS date), 'MM/dd/yyyy') AS "DependentEnrollmentDate",

    /* Provide employee identity for dependent-type events as well */
    REPLACE(id."IdentificationNumberDisplay", '-', '') AS "EmployeeSSN",
    e."Employee" AS "EmployeeID",
    TRIM(
        CONCAT_WS(
            ' ',
            NULLIF(TRIM(e."Name.GivenName"), ''),
            NULLIF(TRIM(e."Name.MiddleName"), ''),
            NULLIF(TRIM(e."Name.FamilyName"), '')
        )
    ) AS "EmployeeName",

    '' AS "SecondEventOriginalFDOC",

    /* ===================================================================
       PLAN OUTPUT (QBPLANINITIAL-like)
       - Applies special SMKR suppression rules
       - Applies dependent filtering rules (only show plan when EE+FAMILY or
         EE+CHILDREN for dependent rows)
       =================================================================== */
    CASE
        /* Dependents only get plan rows when coverage includes children */
        WHEN d."Dependent" IS NOT NULL
             AND bp."CoverageLevel" NOT IN ('EE+FAMILY', 'EE+CHILDREN')
        THEN NULL

        /* Never show SMKR plan for ineligible dependent event */
        WHEN bp."PlanName" = 'Tobacco Surcharge'
             AND ao."Employee" IS NOT NULL
        THEN NULL

        /* For TERMINATION events, allow SMKR only for EE or EE+SPOUSE,
           and if dependent row then only spouse-like relationship */
        WHEN bp."PlanName" = 'Tobacco Surcharge'
             AND e."RelationshipStatus" IN ('SI','SP')
             AND e."TerminationDate" IS NOT NULL
             AND CAST(e."TerminationDate" AS date) >= date_sub(CURRENT_DATE, 21)
             AND CAST(e."TerminationDate" AS date) <= CURRENT_DATE
             AND bp."CoverageLevel" IN ('EE','EE+SPOUSE')
             AND (
                 d."Dependent" IS NULL
                 OR d."Relationship" IN ('SPOUSE','SPOUSE-EE','CU PRTNR','EX-SPOUSE')
             )
        THEN bp."PlanName"

        /* All other SMKR: suppress */
        WHEN bp."PlanName" = 'Tobacco Surcharge'
        THEN NULL

        /* Non-SMKR: pass through */
        ELSE bp."PlanName"
    END AS "PlanName",

    CASE
        WHEN d."Dependent" IS NOT NULL
             AND bp."CoverageLevel" NOT IN ('EE+FAMILY', 'EE+CHILDREN')
        THEN NULL

        WHEN bp."PlanName" = 'Tobacco Surcharge'
             AND ao."Employee" IS NOT NULL
        THEN NULL

        WHEN bp."PlanName" = 'Tobacco Surcharge'
             AND e."RelationshipStatus" IN ('SI','SP')
             AND e."TerminationDate" IS NOT NULL
             AND CAST(e."TerminationDate" AS date) >= date_sub(CURRENT_DATE, 21)
             AND CAST(e."TerminationDate" AS date) <= CURRENT_DATE
             AND bp."CoverageLevel" IN ('EE','EE+SPOUSE')
             AND (
                 d."Dependent" IS NULL
                 OR d."Relationship" IN ('SPOUSE','SPOUSE-EE','CU PRTNR','EX-SPOUSE')
             )
        THEN bp."CoverageLevel"

        WHEN bp."PlanName" = 'Tobacco Surcharge'
        THEN NULL

        ELSE bp."CoverageLevel"
    END AS "CoverageLevel",

    CASE
        WHEN d."Dependent" IS NOT NULL
             AND bp."CoverageLevel" NOT IN ('EE+FAMILY', 'EE+CHILDREN')
        THEN NULL

        WHEN bp."PlanName" = 'Tobacco Surcharge'
             AND ao."Employee" IS NOT NULL
        THEN NULL

        WHEN bp."PlanName" = 'Tobacco Surcharge'
             AND e."RelationshipStatus" IN ('SI','SP')
             AND e."TerminationDate" IS NOT NULL
             AND CAST(e."TerminationDate" AS date) >= date_sub(CURRENT_DATE, 21)
             AND CAST(e."TerminationDate" AS date) <= CURRENT_DATE
             AND bp."CoverageLevel" IN ('EE','EE+SPOUSE')
             AND (
                 d."Dependent" IS NULL
                 OR d."Relationship" IN ('SPOUSE','SPOUSE-EE','CU PRTNR','EX-SPOUSE')
             )
        THEN date_format(CAST(bp."DateRange.End" AS date), 'MM/dd/yyyy')

        WHEN bp."PlanName" = 'Tobacco Surcharge'
        THEN NULL

        ELSE date_format(CAST(bp."DateRange.End" AS date), 'MM/dd/yyyy')
    END AS "PlanEndDate",

    /* -----------------------------
       Dependent identity fields
       ----------------------------- */
    REPLACE(din."IdentificationNumberDisplay", '-', '') AS "DependentSSN",

    /* Relationship mapping: normalize to SPOUSE/CHILD buckets */
    CASE
        WHEN d."Relationship" IN ('CU PRTNR','DEC SPOUSE','EX-SPOUSE','SPOUSE','SPOUSE-EE')
            THEN 'SPOUSE'
        WHEN d."Relationship" IN ('ADPDTR','ADPSN','DAUGHTER','DEC CHILD','LEGAL CUST',
                                  'NEPHEW','SON','SP EQUIV','STPDTR','STPSN')
            THEN 'CHILD'
        ELSE d."Relationship"
    END AS "DependentRelationship",

    NULLIF(TRIM(d."Name.GivenName"), '') AS "DependentFirstName",
    NULLIF(TRIM(d."Name.FamilyName"), '') AS "DependentLastName",

    /* Dependent address fields are intentionally blanked in this output */
    'TRUE' AS "DependentAddressSameAsQB",
    '' AS "DependentAddress1",
    '' AS "DependentAddress2",
    '' AS "DependentCity",
    '' AS "DependentStateOrProvince",
    '' AS "DependentPostalCode",
    '' AS "DependentCountry",

    CASE
        WHEN d."DependentGender" = 3 THEN 'M'
        WHEN d."DependentGender" = 2 THEN 'F'
        ELSE 'U'
    END AS "DependentSex",

    date_format(CAST(d."Birthdate" AS date), 'MM/dd/yyyy') AS "DependentDOB",

    /* Approximate age calculation accounting for birthday not yet occurred this year */
    CAST(date_format(CURRENT_DATE, 'yyyy') AS int)
    - CAST(date_format(CAST(d."Birthdate" AS date), 'yyyy') AS int)
    - CASE
        WHEN date_format(CURRENT_DATE, 'MMdd') < date_format(CAST(d."Birthdate" AS date), 'MMdd')
          THEN 1
        ELSE 0
      END AS "DependentAge",

    NULL AS "IsDependentQMCSO",

/* Disabled status should only be provided for CHILD dependents */
CASE
    WHEN d."Relationship" IN (
        'ADPDTR','ADPSN','DAUGHTER','DEC CHILD','LEGAL CUST',
        'NEPHEW','SON','SP EQUIV','STPDTR','STPSN'
    )
    THEN CASE
        WHEN d."Disabled" = 2 THEN 'TRUE'
        ELSE 'FALSE'
    END
    ELSE NULL
END AS "IsDisabledDependent"

FROM "WorkAssignment_COBRA_V2" AS wa
JOIN "Employee_COBRA_V2" AS e
    ON wa."Employee" = e."Employee"

LEFT JOIN "EmployeeIdentificationNumber_COBRA_V2" AS id
    ON e."Employee" = id."Employee"

LEFT JOIN RankedContacts AS rc
    ON e."Employee" = rc."Employee"
   AND rc.rn = 1

LEFT JOIN RankedMedicalBenefits AS rm
    ON rm."Employee" = e."Employee"
   AND rm.rn = 1

/* NOTE: This join selects only ONE carrier-bucket row overall because
   you filter bp.rn = 1 (but rn is per carrier in the CTE). If you ever
   need one row per carrier (e.g., output multiple plan lines), you would
   remove this rn filter and emit multiple rows or pivot them. */
LEFT JOIN RankedPlanByName AS bp
    ON bp."Employee" = e."Employee"
   AND bp.rn = 1

LEFT JOIN "Dependent_COBRA_V2" AS d
    ON d."Employee" = e."Employee"

LEFT JOIN "DependentIdentificationNumber_COBRA_V2" AS din
    ON din."Dependent" = d."Dependent"
   AND din."Employee"  = d."Employee"

LEFT JOIN IneligibleDependents ao
    ON ao."Employee" = d."Employee"
   AND ao."Dependent" = d."Dependent"

WHERE
    /* Only active work assignments; exclude position 3777 */
    wa."Active" = 1
    AND wa."Position" <> 3777

    /* Include if employee had a qualifying event in last 21 days OR
       dependent aged out (ao join hit) */
    AND (
        /* (1) Termination events in last 21 days */
        (
            e."RelationshipStatus" IN ('SI', 'SP')
            AND e."TerminationDate" IS NOT NULL
            AND CAST(e."TerminationDate" AS date) >= date_sub(CURRENT_DATE, 21)
            AND CAST(e."TerminationDate" AS date) <= CURRENT_DATE
        )
        OR
        /* (2) Death events in last 21 days */
        (
            e."RelationshipStatus" = 'DE'
            AND e."TerminationDate" IS NOT NULL
            AND CAST(e."TerminationDate" AS date) >= date_sub(CURRENT_DATE, 21)
            AND CAST(e."TerminationDate" AS date) <= CURRENT_DATE
        )
        OR
        /* (3) Retirement events in last 21 days */
        (
            e."RelationshipStatus" IN ('RI','RN','RE')
            AND e."TerminationDate" IS NOT NULL
            AND CAST(e."TerminationDate" AS date) >= date_sub(CURRENT_DATE, 21)
            AND CAST(e."TerminationDate" AS date) <= CURRENT_DATE
        )
        OR
        /* (4) Age-26 ineligible dependents */
        ao."Employee" IS NOT NULL
    );
