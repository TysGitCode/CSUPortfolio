import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import f_oneway
from statsmodels.stats.multicomp import pairwise_tukeyhsd

# Load the CSV data into a DataFrame
df = pd.read_csv('ServiceYearsSCKAnalysis/EmployeeData.csv')

# Define subgroups based on ranges of adjusted service years
bins = [0, 5, 10, 15, 20, 25, 30, 35, 40]
labels = ['0-5', '5-10', '10-15', '15-20', '20-25', '25-30', '30-35', '35-40']
df['ServiceYearsGroup'] = pd.cut(df['AdjustedStartDateLengthOfServiceYears'], bins=bins, labels=labels)

# Ensure that the groups are treated as categorical data and ordered correctly
df['ServiceYearsGroup'] = pd.Categorical(df['ServiceYearsGroup'], categories=labels, ordered=True)

# Drop rows with NaN values in either 'AvailableHours' or 'ServiceYearsGroup'
df = df.dropna(subset=['AvailableHours', 'ServiceYearsGroup'])

# Perform ANOVA
anova_result = f_oneway(*[df[df['ServiceYearsGroup'] == group]['AvailableHours'] for group in labels])

# Perform Tukey's HSD test for post hoc analysis if ANOVA is significant
if anova_result.pvalue < 0.05:
    tukey_result = pairwise_tukeyhsd(df['AvailableHours'], df['ServiceYearsGroup'])
else:
    tukey_result = None

# Plot the subgroup analysis results
plt.figure(figsize=(12, 8))

# Boxplot for each subgroup with improved color scheme and readability
boxprops = dict(linestyle='-', linewidth=2, color='darkgoldenrod')
medianprops = dict(linestyle='-', linewidth=2.5, color='firebrick')
meanprops = dict(marker='o', markerfacecolor='blue', markeredgecolor='black', markersize=10)

boxplot = df.boxplot(column='AvailableHours', by='ServiceYearsGroup', grid=False,
                     boxprops=boxprops, medianprops=medianprops, meanprops=meanprops,
                     showmeans=True, patch_artist=True)

plt.title('Sick Leave Balance by Adjusted Service Years Group')
plt.suptitle('')
plt.xlabel('Adjusted Service Years Group')
plt.ylabel('Sick Leave Balance (Available Hours)')
plt.xticks(rotation=45)
plt.grid(True, linestyle='--', alpha=0.7)

# Create a custom legend and place it below the plot area
handles = [
    plt.Line2D([0], [0], color='darkgoldenrod', lw=2, label='Box (Interquartile Range)'),
    plt.Line2D([0], [0], color='firebrick', lw=2.5, label='Median (Red Line)'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='Mean (Blue Dot)'),
    plt.Line2D([0], [0], color='black', lw=1, linestyle='--', label='Whiskers (Range excluding outliers)'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='black', markersize=5, label='Outliers (Black Dots)')
]
plt.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)

# Show plot
plt.show()

# Provide relevant information for a manager to understand the subgroup analysis results
info = f"""
This boxplot visualizes the Sick Leave Balance (Available Hours) for different subgroups based on Adjusted Service Years.

Key Points:
1. **Subgroups**: The data is divided into subgroups based on ranges of Adjusted Service Years.
2. **Boxplot**: Each box represents the distribution of Sick Leave Balance within a specific subgroup.
   - **Box (Interquartile Range)**: The box shows the interquartile range (IQR), which contains the middle 50% of the data.
   - **Median (Red Line)**: The red line inside the box represents the median Sick Leave Balance for each subgroup.
   - **Mean (Blue Dot)**: The blue dot represents the mean Sick Leave Balance for each subgroup.
   - **Whiskers (Range excluding outliers)**: The whiskers extend from the box to the smallest and largest values within 1.5 times the IQR from the lower and upper quartiles.
   - **Outliers (Black Dots)**: Individual points outside the whiskers are considered outliers.

ANOVA Results:
- F-statistic: {anova_result.statistic:.4f}
- p-value: {anova_result.pvalue:.4f}

Tukey's HSD Test Results:
{tukey_result if tukey_result else "ANOVA was not significant; no post hoc test performed."}

These results help identify significant differences in Sick Leave Balance between different subgroups based on Adjusted Service Years.
"""
print(info)
