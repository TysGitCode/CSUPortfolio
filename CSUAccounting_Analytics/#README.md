# Accounting Data Analytics – Accruals & Usage AnalysisThis project analyzes **employee sick time usage and accruals** to support accounting, forecasting, and variance analysis.  The focus is on identifying **trends, correlations, and subgroup differences** that impact accrual liabilities and year‑end financial planning.The work combines structured datasets with statistical testing and regression analysis using Python.---## Project Objectives- Analyze historical sick time **usage vs. accrual behavior**- Identify trends across multiple years- Test whether observed changes are statistically significant- Support accounting insights related to accrual forecasting and liability management---## Repository StructureShow more lines
├─ Charts/
├─ Docs/
├─ EmployeeData.csv
├─ SickTimeAccrualsPerYear.csv
├─ SickTimeAccrualsPerYear2022.csv
├─ SCKTIMEACCRUALS.xlsx
├─ SCKUsage2022.py
├─ SCKUsage2024.py
├─ RegressionAnalysis.py
├─ PearsonTest.py
├─ SubgroupTesting.py
├─ TrendLine.py

---

## Data Sources

### Core Datasets
- **EmployeeData.csv**  
  Employee‑level reference data used for grouping and analysis.

- **SCKTIMEACCRUALS.xlsx**  
  Source workbook containing accrual and usage data.

- **SickTimeAccrualsPerYear.csv**  
- **SickTimeAccrualsPerYear2022.csv**  
  Year‑specific extracts used for trend and comparison analysis.

---

## Analysis Scripts

### Usage Analysis
- **SCKUsage2022.py**  
  Analyzes sick time usage patterns for 2022.

- **SCKUsage2024.py**  
  Analyzes sick time usage patterns for 2024 and supports year‑over‑year comparison.

---

### Statistical Testing
- **PearsonTest.py**  
  Performs Pearson correlation testing to evaluate relationships between usage, accruals, and related variables.

- **SubgroupTesting.py**  
  Tests differences across defined employee subgroups to identify statistically meaningful variation.

---

### Trend & Regression Analysis
- **TrendLine.py**  
  Generates trend lines to visualize changes over time and support forecasting insight.

- **RegressionAnalysis.py**  
  Performs regression analysis to model relationships and assess drivers of accrual behavior.

---

## Outputs

- **Charts/**  
  Generated visualizations supporting trend analysis and statistical interpretation.
<img width="1000" height="600" alt="TrendLines" src="https://github.com/user-attachments/assets/1c8aa546-0ae6-46c1-bee9-34cff0bffc1b" />
<img width="1280" height="612" alt="SubGroups" src="https://github.com/user-attachments/assets/de8b91d9-9b6a-4a48-88e4-41a0a02586b8" />
<img width="1280" height="612" alt="MultipleRegressionAnalysis" src="https://github.com/user-attachments/assets/1ab8dcb9-daed-4391-b237-782a51bcdd41" />
<img width="1280" height="612" alt="Correlation" src="https://github.com/user-attachments/assets/c5a1aa50-8298-4f66-9a1b-00357830cb96" />

- **Docs/**  
  Supporting documentation, notes, or methodology references related to the analysis.

---

## Why This Project Matters

From an accounting perspective, sick time accruals represent a **real financial liability**.  
This project demonstrates how data analytics can be used to:

- Move from raw transactional data to **actionable insight**
- Quantify trends rather than relying on intuition
- Support more accurate forecasting and accrual management
- Apply statistical rigor to operational accounting questions

---

## Tools & Technologies

- **Python**
- **pandas**
- **Statistical testing (Pearson correlation)**
- **Regression analysis**
- **CSV and Excel data sources**

---

## Notes

This project emphasizes **clarity, repeatability, and audit‑friendly analysis**.  
Each script is focused on a specific analytical question and can be run independently using the provided datasets.
