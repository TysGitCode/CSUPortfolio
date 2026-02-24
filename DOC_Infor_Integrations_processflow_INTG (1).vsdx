"""COBRACLEAN.py

COBRA QB Import File Builder (Compass -> Vendor Import)
======================================================

WHAT THIS SCRIPT DOES
---------------------
This script converts a *row-based* Compass export (cobra_raw.csv) into a
*segment-based* COBRA QB Import file (cobra_out.csv) using the record
identifiers described in the QB Import Specification (e.g., [VERSION], [QB],
[QBEVENT], [QBPLANINITIAL], [QBDEPENDENT], [QBDEPENDENTPLANINITIAL]).

WHY THIS EXISTS
---------------
The Compass export is typically a flattened table with one row per
(Employee + optional Dependent + optional Plan). Vendor imports, however,
expect a hierarchical file where each Qualified Beneficiary (QB) begins with
one [QB] line, followed by a [QBEVENT] line, followed by one or more plan
and dependent segment lines.

HIGH-LEVEL ALGORITHM
--------------------
1) Read cobra_raw.csv (skipping the first line if it is the Excel hint: sep=,)
2) Group rows by EmployeeID
3) For each employee group:
   a) Emit [QB] from the first row in that group
   b) Emit [QBEVENT] from the first row in that group
   c) Emit one [QBPLANINITIAL] line per distinct (PlanName, CoverageLevel)
   d) For each dependent (grouped by DependentSSN):
      i) Emit [QBDEPENDENT]
     ii) Emit one [QBDEPENDENTPLANINITIAL] per distinct PlanName

IMPORTANT DATA CONTRACT (INPUT)
-------------------------------
The script assumes cobra_raw.csv already contains the columns that your
Compass SQL export produces (examples):
  - EmployeeID, ClientName, ClientDivisionName, FirstName, LastName, SSN
  - Address1, Address2, City, StateOrProvince, PostalCode, Country
  - PremiumAddressSameAsPrimary, Sex, DOB, TobaccoUse
  - EmployeeType, EmployeePayrollType, PremiumCouponType, UsesHCTC, Active,
    AllowMemberSSO
  - EventType, EventDate, DependentEnrollmentDate, EmployeeSSN, EmployeeName
  - PlanName, CoverageLevel
  - DependentSSN, DependentRelationship, DependentFirstName, DependentLastName,
    DependentSex, DependentDOB, IsDisabledDependent

If any of these columns are missing or named differently, the script will raise
KeyError during indexing (e.g., p["EmployeeID"]).

OUTPUT
------
Writes cobra_out.csv using csv.writer with:
  - First line: sep=,
  - Second line: [VERSION],1.2
  - Then repeating QB blocks as described above.

MAINTENANCE NOTES
-----------------
- The exact field ordering in each segment is critical. The vendor parser
  expects specific column positions.
- Several fields are intentionally blank (""), used as placeholders to keep
  downstream columns aligned.

"""

import pandas as pd
import csv

# ---------------------------------------------------------------------------
# File paths (relative to the working directory)
# ---------------------------------------------------------------------------
INPUT_CSV = "cobra_raw.csv"   # Compass extract (flattened rows)
OUTPUT_CSV = "cobra_out.csv"  # Vendor-ready QB Import output (segmented)


def fmt_ssn(ssn: str) -> str:
    """Normalize Social Security Numbers.

    The vendor import accepts SSN values either with or without dashes,
    but downstream processes frequently prefer 9 digits with no punctuation.

    Rules implemented:
    - If the value can be normalized to exactly 9 digits, return those 9 digits.
    - Otherwise, return the trimmed original string.

    Parameters
    ----------
    ssn : str
        Value from the input file (may be blank, NaN, numeric-as-string, etc.)

    Returns
    -------
    str
        Normalized SSN string.
    """

    # Ensure we are working with a string representation
    if not isinstance(ssn, str):
        ssn = "" if pd.isna(ssn) else str(ssn)

    # Remove dashes and whitespace
    s = ssn.replace("-", "").strip()

    # Keep only valid 9-digit numbers; otherwise return original trimmed
    if len(s) == 9 and s.isdigit():
        return s
    return ssn.strip()


