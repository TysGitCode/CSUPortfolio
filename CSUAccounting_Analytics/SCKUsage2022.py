import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the CSV file
file_path = 'ServiceYearsSCKAnalysis/SickTimeAccuralsPerYear2022.csv'
df = pd.read_csv(file_path)

# Convert the 'EmployeeAbsenceTransaction.Date' column to datetime
df['EmployeeAbsenceTransaction.Date'] = pd.to_datetime(df['EmployeeAbsenceTransaction.Date'], format='%m/%d/%Y')

# Forward fill the 'Available Hours Per Employee' column to handle NaN values
df['Available Hours Per Employee'] = df.groupby('Employee')['Available Hours Per Employee'].ffill()

# Filter out rows where 'Available Hours Per Employee' is still NaN
df = df.dropna(subset=['Available Hours Per Employee'])

# Ensure 'Available Hours Per Employee' is of numeric type
df['Available Hours Per Employee'] = pd.to_numeric(df['Available Hours Per Employee'], errors='coerce')

# Check for NaN values in 'Available Hours Per Employee' after conversion
print(df['Available Hours Per Employee'].isna().sum())

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

# Count the total number of unique employee IDs
total_unique_employees = df['Employee'].nunique()
print(f"Total number of unique employee IDs: {total_unique_employees}")

# Ensure the groups are in order for all plots
metrics_with_zeros['Hour Group'] = pd.Categorical(metrics_with_zeros['Hour Group'], categories=labels, ordered=True)
metrics_with_zeros = metrics_with_zeros.sort_values('Hour Group')

# Visualize the average used sick time hours per group including employees without transactions
plt.figure(figsize=(14, 7))
sns.barplot(x='Hour Group', y='mean', data=metrics_with_zeros, palette='rainbow')
plt.title('Average Used Sick Time Hours per Hour Group (including employees without transactions)')
plt.xlabel('Hour Group')
plt.ylabel('Average Used Sick Time Hours')
plt.xticks(rotation=45)
plt.show()

# Visualize the median used sick time hours per group including employees without transactions
plt.figure(figsize=(14, 7))
sns.barplot(x='Hour Group', y='median', data=metrics_with_zeros, palette='rainbow')
plt.title('Median Used Sick Time Hours per Hour Group (including employees without transactions)')
plt.xlabel('Hour Group')
plt.ylabel('Median Used Sick Time Hours')
plt.xticks(rotation=45)
plt.show()

# Calculate the weighted average of available hours per employee correctly
# Group by 'Employee' and get the last available hours for each employee
latest_hours_per_employee = df.groupby('Employee')['Available Hours Per Employee'].last()

# Calculate the total hours and total number of employees
total_hours = latest_hours_per_employee.sum()
total_employees = latest_hours_per_employee.count()

# Calculate the weighted average
weighted_average_hours_corrected = total_hours / total_employees

print(f"Corrected Weighted Average Available Hours per Employee: {weighted_average_hours_corrected:.2f}")

