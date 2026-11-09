# Runs DAX measures against the model hosted by an open Power BI Desktop instance and
# writes the results to data/aggregate/powerbi_validation/. Run with: -PbiProcessId <pid of PBIDesktop>
param([Parameter(Mandatory = $true)][int]$PbiProcessId)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $projectRoot 'data\aggregate\powerbi_validation'
New-Item -ItemType Directory -Force $outDir | Out-Null

# Power BI hosts its model in a child msmdsrv process listening on a local port.
$engine = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe' AND ParentProcessId=$PbiProcessId" | Select-Object -First 1
if (-not $engine) { throw "No model engine found for Power BI process $PbiProcessId." }
$port = (Get-NetTCPConnection -OwningProcess $engine.ProcessId -State Listen | Select-Object -First 1).LocalPort
[void][Reflection.Assembly]::LoadFrom('C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll')
$connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "Data Source=localhost:$port"
$connection.Open()

function Invoke-Dax([string]$query, [string]$name) {
    $command = $connection.CreateCommand()
    $command.CommandText = $query
    $command.CommandTimeout = 300
    $reader = $command.ExecuteReader()
    $rows = New-Object System.Collections.ArrayList
    while ($reader.Read()) {
        $row = [ordered]@{}
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            $column = $reader.GetName($i) -replace '^.*\[(.*)\]$', '$1'
            $value = $reader.GetValue($i)
            if ($value -is [double] -or $value -is [decimal]) { $value = ([double]$value).ToString('R', [Globalization.CultureInfo]::InvariantCulture) }
            $row[$column] = $value
        }
        [void]$rows.Add([pscustomobject]$row)
    }
    $reader.Close()
    $rows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $outDir "$name.csv")
    "$name rows=$($rows.Count)"
}

Invoke-Dax @'
EVALUATE ROW(
 "total_loans", [Total Loans], "total_funded", [Total Funded Amount], "avg_funded", [Average Loan Amount], "avg_int_rate", [Average Interest Rate],
 "fully_paid", [Fully Paid Loans], "charged_off", [Charged-Off Loans], "resolved", [Resolved Loans], "default_rate", [Historical Default Rate],
 "principal_weighted_rate", [Principal-Weighted Charge-Off Rate], "mature_default_rate", [Mature Default Rate], "total_payments", [Total Payments Received],
 "principal_received", [Total Principal Received], "unpaid_principal_at_chargeoff", [Charged-Off Principal Exposure], "recoveries", [Total Recoveries],
 "recovery_fees", [Total Recovery Fees], "est_net_principal_loss", [Estimated Net Principal Loss], "recovery_ratio", [Recovery Ratio], "unresolved", [Unresolved Loans],
 "avg_income", [Average Annual Income], "avg_dti", [Average DTI], "avg_emp_years", [Average Employment Length]
)
'@ 'dax_portfolio'

Invoke-Dax @'
EVALUATE SUMMARIZECOLUMNS(dim_grade[grade], "loans", [Total Loans], "resolved", [Resolved Loans], "default_rate", [Historical Default Rate], "mature_default_rate", [Mature Default Rate], "unpaid", [Charged-Off Principal Exposure], "recovery_ratio", [Recovery Ratio])
ORDER BY dim_grade[grade]
'@ 'dax_by_grade'

Invoke-Dax @'
EVALUATE SUMMARIZECOLUMNS(dim_date[issue_year], dim_term[term_months], "loans", [Total Loans], "elapsed", [Pct Term Elapsed], "mature_cohort", [Mature Cohort Default Rate])
ORDER BY dim_date[issue_year], dim_term[term_months]
'@ 'dax_by_year_term'

# Filter behaviour: a slicer-style filter must change numerator and denominator together.
Invoke-Dax @'
EVALUATE ROW(
 "grade_a_rate", CALCULATE([Historical Default Rate], dim_grade[grade] = "A"),
 "grade_a_loans", CALCULATE([Total Loans], dim_grade[grade] = "A"),
 "ca_rate", CALCULATE([Historical Default Rate], dim_state[addr_state] = "CA"),
 "y2015_36m_rate", CALCULATE([Historical Default Rate], dim_date[issue_year] = 2015, dim_term[term_months] = 36),
 "small_business_rate", CALCULATE([Historical Default Rate], dim_purpose[purpose_label] = "Small Business"),
 "dti_40_rate", CALCULATE([Historical Default Rate], dim_dti_band[dti_band] = "40+"),
 "high_tier_loans", CALCULATE([Total Loans], dim_risk_segment[risk_tier] = "High"),
 "current_rate_blank", CALCULATE([Historical Default Rate], dim_status[status_clean] = "Current")
)
'@ 'dax_filter_checks'

# Every measure must evaluate without error.
$measures = (Get-Content (Join-Path $PSScriptRoot 'measure_names.txt')) | Where-Object { $_ }
$pieces = $measures | ForEach-Object { '"' + $_ + '", [' + $_ + ']' }
$results = foreach ($m in $measures) {
    try {
        $command = $connection.CreateCommand()
        $command.CommandText = "EVALUATE ROW(""v"", CALCULATE([$m], dim_grade[grade] = ""B""))"
        $reader = $command.ExecuteReader(); [void]$reader.Read(); $value = $reader.GetValue(0); $reader.Close()
        [pscustomobject]@{ measure = $m; status = 'ok'; value_grade_B = $value }
    } catch { [pscustomobject]@{ measure = $m; status = 'error'; value_grade_B = $_.Exception.Message } }
}
$results | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $outDir 'dax_all_measures.csv')
"measures ok=$(($results | Where-Object status -eq 'ok').Count) error=$(($results | Where-Object status -eq 'error').Count)"
$connection.Close()

