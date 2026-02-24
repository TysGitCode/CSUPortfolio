import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the CSV file
file_path = 'ServiceYearsSCKAnalysis/SickTimeAccuralsPerYear.csv'
df = pd.read_csv(file_path)

# Convert the 'EmployeeAbsenceTransaction.Date' column to datetime
df['EmployeeAbsenceTransaction.Date'] = pd.to_datetime(df['EmployeeAbsenceTransaction.Date'], format='%m/%d/%Y')

# Forward fill the 'Available Hours Per Employee' column to handle NaN values
df['Available Hours Per Employee'] = df.groupby('Employee')['Available Hours Per Employee'].ffill()

# Filter out rows where 'Available Hours Per Employee' is still NaN
df = df.dropna(subset=['Available Hours Per Employee'])

# Group employees by their current balance in 'Available Hours Per Employee'
bins = range(0, 1101, 100)
labels = [f'{i}-{i+99}' for i in bins[:-1]]
df['Hour Group'] = pd.cut(df['Available Hours Per Employee'], bins=bins, labels=labels, right=False)

# Filter for transaction type 61 (used sick time)
df_used_sick_time = df[df['TransactionType'] == 61]

# Convert all numbers to positive
df_used_sick_time['Hours'] = df_used_sick_time['Hours'].abs()

# Identify employee IDs with no transactions
all_employees = set(df['Employee'])
employees_with_transactions = set(df_used_sick_time['Employee'])
employees_without_transactions = all_employees - employees_with_transactions

print("Employee IDs with no transactions:")
print(employees_without_transactions)

# Add employees without transactions to the dataframe with 0 hours and their current balance
new_rows = []
for emp_id in employees_without_transactions:
    current_balance = df[df['Employee'] == emp_id]['Available Hours Per Employee'].iloc[-1]
    new_rows.append({
        'Employee': emp_id,
        'TransactionType': 61,
        'Hours': 0,
        'EmployeeAbsenceTransaction.Date': pd.Timestamp.now(),
        'Available Hours Per Employee': current_balance,
        'Hour Group': pd.cut([current_balance], bins=bins, labels=labels, right=False)[0]
    })
df_used_sick_time = pd.concat([df_used_sick_time, pd.DataFrame(new_rows)], ignore_index=True)

# Calculate relevant metrics including employees without transactions
metrics_with_zeros = df_used_sick_time.groupby('Hour Group')['Hours'].agg(['mean', 'median']).reset_index()

# Calculate the count of unique employees in each hour group
employee_counts = df.groupby('Hour Group')['Employee'].nunique().reset_index()
employee_counts.columns = ['Hour Group', 'Total Employee Count']

# Calculate the count of unique employees with transactions in each hour group
employee_counts_with_transactions = df_used_sick_time[df_used_sick_time['Hours'] > 0].groupby('Hour Group')['Employee'].nunique().reset_index()
employee_counts_with_transactions.columns = ['Hour Group', 'Employees with Transactions']

# Calculate the count of unique employees without transactions in each hour group
employee_counts_without_transactions = df_used_sick_time[df_used_sick_time['Hours'] == 0].groupby('Hour Group')['Employee'].nunique().reset_index()
employee_counts_without_transactions.columns = ['Hour Group', 'Employees without Transactions']

# Merge the employee counts with the metrics
metrics_with_zeros = metrics_with_zeros.merge(employee_counts, on='Hour Group')
metrics_with_zeros = metrics_with_zeros.merge(employee_counts_with_transactions, on='Hour Group')
metrics_with_zeros = metrics_with_zeros.merge(employee_counts_without_transactions, on='Hour Group')

print("Relevant Metrics for Each Hour Group (including employees without transactions):")
print(metrics_with_zeros)

# Ensure the groups are in order for all plots
metrics_with_zeros['Hour Group'] = pd.Categorical(metrics_with_zeros['Hour Group'], categories=labels, ordered=True)
metrics_with_zeros = metrics_with_zeros.sort_values('Hour Group')

