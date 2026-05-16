"""RMM Script Templates — CRUD e seed de templates builtin."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rmm import RmmScriptTemplate

BUILTIN_TEMPLATES = [
    # ── Monitoramento ─────────────────────────────────────────────────────────
    {
        "name": "Listar Processos em Execução",
        "description": "Exibe todos os processos em execução com uso de CPU e memória.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Name, Id, CPU, WorkingSet | Format-Table -AutoSize",
    },
    {
        "name": "Verificar Uso de Disco",
        "description": "Exibe o espaço livre e usado em todos os volumes.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,2)}}, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,2)}} | Format-Table -AutoSize",
    },
    {
        "name": "Verificar Uso de Memória RAM",
        "description": "Exibe memória total, livre e em uso.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "command",
        "body": "$os = Get-CimInstance Win32_OperatingSystem; [PSCustomObject]@{Total_GB=[math]::Round($os.TotalVisibleMemorySize/1MB,2); Free_GB=[math]::Round($os.FreePhysicalMemory/1MB,2); Used_GB=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2)} | Format-List",
    },
    {
        "name": "Uptime do Sistema",
        "description": "Exibe há quanto tempo o sistema está em execução.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "command",
        "body": "(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | Select-Object Days, Hours, Minutes | Format-List",
    },
    {
        "name": "Listar Serviços Parados",
        "description": "Lista todos os serviços configurados como Automático que estão parados.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -ne 'Running'} | Select-Object Name, Status, DisplayName | Format-Table -AutoSize",
    },
    # ── Segurança ─────────────────────────────────────────────────────────────
    {
        "name": "Listar Usuários Locais",
        "description": "Lista todos os usuários locais e seu status (habilitado/desabilitado).",
        "category": "security",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-LocalUser | Select-Object Name, Enabled, LastLogon, PasswordLastSet | Format-Table -AutoSize",
    },
    {
        "name": "Verificar Membros do Grupo Administradores",
        "description": "Lista todos os membros do grupo Administrators local.",
        "category": "security",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-LocalGroupMember -Group Administrators | Select-Object Name, ObjectClass, PrincipalSource | Format-Table -AutoSize",
    },
    {
        "name": "Verificar Portas Abertas (Netstat)",
        "description": "Lista portas TCP em estado LISTENING com o processo associado.",
        "category": "security",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-NetTCPConnection -State Listen | Select-Object LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -EA SilentlyContinue).Name}}, OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize",
    },
    {
        "name": "Status do Windows Defender",
        "description": "Verifica o status do antivírus Windows Defender.",
        "category": "security",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated, QuickScanAge | Format-List",
    },
    {
        "name": "Verificar Atualizações Pendentes",
        "description": "Lista atualizações do Windows que estão pendentes de instalação.",
        "category": "security",
        "shell": "powershell",
        "run_type": "script",
        "body": "$UpdateSession = New-Object -ComObject Microsoft.Update.Session\n$Searcher = $UpdateSession.CreateUpdateSearcher()\n$Results = $Searcher.Search('IsInstalled=0 and Type=Software')\nif ($Results.Updates.Count -eq 0) { Write-Output 'Nenhuma atualização pendente.' } else { $Results.Updates | ForEach-Object { Write-Output \"$($_.Title)\" } }",
    },
    # ── Manutenção ────────────────────────────────────────────────────────────
    {
        "name": "Reiniciar Máquina",
        "description": "Reinicia o computador imediatamente.",
        "category": "maintenance",
        "shell": "powershell",
        "run_type": "command",
        "body": "Restart-Computer -Force",
    },
    {
        "name": "Limpar Arquivos Temporários",
        "description": "Remove arquivos da pasta Temp do sistema e do usuário.",
        "category": "maintenance",
        "shell": "powershell",
        "run_type": "script",
        "body": "$paths = @($env:TEMP, 'C:\\Windows\\Temp')\nforeach ($p in $paths) {\n    Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue\n}\nWrite-Output 'Limpeza concluída.'",
    },
    # ── Rede ──────────────────────────────────────────────────────────────────
    {
        "name": "Listar Pastas Compartilhadas",
        "description": "Exibe todas as pastas compartilhadas na máquina.",
        "category": "network",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-SmbShare | Select-Object Name, Path, Description | Format-Table -AutoSize",
    },
    {
        "name": "Informações de Rede",
        "description": "Exibe adaptadores de rede, endereços IP e gateway padrão.",
        "category": "network",
        "shell": "powershell",
        "run_type": "command",
        "body": "Get-NetIPConfiguration | Where-Object {$_.IPv4Address} | Select-Object InterfaceAlias, @{N='IP';E={$_.IPv4Address.IPAddress}}, @{N='Gateway';E={$_.IPv4DefaultGateway.NextHop}} | Format-Table -AutoSize",
    },
    {
        "name": "Flush de Cache DNS",
        "description": "Limpa o cache DNS do sistema.",
        "category": "network",
        "shell": "powershell",
        "run_type": "command",
        "body": "Clear-DnsClientCache; Write-Output 'Cache DNS limpo com sucesso.'",
    },
    # ── Resposta a Incidentes ────────────────────────────────────────────────
    {
        "name": "TPL-001 · Full Endpoint Snapshot",
        "description": "Coleta estruturada de processos, conexões TCP, serviços parados, usuários logados e erros do sistema. Alimenta SIEM (F37), AI Assistant (F40) e GLPI (F43). Roles: SecOps, N2, Servidores.",
        "category": "incident_response",
        "shell": "powershell",
        "run_type": "script",
        "body": "$os = Get-CimInstance Win32_OperatingSystem\n$procs = Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name, Id, @{N='CPU';E={[math]::Round($_.CPU,1)}}, @{N='RAM_MB';E={[math]::Round($_.WorkingSet/1MB,1)}} -ErrorAction SilentlyContinue\n$conns = Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -EA SilentlyContinue).Name}}\n$svcKO = Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -ne 'Running'} | Select-Object Name, Status\n$evts = Get-WinEvent -LogName System -MaxEvents 15 -FilterHashtable @{Level=2} -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(120,$_.Message.Length))}}\nWrite-Output \"=== FULL ENDPOINT SNAPSHOT === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"HOST: $($env:COMPUTERNAME) | OS: $($os.Caption) | Uptime: $([math]::Round(((Get-Date)-$os.LastBootUpTime).TotalHours,1))h\"\nWrite-Output \"RAM: $([math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2))GB usados / $([math]::Round($os.TotalVisibleMemorySize/1MB,2))GB total\"\nWrite-Output '--- TOP 15 PROCESSOS ---'\n$procs | Format-Table -AutoSize | Out-String\nWrite-Output '--- TCP ESTABLISHED ---'\n$conns | Format-Table -AutoSize | Out-String\nWrite-Output '--- SERVICOS AUTO/PARADOS ---'\nif ($svcKO) { $svcKO | Format-Table -AutoSize | Out-String } else { Write-Output 'Nenhum servico automatico parado.' }\nWrite-Output '--- USUARIOS LOGADOS ---'\nquery user 2>$null\nWrite-Output '--- ERROS DO SISTEMA (ultimos 15) ---'\n$evts | Format-List | Out-String",
    },
    {
        "name": "TPL-003 · IOC Sweep",
        "description": "Varre processos, conexões e scheduled tasks por indicadores de comprometimento. Integra com SOAR (F35), SIEM (F37), DLP (F28.1). Roles: SecOps, N2.",
        "category": "incident_response",
        "shell": "powershell",
        "run_type": "script",
        "body": "# EDITE as listas de IoCs antes de executar\n$SuspectIPs = @('185.234.216.1','91.108.56.1')  # Adicione IPs suspeitos\n$hits = @()\n# Conexoes com IPs suspeitos\n$conns = Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue\nforeach ($ip in $SuspectIPs) {\n    $match = $conns | Where-Object { $_.RemoteAddress -like \"$ip*\" }\n    foreach ($c in $match) {\n        $proc = (Get-Process -Id $c.OwningProcess -EA SilentlyContinue).Name\n        $hits += [PSCustomObject]@{Type='IP';IOC=$ip;Detail=\"$($c.LocalAddress):$($c.LocalPort)->$($c.RemoteAddress):$($c.RemotePort)\";Process=$proc;Severity='HIGH'}\n    }\n}\n# svchost fora de System32\n$svchosts = Get-Process svchost -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -notlike '*System32*' }\nforeach ($p in $svchosts) { $hits += [PSCustomObject]@{Type='PROCESS';IOC='svchost fora de System32';Detail=$p.Path;Process=$p.Name;Severity='CRITICAL'} }\n# Scheduled tasks criadas nos ultimos 7 dias\n$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.Date -gt (Get-Date).AddDays(-7) }\nforeach ($t in $tasks) { $hits += [PSCustomObject]@{Type='TASK';IOC='Nova Task <7d';Detail=\"$($t.TaskPath)$($t.TaskName)\";Process='N/A';Severity='MEDIUM'} }\n# Scripts em AppData/Temp via tasks\n$suspTasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { ($_.Actions | Select-Object -First 1 -ExpandProperty Execute -EA SilentlyContinue) -match 'Temp|AppData|mshta|wscript|cscript|-enc' }\nforeach ($t in $suspTasks) { $hits += [PSCustomObject]@{Type='TASK_SUSP';IOC='Acao suspeita';Detail=\"$($t.TaskPath)$($t.TaskName)\";Process='N/A';Severity='CRITICAL'} }\nWrite-Output \"=== IOC SWEEP === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Hits: $($hits.Count)\"\nif ($hits.Count -gt 0) { Write-Output \"`nALERTA: $($hits.Count) indicador(es) encontrado(s)!\"; $hits | Format-Table -AutoSize | Out-String } else { Write-Output 'Nenhum IoC encontrado.' }",
    },
    {
        "name": "TPL-015 · Isolamento de Endpoint",
        "description": "Isola o endpoint desabilitando NICs e criando regras de bloqueio total no firewall. Use durante resposta a incidentes. Reverta com TPL-016. Roles: SecOps.",
        "category": "incident_response",
        "shell": "powershell",
        "run_type": "script",
        "body": "$timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'\nWrite-Output \"=== ISOLAMENTO DE ENDPOINT === $timestamp\"\nWrite-Output \"Host: $env:COMPUTERNAME | ATENCAO: Esta acao bloqueia toda comunicacao de rede!\"\n$adapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' }\nWrite-Output \"Adaptadores encontrados:\"\n$adapters | Select-Object Name, InterfaceDescription, MACAddress | Format-Table -AutoSize | Out-String\n# Criar regras de bloqueio total\nNew-NetFirewallRule -DisplayName 'ISOLAMENTO-EMERGENCIA-BLOCK-IN' -Direction Inbound -Action Block -Profile Any -ErrorAction SilentlyContinue | Out-Null\nNew-NetFirewallRule -DisplayName 'ISOLAMENTO-EMERGENCIA-BLOCK-OUT' -Direction Outbound -Action Block -Profile Any -ErrorAction SilentlyContinue | Out-Null\nWrite-Output 'Regras de bloqueio de emergencia criadas no firewall.'\n# Desabilitar NICs\nforeach ($a in $adapters) {\n    if ($a.Name -ne 'Loopback Pseudo-Interface 1') {\n        Disable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction SilentlyContinue\n        Write-Output \"Desabilitado: $($a.Name)\"\n    }\n}\n# Registrar no Event Log\nWrite-EventLog -LogName Application -Source 'Application' -EventId 9999 -EntryType Warning -Message \"ISOLAMENTO aplicado em $timestamp via RMM\" -ErrorAction SilentlyContinue\nWrite-Output \"`nISOLAMENTO CONCLUIDO. Use TPL-016 para restaurar apos analise forense.\"",
    },
    {
        "name": "TPL-016 · Restauracao de Endpoint (pos-IR)",
        "description": "Reverte o isolamento aplicado pelo TPL-015. Reabilita NICs e remove regras de emergencia. Execute somente após análise forense concluída. Roles: SecOps, N2.",
        "category": "incident_response",
        "shell": "powershell",
        "run_type": "script",
        "body": "$timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'\nWrite-Output \"=== RESTAURACAO DE ENDPOINT === $timestamp\"\nWrite-Output \"Host: $env:COMPUTERNAME\"\n# Remover regras de emergencia\nRemove-NetFirewallRule -DisplayName 'ISOLAMENTO-EMERGENCIA-BLOCK-IN' -ErrorAction SilentlyContinue\nRemove-NetFirewallRule -DisplayName 'ISOLAMENTO-EMERGENCIA-BLOCK-OUT' -ErrorAction SilentlyContinue\nWrite-Output 'Regras de bloqueio de emergencia removidas.'\n# Reabilitar adaptadores\n$adapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Disabled' }\nforeach ($a in $adapters) {\n    Enable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction SilentlyContinue\n    Write-Output \"Reabilitado: $($a.Name)\"\n}\n# Testar conectividade\nStart-Sleep -Seconds 5\n$conn = Test-NetConnection -ComputerName 8.8.8.8 -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue\nWrite-EventLog -LogName Application -Source 'Application' -EventId 9998 -EntryType Information -Message \"ISOLAMENTO REVERTIDO em $timestamp via RMM\" -ErrorAction SilentlyContinue\nWrite-Output \"Conectividade: $(if($conn){'RESTAURADA - OK'}else{'SEM RESPOSTA - Verifique manualmente'})\"\nWrite-Output 'RESTAURACAO CONCLUIDA.'",
    },
    {
        "name": "TPL-019 · Auditoria de Scheduled Tasks",
        "description": "Detecta scheduled tasks suspeitas: criadas recentemente, com execução em AppData/Temp, com encoding Base64 ou invocando mshta/wscript. Roles: SecOps, N2.",
        "category": "incident_response",
        "shell": "powershell",
        "run_type": "script",
        "body": "$allTasks = Get-ScheduledTask -ErrorAction SilentlyContinue\n$recent = @(); $suspicious = @(); $highPriv = @()\nforeach ($task in $allTasks) {\n    $action = $task.Actions | Select-Object -First 1 -EA SilentlyContinue\n    if ($task.Date -and $task.Date -gt (Get-Date).AddDays(-14)) {\n        $recent += [PSCustomObject]@{Task=\"$($task.TaskPath)$($task.TaskName)\";Criada=$task.Date;Exec=($action.Execute);User=$task.Principal.UserId}\n    }\n    if ($action -and $action.Execute -match 'Temp|AppData|mshta|regsvr32|wscript|cscript|-enc|-EncodedCommand|rundll32') {\n        $suspicious += [PSCustomObject]@{Task=\"$($task.TaskPath)$($task.TaskName)\";Exec=$action.Execute;Args=$action.Arguments;User=$task.Principal.UserId;Risco='CRITICO'}\n    }\n    if ($task.Principal.UserId -eq 'S-1-5-18' -and $task.Principal.RunLevel -eq 'Highest') {\n        $highPriv += [PSCustomObject]@{Task=\"$($task.TaskPath)$($task.TaskName)\";User='SYSTEM';RunLevel='Highest'}\n    }\n}\nWrite-Output \"=== SCHEDULED TASK AUDIT === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Total: $($allTasks.Count) | Suspeitas: $($suspicious.Count) | Recentes <14d: $($recent.Count)\"\nif ($suspicious.Count -gt 0) { Write-Output \"`nALERTA CRITICO: Tasks com padroes suspeitos!\"; $suspicious | Format-Table -AutoSize | Out-String }\nWrite-Output '--- TASKS RECENTES (<14 dias) ---'\nif ($recent) { $recent | Format-Table -AutoSize | Out-String } else { Write-Output 'Nenhuma.' }\nWrite-Output '--- TASKS SYSTEM/HIGHEST (top 10) ---'\n$highPriv | Select-Object -First 10 | Format-Table -AutoSize | Out-String",
    },
    # ── Compliance ───────────────────────────────────────────────────────────
    {
        "name": "TPL-002 · CIS Benchmark Checker",
        "description": "Verifica controles CIS: SMBv1, RDP NLA, conta Guest, Windows Firewall, política de senha, auditoria de logon e Windows Defender. Alimenta Compliance (F30) e Golden Config (F26). Roles: Servidores, SecOps.",
        "category": "compliance",
        "shell": "powershell",
        "run_type": "script",
        "body": "$results = @()\n$smb1 = (Get-SmbServerConfiguration -ErrorAction SilentlyContinue).EnableSMB1Protocol\n$results += [PSCustomObject]@{Check='SMBv1 Desabilitado';Status=if(!$smb1){'PASS'}else{'FAIL'};Severity='Critical'}\n$nla = (Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name 'UserAuthenticationRequired' -EA SilentlyContinue).UserAuthenticationRequired\n$results += [PSCustomObject]@{Check='RDP com NLA';Status=if($nla -eq 1){'PASS'}else{'FAIL'};Severity='High'}\n$guest = (Get-LocalUser -Name 'Guest' -EA SilentlyContinue).Enabled\n$results += [PSCustomObject]@{Check='Conta Guest Desabilitada';Status=if(!$guest){'PASS'}else{'FAIL'};Severity='High'}\n$fw = Get-NetFirewallProfile -ErrorAction SilentlyContinue\n$fwOk = ($fw | Where-Object { $_.Enabled -eq $false }).Count -eq 0\n$results += [PSCustomObject]@{Check='Windows Firewall Ativo';Status=if($fwOk){'PASS'}else{'FAIL'};Severity='Critical'}\n$pwLine = (net accounts 2>$null | Select-String 'Comprimento' -ErrorAction SilentlyContinue)\n$pwMin = if ($pwLine) { ($pwLine.ToString() -replace '\\D','') } else { '0' }\n$results += [PSCustomObject]@{Check='Senha Minima >= 8 chars';Status=if([int]$pwMin -ge 8){'PASS'}else{'FAIL'};Severity='High'}\n$def = Get-MpComputerStatus -ErrorAction SilentlyContinue\n$results += [PSCustomObject]@{Check='Defender Ativo';Status=if($def.AntivirusEnabled){'PASS'}else{'FAIL'};Severity='Critical'}\n$pass = ($results | Where-Object {$_.Status -eq 'PASS'}).Count\n$score = [math]::Round($pass/$results.Count*100)\nWrite-Output \"=== CIS BENCHMARK CHECK === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Score: $score% ($pass/$($results.Count) controles OK)\"\n$results | Format-Table Check, Status, Severity -AutoSize | Out-String\nif ($score -lt 80) { Write-Output \"ACAO: Score abaixo de 80%. Corrija os itens FAIL e execute TPL-018 (Golden Config Apply).\" }",
    },
    {
        "name": "TPL-010 · Patch Status Report",
        "description": "Relata patches instalados e pendentes do Windows Update. Identifica patches críticos ausentes há mais de 30 dias. Alimenta Compliance (F30) e GLPI (F43). Roles: Servidores, N2.",
        "category": "compliance",
        "shell": "powershell",
        "run_type": "script",
        "body": "$hotfixes = Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending\n$lastPatch = $hotfixes | Select-Object -First 1\n$daysSince = if ($lastPatch.InstalledOn) { ((Get-Date) - $lastPatch.InstalledOn).Days } else { 999 }\n$pending = @()\ntry {\n    $session = New-Object -ComObject Microsoft.Update.Session\n    $searcher = $session.CreateUpdateSearcher()\n    $search = $searcher.Search('IsInstalled=0 and Type=Software and IsHidden=0')\n    $pending = $search.Updates | ForEach-Object { [PSCustomObject]@{Titulo=$_.Title;Severidade=$_.MsrcSeverity;KB=($_.KBArticleIDs -join ',')} }\n} catch { $pending = @([PSCustomObject]@{Titulo='Erro ao verificar atualizacoes';Severidade='N/A';KB='N/A'}) }\n$critical = ($pending | Where-Object { $_.Severidade -in 'Critical','Important' }).Count\nWrite-Output \"=== PATCH STATUS REPORT === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME\"\nWrite-Output \"Ultimo patch: $($lastPatch.HotFixID) em $($lastPatch.InstalledOn) ($daysSince dias atras)\"\nWrite-Output \"Patches pendentes: $($pending.Count) | Criticos/Importantes: $critical\"\nif ($daysSince -gt 30) { Write-Output 'ALERTA: Sistema sem patches ha mais de 30 dias!' }\nWrite-Output '--- PATCHES PENDENTES ---'\nif ($pending.Count -gt 0) { $pending | Format-Table -AutoSize | Out-String } else { Write-Output 'Nenhum patch pendente.' }\nWrite-Output '--- ULTIMOS 10 PATCHES INSTALADOS ---'\n$hotfixes | Select-Object -First 10 HotFixID, Description, InstalledOn | Format-Table -AutoSize | Out-String",
    },
    # ── Identidade ────────────────────────────────────────────────────────────
    {
        "name": "TPL-006 · Auditoria de Grupos Locais Privilegiados",
        "description": "Lista membros de Administrators, Remote Desktop Users e Backup Operators. Detecta adições não autorizadas. Alimenta Identity Governance (F36), Compliance (F30) e SIEM (F37). Roles: SecOps, N2.",
        "category": "identity",
        "shell": "powershell",
        "run_type": "script",
        "body": "$results = @()\n$groups = @('Administrators','Remote Desktop Users','Backup Operators','Power Users','Network Configuration Operators')\nforeach ($grp in $groups) {\n    try {\n        $members = Get-LocalGroupMember -Group $grp -ErrorAction SilentlyContinue\n        if ($members) {\n            foreach ($m in $members) {\n                $results += [PSCustomObject]@{Grupo=$grp;Membro=$m.Name;Tipo=$m.ObjectClass;Origem=$m.PrincipalSource;Risco=if($grp -eq 'Administrators'){'HIGH'}elseif($grp -in 'Remote Desktop Users','Backup Operators'){'MEDIUM'}else{'LOW'}}\n            }\n        } else {\n            $results += [PSCustomObject]@{Grupo=$grp;Membro='(vazio)';Tipo='N/A';Origem='N/A';Risco='INFO'}\n        }\n    } catch { $results += [PSCustomObject]@{Grupo=$grp;Membro='ERRO';Tipo='N/A';Origem=$_.Exception.Message;Risco='N/A'} }\n}\n$adminCount = ($results | Where-Object { $_.Grupo -eq 'Administrators' -and $_.Membro -ne '(vazio)' }).Count\nWrite-Output \"=== AD LOCAL GROUPS AUDIT === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Administradores locais: $adminCount\"\nif ($adminCount -gt 3) { Write-Output 'ALERTA: Numero elevado de administradores locais!' }\n$results | Format-Table -AutoSize | Out-String\nWrite-Output 'ACAO: Compare com baseline aprovado no modulo Identity Governance do Eternity SecOps.'",
    },
    {
        "name": "TPL-012 · Reset de Senha AD",
        "description": "Reseta a senha de um usuário AD e força troca no próximo logon. Integra com Self-Service (F39) e SOAR (F35). Edite as variáveis antes de executar. Roles: N1, N2.",
        "category": "identity",
        "shell": "powershell",
        "run_type": "script",
        "body": "# EDITE antes de executar\n$TargetUser = 'usuario.dominio'  # SAMAccountName ou UPN\n$NewPassword = 'Senha@Temp2024!'  # Minimo 12 chars, complexidade obrigatoria\n$ForceChange = $true\ntry {\n    Import-Module ActiveDirectory -ErrorAction Stop\n    $secPwd = ConvertTo-SecureString $NewPassword -AsPlainText -Force\n    Set-ADAccountPassword -Identity $TargetUser -NewPassword $secPwd -Reset -ErrorAction Stop\n    if ($ForceChange) { Set-ADUser -Identity $TargetUser -ChangePasswordAtLogon $true }\n    Unlock-ADAccount -Identity $TargetUser -ErrorAction SilentlyContinue\n    Write-Output \"OK: Senha resetada para '$TargetUser'. Troca obrigatoria no logon: $ForceChange\"\n} catch [System.InvalidOperationException] {\n    net user $TargetUser $NewPassword /logonpasswordchg:yes 2>&1\n    Write-Output 'Senha resetada via net user (conta local).'\n} catch {\n    Write-Output \"ERRO: $($_.Exception.Message)\"\n    Write-Output 'Verifique: usuario existe? Modulo AD disponivel? Permissoes suficientes?'\n}",
    },
    # ── Forense ───────────────────────────────────────────────────────────────
    {
        "name": "TPL-004 · Web Forensics Collector",
        "description": "Localiza bancos de dados de histórico dos browsers (Chrome, Edge, Firefox) e lista downloads recentes. Pré-coleta para análise no módulo Web Audit (F48) com BrowsingHistoryView. Roles: SecOps, N2.",
        "category": "forensics",
        "shell": "powershell",
        "run_type": "script",
        "body": "$results = @()\n$chromeDB = \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\History\"\nif (Test-Path $chromeDB) { $results += [PSCustomObject]@{Browser='Chrome';Status='DB encontrado';Path=$chromeDB;Tamanho_KB=[math]::Round((Get-Item $chromeDB).Length/1KB,1)} }\n$edgeDB = \"$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\History\"\nif (Test-Path $edgeDB) { $results += [PSCustomObject]@{Browser='Edge';Status='DB encontrado';Path=$edgeDB;Tamanho_KB=[math]::Round((Get-Item $edgeDB).Length/1KB,1)} }\n$ffPath = \"$env:APPDATA\\Mozilla\\Firefox\\Profiles\"\nif (Test-Path $ffPath) {\n    $ffDBs = Get-ChildItem -Path $ffPath -Recurse -Filter 'places.sqlite' -ErrorAction SilentlyContinue\n    foreach ($db in $ffDBs) { $results += [PSCustomObject]@{Browser='Firefox';Status='DB encontrado';Path=$db.FullName;Tamanho_KB=[math]::Round($db.Length/1KB,1)} }\n}\n$downloads = Get-ChildItem \"$env:USERPROFILE\\Downloads\" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 20 Name, LastWriteTime, @{N='Size_KB';E={[math]::Round($_.Length/1KB,1)}}\nWrite-Output \"=== WEB FORENSICS COLLECTOR === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Usuario: $env:USERNAME | Host: $env:COMPUTERNAME\"\nWrite-Output '--- BANCOS DE HISTORICO ---'\n$results | Format-Table -AutoSize | Out-String\nWrite-Output '--- DOWNLOADS RECENTES (top 20) ---'\n$downloads | Format-Table -AutoSize | Out-String\nWrite-Output 'PROXIMA ACAO: Execute BrowsingHistoryView.exe nos paths acima via GPO (modulo Web Audit F48).'",
    },
    {
        "name": "TPL-017 · DLP Local Scan",
        "description": "Varre Documents, Desktop e Downloads por padrões de dados sensíveis: CPF, CNPJ, cartões, chaves SSH, AWS keys, connection strings. Alimenta DLP (F28.1) e SIEM (F37). Roles: SecOps, N2.",
        "category": "forensics",
        "shell": "powershell",
        "run_type": "script",
        "body": "$scanPaths = @(\"$env:USERPROFILE\\Documents\",\"$env:USERPROFILE\\Desktop\",\"$env:USERPROFILE\\Downloads\")\n$extensions = @('*.txt','*.csv','*.xls','*.xlsx','*.doc','*.docx','*.json','*.xml','*.ini','*.cfg','*.conf','*.env')\n$patterns = @{\n    'CPF'='\\b\\d{3}\\.?\\d{3}\\.?\\d{3}-?\\d{2}\\b'\n    'CNPJ'='\\b\\d{2}\\.?\\d{3}\\.?\\d{3}\\/?\\d{4}-?\\d{2}\\b'\n    'Cartao'='\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\\b'\n    'SSH_Key'='-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----'\n    'AWS_Key'='AKIA[0-9A-Z]{16}'\n    'Senha_Plain'='(?i)(password|senha|passwd)\\s*[=:]\\s*\\S+'\n    'Conn_String'='(?i)(server|host)\\s*=.*?(password|pwd)\\s*='\n}\n$hits = @()\nforeach ($path in $scanPaths) {\n    if (-not (Test-Path $path)) { continue }\n    $files = Get-ChildItem -Path $path -Include $extensions -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Length -lt 10MB }\n    foreach ($file in $files) {\n        try {\n            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue\n            foreach ($key in $patterns.Keys) {\n                if ($content -match $patterns[$key]) { $hits += [PSCustomObject]@{Tipo=$key;Arquivo=$file.FullName;Tamanho_KB=[math]::Round($file.Length/1KB,1)} }\n            }\n        } catch {}\n    }\n}\nWrite-Output \"=== DLP LOCAL SCAN === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Arquivos sensiveis encontrados: $($hits.Count)\"\nif ($hits.Count -gt 0) { Write-Output 'ALERTA DLP!'; $hits | Sort-Object Tipo | Format-Table -AutoSize | Out-String } else { Write-Output 'Nenhum dado sensivel detectado nos paths verificados.' }",
    },
    # ── Segurança (avançado) ──────────────────────────────────────────────────
    {
        "name": "TPL-005 · Inventário de Software + Versões",
        "description": "Inventário completo de aplicativos instalados via registro do Windows e versão de BIOS/firmware. Alimenta Firmware CVE (F44) para cruzamento com NVD. Roles: Servidores, N2, SecOps.",
        "category": "security",
        "shell": "powershell",
        "run_type": "script",
        "body": "$sw = @()\n$sw += Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate\n$sw += Get-ItemProperty 'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate\n$sw = $sw | Sort-Object DisplayName -Unique\n$bios = Get-WmiObject Win32_BIOS -ErrorAction SilentlyContinue | Select-Object SMBIOSBIOSVersion, Manufacturer, ReleaseDate\n$drivers = Get-WmiObject Win32_PnPSignedDriver -ErrorAction SilentlyContinue | Where-Object { $_.DeviceName -and $_.DriverVersion } | Select-Object -First 20 DeviceName, DriverVersion, Manufacturer\nWrite-Output \"=== SOFTWARE INVENTORY === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Total de aplicativos: $($sw.Count)\"\nWrite-Output '--- APLICATIVOS INSTALADOS ---'\n$sw | Sort-Object DisplayName | Format-Table DisplayName, DisplayVersion, Publisher -AutoSize | Out-String\nWrite-Output '--- BIOS/FIRMWARE ---'\n$bios | Format-List | Out-String\nWrite-Output '--- DRIVERS (top 20) ---'\n$drivers | Format-Table -AutoSize | Out-String\nWrite-Output 'ACAO: Envie para o modulo Firmware CVE (F44) do Eternity SecOps para cruzamento com NVD.'",
    },
    {
        "name": "TPL-007 · Exportar Regras de Firewall",
        "description": "Exporta regras do Windows Firewall com detecção de regras Any-Any críticas. Alimenta Golden Config (F26), Compliance (F30) e AI Assistant (F40) para análise de inconsistências. Roles: Firewall, SecOps.",
        "category": "security",
        "shell": "powershell",
        "run_type": "script",
        "body": "$allRules = Get-NetFirewallRule -ErrorAction SilentlyContinue\n$enriched = foreach ($rule in $allRules) {\n    $addr = $rule | Get-NetFirewallAddressFilter -EA SilentlyContinue\n    $port = $rule | Get-NetFirewallPortFilter -EA SilentlyContinue\n    $app  = $rule | Get-NetFirewallApplicationFilter -EA SilentlyContinue\n    [PSCustomObject]@{Nome=$rule.DisplayName;Direcao=$rule.Direction;Acao=$rule.Action;Ativa=$rule.Enabled;Perfil=$rule.Profile;RemoteAddr=$addr.RemoteAddress;Porta=$port.LocalPort;Protocolo=$port.Protocol;Programa=$app.Program;Risco=if($rule.Action -eq 'Allow' -and $addr.RemoteAddress -contains 'Any' -and $port.LocalPort -contains 'Any'){'ANY-ANY'}else{'OK'}}\n}\n$anyAny = $enriched | Where-Object { $_.Risco -eq 'ANY-ANY' -and $_.Ativa -eq 'True' }\n$inboundAllow = $enriched | Where-Object { $_.Direcao -eq 'Inbound' -and $_.Ativa -eq 'True' -and $_.Acao -eq 'Allow' }\nWrite-Output \"=== FIREWALL RULES EXPORT === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Total: $($allRules.Count) | Inbound Allow: $($inboundAllow.Count)\"\nWrite-Output \"ALERTA ANY-ANY (ativas): $($anyAny.Count)\"\nif ($anyAny) { Write-Output '--- REGRAS ANY-ANY (RISCO CRITICO) ---'; $anyAny | Format-Table Nome, Direcao, Perfil -AutoSize | Out-String }\nWrite-Output '--- INBOUND ALLOW (top 40) ---'\n$inboundAllow | Select-Object -First 40 | Format-Table Nome, RemoteAddr, Porta, Protocolo -AutoSize | Out-String",
    },
    {
        "name": "TPL-014 · Browser Security Baseline",
        "description": "Verifica políticas GPO de segurança dos browsers: Safe Browsing, SmartScreen, cookies de terceiros. Alimenta Web Audit (F48), Compliance (F30) e DLP (F28.1). Roles: SecOps, N2.",
        "category": "security",
        "shell": "powershell",
        "run_type": "script",
        "body": "$issues = @()\n$chromePolicy = 'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome'\nif (Test-Path $chromePolicy) {\n    $sb = (Get-ItemProperty $chromePolicy -Name 'SafeBrowsingEnabled' -EA SilentlyContinue).SafeBrowsingEnabled\n    if ($sb -ne 1) { $issues += [PSCustomObject]@{Browser='Chrome';Issue='Safe Browsing desabilitado via GPO';Severity='HIGH'} }\n    $tp = (Get-ItemProperty $chromePolicy -Name 'BlockThirdPartyCookies' -EA SilentlyContinue).BlockThirdPartyCookies\n    if ($tp -ne 1) { $issues += [PSCustomObject]@{Browser='Chrome';Issue='Third-party cookies nao bloqueados';Severity='MEDIUM'} }\n} else { $issues += [PSCustomObject]@{Browser='Chrome';Issue='Sem politicas GPO aplicadas';Severity='MEDIUM'} }\n$edgePolicy = 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge'\nif (Test-Path $edgePolicy) {\n    $ss = (Get-ItemProperty $edgePolicy -Name 'SmartScreenEnabled' -EA SilentlyContinue).SmartScreenEnabled\n    if ($ss -ne 1) { $issues += [PSCustomObject]@{Browser='Edge';Issue='SmartScreen desabilitado';Severity='HIGH'} }\n} else { $issues += [PSCustomObject]@{Browser='Edge';Issue='Sem politicas GPO aplicadas';Severity='MEDIUM'} }\n$browsers = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -EA SilentlyContinue | Where-Object { $_.DisplayName -match 'Chrome|Firefox|Edge|Opera' } | Select-Object DisplayName, DisplayVersion\nWrite-Output \"=== BROWSER SECURITY BASELINE === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Issues: $($issues.Count)\"\nWrite-Output '--- BROWSERS INSTALADOS ---'\n$browsers | Format-Table -AutoSize | Out-String\nWrite-Output '--- SECURITY ISSUES ---'\nif ($issues) { $issues | Format-Table -AutoSize | Out-String } else { Write-Output 'Nenhum issue detectado.' }",
    },
    # ── Monitoramento (avançado) ──────────────────────────────────────────────
    {
        "name": "TPL-008 · Saúde de Disco e Forecast",
        "description": "Verifica espaço livre em volumes e status SMART dos discos físicos. Detecta volumes críticos e projeta risco. Alimenta SOAR (F35) para abertura proativa de tickets GLPI (F43). Roles: Servidores, N1, N2.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "script",
        "body": "$volumes = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null }\n$report = foreach ($vol in $volumes) {\n    $usedGB  = [math]::Round($vol.Used/1GB,2)\n    $freeGB  = [math]::Round($vol.Free/1GB,2)\n    $totalGB = $usedGB + $freeGB\n    $usePct  = if ($totalGB -gt 0) { [math]::Round($usedGB/$totalGB*100,1) } else { 0 }\n    [PSCustomObject]@{Volume=$vol.Name;Used_GB=$usedGB;Free_GB=$freeGB;Total_GB=$totalGB;'Use%'=$usePct;Status=if($usePct -ge 90){'CRITICO'}elseif($usePct -ge 75){'ATENCAO'}else{'OK'}}\n}\n$disks = Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus, @{N='Size_GB';E={[math]::Round($_.Size/1GB)}}\nWrite-Output \"=== DISK HEALTH & FORECAST === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME\"\nWrite-Output '--- VOLUMES ---'\n$report | Format-Table -AutoSize | Out-String\nWrite-Output '--- DISCOS FISICOS (SMART) ---'\n$disks | Format-Table -AutoSize | Out-String\n$alerta = $report | Where-Object { $_.Status -ne 'OK' }\nif ($alerta) { Write-Output \"ALERTA: $($alerta.Count) volume(s) em estado critico/atencao!\"; $alerta | Format-Table -AutoSize | Out-String }",
    },
    {
        "name": "TPL-011 · Triagem Rápida N1",
        "description": "Coleta diagnóstico rápido em menos de 15 segundos: CPU, RAM, disco, top 5 processos, erros recentes e conectividade. Alimenta GLPI (F43) e AI Assistant (F40) para sugestão de solução. Roles: N1.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "script",
        "body": "$os   = Get-CimInstance Win32_OperatingSystem\n$cpu  = (Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average\n$top5 = Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name, @{N='CPU%';E={[math]::Round($_.CPU,1)}}, @{N='RAM_MB';E={[math]::Round($_.WorkingSet/1MB,1)}}\n$disk = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used } | Select-Object Name, @{N='Free_GB';E={[math]::Round($_.Free/1GB,1)}}, @{N='Use%';E={if(($_.Used+$_.Free)-gt 0){[math]::Round($_.Used/($_.Used+$_.Free)*100,0)}else{0}}}\n$errs = Get-WinEvent -LogName System -MaxEvents 5 -FilterHashtable @{Level=2} -ErrorAction SilentlyContinue | Select-Object TimeCreated, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(80,$_.Message.Length))}}\n$conn = Test-NetConnection -ComputerName 8.8.8.8 -WarningAction SilentlyContinue -InformationLevel Quiet -ErrorAction SilentlyContinue\nWrite-Output \"=== TRIAGEM RAPIDA N1 === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"HOST: $env:COMPUTERNAME | Uptime: $([math]::Round(((Get-Date)-$os.LastBootUpTime).TotalHours,1))h | Internet: $(if($conn){'OK'}else{'SEM CONEXAO'})\"\nWrite-Output \"CPU: $cpu% | RAM: $([math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2))/$([math]::Round($os.TotalVisibleMemorySize/1MB,2))GB\"\nWrite-Output '--- TOP 5 PROCESSOS ---'\n$top5 | Format-Table -AutoSize | Out-String\nWrite-Output '--- VOLUMES ---'\n$disk | Format-Table -AutoSize | Out-String\nWrite-Output '--- ULTIMOS ERROS ---'\nif ($errs) { $errs | Format-List | Out-String } else { Write-Output 'Nenhum erro recente de sistema.' }",
    },
    {
        "name": "TPL-013 · Monitor e Restart de Serviços",
        "description": "Verifica serviços críticos configurados como Automático e tenta restart dos que estiverem parados. Integra com SOAR (F35) e GLPI (F43). Roles: N1, N2, Servidores.",
        "category": "monitoring",
        "shell": "powershell",
        "run_type": "script",
        "body": "$criticalServices = @('wuauserv','Spooler','RpcSs','EventLog','Schedule','W32Time','Winmgmt','Dhcp','dnscache','LanmanServer')\n$results = @()\nforeach ($svc in $criticalServices) {\n    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue\n    if (-not $s) { $results += [PSCustomObject]@{Servico=$svc;Status='NAO_ENCONTRADO';Acao='N/A';Resultado='N/A'}; continue }\n    if ($s.Status -ne 'Running') {\n        try {\n            Start-Service -Name $svc -ErrorAction Stop\n            $results += [PSCustomObject]@{Servico=$s.DisplayName;Status='PARADO';Acao='RESTART';Resultado='OK'}\n        } catch {\n            $results += [PSCustomObject]@{Servico=$s.DisplayName;Status='PARADO';Acao='RESTART';Resultado=\"FALHA: $($_.Exception.Message)\"}\n        }\n    } else {\n        $results += [PSCustomObject]@{Servico=$s.DisplayName;Status='RUNNING';Acao='Nenhuma';Resultado='OK'}\n    }\n}\n$stopped = ($results | Where-Object { $_.Status -eq 'PARADO' }).Count\nWrite-Output \"=== SERVICE HEALTH MONITOR === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Verificados: $($criticalServices.Count) | Parados: $stopped\"\n$results | Format-Table -AutoSize | Out-String",
    },
    # ── Rede (avançado) ───────────────────────────────────────────────────────
    {
        "name": "TPL-009 · Varredura de Conectividade",
        "description": "Testa conectividade com gateway, DNS, controlador de domínio e destinos críticos. Mede latência e detecta falhas. Alimenta SOAR (F35) e SIEM (F37). Roles: Redes, N1.",
        "category": "network",
        "shell": "powershell",
        "run_type": "script",
        "body": "$gw = ((Get-NetRoute -DestinationPrefix '0.0.0.0/0' -EA SilentlyContinue | Sort-Object RouteMetric)[0]).NextHop\n$dc = $env:LOGONSERVER -replace '\\\\',''\n$targets = @(\n    @{Name='Gateway';Host=$gw},\n    @{Name='DNS Google';Host='8.8.8.8'},\n    @{Name='DNS Cloudflare';Host='1.1.1.1'},\n    @{Name='Controlador de Dominio';Host=$dc},\n    @{Name='Microsoft Update';Host='update.microsoft.com'}\n)\n$results = foreach ($t in $targets) {\n    if (-not $t.Host -or $t.Host -eq '') { [PSCustomObject]@{Destino=$t.Name;Host='N/A';Status='SEM_HOST';RTT_ms='N/A'}; continue }\n    $ok = Test-NetConnection -ComputerName $t.Host -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue\n    $rtt = (Test-Connection $t.Host -Count 3 -ErrorAction SilentlyContinue | Measure-Object ResponseTime -Average).Average\n    [PSCustomObject]@{Destino=$t.Name;Host=$t.Host;Status=if($ok){'OK'}else{'FALHA'};RTT_ms=if($rtt){[math]::Round($rtt,1)}else{'N/A'}}\n}\n$falhas = ($results | Where-Object { $_.Status -eq 'FALHA' }).Count\nWrite-Output \"=== NETWORK CONNECTIVITY SWEEP === $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"\nWrite-Output \"Host: $env:COMPUTERNAME | Destinos: $($targets.Count) | Falhas: $falhas\"\n$results | Format-Table -AutoSize | Out-String\nif ($falhas -gt 0) { Write-Output \"ALERTA: $falhas destino(s) inacessivel(is)!\" }",
    },
    # ── Manutenção (avançado) ─────────────────────────────────────────────────
    {
        "name": "TPL-018 · Aplicar Golden Config (Baseline)",
        "description": "Aplica configurações de baseline: desabilita SMBv1, habilita Firewall, configura NTP e ativa auditoria de logon. Integra com Golden Config (F26) e Compliance (F30). Roles: Servidores, Firewall, N2.",
        "category": "maintenance",
        "shell": "powershell",
        "run_type": "script",
        "body": "$timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'\n$results = @()\ntry { Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force -EA Stop; $results += [PSCustomObject]@{Config='Desabilitar SMBv1';Status='OK'} } catch { $results += [PSCustomObject]@{Config='Desabilitar SMBv1';Status=\"ERRO: $($_.Exception.Message)\"} }\ntry { Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True -EA Stop; $results += [PSCustomObject]@{Config='Habilitar Firewall (todos os perfis)';Status='OK'} } catch { $results += [PSCustomObject]@{Config='Habilitar Firewall';Status=\"ERRO: $($_.Exception.Message)\"} }\ntry { w32tm /config /manualpeerlist:'time.windows.com' /syncfromflags:manual /reliable:yes /update | Out-Null; Start-Service W32Time -EA SilentlyContinue; w32tm /resync /force | Out-Null; $results += [PSCustomObject]@{Config='Configurar NTP (time.windows.com)';Status='OK'} } catch { $results += [PSCustomObject]@{Config='Configurar NTP';Status=\"ERRO: $($_.Exception.Message)\"} }\ntry { auditpol /set /subcategory:'Logon' /success:enable /failure:enable | Out-Null; $results += [PSCustomObject]@{Config='Auditoria de Logon';Status='OK'} } catch { $results += [PSCustomObject]@{Config='Auditoria de Logon';Status=\"ERRO: $($_.Exception.Message)\"} }\ntry { Set-ItemProperty -Path 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -Name 'EnableLUA' -Value 1 -EA Stop; $results += [PSCustomObject]@{Config='UAC Habilitado';Status='OK'} } catch { $results += [PSCustomObject]@{Config='UAC Habilitado';Status=\"ERRO: $($_.Exception.Message)\"} }\n$ok   = ($results | Where-Object { $_.Status -eq 'OK' }).Count\n$fail = ($results | Where-Object { $_.Status -ne 'OK' }).Count\nWrite-Output \"=== GOLDEN CONFIG APPLY === $timestamp\"\nWrite-Output \"Host: $env:COMPUTERNAME | OK: $ok | Falhas: $fail\"\n$results | Format-Table -AutoSize | Out-String\nif ($fail -gt 0) { Write-Output \"ACAO: $fail configuracao(oes) com falha. Revise manualmente e registre no modulo Compliance (F30).\" }",
    },
    {
        "name": "TPL-020 · Coletor de Evidências para RCA",
        "description": "Coleta logs de sistema, eventos de aplicação, serviços parados, processos e conexões ativas das últimas N horas. Alimenta AI Assistant (F40) para geração automática de rascunho de RCA no GLPI (F43). Roles: N2, Servidores.",
        "category": "maintenance",
        "shell": "powershell",
        "run_type": "script",
        "body": "$HorasAtras = 4  # EDITE: janela de analise em horas\n$desde = (Get-Date).AddHours(-$HorasAtras)\n$timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'\nWrite-Output \"=== RCA EVIDENCE COLLECTOR === $timestamp\"\nWrite-Output \"Host: $env:COMPUTERNAME | Janela: Ultimas $HorasAtras hora(s) (desde $($desde.ToString('HH:mm:ss')))\"\nWrite-Output '===================================================================='\nWrite-Output '--- ERROS DE SISTEMA ---'\nGet-WinEvent -LogName System -StartTime $desde -FilterHashtable @{Level=1,2} -EA SilentlyContinue | Select-Object TimeCreated, Id, LevelDisplayName, @{N='Mensagem';E={$_.Message.Substring(0,[Math]::Min(200,$_.Message.Length))}} | Format-Table -AutoSize -Wrap | Out-String\nWrite-Output '--- ERROS DE APLICACAO ---'\nGet-WinEvent -LogName Application -StartTime $desde -FilterHashtable @{Level=1,2} -EA SilentlyContinue | Select-Object -First 20 TimeCreated, ProviderName, Id, @{N='Mensagem';E={$_.Message.Substring(0,[Math]::Min(150,$_.Message.Length))}} | Format-Table -AutoSize -Wrap | Out-String\nWrite-Output '--- SERVICOS AUTO/PARADOS (estado atual) ---'\nGet-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -ne 'Running'} | Select-Object Name, Status, DisplayName | Format-Table -AutoSize | Out-String\nWrite-Output '--- TOP 20 PROCESSOS ATIVOS ---'\nGet-Process | Sort-Object CPU -Descending | Select-Object -First 20 Name, Id, @{N='CPU';E={[math]::Round($_.CPU,1)}}, @{N='RAM_MB';E={[math]::Round($_.WorkingSet/1MB,1)}} | Format-Table -AutoSize | Out-String\nWrite-Output '--- CONEXOES TCP ATIVAS ---'\nGet-NetTCPConnection -State Established -EA SilentlyContinue | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -EA SilentlyContinue).Name}} | Format-Table -AutoSize | Out-String\nWrite-Output '===================================================================='\nWrite-Output 'PROXIMA ACAO: Copie esta saida para o ticket GLPI e use o AI Assistant (F40) para gerar o rascunho de RCA.'",
    },
]


async def list_templates(
    db: AsyncSession,
    tenant_id: UUID | None = None,
    category: str | None = None,
) -> list[RmmScriptTemplate]:
    q = select(RmmScriptTemplate).where(
        or_(RmmScriptTemplate.tenant_id == tenant_id, RmmScriptTemplate.is_builtin == True)  # noqa: E712
    )
    if category:
        q = q.where(RmmScriptTemplate.category == category)
    q = q.order_by(RmmScriptTemplate.category, RmmScriptTemplate.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_template(
    db: AsyncSession,
    template_id: UUID,
    tenant_id: UUID,
) -> RmmScriptTemplate | None:
    result = await db.execute(
        select(RmmScriptTemplate).where(
            RmmScriptTemplate.id == template_id,
            or_(RmmScriptTemplate.tenant_id == tenant_id, RmmScriptTemplate.is_builtin == True),  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def create_template(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    body: str,
    shell: str = "powershell",
    run_type: str = "command",
    category: str = "general",
    description: str | None = None,
) -> RmmScriptTemplate:
    tmpl = RmmScriptTemplate(
        tenant_id=tenant_id,
        name=name.strip(),
        description=description,
        category=category,
        shell=shell,
        run_type=run_type,
        body=body,
        is_builtin=False,
    )
    db.add(tmpl)
    await db.flush()
    await db.refresh(tmpl)
    return tmpl


async def update_template(
    db: AsyncSession,
    template: RmmScriptTemplate,
    name: str | None = None,
    description: str | None = None,
    category: str | None = None,
    shell: str | None = None,
    run_type: str | None = None,
    body: str | None = None,
) -> RmmScriptTemplate:
    if name is not None:
        template.name = name.strip()
    if description is not None:
        template.description = description
    if category is not None:
        template.category = category
    if shell is not None:
        template.shell = shell
    if run_type is not None:
        template.run_type = run_type
    if body is not None:
        template.body = body
    await db.flush()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, template: RmmScriptTemplate) -> None:
    await db.delete(template)


async def seed_builtin_templates(db: AsyncSession) -> int:
    existing = await db.execute(
        select(RmmScriptTemplate.name).where(RmmScriptTemplate.is_builtin == True)  # noqa: E712
    )
    existing_names = {row[0] for row in existing.all()}

    added = 0
    for t in BUILTIN_TEMPLATES:
        if t["name"] not in existing_names:
            db.add(RmmScriptTemplate(
                tenant_id=None,
                is_builtin=True,
                **t,
            ))
            added += 1

    if added:
        await db.flush()
    return added
