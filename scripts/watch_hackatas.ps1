# Observa o Project "Hackatas" e registra quando surgir task nova no Backend_template.
# Snapshot do ultimo check fica em scripts/hackatas_snapshot.json; o log em scripts/hackatas_watch.log.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectNumber = 1
$Org = "Hackathon-Fabrica-2k26"
$BackendRepo = "Hackathon-Fabrica-2k26/Backend_template"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SnapshotFile = Join-Path $ScriptDir "hackatas_snapshot.json"
$LogFile = Join-Path $ScriptDir "hackatas_watch.log"

function Log([string]$Message) {
    $line = "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line
}

# Statuses que indicam "tem coisa pra olhar"
$Ativos = @("Backlog", "Ready", "In Progress")

try {
    $output = gh project item-list $ProjectNumber --owner $Org --limit 100 --format json 2>&1
    if ($LASTEXITCODE -ne 0) {
        Log "ERRO ao listar o project: $output"
        exit 1
    }

    $items = ($output | ConvertFrom-Json).items
    $backlog = $items | Where-Object {
        $_.repository -like "*Backend_template" -and
        $_.content.type -eq "Issue" -and
        ($_.PSObject.Properties.Name -contains "status") -and $Ativos -contains $_.status
    } | ForEach-Object {
        [PSCustomObject]@{
            Url     = $_.content.url
            Numero  = $_.content.number
            Titulo  = $_.content.title
            Status  = $_.status
            Done    = if ($_.PSObject.Properties.Name -contains "assignees") { $_.assignees -join "," } else { "" }
        }
    }

    $atual = @{}
    foreach ($i in $backlog) {
        $id = "$($i.Numero):$($i.Titulo):$($i.Status):$($i.Done)"
        $atual[$i.Url] = $id
    }

    if (Test-Path $SnapshotFile) {
        $antes = @{}
        (Get-Content $SnapshotFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object {
            $antes[$_.Name] = $_.Value
        }

        # Tasks novas (nao existiam no snapshot anterior)
        $novas = $atual.Keys | Where-Object { -not $antes.ContainsKey($_) }
        foreach ($url in $novas) {
            $info = $backlog | Where-Object { $_.Url -eq $url }
            Log "NOVA TASK BACKEND: [$($info.Status)] #$($info.Numero) $($info.Titulo) -> $url"
        }

        # Avisos de mudanca: precisa de revisao, faturou ou saiu do backlog
        foreach ($entry in $antes.GetEnumerator()) {
            if ($atual.ContainsKey($entry.Key)) {
                if ($entry.Value -ne $atual[$entry.Key]) {
                    $info = $backlog | Where-Object { $_.Url -eq $entry.Key }
                    Log "MUDOU: #$($info.Numero) $($info.Titulo) agora [$($info.Status)] -> $($info.Url)"
                }
            } else {
                Log "SAIU (Done ou removida): $entry.Key"
            }
        }

        $totalNovos = ($novas | Measure-Object).Count
        if ($totalNovos -eq 0) {
            Log "Sem tasks novas. Total ativo no backend: $((($atual.Keys | Measure-Object).Count))"
        }
    } else {
        Log "Primeira execucao: snapshot criado com $((($atual.Keys | Measure-Object).Count)) task(s) ativa(s) no backend."
    }

    $atual | ConvertTo-Json | Set-Content -Path $SnapshotFile -Encoding UTF8
} catch {
    Log "EXCECAO: $($_.Exception.Message)"
    exit 1
}