# Visualize the average used sick time hours per group including employees without transactions
plt.figure(figsize=(14, 7))
sns.barplot(x='Hour Group', y='mean', data=metrics_with_zeros, palette='viridis')
plt.xlabel('Hour Group')
plt.ylabel('Average Used Sick Time Hours per Month')
plt.title('Average Used Sick Time Hours per Month by Hour Group (including employees without transactions)')
plt.xticks(rotation=45)
plt.grid(True)
plt.show()

# Visualize the median used sick time hours per group including employees without transactions
plt.figure(figsize=(14, 7))
sns.barplot(x='Hour Group', y='median', data=metrics_with_zeros, palette='viridis')
plt.xlabel('Hour Group')
plt.ylabel('Median Used Sick Time Hours per Month')
plt.title('Median Used Sick Time Hours per Month by Hour Group (including employees without transactions)')
plt.xticks(rotation=45)
plt.grid(True)
plt.show()

# Count unique employee IDs with and without transactions and total
total_employees = len(all_employees)
employees_with_transactions_count = len(employees_with_transactions)
employees_without_transactions_count = len(employees_without_transactions)

print(f"Total unique employees: {total_employees}")
print(f"Employees with transactions: {employees_with_transactions_count}")
print(f"Employees without transactions: {employees_without_transactions_count}")

# Analysis and Explanations
analysis_output = f"""
Analysis and Explanations:

1. Median Value of 8:
   - The median value of 8 hours in many groups suggests that a significant number of employees are taking exactly one full workday (8 hours) of sick leave.
   - This could be due to company policies or common practices where employees prefer to take a full day off rather than partial days.
   - It is also possible that the standard workday duration is 8 hours, leading to this common value.

2. Mean Values:
   - The mean values vary across different hour groups, indicating that while some employees take full days off, others might take partial days.
   - The mean values are generally lower than the median values in groups with a median of 8, suggesting that there are many instances of partial day sick leaves as well.

3. Count of Employees in Each Group:
   - The count of unique employees in each group provides insight into how many employees fall into each hour group category.
   - This helps in understanding the distribution of available hours among employees and how it correlates with their sick leave usage.

4. Employees Without Transactions:
   - A significant number of employees have no recorded sick leave transactions.
   - These employees have been accounted for with zero hours in the analysis to ensure accurate metrics.

5. Possible Theories:
   - The high frequency of exact 8-hour sick leaves could indicate a preference for taking full days off rather than partial days.
   - Company policies might encourage or mandate taking full days off for sick leave.
   - Employees might find it more convenient to take a full day off rather than splitting their sick leave into smaller increments.

6. Further Investigation:
   - To gain more insights, it would be helpful to analyze the reasons behind taking sick leave and whether there are any patterns related to specific departments or job roles.
   - Understanding the impact of company policies on sick leave usage could provide valuable information for optimizing employee well-being and productivity.

### Practical Application:

- **Budgeting for Sick Leave:**
  - Use the median to estimate the typical sick leave usage per employee. This helps in setting realistic expectations for most employees.
  - Use the mean to estimate the total sick leave liability for the entire workforce. This helps in understanding the overall financial impact and ensuring sufficient reserves are in place.

- **Policy Making:**
  - Analyze the median to understand common sick leave patterns and identify if there are any policy changes needed to address frequent full-day absences.
  - Analyze the mean to identify the overall trend and ensure that sick leave policies are aligned with the actual usage patterns.

By using both the median and mean, organizations can gain a comprehensive understanding of sick leave usage and make informed decisions for liability accounting and policy making. This dual approach ensures that both typical and overall usage patterns are considered, leading to more accurate budgeting and effective policy development.

### Employee Counts:
- Total unique employees: {total_employees}
- Employees with transactions: {employees_with_transactions_count}
- Employees without transactions: {employees_without_transactions_count}

### Employee Counts by Hour Group:
{metrics_with_zeros.to_string(index=False)}
"""

print(analysis_output)

# Calculate the weighted average of available hours per employee correctly
latest_hours_per_employee = df.groupby('Employee')['Available Hours Per Employee'].last()
total_hours = latest_hours_per_employee.sum()
total_employees = latest_hours_per_employee.count()
weighted_average_hours_corrected = total_hours / total_employees

print(f"Corrected Weighted Average Available Hours per Employee: {weighted_average_hours_corrected:.2f}")
