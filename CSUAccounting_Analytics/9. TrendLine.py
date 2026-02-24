import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score

# Define the linear function
def linear(x, a, b):
    return a * x + b

# Define the quadratic function
def quadratic(x, a, b, c):
    return a * x**2 + b * x + c

# Load the CSV data into a DataFrame
df = pd.read_csv('EmployeeData.csv')

# Extract the relevant columns
x = df['AdjustedStartDateLengthOfServiceYears']
y = df['AvailableHours']

# Scatter plot
plt.figure(figsize=(10, 6))
plt.scatter(x, y, label='Data', color='darkorange', edgecolor='k', alpha=0.7)

# Fit the data to a linear function
try:
    params_lin, _ = curve_fit(linear, x, y)
    # Sort the values for plotting the linear fit line correctly
    sorted_x = np.sort(x)
    plt.plot(sorted_x, linear(sorted_x, *params_lin), label='Linear fit', color='blue', linewidth=2)
    # Calculate R-squared for linear fit
    r2_lin = r2_score(y, linear(x, *params_lin))
except RuntimeError:
    print("Linear fit did not converge")
    r2_lin = None

# Fit the data to a quadratic function
try:
    params_quad, _ = curve_fit(quadratic, x, y)
    # Sort the values for plotting the quadratic fit line correctly
    plt.plot(sorted_x, quadratic(sorted_x, *params_quad), label='Quadratic fit', color='green', linewidth=2)
    # Calculate R-squared for quadratic fit
    r2_quad = r2_score(y, quadratic(x, *params_quad))
except RuntimeError:
    print("Quadratic fit did not converge")
    r2_quad = None

# Add labels and legend
plt.xlabel('Adjusted Service Years', fontsize=12)
plt.ylabel('Sick Leave Balance (Available Hours)', fontsize=12)
plt.legend(fontsize=12)
plt.title('Scatter Plot with Trend Lines', fontsize=14)
plt.grid(True)
plt.tight_layout()

# Show plot
plt.show()

# Provide relevant information for a manager to understand the graph
info = f"""
This scatter plot visualizes the correlation between Adjusted Service Years and Sick Leave Balance (Available Hours) for employees.

Key Points:
1. **Data Points**: Each point represents an employee's Adjusted Service Years and their corresponding Sick Leave Balance. 
2. **Linear Trend Line (Blue)**: This line represents a linear relationship between Adjusted Service Years and Sick Leave Balance. It shows the general trend of how Sick Leave Balance changes with Adjusted Service Years.
3. **Quadratic Trend Line (Green)**: This line represents a quadratic relationship between Adjusted Service Years and Sick Leave Balance. It provides a more flexible fit to capture any non-linear patterns in the data.

Interpretation:
- If the Linear Trend Line fits well, it suggests a consistent rate of change in Sick Leave Balance with Adjusted Service Years.
- If the Quadratic Trend Line fits better, it indicates that the rate of change in Sick Leave Balance varies with Adjusted Service Years. For example, there might be an initial increase followed by a decrease or vice versa.

Additional Calculations:
- **Linear Fit Parameters**: Slope (a) = {params_lin[0]:.4f}, Intercept (b) = {params_lin[1]:.4f}, R-squared = {r2_lin:.4f}
- **Quadratic Fit Parameters**: a = {params_quad[0]:.4f}, b = {params_quad[1]:.4f}, c = {params_quad[2]:.4f}, R-squared = {r2_quad:.4f}

These parameters can help quantify the relationships and make predictions based on the trend lines.
"""

print(info)
