import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm

# Load the CSV data into a DataFrame
df = pd.read_csv('EmployeeData.csv')

# Drop rows with NaN values in the relevant columns
df = df.dropna(subset=['AdjustedStartDateLengthOfServiceYears', 'TotalPayRate', 'AvailableHours'])

# Perform multiple regression analysis
predictor_vars = ['AdjustedStartDateLengthOfServiceYears', 'TotalPayRate']
X = df[predictor_vars]
y = df['AvailableHours']
X = sm.add_constant(X)  # Adds a constant term to the predictors

model_multiple = sm.OLS(y, X).fit()
predictions_multiple = model_multiple.predict(X)

# Perform simple linear regression analysis
X_simple = df['AdjustedStartDateLengthOfServiceYears']
X_simple = sm.add_constant(X_simple)  # Adds a constant term to the predictor

model_simple = sm.OLS(y, X_simple).fit()
predictions_simple = model_simple.predict(X_simple)

# Plot the regression analysis results
plt.figure(figsize=(12, 8))

plt.scatter(df['AdjustedStartDateLengthOfServiceYears'], df['AvailableHours'], color='blue', label='Data Points')

# Create a grid of values for Adjusted Service Years to plot the multiple regression line
x_range = np.linspace(df['AdjustedStartDateLengthOfServiceYears'].min(), df['AdjustedStartDateLengthOfServiceYears'].max(), 100)
X_pred_multiple = pd.DataFrame({'const': 1, 'AdjustedStartDateLengthOfServiceYears': x_range, 'TotalPayRate': np.mean(df['TotalPayRate'])})
y_pred_multiple = model_multiple.predict(X_pred_multiple)

plt.plot(x_range, y_pred_multiple, color='red', linewidth=2, label='Multiple Regression Line')

# Create a grid of values for Adjusted Service Years to plot the simple regression line
X_pred_simple = pd.DataFrame({'const': 1, 'AdjustedStartDateLengthOfServiceYears': x_range})
y_pred_simple = model_simple.predict(X_pred_simple)

plt.plot(x_range, y_pred_simple, color='green', linewidth=2, label='Simple Regression Line')

plt.title('Regression Analysis: Sick Leave Balance vs. Adjusted Service Years and Total Pay Rate')
plt.xlabel('Adjusted Service Years')
plt.ylabel('Sick Leave Balance (Available Hours)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)

# Show plot
plt.show()

# Provide relevant information for a manager to understand the regression analysis results
info = f"""
This scatter plot visualizes the relationship between Sick Leave Balance (Available Hours) and Adjusted Service Years.

Key Points:
1. **Data Points**: Each blue dot represents an individual employee's Sick Leave Balance and Adjusted Service Years.
2. **Multiple Regression Line**: The red line represents the best-fit multiple regression line that models the relationship between Sick Leave Balance and Adjusted Service Years, considering Total Pay Rate.
3. **Simple Regression Line**: The green line represents the best-fit simple regression line that models the relationship between Sick Leave Balance and Adjusted Service Years alone.

Multiple Regression Analysis Results:
- Coefficients:
  - const: {model_multiple.params['const']}
  - Adjusted Service Years: {model_multiple.params['AdjustedStartDateLengthOfServiceYears']}
  - Total Pay Rate: {model_multiple.params['TotalPayRate']}

- R-squared: {model_multiple.rsquared}

- p-values:
  - const: {model_multiple.pvalues['const']}
  - Adjusted Service Years: {model_multiple.pvalues['AdjustedStartDateLengthOfServiceYears']}
  - Total Pay Rate: {model_multiple.pvalues['TotalPayRate']}

Simple Regression Analysis Results:
- Coefficients:
  - const: {model_simple.params['const']}
  - Adjusted Service Years: {model_simple.params['AdjustedStartDateLengthOfServiceYears']}

- R-squared: {model_simple.rsquared}

- p-values:
  - const: {model_simple.pvalues['const']}
  - Adjusted Service Years: {model_simple.pvalues['AdjustedStartDateLengthOfServiceYears']}

These results help identify the strength and significance of the relationship between Sick Leave Balance and multiple predictor variables (Adjusted Service Years, Total Pay Rate), as well as the relationship with Adjusted Service Years alone.
"""
print(info)

