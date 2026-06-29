# agendar_sync.ps1
# Cria (ou recria) o agendamento do sync de indices BCB no Task Scheduler.
# Compativel com Windows PowerShell 5 e PowerShell 7.
# Requer privilegios de Administrador.

$taskName  = 'BCB_Sync_Indices'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python    = Join-Path $scriptDir '.venv\Scripts\python.exe'
$script    = Join-Path $scriptDir 'sync_indices.py'

Write-Host ""
Write-Host "============================================================"
Write-Host "  Agendamento : $taskName"
Write-Host "  Script      : $script"
Write-Host "  Execucao    : Todo dia 15 de cada mes, as 08:00"
Write-Host "  Missed run  : Executa no primeiro login apos horario perdido"
Write-Host "============================================================"
Write-Host ""

if (-not (Test-Path $python)) {
    Write-Host "[ERRO] Python nao encontrado: $python"
    Write-Host "       Execute instalar.bat primeiro."
    exit 1
}
if (-not (Test-Path $script)) {
    Write-Host "[ERRO] Script nao encontrado: $script"
    exit 1
}

# --- Gera XML da tarefa (mais confiavel que cmdlets para trigger mensal) ---
$xmlPath = Join-Path $env:TEMP 'bcb_sync_task.xml'

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Sincroniza indices monetarios BCB/SGS para o PostgreSQL (schema aux)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-07-15T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth><Day>15</Day></DaysOfMonth>
        <Months>
          <January/><February/><March/><April/>
          <May/><June/><July/><August/>
          <September/><October/><November/><December/>
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>"$python"</Command>
      <Arguments>"$script"</Arguments>
    </Exec>
  </Actions>
</Task>
"@

# Salva como UTF-16 (exigido pelo schtasks /xml)
[System.IO.File]::WriteAllText($xmlPath, $xml, [System.Text.Encoding]::Unicode)

# Remove tarefa anterior se existir
schtasks /delete /tn $taskName /f 2>$null

# Cria a partir do XML
schtasks /create /tn $taskName /xml $xmlPath /f

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Agendamento criado com sucesso!"
    Write-Host ""
    Write-Host "     Tarefa           : $taskName"
    Write-Host "     Executa          : Todo dia 15 de cada mes, as 08:00"
    Write-Host "     Se perder horario: executa no primeiro login seguinte"
    Write-Host "     Timeout maximo   : 1 hora"
    Write-Host ""
    Write-Host "Comandos uteis:"
    Write-Host "  Verificar  : schtasks /query /tn $taskName /fo LIST /v"
    Write-Host "  Rodar agora: schtasks /run   /tn $taskName"
    Write-Host "  Remover    : schtasks /delete /tn $taskName /f"
} else {
    Write-Host ""
    Write-Host "[ERRO] Falha ao criar o agendamento."
    Write-Host "       Execute este script como Administrador."
    exit 1
}

Remove-Item $xmlPath -ErrorAction SilentlyContinue
