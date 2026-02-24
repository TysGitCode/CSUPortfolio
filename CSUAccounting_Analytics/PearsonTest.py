import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr

# Load the CSV file
df = pd.read_csv('EmployeeData.csv')

# Step 1: Check for missing or incorrect values
print(df.isnull().sum())  # Check for missing values
print(df.describe())  # Get a summary of the data

# Step 2: Calculate the correlation between Length of Service and Sick Leave Usage
correlation, p_value = pearsonr(df['AdjustedStartDateLengthOfServiceYears'], df['AvailableHours'])

# Explanation of the correlation and p-value
correlation_explanation = f"""
The Pearson correlation coefficient measures the linear relationship between two variables.
In this case, we are measuring the relationship between the length of service (in years) and sick leave usage (in hours).

- A correlation coefficient close to +1 indicates a strong positive relationship.
- A correlation coefficient close to -1 indicates a strong negative relationship.
- A correlation coefficient close to 0 indicates no linear relationship.

The calculated correlation coefficient is {correlation:.2f}.
This value indicates the strength and direction of the linear relationship between length of service and sick leave usage.

The p-value indicates the statistical significance of the correlation.
- A p-value less than 0.05 typically indicates that the correlation is statistically significant.

The calculated p-value is {p_value:.4f}.
This value helps us determine whether the observed correlation is statistically significant.
"""

# Step 3: Plot the data to visualize the correlation
plt.figure(figsize=(10, 6))
sns.scatterplot(x='AdjustedStartDateLengthOfServiceYears', y='AvailableHours', data=df)
plt.title('Correlation between Length of Service and Sick Leave Usage')
plt.xlabel('Length of Service (Years)')
plt.ylabel('Sick Leave Usage (Hours)')
plt.show()

# Print the correlation and p-value with explanations
print(correlation_explanation)