def main():
    """Main entrypoint.

    Reads the Compass extract, writes a segment-based QB Import file.
    """

    # -----------------------------------------------------------------------
    # 1) Read CSV
    # -----------------------------------------------------------------------
    # Many of the exported CSVs include a first line: "sep=,"
    # which is an Excel hint. We skip that line.
    df = pd.read_csv(INPUT_CSV, skiprows=1, dtype=str)

    # Replace NaN with empty strings so downstream indexing is consistent
    df = df.fillna("")

    # Stable sort keeps deterministic output ordering across runs.
    # mergesort is stable (preserves input order for ties).
    df = df.sort_values(
        by=["EmployeeID", "DependentSSN", "PlanName", "CoverageLevel"],
        kind="mergesort"
    )

    # -----------------------------------------------------------------------
    # 2) Open output writer
    # -----------------------------------------------------------------------
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Optional: Excel separator hint line, matching typical inbound format
        writer.writerow(["sep=,"])

        # VERSION record required by the QB Import Specification
        writer.writerow(["[VERSION]", "1.2"])

        # -------------------------------------------------------------------
        # 3) Process one employee (QB) at a time
        # -------------------------------------------------------------------
        for emp_id, emp_df in df.groupby("EmployeeID", sort=True):
            emp_df = emp_df.copy()

            # Sort rows inside employee group to keep plan/dependent ordering
            emp_df = emp_df.sort_values(
                by=["PlanName", "DependentLastName", "DependentFirstName", "DependentSSN"],
                kind="mergesort"
            )

            # First row contains the employee/QB-level columns we need
            p = emp_df.iloc[0]

            # ===============================================================
            # [QB] segment
            # ---------------------------------------------------------------
            # The [QB] record describes the Qualified Beneficiary (QB).
            # Many optional columns are left blank here (""), which act as
            # placeholder columns to match the vendor’s required layout.
            # ===============================================================
            qb_row = [
                "[QB]",
                p["ClientName"],
                p["ClientDivisionName"],
                "",                    # Salutation (unused)
                p["LastName"],
                "",                    # MiddleInitial (unused)
                p["FirstName"],
                fmt_ssn(p["SSN"]),      # SSN (no dashes when possible)
                "",                    # IndividualID (unused here)
                "",                    # Email (not included in this script)
                "",                    # Phone 1
                "",                    # Phone 2
                "",                    # filler column (alignment)
                p["Address1"],
                p["Address2"],
                p["City"],
                p["StateOrProvince"],
                p["PostalCode"],
                p["Country"],
                "TRUE" if p["PremiumAddressSameAsPrimary"].upper() == "TRUE" else "FALSE",

                # Deprecated premium address fields (kept as placeholders)
                "", "", "", "", "", "",

                # Demographics
                p["Sex"],
                p["DOB"],
                p["TobaccoUse"],

                # Employment descriptors
                p["EmployeeType"],
                p["EmployeePayrollType"],

                # Event-related placeholder
                p["SecondEventOriginalFDOC"],

                # Billing / flags
                p["PremiumCouponType"],
                p["UsesHCTC"].lower() if p["UsesHCTC"] else "",
                p["Active"].lower() if p["Active"] else "",
                p["AllowMemberSSO"].lower() if p["AllowMemberSSO"] else "",

                # Trailing placeholders (alignment)
                "", ""
            ]
            writer.writerow(qb_row)

            # ===============================================================
            # [QBEVENT] segment
            # ---------------------------------------------------------------
            # This record describes the qualifying event triggering COBRA.
            # The script passes EventType/EventDate/EnrollmentDate through
            # directly from the Compass extract.
            # ===============================================================
            event_row = [
                "[QBEVENT]",
                p["EventType"],                # EventType (TERMINATION, DEATH, etc.)
                p["EventDate"],                # EventDate (MM/DD/YYYY)
                p["DependentEnrollmentDate"],  # EnrollmentDate / FDOC source
                fmt_ssn(p["EmployeeSSN"]),     # Employee SSN (no dashes)
                p["EmployeeName"],             # Employee full name
                "", "", ""                   # filler columns
            ]
            writer.writerow(event_row)

            # ===============================================================
            # [QBPLANINITIAL] segments (employee-level plans)
            # ---------------------------------------------------------------
            # Emit one plan row per distinct (PlanName, CoverageLevel)
            # for the employee.
            # ===============================================================
            emp_plans = (
                emp_df[emp_df["PlanName"] != ""]
                .loc[:, ["PlanName", "CoverageLevel"]]
                .drop_duplicates()
            )
            for _, row in emp_plans.iterrows():
                writer.writerow([
                    "[QBPLANINITIAL]",
                    row["PlanName"],
                    row["CoverageLevel"]
                ])

            # ===============================================================
            # Dependent segments
            # ---------------------------------------------------------------
            # Dependents are identified by DependentSSN.
            # For each dependent we output:
            #   - One [QBDEPENDENT] line
            #   - One or more [QBDEPENDENTPLANINITIAL] lines
            # ===============================================================
            deps = emp_df[emp_df["DependentSSN"] != ""]

            for dep_ssn, dep_df in deps.groupby("DependentSSN", sort=True):
                dep_df = dep_df.copy().sort_values(
                    by=["PlanName", "CoverageLevel"],
                    kind="mergesort"
                )
                d = dep_df.iloc[0]

                # -----------------------------------------------------------
                # [QBDEPENDENT] segment
                # -----------------------------------------------------------
                # Notes from prior fixes:
                # - Age REMOVED from output; we leave a blank placeholder column
                #   to maintain expected downstream column positions.
                # - Uses employee address for dependent (AddressSameAsQB=TRUE).
                # -----------------------------------------------------------
                qbdep_row = [
                    "[QBDEPENDENT]",
                    fmt_ssn(d["DependentSSN"]),       # Dependent SSN (no dashes)
                    d["DependentRelationship"],       # Relationship (SPOUSE/CHILD)
                    "",                               # Salutation/Title
                    d["DependentFirstName"],          # First
                    "",                               # Middle
                    d["DependentLastName"],           # Last

                    # Placeholders for optional ID/email/phone fields
                    "", "", "",

                    "TRUE",                           # AddressSameAsQB
                    p["Address1"],                    # Use employee address
                    p["Address2"],
                    p["City"],
                    p["StateOrProvince"],
                    p["PostalCode"],
                    p["Country"],

                    "",                               # Extra address placeholder
                    d["DependentSex"],                # Sex
                    d["DependentDOB"],                # DOB

                    "",                               # Placeholder (was Age)
                    d["IsDisabledDependent"]          # Disabled flag
                ]
                writer.writerow(qbdep_row)

                # -----------------------------------------------------------
                # [QBDEPENDENTPLANINITIAL] segments
                # -----------------------------------------------------------
                # Emit one row per distinct dependent PlanName.
                # CoverageLevel is not included in this segment by spec.
                dep_plans = (
                    dep_df[dep_df["PlanName"] != ""]
                    .loc[:, ["PlanName"]]
                    .drop_duplicates()
                )
                for _, prow in dep_plans.iterrows():
                    writer.writerow([
                        "[QBDEPENDENTPLANINITIAL]",
                        prow["PlanName"]
                    ])


if __name__ == "__main__":
    main()
