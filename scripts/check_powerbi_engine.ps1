#requires -Version 7.4
<#
Validate the source model in a temporary database on an open AquaWatch Desktop engine.
Existing report databases and source files are not modified. The temporary database is
removed in finally. This tests native Power Query/DAX, not PBIP opening or visual layout.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ReportPath,
    [string]$ClientDirectory = (Join-Path $PSScriptRoot '../runtime/powerbi-client'),
    [switch]$DownloadClient,
    [string]$ResultsDirectory = (Join-Path $PSScriptRoot '../runtime/powerbi-validation')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$resolvedReport = (Resolve-Path -LiteralPath $ReportPath).Path
if ([IO.Path]::GetFileName($resolvedReport) -ne 'AquaWatch.pbip') {
    throw 'Select an open AquaWatch.pbip report, preferably an isolated copy.'
}
$report = @(Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains('"' + $resolvedReport + '"')
})
if ($report.Count -ne 1) { throw 'Open the selected AquaWatch.pbip in Desktop first; expected exactly one matching process.' }
$engine = @(Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object ParentProcessId -eq $report[0].ProcessId)
if ($engine.Count -ne 1) { throw 'Expected exactly one model engine for the selected report.' }
$ports = @(Get-NetTCPConnection -State Listen | Where-Object OwningProcess -eq $engine[0].ProcessId | Select-Object -ExpandProperty LocalPort -Unique)
if ($ports.Count -ne 1) { throw 'Expected exactly one localhost port for the selected model engine.' }

$clientVersion = '19.117.0'
foreach ($package in @('microsoft.analysisservices', 'microsoft.analysisservices.adomdclient')) {
    $target = Join-Path $ClientDirectory $package
    if (-not (Test-Path -LiteralPath (Join-Path $target 'lib/net8.0'))) {
        if (-not $DownloadClient) { throw 'Microsoft client libraries are missing. Rerun with -DownloadClient to download the pinned official NuGet packages.' }
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        $archive = Join-Path $target 'client.zip'
        $uri = "https://api.nuget.org/v3-flatcontainer/$package/$clientVersion/$package.$clientVersion.nupkg"
        Invoke-WebRequest -Uri $uri -OutFile $archive
        Expand-Archive -LiteralPath $archive -DestinationPath $target -Force
        Remove-Item -LiteralPath $archive
    }
}
$amoRoot = Join-Path $ClientDirectory 'microsoft.analysisservices/lib/net8.0'
foreach ($assembly in @('Microsoft.AnalysisServices.Runtime.Core.dll', 'Microsoft.AnalysisServices.Runtime.Windows.dll', 'Microsoft.AnalysisServices.Core.dll', 'Microsoft.AnalysisServices.Tabular.dll', 'Microsoft.AnalysisServices.Tabular.Json.dll')) {
    [void][Reflection.Assembly]::LoadFrom((Join-Path $amoRoot $assembly))
}
[void][Reflection.Assembly]::LoadFrom((Join-Path $ClientDirectory 'microsoft.analysisservices.adomdclient/lib/net8.0/Microsoft.AnalysisServices.AdomdClient.dll'))
$modelDocument = Get-Content -LiteralPath (Join-Path $root 'powerbi/AquaWatch.SemanticModel/model.bim') -Raw -Encoding utf8 | ConvertFrom-Json
$dataDirectory = (Resolve-Path -LiteralPath (Join-Path $root 'powerbi/data')).Path.Replace('\','/')
($modelDocument.model.expressions | Where-Object name -eq 'DataFolder').expression = '"' + $dataDirectory + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
$definition = [Microsoft.AnalysisServices.Tabular.JsonSerializer]::DeserializeDatabase(($modelDocument | ConvertTo-Json -Depth 100))
$temporaryId = 'AquaWatchValidation-' + [guid]::NewGuid().ToString('N')
$definition.ID = $temporaryId
$definition.Name = $temporaryId
New-Item -ItemType Directory -Path $ResultsDirectory -Force | Out-Null
$server = [Microsoft.AnalysisServices.Tabular.Server]::new()
$connection = $null
try {
    $server.Connect("Data Source=localhost:$($ports[0]);Connect Timeout=15")
    [void]$server.Databases.Add($definition)
    $definition.Update([Microsoft.AnalysisServices.UpdateOptions]::ExpandFull)
    $definition.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $definition.Model.SaveChanges() | Out-Null
    Write-Output 'Native Power Query refresh passed for the source model.'
    $connection = [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]::new("Data Source=localhost:$($ports[0]);Initial Catalog=$temporaryId;Connect Timeout=15")
    $connection.Open()
    $command = $connection.CreateCommand()
    $fields = @($modelDocument.model.tables.measures | Where-Object { $_ } | ForEach-Object { '"' + $_.name + '", [' + $_.name + ']' })
    $queries = [ordered]@{
        measures = ('EVALUATE ROW(' + ($fields -join ', ') + ')')
        tables = ('EVALUATE ROW(' + (($modelDocument.model.tables | ForEach-Object { '"' + $_.name + '", COUNTROWS(' + $_.name + ')' }) -join ', ') + ')')
        districts = 'EVALUATE SUMMARIZECOLUMNS(dim_meters[district], "readings", COUNTROWS(fct_consumption), "liters", SUM(fct_consumption[consumption_liters]), "cases", COALESCE(COUNTROWS(fct_cases),0), "invoices", COALESCE(COUNTROWS(fct_billing),0))'
        dates = 'EVALUATE SUMMARIZECOLUMNS(dim_date[calendar_date], "readings", COUNTROWS(fct_consumption), "liters", SUM(fct_consumption[consumption_liters]), "cases", COALESCE(COUNTROWS(fct_cases),0), "invoices", COALESCE(COUNTROWS(fct_billing),0), "network_rows", COUNTROWS(network_daily))'
    }
    $filters = [ordered]@{}
    foreach ($entry in $queries.GetEnumerator()) {
        $command.CommandText = $entry.Value
        $reader = $command.ExecuteReader()
        try {
            $rows = @()
            while ($reader.Read()) {
                $row = [ordered]@{}
                for ($i=0; $i -lt $reader.FieldCount; $i++) {
                    $row[$reader.GetName($i)] = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) }
                }
                $rows += [PSCustomObject]$row
            }
        } finally { $reader.Close() }
        if ($entry.Key -eq 'measures') {
            $rows[0] | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $ResultsDirectory 'measures.json') -Encoding utf8
        } else { $filters[$entry.Key] = $rows }
    }
    $filters | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $ResultsDirectory 'filters.json') -Encoding utf8
    [PSCustomObject]@{
        ValidatedAtUtc = [DateTime]::UtcNow.ToString('o')
        EngineVersion = $server.Version
        ClientVersion = $clientVersion
        NativeRefresh = 'passed'
        NativeQueries = 'passed'
        PbipOpening = 'not_verified'
        VisualRendering = 'not_verified'
    } | ConvertTo-Json | Set-Content (Join-Path $ResultsDirectory 'engine.json') -Encoding utf8
    Write-Output 'Native DAX queries passed. Compare the results with python scripts/check_powerbi_results.py.'
} finally {
    if ($connection) { $connection.Dispose() }
    if ($server.Connected) {
        # Only the unique temporary database created by this invocation.
        $ownedDatabase = $server.Databases.FindByName($temporaryId)
        if ($ownedDatabase) { $ownedDatabase.Drop() }
        $server.Disconnect()
    }
    $server.Dispose()
}
